import json
import os
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq

from database import MindMirrorDB
from prompt_library import (
    EXTRACTION_PROMPT,
    INSIGHT_PROMPT,
    CONTRADICTION_PROMPT,
    FOLLOWUP_PROMPT,
    DELTA_INSIGHT_PROMPT,
    GREETING_PROMPT,
)

load_dotenv()


class MindMirrorEngine:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY missing — set it in .env")
        self.client = Groq(api_key=api_key)
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.db = MindMirrorDB()
        self.session_id = self._new_session_id()

    @staticmethod
    def _new_session_id():
        return datetime.now().strftime("%Y-%m-%d_%H%M%S")

    def start_new_session(self):
        self.session_id = self._new_session_id()
        return self.session_id

    def _chat(self, system, user, json_mode=False, temperature=0.2):
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"Groq API error: {e}")

    # ---------------------------------------------------------------- ingest
    def ingest_thought(self, raw_input):
        """Extract → validate → persist → detect contradictions → generate follow-up."""
        result = {
            "success": False,
            "message": "",
            "extraction": {"nodes": [], "relationships": []},
            "contradictions": [],
            "followup_question": None,
        }

        try:
            raw_json = self._chat(EXTRACTION_PROMPT, raw_input, json_mode=True)
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            result["message"] = f"LLM returned invalid JSON: {e}"
            return result
        except Exception as e:
            result["message"] = f"LLM call failed: {e}"
            return result

        nodes = data.get("nodes", [])
        relationships = data.get("relationships", [])
        result["extraction"] = {"nodes": nodes, "relationships": relationships}

        if not nodes:
            result["message"] = "No nodes extracted from this input — try a richer thought."
            return result

        success, msg, written_ids = self.db.write_graph(
            nodes, relationships, self.session_id, source_text=raw_input
        )
        result["success"] = success
        result["message"] = msg
        if not success:
            return result

        try:
            result["contradictions"] = self._detect_contradictions(nodes, written_ids)
        except Exception as e:
            print(f"⚠ Contradiction detection failed: {e}")

        try:
            result["followup_question"] = self._generate_followup(
                raw_input, nodes, result["contradictions"]
            )
        except Exception as e:
            print(f"⚠ Follow-up generation failed: {e}")

        return result

    def _detect_contradictions(self, new_nodes, written_ids):
        neighbors = self.db.get_neighbors(written_ids)
        new_id_set = set(written_ids)
        existing = []
        for nb in neighbors:
            if nb["target"] not in new_id_set:
                existing.append({
                    "id": nb["target"], "label": nb["target_label"], "class": nb["target_class"],
                })
            if nb["source"] not in new_id_set:
                existing.append({
                    "id": nb["source"], "label": nb["source_label"], "class": nb["source_class"],
                })
        if not existing:
            return []

        seen = set()
        unique_existing = []
        for e in existing:
            if e["id"] in seen:
                continue
            seen.add(e["id"])
            unique_existing.append(e)

        payload = json.dumps({
            "new_nodes": [
                {"id": n["id"], "class": n.get("class"), "label": n.get("label")}
                for n in new_nodes
            ],
            "existing_nodes": unique_existing[:30],
        })
        raw = self._chat(CONTRADICTION_PROMPT, payload, json_mode=True)
        try:
            return json.loads(raw).get("contradictions", [])
        except json.JSONDecodeError:
            return []

    def _generate_followup(self, raw_input, nodes, contradictions):
        payload = json.dumps({
            "raw_thought": raw_input,
            "extracted_nodes": [
                {"id": n["id"], "class": n.get("class"), "label": n.get("label")}
                for n in nodes
            ],
            "contradictions": contradictions,
        })
        return self._chat(FOLLOWUP_PROMPT, payload, temperature=0.5).strip().strip('"')

    # ---------------------------------------------------------------- insight
    def generate_insight(self, session_id=None):
        """Returns a dict: {shape, tension, load_bearers, question} or {error}."""
        graph_map = self.db.get_full_graph(session_id=session_id)
        if not graph_map:
            return {"error": "Map is empty for this scope. Commit some thoughts first."}
        try:
            raw = self._chat(
                INSIGHT_PROMPT,
                f"CURRENT GRAPH TOPOLOGY:\n\n{graph_map}",
                json_mode=True,
            )
            return json.loads(raw)
        except Exception as e:
            return {"error": f"Couldn't read the map: {e}"}

    def generate_delta_insight(self, days=7):
        """Returns a dict: {shift, recurring, blindspot, question} or {error}."""
        new_nodes, new_rels = self.db.get_recent_changes(days=days)
        recurring = self.db.get_recurring_nodes(min_times_seen=2, limit=10)
        sample = self.db.get_sample_nodes(limit=15)

        if not new_nodes and not recurring and not sample:
            return {"error": f"No activity yet — commit a thought first."}

        payload = json.dumps({
            "window_days": days,
            "new_nodes": new_nodes,
            "new_relationships": new_rels,
            "recurring_load_bearers": recurring,
            "sample_nodes_in_map": sample,
        })
        try:
            raw = self._chat(DELTA_INSIGHT_PROMPT, payload, temperature=0.4, json_mode=True)
            return json.loads(raw)
        except Exception as e:
            return {"error": f"Couldn't reflect: {e}"}

    def get_snapshot_stats(self):
        """Quick stats for the snapshot tiles: total nodes, sessions, recent activity, recurring."""
        sessions = self.db.list_sessions()
        total_nodes = sum(c for _, c in sessions)
        recent_nodes, _ = self.db.get_recent_changes(days=7)
        recurring = self.db.get_recurring_nodes(min_times_seen=2, limit=10)
        sample = self.db.get_sample_nodes(limit=1)
        last_seen = sample[0]["seen_at"][:10] if sample and sample[0].get("seen_at") else "—"
        return {
            "total_nodes": total_nodes,
            "session_count": len(sessions),
            "new_last_7d": len(recent_nodes),
            "recurring_count": len(recurring),
            "last_seen": last_seen,
            "top_recurring": recurring[:3],
        }

    # ---------------------------------------------------------------- greeting
    def generate_greeting(self):
        """One- or two-sentence greeting personalized to current graph state."""
        sessions = self.db.list_sessions()
        total_nodes = sum(cnt for _, cnt in sessions)

        if total_nodes == 0:
            return "Nothing in your map yet. Tell me what's been on your mind."

        recent_nodes, _ = self.db.get_recent_changes(days=14)
        recurring = self.db.get_recurring_nodes(min_times_seen=2, limit=3)
        sample_nodes = self.db.get_sample_nodes(limit=12)
        last_session_id = sessions[0][0] if sessions else None

        try:
            payload = json.dumps({
                "total_nodes_in_graph": total_nodes,
                "session_count": len(sessions),
                "last_session_id": last_session_id,
                "sample_nodes_in_map": sample_nodes,
                "recent_nodes_last_14_days": recent_nodes[:10],
                "recurring_nodes": recurring,
            })
            return self._chat(GREETING_PROMPT, payload, temperature=0.6).strip().strip('"')
        except Exception:
            sample_label = sample_nodes[0]["label"] if sample_nodes else None
            if sample_label:
                return f"You've got {total_nodes} threads in your map — last one was about \"{sample_label}\". What's on your mind today?"
            return f"You've got {total_nodes} threads in your map. What's on your mind?"

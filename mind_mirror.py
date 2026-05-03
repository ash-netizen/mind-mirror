import json
import os
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq

from database import MindMirrorDB
from prompt_library import (
    EXTRACTION_PROMPT,
    MIRROR_PROMPT,
    INSIGHT_PROMPT,
    CONTRADICTION_PROMPT,
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

    def _build_map_context(self):
        """The 'memory' passed to every LLM call so responses feel context-aware."""
        recurring = self.db.get_recurring_nodes(min_times_seen=2, limit=8)
        recent_nodes, _ = self.db.get_recent_changes(days=14)
        sample = self.db.get_sample_nodes(limit=20)
        sessions = self.db.list_sessions()
        return {
            "total_nodes_in_map": sum(c for _, c in sessions),
            "recurring_nodes": recurring,
            "recent_nodes_last_14_days": recent_nodes[:10],
            "other_nodes_in_map": [
                {"label": s["label"], "class": s.get("class")} for s in sample
            ],
        }

    # ============================================================ MAIN
    def respond(self, raw_input, recent_history=None):
        """
        The single unified entry point. Takes raw input + recent conversation history.

        Returns:
        {
          "type": "meta" | "cognitive",
          "response": str,
          "followups": [str, ...],
          "extraction": {nodes, relationships},
          "contradictions": [...],
          "persisted": bool,
          "message": str,
          "error": str | None
        }
        """
        result = {
            "type": "cognitive",
            "response": "",
            "followups": [],
            "extraction": {"nodes": [], "relationships": []},
            "contradictions": [],
            "persisted": False,
            "message": "",
            "error": None,
        }

        map_context = self._build_map_context()

        # --- 1. Mirror call: voice + routing + followups
        try:
            mirror_payload = json.dumps({
                "what_user_just_said": raw_input,
                "recent_conversation_history": recent_history or [],
                "their_map": map_context,
            })
            raw = self._chat(MIRROR_PROMPT, mirror_payload, json_mode=True, temperature=0.6)
            mirror_data = json.loads(raw)
            result["type"] = mirror_data.get("type", "cognitive")
            result["response"] = mirror_data.get("response", "").strip()
            followups = mirror_data.get("followups", []) or []
            # filter any empty/None entries
            result["followups"] = [q.strip() for q in followups if q and q.strip()][:2]
        except Exception as e:
            result["error"] = f"Inner voice call failed: {e}"
            return result

        # --- 2. If meta, we're done — no extraction, no persistence
        if result["type"] == "meta":
            return result

        # --- 3. Cognitive: extract structure
        try:
            ext_raw = self._chat(EXTRACTION_PROMPT, raw_input, json_mode=True)
            ext_data = json.loads(ext_raw)
            nodes = ext_data.get("nodes", [])
            relationships = ext_data.get("relationships", [])
            result["extraction"] = {"nodes": nodes, "relationships": relationships}
        except Exception as e:
            result["error"] = f"Extraction failed: {e}"
            return result

        if not nodes:
            result["message"] = "Nothing structural to extract — input felt thin."
            return result

        # --- 4. Persist
        success, msg, written_ids = self.db.write_graph(
            nodes, relationships, self.session_id, source_text=raw_input
        )
        result["persisted"] = success
        result["message"] = msg
        if not success:
            result["error"] = msg
            return result

        # --- 5. Contradiction detection (best effort)
        try:
            result["contradictions"] = self._detect_contradictions(nodes, written_ids)
        except Exception:
            pass

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

    # ============================================================ INSIGHT
    def generate_insight(self, session_id=None):
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
        new_nodes, new_rels = self.db.get_recent_changes(days=days)
        recurring = self.db.get_recurring_nodes(min_times_seen=2, limit=10)
        sample = self.db.get_sample_nodes(limit=15)
        if not new_nodes and not recurring and not sample:
            return {"error": "No activity yet — commit a thought first."}
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

    # ============================================================ greeting
    def generate_greeting(self):
        sessions = self.db.list_sessions()
        total_nodes = sum(cnt for _, cnt in sessions)
        if total_nodes == 0:
            return "Nothing in your map yet. Tell me what's on your mind."
        recurring = self.db.get_recurring_nodes(min_times_seen=2, limit=3)
        sample = self.db.get_sample_nodes(limit=12)
        last_session_id = sessions[0][0] if sessions else None
        try:
            payload = json.dumps({
                "total_nodes_in_graph": total_nodes,
                "session_count": len(sessions),
                "last_session_id": last_session_id,
                "sample_nodes_in_map": sample,
                "recurring_nodes": recurring,
            })
            return self._chat(GREETING_PROMPT, payload, temperature=0.6).strip().strip('"')
        except Exception:
            return f"You've got {total_nodes} threads in your map. What's on your mind?"

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
)

load_dotenv()


class MindMirrorEngine:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY missing — set it in .env")
        self.client = Groq(api_key=api_key)
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.whisper_model = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
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
        graph_map = self.db.get_full_graph(session_id=session_id)
        if not graph_map:
            return "Knowledge Graph is empty for this scope. Map some thoughts first."
        return self._chat(INSIGHT_PROMPT, f"CURRENT GRAPH TOPOLOGY:\n\n{graph_map}")

    def generate_delta_insight(self, days=7):
        new_nodes, new_rels = self.db.get_recent_changes(days=days)
        recurring = self.db.get_recurring_nodes(min_times_seen=2, limit=10)
        if not new_nodes and not recurring:
            return f"No activity in the last {days} days, and no recurring patterns yet."
        payload = json.dumps({
            "window_days": days,
            "new_nodes": new_nodes,
            "new_relationships": new_rels,
            "recurring_load_bearers": recurring,
        })
        return self._chat(DELTA_INSIGHT_PROMPT, payload, temperature=0.4)

    # ---------------------------------------------------------------- voice
    def transcribe_voice(self, audio_bytes, filename="voice.webm"):
        try:
            transcription = self.client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model=self.whisper_model,
                response_format="text",
            )
            return str(transcription).strip()
        except Exception as e:
            raise RuntimeError(f"Voice transcription failed: {e}")

# 🧠 Mind Mirror

> A cognitive auditor for your own mind. Treats beliefs like services, triggers like events, contradictions like race conditions, and patterns like architectural signatures — all stored in a live knowledge graph.

**Mind Mirror** is a personal "extended consciousness" tool. You feed it raw thoughts (typed or spoken). An LLM extracts the cognitive structure — beliefs, values, triggers, behaviors, contradictions — and persists it to a graph database. The app then surfaces what you don't see about yourself: contradictions in real time, recurring load-bearers, drift, blindspots, and a daily probing question delivered to your inbox.

---

## ✨ Features

| Capability | What it does |
|---|---|
| 🎙 **Voice or text intake** | Speak or type a thought; transcribed via Groq Whisper |
| 🧬 **Structured extraction** | Llama 3.3 70B parses thought → JSON nodes/relationships using a fixed cognitive ontology |
| 🌐 **Live knowledge graph** | Force-directed visualization of your cognitive topology, color-coded by node class |
| ⚠ **Real-time contradiction detection** | Every commit cross-checks new beliefs against the existing 1-hop neighborhood |
| 💭 **Adaptive follow-up questions** | After each commit, the app asks ONE probing question to deepen the signal |
| 📊 **Delta insight report** | "What changed in the last 7 days, what you keep returning to, what you're avoiding" |
| 🗂 **Session history** | Every thought tagged with a session ID; filter the graph or insight to any past session |
| 📩 **Daily reflection email** | A cron job picks one fertile question from your graph each morning and emails it to you |
| 🆓 **100% free stack** | No paid services — Groq + Neo4j AuraDB Free + Streamlit Cloud + GitHub Actions + Gmail SMTP |

---

## 🏗 Architecture

```
                                ┌────────────────────────┐
                                │   Streamlit Cloud      │
        ┌──────────┐            │   (web UI, free tier)  │
        │ Browser  │◄──────────►│                        │
        │ + mic    │            │   app.py (UI)          │
        └──────────┘            │   mind_mirror.py       │──┐
                                │   database.py          │  │
                                │   prompt_library.py    │  │
                                └─────────┬──────────────┘  │
                                          │                  │
                ┌─────────────────────────┤                  │
                │                         │                  │
                ▼                         ▼                  ▼
        ┌───────────────┐         ┌───────────────┐  ┌───────────────┐
        │  Groq API     │         │ Neo4j AuraDB  │  │ GitHub        │
        │  (LLM + STT)  │         │  Free (graph) │  │ Actions       │
        │  Llama 3.3    │         │               │  │ daily 8AM IST │
        │  Whisper v3   │         │  50k nodes    │  │   ↓           │
        └───────────────┘         └───────────────┘  │ daily_prompt  │
                                                     │   ↓ Gmail SMTP│
                                                     │  📧 You       │
                                                     └───────────────┘
```

### The cognitive ontology

**Node classes:** `CORE_BELIEF`, `VALUE`, `TRIGGER`, `COGNITIVE_PROCESS`, `AFFECT`, `BEHAVIOR`, `INTENT`, `PATTERN`

**Predicates:** `INFLUENCES`, `REINFORCES`, `CONTRADICTS`, `TRIGGERS`, `CAUSES_AVOIDANCE_OF`, `PRECEDES`, `RESOLVES`, `STRUCTURALLY_MATCHES`

Every node carries `id`, `label` (user's own words), `created_at`, `last_seen_at`, `times_seen`, `session_id`. Every edge carries `created_at`. This makes temporal queries — "what shifted in the last 7 days?", "what do I keep returning to?" — first-class.

---

## 🚀 Quickstart (local)

### 1. Clone and install

```bash
git clone https://github.com/<your-username>/mind_mirror.git
cd mind_mirror
pip install -r requirements.txt
```

### 2. Get free API keys / accounts

| Service | Where | Free tier limit |
|---|---|---|
| Groq API | https://console.groq.com/keys | 30 req/min |
| Neo4j AuraDB | https://console.neo4j.io/ | 50k nodes / 175k rels |
| Gmail App Password (optional, for daily emails) | https://myaccount.google.com/apppasswords | 500 emails/day |

### 3. Configure `.env`

```bash
cp .env.example .env
# fill in keys
```

### 4. Run

```bash
streamlit run app.py
```

Visit `http://localhost:8501`.

### 5. (Optional) Schedule daily emails

Push to GitHub → add the same env vars as repository **Secrets** → the workflow at `.github/workflows/daily_prompt.yml` runs daily at 8 AM IST.

---

## 🧠 Why this exists

Most journaling tools are write-only — you dump words, they vanish. Most therapy/coaching tools are advice-givers — they tell you what to do.

Mind Mirror is neither. It is a **structural auditor**: it doesn't interpret your feelings, it indexes their architecture. The goal is not to feel better; it is to *see more clearly* — to surface contradictions you've been quietly maintaining, beliefs you keep reinforcing without examining, intents you've abandoned without noticing.

The hypothesis: if you can render your cognition as a system, you can debug it like one.

---

## 🛣 Roadmap (v3+)

- [ ] **Multi-modal input** — image of a journal page → OCR → ingest
- [ ] **Evolution view** — slider through time, see how the graph morphed
- [ ] **Pattern naming** — name a recurring loop ("Sunday spiral"), app detects when it activates
- [ ] **Search-by-meaning** — vector embeddings over node labels for semantic recall
- [ ] **Multi-user** — therapist/coach view of a client's graph (with consent)
- [ ] **Export** — Markdown export of any session for offline review
- [ ] **Mobile-first PWA** — installable home-screen icon, native voice button

---

## 🗂 Project structure

```
mind_mirror_v1/
├── app.py                  # Streamlit UI
├── mind_mirror.py          # Engine: ingest + insight + voice
├── database.py             # Neo4j wrapper + temporal queries
├── prompt_library.py       # System prompts for each LLM mode
├── daily_prompt.py         # Scheduled daily email script
├── migrate.py              # One-shot local Neo4j → AuraDB migration
├── requirements.txt
├── .env.example
└── .github/workflows/
    └── daily_prompt.yml    # GitHub Actions cron
```

---

## 📜 License

MIT — use it, fork it, build your own.

---

*"You cannot debug what you cannot see."*

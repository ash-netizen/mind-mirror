import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
from streamlit_mic_recorder import mic_recorder

from mind_mirror import MindMirrorEngine

st.set_page_config(
    page_title="Mind Mirror | Cognitive Auditor",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

CLASS_COLORS = {
    "CORE_BELIEF": "#E63946",
    "VALUE": "#F4A261",
    "TRIGGER": "#E76F51",
    "COGNITIVE_PROCESS": "#9D4EDD",
    "AFFECT": "#F72585",
    "BEHAVIOR": "#4361EE",
    "INTENT": "#06A77D",
    "PATTERN": "#2A9D8F",
    "UNKNOWN": "#888888",
}


def _scope_to_sid(scope_label: str):
    if scope_label == "All sessions":
        return None
    return scope_label.split(" (")[0]


def _init_state():
    if "mirror" not in st.session_state:
        with st.spinner("Synchronizing Cognitive Ontology..."):
            st.session_state.mirror = MindMirrorEngine()
    st.session_state.setdefault("view_scope", "All sessions")
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("pending_input", "")
    st.session_state.setdefault("ingesting", False)
    st.session_state.setdefault("confirm_nuke", False)


_init_state()

st.title("🧠 Mind Mirror")
st.markdown("*Local Cognitive Pattern Analyzer — extended consciousness as a graph*")
st.markdown("---")

# ============================================================ INGESTION + AUDIT
col_ingest, col_audit = st.columns([1, 1], gap="large")

with col_ingest:
    st.subheader("📡 Ingestion Zone")
    st.caption("Type or speak a thought. The graph remembers and reflects.")

    # ---- Voice capture
    voice = mic_recorder(
        start_prompt="🎙 Start recording",
        stop_prompt="⏹ Stop & transcribe",
        just_once=True,
        use_container_width=True,
        format="webm",
        key="voice_recorder",
    )
    if voice and voice.get("bytes"):
        with st.spinner("Transcribing voice via Groq Whisper..."):
            try:
                text = st.session_state.mirror.transcribe_voice(voice["bytes"])
                st.session_state.pending_input = text
                st.toast(f"📝 Transcribed {len(text)} chars")
            except Exception as e:
                st.error(f"Voice failed: {e}")

    thought_input = st.text_area(
        "Signal Input",
        value=st.session_state.pending_input,
        placeholder="Enter a thought, a conflict, a contradiction, an observation...",
        height=200,
        label_visibility="collapsed",
        key="thought_textarea",
    )

    commit_disabled = st.session_state.ingesting or len(thought_input.strip()) < 10
    btn_label = "⏳ Processing..." if st.session_state.ingesting else "Commit to Graph"

    if st.button(btn_label, type="primary", use_container_width=True, disabled=commit_disabled):
        st.session_state.ingesting = True
        with st.status("Processing Cognitive Pipeline...", expanded=True) as status:
            st.write("Extracting structure via Groq Llama 3.3 70B...")
            result = st.session_state.mirror.ingest_thought(thought_input)
            st.session_state.last_result = result
            st.session_state.pending_input = ""
            if result["success"]:
                status.update(label="✅ Persistence Complete", state="complete", expanded=False)
            else:
                status.update(label="❌ Pipeline Failure", state="error")
        st.session_state.ingesting = False
        st.rerun()

    # ---- Show last commit results
    res = st.session_state.last_result
    if res:
        if res["success"]:
            st.success(f"✅ {res['message']}")

            if res["contradictions"]:
                st.warning(f"⚠ {len(res['contradictions'])} contradiction(s) detected:")
                for c in res["contradictions"]:
                    st.markdown(
                        f"- **`{c['new_node_id']}`** vs **`{c['existing_node_id']}`**  \n"
                        f"  {c['explanation']}"
                    )

            if res["followup_question"]:
                st.info(f"💭 **Follow-up:** {res['followup_question']}")
        else:
            st.error(f"Error: {res['message']}")

with col_audit:
    st.subheader("🔍 Reflection Zone")

    audit_tab1, audit_tab2 = st.tabs(["Delta (Last 7 days)", "Full Topology Audit"])

    with audit_tab1:
        st.caption("What changed, what you keep returning to, what you're avoiding.")
        if st.button("Generate Delta Report", use_container_width=True):
            with st.spinner("Computing delta + recurring patterns..."):
                try:
                    report = st.session_state.mirror.generate_delta_insight(days=7)
                    st.markdown(report)
                except Exception as e:
                    st.error(f"Failed: {e}")

    with audit_tab2:
        st.caption("Full structural audit of the current scope.")
        if st.button("Generate Full Insight", use_container_width=True):
            with st.spinner("Analyzing entire architecture..."):
                try:
                    scope_sid = _scope_to_sid(st.session_state.view_scope)
                    report = st.session_state.mirror.generate_insight(session_id=scope_sid)
                    st.markdown(report)
                except Exception as e:
                    st.error(f"Failed: {e}")

# ============================================================ TOPOLOGY VIZ
st.markdown("---")
st.subheader("🌐 Cognitive Topology")
st.caption(f"Viewing: **{st.session_state.view_scope}** — drag nodes to explore.")

try:
    nodes_data, edges_data = st.session_state.mirror.db.get_graph_data(
        session_id=_scope_to_sid(st.session_state.view_scope)
    )
except Exception as e:
    st.error(f"Couldn't fetch graph: {e}")
    nodes_data, edges_data = [], []

if not nodes_data:
    st.info("Graph is empty for this scope. Commit a thought above to begin mapping.")
else:
    # Dedupe nodes by id
    seen_ids = set()
    unique_nodes = []
    for n in nodes_data:
        if n["id"] in seen_ids:
            continue
        seen_ids.add(n["id"])
        unique_nodes.append(n)

    seen_edges = set()
    unique_edges = []
    for e in edges_data:
        key = (e["source"], e["target"], e["rel"])
        if key in seen_edges:
            continue
        seen_edges.add(key)
        unique_edges.append(e)

    viz_nodes = [
        Node(
            id=n["id"],
            label=n["label"],
            size=20,
            color=CLASS_COLORS.get(n["class"], CLASS_COLORS["UNKNOWN"]),
            title=f"{n['class']}: {n['label']}",
        )
        for n in unique_nodes
    ]
    viz_edges = [
        Edge(source=e["source"], target=e["target"], label=e["rel"])
        for e in unique_edges
    ]
    config = Config(
        width="100%",
        height=600,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#FFD60A",
        collapsible=False,
    )
    agraph(nodes=viz_nodes, edges=viz_edges, config=config)

    legend_cols = st.columns(len(CLASS_COLORS) - 1)
    for i, (cls, color) in enumerate((c for c in CLASS_COLORS.items() if c[0] != "UNKNOWN")):
        with legend_cols[i]:
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:6px;font-size:12px;'>"
                f"<div style='width:12px;height:12px;background:{color};border-radius:50%;'></div>"
                f"<span>{cls}</span></div>",
                unsafe_allow_html=True,
            )

# ============================================================ SIDEBAR
with st.sidebar:
    st.title("Sessions")
    st.write(f"**Writing to:** `{st.session_state.mirror.session_id}`")

    if st.button("➕ Start New Session", use_container_width=True):
        new_sid = st.session_state.mirror.start_new_session()
        st.toast(f"New session: {new_sid}")
        st.rerun()

    sessions = st.session_state.mirror.db.list_sessions()
    scope_options = ["All sessions"] + [f"{sid} ({cnt} nodes)" for sid, cnt in sessions]

    if st.session_state.view_scope not in scope_options:
        st.session_state.view_scope = "All sessions"

    st.session_state.view_scope = st.selectbox(
        "View scope",
        options=scope_options,
        index=scope_options.index(st.session_state.view_scope),
    )

    st.divider()
    st.title("System")
    st.write(f"**Model:** `{st.session_state.mirror.model}`")
    st.write(f"**STT:** `{st.session_state.mirror.whisper_model}`")
    st.write(f"**DB:** `Neo4j AuraDB`")

    st.divider()
    st.subheader("⚠ Danger Zone")
    if not st.session_state.confirm_nuke:
        if st.button("Reset Graph", use_container_width=True):
            st.session_state.confirm_nuke = True
            st.rerun()
    else:
        st.error("This permanently deletes ALL nodes. Are you sure?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, nuke", type="primary", use_container_width=True):
                st.session_state.mirror.db.reset()
                st.session_state.confirm_nuke = False
                st.session_state.last_result = None
                st.toast("Graph reset.")
                st.rerun()
        with c2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_nuke = False
                st.rerun()

    st.markdown("---")
    st.caption("Mind Mirror v2.0 | Extended Consciousness")

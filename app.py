import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config

from mind_mirror import MindMirrorEngine

st.set_page_config(
    page_title="Mind Mirror",
    page_icon="🪞",
    layout="centered",
    initial_sidebar_state="collapsed",
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

CLASS_LABEL = {
    "CORE_BELIEF": "belief",
    "VALUE": "value",
    "TRIGGER": "trigger",
    "COGNITIVE_PROCESS": "thought process",
    "AFFECT": "feeling",
    "BEHAVIOR": "behavior",
    "INTENT": "intent",
    "PATTERN": "pattern",
    "UNKNOWN": "node",
}

st.markdown(
    """
    <style>
      .block-container { max-width: 760px; padding-top: 2rem; padding-bottom: 4rem; }
      .stTextArea textarea { font-size: 1.05rem; line-height: 1.55; }
      .greeting { font-size: 1.05rem; color: #c9c9c9; line-height: 1.6; margin: 0.25rem 0 1.25rem 0; font-style: italic; }
      .status-strip { font-size: 0.78rem; color: #777; margin-bottom: 1.5rem; letter-spacing: 0.02em; }
      .status-strip .dot { color: #444; margin: 0 0.5rem; }
      .thread-block { background: rgba(255,255,255,0.02); border: 1px solid #2a2a2a; border-radius: 8px; padding: 1.25rem 1.4rem; margin: 1rem 0; }
      .thread-block .you-said { font-size: 0.74rem; color: #888; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.5rem; }
      .thread-block .input-text { font-size: 1.02rem; line-height: 1.55; color: #ddd; }
      .reply-line { border-left: 2px solid #4361EE; margin-left: 0.5rem; padding: 0.75rem 0 0.75rem 1rem; margin-top: 1rem; }
      .reply-line .you-said { color: #6a8eff; }
      .insight-card { background: rgba(255,255,255,0.03); border-left: 3px solid #4361EE; padding: 0.95rem 1.15rem; border-radius: 4px; margin: 0.6rem 0; }
      .insight-card .ic-title { font-size: 0.72rem; color: #888; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 0.35rem; }
      .insight-card .ic-headline { font-size: 1.05rem; font-weight: 600; color: #f0f0f0; margin-bottom: 0.4rem; line-height: 1.35; }
      .insight-card .ic-body { font-size: 0.93rem; color: #cccccc; line-height: 1.55; }
      .insight-card.shift { border-left-color: #06A77D; }
      .insight-card.recurring { border-left-color: #F4A261; }
      .insight-card.blindspot { border-left-color: #E76F51; }
      .insight-card.question { border-left-color: #FFD60A; }
      .insight-card.shape { border-left-color: #9D4EDD; }
      .insight-card.tension { border-left-color: #E63946; }
      .insight-card.load { border-left-color: #2A9D8F; }
      .chip { display: inline-block; padding: 2px 9px; margin: 2px 4px 2px 0; border-radius: 12px; font-size: 0.78rem; background: rgba(255,255,255,0.05); }
      .tension-line { color: #ff9999; font-size: 0.92rem; margin: 0.6rem 0; }
      .followup-line { color: #ffd966; font-size: 0.95rem; margin: 0.7rem 0 0.4rem 0; line-height: 1.5; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _scope_to_sid(scope_label: str):
    if scope_label == "All sessions":
        return None
    return scope_label.split(" (")[0]


def _init_state():
    if "mirror" not in st.session_state:
        with st.spinner("Loading your map..."):
            st.session_state.mirror = MindMirrorEngine()
            st.session_state.greeting = st.session_state.mirror.generate_greeting()
            st.session_state.stats = st.session_state.mirror.get_snapshot_stats()
    st.session_state.setdefault("view_scope", "All sessions")
    # active_thread = list of {input, result, is_reply}, in order; replaces old multi-thread "journal"
    st.session_state.setdefault("active_thread", [])
    st.session_state.setdefault("archived_threads", [])  # list of lists
    st.session_state.setdefault("ingesting", False)
    st.session_state.setdefault("confirm_nuke", False)
    st.session_state.setdefault("selected_node", None)
    st.session_state.setdefault("delta_report", None)
    st.session_state.setdefault("full_report", None)


def _refresh_stats():
    st.session_state.stats = st.session_state.mirror.get_snapshot_stats()


def _archive_active_thread():
    if st.session_state.active_thread:
        st.session_state.archived_threads.append(st.session_state.active_thread)
        st.session_state.active_thread = []


_init_state()
mirror = st.session_state.mirror

# ============================================================ HEADER
st.markdown("# 🪞 Mind Mirror")
st.markdown(f"<div class='greeting'>{st.session_state.greeting}</div>", unsafe_allow_html=True)

# Subtle status strip (no loud tiles)
stats = st.session_state.stats
recurring_str = ""
if stats["top_recurring"]:
    recurring_str = " · returning to: " + ", ".join(
        f"<span style='color:{CLASS_COLORS.get(r['class'], '#888')}'>{r['label']}</span>"
        for r in stats["top_recurring"][:2]
    )
st.markdown(
    f"<div class='status-strip'>"
    f"{stats['total_nodes']} nodes <span class='dot'>·</span> "
    f"{stats['session_count']} sessions <span class='dot'>·</span> "
    f"{stats['new_last_7d']} new in 7d"
    f"{recurring_str}"
    f"</div>",
    unsafe_allow_html=True,
)


# ============================================================ ACTIVE THREAD
def _render_extraction_chips(nodes):
    chips = " ".join(
        f"<span class='chip' style='color:{CLASS_COLORS.get(n['class'], '#888')}'>"
        f"{n.get('label', n['id'])}</span>"
        for n in nodes
    )
    st.markdown(f"<div style='margin-top:0.6rem'>{chips}</div>", unsafe_allow_html=True)


def _render_thread_entry(entry, in_reply_block=False):
    res = entry["result"]
    cls = "reply-line" if in_reply_block else "thread-block"
    label = "You replied" if in_reply_block else "You said"
    st.markdown(f"<div class='{cls}'>", unsafe_allow_html=True)
    st.markdown(f"<div class='you-said'>{label}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='input-text'>{entry['input']}</div>", unsafe_allow_html=True)

    if res["success"]:
        nodes = res["extraction"]["nodes"]
        if nodes:
            _render_extraction_chips(nodes)
        if res["contradictions"]:
            for c in res["contradictions"]:
                st.markdown(f"<div class='tension-line'>⚠ <strong>Tension:</strong> {c['explanation']}</div>", unsafe_allow_html=True)
        if res["followup_question"]:
            st.markdown(f"<div class='followup-line'>↳ {res['followup_question']}</div>", unsafe_allow_html=True)
    else:
        st.error(res["message"])
    st.markdown("</div>", unsafe_allow_html=True)


# Render the active thread (compact: first entry as block, replies indented)
if st.session_state.active_thread:
    for i, entry in enumerate(st.session_state.active_thread):
        _render_thread_entry(entry, in_reply_block=(i > 0))


# ============================================================ INPUT
# Determine whether next commit is a reply (extends active thread) or a new thought.
is_reply_mode = bool(st.session_state.active_thread) and bool(
    st.session_state.active_thread[-1]["result"].get("followup_question")
)

input_label = "Reply" if is_reply_mode else ("Continue" if st.session_state.active_thread else "What's on your mind?")
input_placeholder = (
    "Reply to the question above…"
    if is_reply_mode
    else ("Add another thought to this thread…" if st.session_state.active_thread else "A thought, a tension, something you noticed…")
)

with st.form("intake_form", clear_on_submit=True):
    thought_input = st.text_area(
        input_label,
        placeholder=input_placeholder,
        height=130,
    )
    cols = st.columns([3, 1])
    with cols[0]:
        submitted = st.form_submit_button(
            "Commit",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.ingesting,
        )
    with cols[1]:
        # Show "New thread" button only when there's already content in the active thread
        new_thread_clicked = False
        if st.session_state.active_thread:
            new_thread_clicked = st.form_submit_button("New thread", use_container_width=True)
        else:
            st.write("")  # keep layout stable

if new_thread_clicked:
    _archive_active_thread()
    st.rerun()

if submitted:
    if len(thought_input.strip()) < 10:
        st.warning("Give me a bit more — at least a sentence.")
    else:
        st.session_state.ingesting = True
        with st.spinner("Reading you..."):
            result = mirror.ingest_thought(thought_input)
        st.session_state.active_thread.append({
            "input": thought_input,
            "result": result,
            "is_reply": is_reply_mode,
        })
        st.session_state.ingesting = False
        _refresh_stats()
        st.rerun()


# ============================================================ REFLECT
st.markdown("---")
st.markdown("### Reflect")

c1, c2 = st.columns(2)
with c1:
    if st.button("📊 What shifted (7d)", use_container_width=True):
        with st.spinner("Looking at the last 7 days..."):
            st.session_state.delta_report = mirror.generate_delta_insight(days=7)
            st.session_state.full_report = None

with c2:
    if st.button("🌐 Read the whole map", use_container_width=True):
        with st.spinner("Reading the map..."):
            scope_sid = _scope_to_sid(st.session_state.view_scope)
            st.session_state.full_report = mirror.generate_insight(session_id=scope_sid)
            st.session_state.delta_report = None


def _card(kind, title, headline, body):
    st.markdown(
        f"<div class='insight-card {kind}'>"
        f"<div class='ic-title'>{title}</div>"
        f"<div class='ic-headline'>{headline}</div>"
        f"<div class='ic-body'>{body}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _unwrap(obj):
    """Handle both old (string) and new (dict) shapes from prompts."""
    if isinstance(obj, dict):
        return obj.get("headline", "—"), obj.get("body", "—")
    if isinstance(obj, str):
        return obj, ""
    return "—", ""


if st.session_state.delta_report:
    rep = st.session_state.delta_report
    if "error" in rep:
        st.info(rep["error"])
    else:
        for kind, title, key in [
            ("shift", "What shifted", "shift"),
            ("recurring", "What you keep returning to", "recurring"),
            ("blindspot", "Quietly absent", "blindspot"),
        ]:
            h, b = _unwrap(rep.get(key))
            _card(kind, title, h, b)
        if rep.get("question"):
            _card("question", "Question for you", rep["question"], "")

if st.session_state.full_report:
    rep = st.session_state.full_report
    if "error" in rep:
        st.info(rep["error"])
    else:
        for kind, title, key in [
            ("shape", "Shape of your map", "shape"),
            ("tension", "One tension", "tension"),
            ("load", "Everything circles around", "load_bearers"),
        ]:
            h, b = _unwrap(rep.get(key))
            _card(kind, title, h, b)
        if rep.get("question"):
            _card("question", "Question for you", rep["question"], "")


# ============================================================ ARCHIVE (past threads)
if st.session_state.archived_threads:
    st.markdown("---")
    with st.expander(f"📂 {len(st.session_state.archived_threads)} earlier thread(s) this visit"):
        for ti, thread in enumerate(reversed(st.session_state.archived_threads)):
            st.markdown(f"**Thread {len(st.session_state.archived_threads) - ti}**")
            for i, entry in enumerate(thread):
                input_short = entry["input"][:120] + ("..." if len(entry["input"]) > 120 else "")
                tag = "↳ " if i > 0 else "• "
                st.markdown(f"{tag}_{input_short}_")
            st.markdown("---")


# ============================================================ MAP
st.markdown("---")
st.markdown(f"### 🗺 Your map  <span style='font-size:0.85rem; color:#888; font-weight:normal'>· {stats['total_nodes']} nodes · scope: {st.session_state.view_scope}</span>", unsafe_allow_html=True)
map_expanded = st.toggle("Show map", value=False)

if map_expanded:
    try:
        nodes_data, edges_data = mirror.db.get_graph_data(
            session_id=_scope_to_sid(st.session_state.view_scope)
        )
    except Exception as e:
        st.error(f"Couldn't fetch map: {e}")
        nodes_data, edges_data = [], []

    if not nodes_data:
        if stats["total_nodes"] == 0:
            st.info("Your map is empty. Commit a thought above and watch it grow.")
        else:
            st.warning(
                f"Map has {stats['total_nodes']} nodes but none match the current view scope. "
                f"Switch scope to **All sessions** in the sidebar."
            )
    else:
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

        def _short(label, n=24):
            label = label or ""
            return label if len(label) <= n else label[: n - 1] + "…"

        viz_nodes = [
            Node(
                id=n["id"],
                label=_short(n["label"]),
                size=18,
                color=CLASS_COLORS.get(n["class"], CLASS_COLORS["UNKNOWN"]),
                title=f"{CLASS_LABEL.get(n['class'], n['class'])}: {n['label']}",
                font={"size": 12, "color": "#e8e8e8", "strokeWidth": 3, "strokeColor": "#0e1117"},
            )
            for n in unique_nodes
        ]
        viz_edges = [
            Edge(
                source=e["source"],
                target=e["target"],
                label="",
                title=e["rel"].lower().replace("_", " "),
                color={"color": "#555", "highlight": "#FFD60A"},
                width=1,
            )
            for e in unique_edges
        ]
        config = Config(
            width="100%",
            height=560,
            directed=True,
            physics={
                "enabled": True,
                "solver": "forceAtlas2Based",
                "forceAtlas2Based": {
                    "gravitationalConstant": -90,
                    "centralGravity": 0.01,
                    "springLength": 200,
                    "springConstant": 0.05,
                    "damping": 0.6,
                    "avoidOverlap": 1,
                },
                "stabilization": {"enabled": True, "iterations": 250, "fit": True},
            },
            interaction={"hover": True, "tooltipDelay": 100, "navigationButtons": True},
            nodeHighlightBehavior=True,
            highlightColor="#FFD60A",
            collapsible=False,
        )
        clicked = agraph(nodes=viz_nodes, edges=viz_edges, config=config)
        if clicked and clicked != st.session_state.selected_node:
            st.session_state.selected_node = clicked
            st.rerun()

        legend_html = "<div style='display:flex; flex-wrap:wrap; gap:14px; font-size:12px; margin-top:8px;'>"
        for cls in [c for c in CLASS_COLORS if c != "UNKNOWN"]:
            legend_html += (
                f"<div style='display:flex; align-items:center; gap:5px;'>"
                f"<div style='width:10px;height:10px;border-radius:50%;background:{CLASS_COLORS[cls]}'></div>"
                f"<span style='color:#aaa'>{CLASS_LABEL[cls]}</span></div>"
            )
        legend_html += "</div>"
        st.markdown(legend_html, unsafe_allow_html=True)

        if st.session_state.selected_node:
            details = mirror.db.get_node_details(st.session_state.selected_node)
            if details:
                st.markdown("---")
                cls_human = CLASS_LABEL.get(details["class"], details["class"])
                st.markdown(f"### `{details['label']}`  *({cls_human})*")
                meta_bits = []
                if details.get("times_seen"):
                    meta_bits.append(f"appeared {details['times_seen']}×")
                if details.get("created_at"):
                    meta_bits.append(f"first seen {details['created_at'][:10]}")
                if details.get("last_seen_at") and details.get("last_seen_at") != details.get("created_at"):
                    meta_bits.append(f"last seen {details['last_seen_at'][:10]}")
                if meta_bits:
                    st.caption(" · ".join(meta_bits))

                if details["thoughts"]:
                    st.markdown("**Originating thoughts**")
                    for t in details["thoughts"][:5]:
                        st.markdown(
                            f"> _{t['text']}_  \n"
                            f"<span style='font-size:0.75rem;color:#888'>{t['created_at'][:10]}</span>",
                            unsafe_allow_html=True,
                        )

                if details["neighbors"]:
                    st.markdown("**Connected to**")
                    for nb in details["neighbors"][:15]:
                        arrow = "→" if nb["outgoing"] else "←"
                        rel = nb["rel"].lower().replace("_", " ")
                        st.markdown(f"- {arrow} `{nb['label'] or nb['id']}` *({rel})*")

                if st.button("Close", key="close_node_detail"):
                    st.session_state.selected_node = None
                    st.rerun()


# ============================================================ SIDEBAR
with st.sidebar:
    st.markdown("### Sessions")
    st.caption(f"Writing to `{mirror.session_id}`")
    if st.button("Start new session", use_container_width=True):
        _archive_active_thread()
        mirror.start_new_session()
        st.session_state.greeting = mirror.generate_greeting()
        _refresh_stats()
        st.rerun()

    sessions = mirror.db.list_sessions()
    scope_options = ["All sessions"] + [f"{sid} ({cnt})" for sid, cnt in sessions]
    if st.session_state.view_scope not in scope_options:
        st.session_state.view_scope = "All sessions"
    st.session_state.view_scope = st.selectbox(
        "View scope", options=scope_options,
        index=scope_options.index(st.session_state.view_scope),
    )

    st.divider()
    st.markdown("### System")
    st.caption(f"Model: `{mirror.model}`")
    st.caption(f"DB: Neo4j AuraDB")

    st.divider()
    if not st.session_state.confirm_nuke:
        if st.button("⚠ Reset graph", use_container_width=True):
            st.session_state.confirm_nuke = True
            st.rerun()
    else:
        st.error("Permanently delete ALL nodes?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, nuke", type="primary", use_container_width=True):
                mirror.db.reset()
                st.session_state.confirm_nuke = False
                st.session_state.active_thread = []
                st.session_state.archived_threads = []
                st.session_state.greeting = mirror.generate_greeting()
                _refresh_stats()
                st.rerun()
        with c2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_nuke = False
                st.rerun()

    st.markdown("---")
    st.caption("Mind Mirror v2.3")

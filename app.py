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
      .block-container { max-width: 780px; padding-top: 2rem; padding-bottom: 4rem; }
      .stTextArea textarea { font-size: 1.05rem; line-height: 1.5; }
      .greeting { font-size: 1.05rem; color: #c9c9c9; line-height: 1.6; margin: 0.5rem 0 1.5rem 0; font-style: italic; }
      .stat-tile { background: rgba(255,255,255,0.04); border: 1px solid #2a2a2a; border-radius: 8px; padding: 0.75rem 1rem; text-align: center; }
      .stat-tile .num { font-size: 1.5rem; font-weight: 600; color: #f0f0f0; line-height: 1.1; }
      .stat-tile .lbl { font-size: 0.72rem; color: #888; margin-top: 0.25rem; text-transform: uppercase; letter-spacing: 0.06em; }
      .insight-card { background: rgba(255,255,255,0.03); border-left: 3px solid #4361EE; padding: 0.85rem 1.1rem; border-radius: 4px; margin: 0.5rem 0; }
      .insight-card .ic-title { font-size: 0.72rem; color: #888; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 0.4rem; }
      .insight-card .ic-body { font-size: 0.95rem; color: #e0e0e0; line-height: 1.5; }
      .insight-card.shift { border-left-color: #06A77D; }
      .insight-card.recurring { border-left-color: #F4A261; }
      .insight-card.blindspot { border-left-color: #E76F51; }
      .insight-card.question { border-left-color: #FFD60A; }
      .insight-card.shape { border-left-color: #9D4EDD; }
      .insight-card.tension { border-left-color: #E63946; }
      .insight-card.load { border-left-color: #2A9D8F; }
      .journal-entry { padding: 1rem 1.25rem; border-left: 3px solid #444; background: rgba(255,255,255,0.02); margin: 1rem 0; border-radius: 4px; }
      .journal-entry .meta { font-size: 0.74rem; color: #888; margin-bottom: 0.4rem; text-transform: uppercase; letter-spacing: 0.05em; }
      .journal-entry.is-reply { border-left-color: #4361EE; margin-left: 1.25rem; }
      .chip { display: inline-block; padding: 2px 9px; margin: 2px; border-radius: 12px; font-size: 0.78rem; background: rgba(255,255,255,0.05); }
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
    st.session_state.setdefault("journal", [])
    st.session_state.setdefault("ingesting", False)
    st.session_state.setdefault("confirm_nuke", False)
    st.session_state.setdefault("selected_node", None)
    st.session_state.setdefault("delta_report", None)
    st.session_state.setdefault("full_report", None)


def _refresh_stats():
    st.session_state.stats = st.session_state.mirror.get_snapshot_stats()


_init_state()
mirror = st.session_state.mirror

# ============================================================ HEADER
st.markdown("# 🪞 Mind Mirror")
st.markdown(f"<div class='greeting'>{st.session_state.greeting}</div>", unsafe_allow_html=True)

# ============================================================ SNAPSHOT TILES
stats = st.session_state.stats
tiles = st.columns(4)
tile_data = [
    ("nodes", stats["total_nodes"]),
    ("sessions", stats["session_count"]),
    ("last 7d", stats["new_last_7d"]),
    ("recurring", stats["recurring_count"]),
]
for col, (lbl, num) in zip(tiles, tile_data):
    with col:
        st.markdown(
            f"<div class='stat-tile'><div class='num'>{num}</div><div class='lbl'>{lbl}</div></div>",
            unsafe_allow_html=True,
        )

if stats["top_recurring"]:
    chips = " ".join(
        f"<span class='chip' style='border-left:3px solid {CLASS_COLORS.get(r['class'], '#888')}'>"
        f"{r['label']} ×{r['times_seen']}</span>"
        for r in stats["top_recurring"]
    )
    st.markdown(
        f"<div style='margin: 0.75rem 0 0 0; font-size:0.8rem; color:#aaa'>"
        f"<span style='text-transform:uppercase; letter-spacing:0.05em; font-size:0.7rem'>most-returned-to</span><br>{chips}</div>",
        unsafe_allow_html=True,
    )


# ============================================================ JOURNAL (last 3 + collapse)
def _entry_html_intro(is_reply, meta="You said"):
    cls = "journal-entry is-reply" if is_reply else "journal-entry"
    return f"<div class='{cls}'><div class='meta'>{'Reply' if is_reply else meta}</div>"


def _render_entry(idx, entry):
    res = entry["result"]
    st.markdown(_entry_html_intro(entry.get("is_reply", False)), unsafe_allow_html=True)
    st.markdown(f"_{entry['input']}_")

    if res["success"]:
        nodes = res["extraction"]["nodes"]
        if nodes:
            chips = " ".join(
                f"<span class='chip' style='color:{CLASS_COLORS.get(n['class'], '#888')}'>"
                f"{n.get('label', n['id'])}</span>"
                for n in nodes
            )
            st.markdown(
                f"<div style='margin-top:0.5rem'>{chips}</div>",
                unsafe_allow_html=True,
            )

        if res["contradictions"]:
            for c in res["contradictions"]:
                st.markdown(f"⚠ **Tension:** {c['explanation']}")

        if res["followup_question"] and not entry.get("reply_submitted"):
            st.markdown(f"**↳** {res['followup_question']}")
            with st.form(f"reply_form_{idx}", clear_on_submit=True):
                reply_text = st.text_area(
                    "Reply",
                    placeholder="Reply to deepen the thread...",
                    height=80,
                    label_visibility="collapsed",
                )
                if st.form_submit_button("Reply", use_container_width=False):
                    if len(reply_text.strip()) < 5:
                        st.warning("Give it a few more words.")
                    else:
                        with st.spinner("Reading you..."):
                            reply_result = mirror.ingest_thought(reply_text)
                        st.session_state.journal.append({
                            "input": reply_text,
                            "result": reply_result,
                            "is_reply": True,
                        })
                        entry["reply_submitted"] = True
                        _refresh_stats()
                        st.rerun()
    else:
        st.error(res["message"])
    st.markdown("</div>", unsafe_allow_html=True)


journal = st.session_state.journal
if journal:
    recent = journal[-3:]
    older = journal[:-3]
    if older:
        with st.expander(f"Show {len(older)} earlier in this session"):
            for i, e in enumerate(older):
                _render_entry(i, e)
    base_idx = len(older)
    for i, e in enumerate(recent):
        _render_entry(base_idx + i, e)


# ============================================================ INPUT
st.markdown("---")

with st.form("intake_form", clear_on_submit=True):
    thought_input = st.text_area(
        "What's on your mind?",
        placeholder="A thought, a tension, something you noticed...",
        height=140,
    )
    submitted = st.form_submit_button(
        "Commit", type="primary", use_container_width=True,
        disabled=st.session_state.ingesting,
    )

if submitted:
    if len(thought_input.strip()) < 10:
        st.warning("Give me a bit more — at least a sentence.")
    else:
        st.session_state.ingesting = True
        with st.spinner("Reading you..."):
            result = mirror.ingest_thought(thought_input)
            st.session_state.journal.append({
                "input": thought_input,
                "result": result,
                "is_reply": False,
            })
        st.session_state.ingesting = False
        _refresh_stats()
        st.rerun()


# ============================================================ REFLECT (cards, not prose)
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


def _card(kind, title, body):
    st.markdown(
        f"<div class='insight-card {kind}'><div class='ic-title'>{title}</div>"
        f"<div class='ic-body'>{body}</div></div>",
        unsafe_allow_html=True,
    )


if st.session_state.delta_report:
    rep = st.session_state.delta_report
    if "error" in rep:
        st.info(rep["error"])
    else:
        _card("shift", "What shifted", rep.get("shift", "—"))
        _card("recurring", "What you keep returning to", rep.get("recurring", "—"))
        _card("blindspot", "Quietly absent", rep.get("blindspot", "—"))
        _card("question", "Question for you", rep.get("question", "—"))

if st.session_state.full_report:
    rep = st.session_state.full_report
    if "error" in rep:
        st.info(rep["error"])
    else:
        _card("shape", "Shape of your map", rep.get("shape", "—"))
        _card("tension", "One tension", rep.get("tension", "—"))
        _card("load", "Everything circles around", rep.get("load_bearers", "—"))
        _card("question", "Question for you", rep.get("question", "—"))


# ============================================================ MAP
st.markdown("---")
map_header_cols = st.columns([3, 1])
with map_header_cols[0]:
    st.markdown(f"### 🗺 Your map  <span style='font-size:0.85rem; color:#888; font-weight:normal'>· {stats['total_nodes']} nodes</span>", unsafe_allow_html=True)
with map_header_cols[1]:
    st.caption(f"Scope: {st.session_state.view_scope}")

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
                f"Try changing scope to **All sessions** in the sidebar."
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
        mirror.start_new_session()
        st.session_state.journal = []
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
                st.session_state.journal = []
                st.session_state.greeting = mirror.generate_greeting()
                _refresh_stats()
                st.rerun()
        with c2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_nuke = False
                st.rerun()

    st.markdown("---")
    st.caption("Mind Mirror v2.2")

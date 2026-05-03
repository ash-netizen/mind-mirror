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
      .block-container { max-width: 720px; padding-top: 2rem; padding-bottom: 5rem; }
      .stTextArea textarea { font-size: 1.05rem; line-height: 1.55; background: rgba(255,255,255,0.03); }
      .greeting { font-size: 1rem; color: #b8b8b8; line-height: 1.6; margin: 0.25rem 0 1.25rem 0; font-style: italic; }
      .status-strip { font-size: 0.78rem; color: #777; margin-bottom: 1.5rem; }
      .status-strip .dot { color: #444; margin: 0 0.45rem; }
      .you-bubble { padding: 0.85rem 1.1rem; background: rgba(255,255,255,0.04); border-radius: 12px 12px 12px 2px; margin: 0.4rem 0 0.6rem 0; font-size: 0.98rem; line-height: 1.55; color: #ddd; }
      .you-meta { font-size: 0.7rem; color: #666; text-transform: uppercase; letter-spacing: 0.06em; margin: 1.4rem 0 0.2rem 0; }
      .mirror-bubble { padding: 0.95rem 1.15rem; background: linear-gradient(180deg, rgba(99,90,255,0.08) 0%, rgba(99,90,255,0.04) 100%); border-left: 3px solid #6a5cff; border-radius: 2px 12px 12px 12px; margin: 0.4rem 0 0.5rem 0; font-size: 1rem; line-height: 1.6; color: #f0f0f0; }
      .mirror-meta { font-size: 0.7rem; color: #6a5cff; text-transform: uppercase; letter-spacing: 0.06em; margin: 1rem 0 0.2rem 0; }
      .followup-pill { display: inline-block; padding: 8px 14px; margin: 4px 6px 4px 0; border-radius: 20px; background: rgba(255, 214, 102, 0.08); border: 1px solid rgba(255, 214, 102, 0.25); color: #ffd966; font-size: 0.88rem; cursor: default; }
      .chip-strip { margin: 0.5rem 0 0.2rem 0; }
      .chip { display: inline-block; padding: 2px 9px; margin: 2px 4px 2px 0; border-radius: 12px; font-size: 0.74rem; background: rgba(255,255,255,0.04); }
      .tension-banner { padding: 0.6rem 0.9rem; background: rgba(230, 57, 70, 0.08); border-left: 3px solid #E63946; border-radius: 4px; color: #ff9999; font-size: 0.9rem; margin: 0.5rem 0; }
      .insight-card { background: rgba(255,255,255,0.03); border-left: 3px solid #4361EE; padding: 0.95rem 1.15rem; border-radius: 4px; margin: 0.6rem 0; }
      .insight-card .ic-title { font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 0.35rem; }
      .insight-card .ic-headline { font-size: 1.02rem; font-weight: 600; color: #f0f0f0; margin-bottom: 0.4rem; line-height: 1.35; }
      .insight-card .ic-body { font-size: 0.92rem; color: #cccccc; line-height: 1.55; }
      .insight-card.shift { border-left-color: #06A77D; }
      .insight-card.recurring { border-left-color: #F4A261; }
      .insight-card.blindspot { border-left-color: #E76F51; }
      .insight-card.question { border-left-color: #FFD60A; }
      .insight-card.shape { border-left-color: #9D4EDD; }
      .insight-card.tension { border-left-color: #E63946; }
      .insight-card.load { border-left-color: #2A9D8F; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _scope_to_sid(scope_label: str):
    return None if scope_label == "All sessions" else scope_label.split(" (")[0]


def _html_escape(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _init_state():
    if "mirror" not in st.session_state:
        with st.spinner("Loading your map..."):
            st.session_state.mirror = MindMirrorEngine()
            st.session_state.greeting = st.session_state.mirror.generate_greeting()
            st.session_state.stats = st.session_state.mirror.get_snapshot_stats()
    st.session_state.setdefault("view_scope", "All sessions")
    # exchanges: list of {input, response, type, followups, extraction, contradictions, persisted}
    st.session_state.setdefault("exchanges", [])
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
st.markdown(f"<div class='greeting'>{_html_escape(st.session_state.greeting)}</div>", unsafe_allow_html=True)

stats = st.session_state.stats
recurring_str = ""
if stats["top_recurring"]:
    recurring_str = " · returning to: " + ", ".join(
        f"<span style='color:{CLASS_COLORS.get(r['class'], '#888')}'>{_html_escape(r['label'])}</span>"
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


# ============================================================ EXCHANGES
def _render_exchange(ex):
    # User bubble
    st.markdown("<div class='you-meta'>You</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='you-bubble'>{_html_escape(ex['input'])}</div>", unsafe_allow_html=True)

    # Mirror bubble
    st.markdown("<div class='mirror-meta'>Mirror</div>", unsafe_allow_html=True)
    body_parts = [f"<div class='mirror-bubble'>{_html_escape(ex.get('response', ''))}"]

    if ex.get("contradictions"):
        for c in ex["contradictions"]:
            body_parts.append(
                f"<div class='tension-banner'>⚠ <strong>Tension:</strong> "
                f"{_html_escape(c.get('explanation', ''))}</div>"
            )

    if ex.get("followups"):
        pills = " ".join(
            f"<span class='followup-pill'>{_html_escape(q)}</span>"
            for q in ex["followups"]
        )
        body_parts.append(f"<div style='margin-top:0.7rem'>{pills}</div>")

    nodes = ex.get("extraction", {}).get("nodes", [])
    if nodes:
        chip_spans = "".join(
            f"<span class='chip' style='color:{CLASS_COLORS.get(n.get('class'), '#888')}'>"
            f"{_html_escape(n.get('label', n.get('id', '')))}</span>"
            for n in nodes
        )
        body_parts.append(
            f"<div class='chip-strip' style='margin-top:0.7rem'>"
            f"<span style='font-size:0.68rem; color:#888; text-transform:uppercase; letter-spacing:0.05em; margin-right:0.5rem;'>mapped</span>"
            f"{chip_spans}</div>"
        )

    body_parts.append("</div>")
    st.markdown("".join(body_parts), unsafe_allow_html=True)


# Show recent exchanges (newest at bottom — natural reading flow)
exchanges = st.session_state.exchanges
RECENT = 5
recent = exchanges[-RECENT:]
older = exchanges[:-RECENT]

if older:
    with st.expander(f"Earlier this visit ({len(older)})"):
        for ex in older:
            _render_exchange(ex)

for ex in recent:
    _render_exchange(ex)


# ============================================================ INPUT
st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

with st.form("intake_form", clear_on_submit=True):
    thought_input = st.text_area(
        " ",
        placeholder="Ask anything. Share anything. The mirror listens.",
        height=120,
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button(
        "Send",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.ingesting,
    )

if submitted:
    if len(thought_input.strip()) < 3:
        st.warning("Say a little more.")
    else:
        st.session_state.ingesting = True
        with st.spinner("Mirror is thinking..."):
            # Pass last 4 exchanges as context for continuity
            recent_history = [
                {"you": e["input"], "mirror": e.get("response", "")}
                for e in exchanges[-4:]
            ]
            result = mirror.respond(thought_input, recent_history=recent_history)
            st.session_state.exchanges.append({
                "input": thought_input,
                "response": result.get("response", ""),
                "type": result.get("type", "cognitive"),
                "followups": result.get("followups", []),
                "extraction": result.get("extraction", {}),
                "contradictions": result.get("contradictions", []),
                "persisted": result.get("persisted", False),
                "error": result.get("error"),
            })
        st.session_state.ingesting = False
        if result.get("type") == "cognitive" and result.get("persisted"):
            _refresh_stats()
        st.rerun()

# Show error from latest exchange if any
if exchanges and exchanges[-1].get("error"):
    st.error(exchanges[-1]["error"])


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
        f"<div class='ic-headline'>{_html_escape(headline)}</div>"
        f"<div class='ic-body'>{_html_escape(body)}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _unwrap(obj):
    if isinstance(obj, dict):
        return obj.get("headline", "—"), obj.get("body", "—")
    if isinstance(obj, str):
        return obj, ""
    return "—", ""


def _render_answer_box(question, key_suffix):
    """Inline answer box that feeds the question + answer back through respond()."""
    with st.form(f"answer_form_{key_suffix}", clear_on_submit=True):
        ans = st.text_area(
            "Answer",
            placeholder="Reply to this question…",
            height=90,
            label_visibility="collapsed",
            key=f"ans_{key_suffix}",
        )
        if st.form_submit_button("Answer", use_container_width=False):
            if len(ans.strip()) < 3:
                st.warning("Say a little more.")
            else:
                framed = f"(answering your question: \"{question}\")\n\n{ans}"
                with st.spinner("Mirror is thinking..."):
                    recent_history = [
                        {"you": e["input"], "mirror": e.get("response", "")}
                        for e in st.session_state.exchanges[-4:]
                    ]
                    result = mirror.respond(framed, recent_history=recent_history)
                    st.session_state.exchanges.append({
                        "input": ans,
                        "response": result.get("response", ""),
                        "type": result.get("type", "cognitive"),
                        "followups": result.get("followups", []),
                        "extraction": result.get("extraction", {}),
                        "contradictions": result.get("contradictions", []),
                        "persisted": result.get("persisted", False),
                        "error": result.get("error"),
                    })
                # Clear the report so the answer becomes the new focus
                st.session_state.delta_report = None
                st.session_state.full_report = None
                _refresh_stats()
                st.rerun()


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
            _render_answer_box(rep["question"], "delta")

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
            _render_answer_box(rep["question"], "full")


# ============================================================ MAP
st.markdown("---")
st.markdown(
    f"### 🗺 Your map  <span style='font-size:0.85rem; color:#888; font-weight:normal'>· {stats['total_nodes']} nodes · scope: {st.session_state.view_scope}</span>",
    unsafe_allow_html=True,
)
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
            st.info("Your map is empty. Send a thought above and watch it grow.")
        else:
            st.warning(
                f"Map has {stats['total_nodes']} nodes but none match the current scope. "
                f"Switch to **All sessions** in the sidebar."
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
        st.session_state.exchanges = []
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
                st.session_state.exchanges = []
                st.session_state.greeting = mirror.generate_greeting()
                _refresh_stats()
                st.rerun()
        with c2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_nuke = False
                st.rerun()

    st.markdown("---")
    st.caption("Mind Mirror v3.0")

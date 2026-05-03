import os
import sys
from datetime import datetime, timezone
from neo4j import GraphDatabase


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _display(label_or_id):
    """Convert snake_case ids into readable text when no label exists."""
    if not label_or_id:
        return ""
    s = str(label_or_id)
    # heuristic: only treat as snake_case if no spaces
    if " " not in s and "_" in s:
        return s.replace("_", " ")
    return s

NODE_CLASSES = {
    "CORE_BELIEF", "VALUE", "TRIGGER", "COGNITIVE_PROCESS",
    "AFFECT", "BEHAVIOR", "INTENT", "PATTERN",
}

PREDICATES = {
    "INFLUENCES", "REINFORCES", "CONTRADICTS", "TRIGGERS",
    "CAUSES_AVOIDANCE_OF", "PRECEDES", "RESOLVES", "STRUCTURALLY_MATCHES",
}


class MindMirrorDB:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        if not password:
            print("❌ NEO4J_PASSWORD not set in environment / .env")
            sys.exit(1)
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
        except Exception as e:
            print(f"❌ Neo4j Connection Error: {e}")
            sys.exit(1)

    def _session(self):
        return self.driver.session(database=self.database)

    def close(self):
        self.driver.close()

    def write_graph(self, nodes, relationships, session_id, source_text=None):
        """Persist a parsed extraction. Returns (success, message, written_node_ids)."""
        valid_nodes = [n for n in nodes if n.get("class") in NODE_CLASSES and n.get("id")]
        valid_rels = [
            r for r in relationships
            if r.get("type") in PREDICATES and r.get("from") and r.get("to")
        ]
        now = _now_iso()
        written_ids = []

        try:
            with self._session() as session:
                for n in valid_nodes:
                    session.execute_write(
                        lambda tx, node=n: tx.run(
                            f"MERGE (x:{node['class']} {{id: $id}}) "
                            f"ON CREATE SET x.created_at = $now, x.first_session = $session_id "
                            f"SET x.label = $label, x.session_id = $session_id, "
                            f"x.last_seen_at = $now, "
                            f"x.times_seen = coalesce(x.times_seen, 0) + 1",
                            id=node["id"],
                            label=node.get("label", node["id"]),
                            session_id=session_id,
                            now=now,
                        )
                    )
                    written_ids.append(n["id"])
                for r in valid_rels:
                    session.execute_write(
                        lambda tx, rel=r: tx.run(
                            f"MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) "
                            f"MERGE (a)-[rel:{rel['type']}]->(b) "
                            f"ON CREATE SET rel.created_at = $now, rel.session_id = $session_id "
                            f"SET rel.last_seen_at = $now",
                            from_id=rel["from"],
                            to_id=rel["to"],
                            now=now,
                            session_id=session_id,
                        )
                    )
                # Persist the raw thought as a Thought node linked to extracted nodes
                if source_text:
                    session.execute_write(
                        lambda tx: tx.run(
                            "CREATE (t:Thought {text: $text, created_at: $now, session_id: $session_id, id: $tid})",
                            text=source_text,
                            now=now,
                            session_id=session_id,
                            tid=f"thought_{now}",
                        )
                    )
                    for nid in written_ids:
                        session.execute_write(
                            lambda tx, target_id=nid: tx.run(
                                "MATCH (t:Thought {created_at: $now}), (x {id: $nid}) "
                                "MERGE (t)-[:EXTRACTED]->(x)",
                                now=now, nid=target_id,
                            )
                        )

            return True, f"Wrote {len(valid_nodes)} nodes, {len(valid_rels)} relationships.", written_ids
        except Exception as e:
            return False, str(e), []

    def get_recent_changes(self, days=7):
        """Return nodes + edges created in the last N days. Labels humanized."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        nodes_q = (
            "MATCH (n) WHERE n.created_at >= $cutoff AND NOT n:Thought "
            "RETURN n.id AS id, n.label AS label, labels(n)[0] AS class, n.created_at AS created_at "
            "ORDER BY n.created_at DESC LIMIT 100"
        )
        rels_q = (
            "MATCH (a)-[r]->(b) WHERE r.created_at >= $cutoff AND NOT a:Thought AND NOT b:Thought "
            "RETURN a.id AS source, type(r) AS rel, b.id AS target, r.created_at AS created_at "
            "ORDER BY r.created_at DESC LIMIT 200"
        )
        with self._session() as session:
            try:
                new_nodes = []
                for r in session.run(nodes_q, cutoff=cutoff):
                    d = dict(r)
                    d["label"] = _display(d.get("label") or d.get("id"))
                    new_nodes.append(d)
                new_rels = []
                for r in session.run(rels_q, cutoff=cutoff):
                    d = dict(r)
                    d["source"] = _display(d.get("source"))
                    d["target"] = _display(d.get("target"))
                    d["rel"] = d["rel"].lower().replace("_", " ")
                    new_rels.append(d)
                return new_nodes, new_rels
            except Exception as e:
                print(f"❌ Recent changes error: {e}")
                return [], []

    def get_recurring_nodes(self, min_times_seen=2, limit=10):
        """Nodes that have appeared in multiple ingestions — likely cognitive load-bearers."""
        q = (
            "MATCH (n) WHERE n.times_seen >= $mts AND NOT n:Thought "
            "RETURN n.id AS id, n.label AS label, labels(n)[0] AS class, "
            "n.times_seen AS times_seen, n.last_seen_at AS last_seen_at "
            "ORDER BY n.times_seen DESC LIMIT $limit"
        )
        with self._session() as session:
            try:
                rows = []
                for r in session.run(q, mts=min_times_seen, limit=limit):
                    d = dict(r)
                    d["label"] = _display(d.get("label") or d.get("id"))
                    rows.append(d)
                return rows
            except Exception as e:
                print(f"❌ Recurring nodes error: {e}")
                return []

    def get_neighbors(self, node_ids, depth=1):
        """For contradiction detection: get the 1-hop graph neighborhood of these nodes."""
        if not node_ids:
            return []
        q = (
            "MATCH (n)-[r]-(m) WHERE n.id IN $ids AND NOT n:Thought AND NOT m:Thought "
            "RETURN n.id AS source, n.label AS source_label, labels(n)[0] AS source_class, "
            "type(r) AS rel, m.id AS target, m.label AS target_label, labels(m)[0] AS target_class "
            "LIMIT 200"
        )
        with self._session() as session:
            try:
                return [dict(r) for r in session.run(q, ids=node_ids)]
            except Exception as e:
                print(f"❌ Neighbors fetch error: {e}")
                return []

    def get_full_graph(self, session_id=None):
        """Return current topology as a text map for the auditor."""
        if session_id is None:
            query = "MATCH (n)-[r]->(m) RETURN n, type(r) AS rel_type, m LIMIT 200"
            params = {}
        elif session_id == "legacy":
            query = (
                "MATCH (n)-[r]->(m) WHERE n.session_id IS NULL AND m.session_id IS NULL "
                "RETURN n, type(r) AS rel_type, m LIMIT 200"
            )
            params = {}
        else:
            query = (
                "MATCH (n)-[r]->(m) WHERE n.session_id = $sid AND m.session_id = $sid "
                "RETURN n, type(r) AS rel_type, m LIMIT 200"
            )
            params = {"sid": session_id}
        with self._session() as session:
            try:
                result = session.run(query, **params)
                triplets = set()
                for record in result:
                    a = _display(record["n"].get("label") or record["n"].get("id"))
                    b = _display(record["m"].get("label") or record["m"].get("id"))
                    rel = record["rel_type"].lower().replace("_", " ")
                    triplets.add(f"[{a}] --{rel}--> [{b}]")
                return "\n".join(sorted(triplets))
            except Exception as e:
                print(f"❌ Retrieval Error: {e}")
                return ""

    def list_sessions(self):
        """Return list of (session_id, node_count) tuples, newest first.
        Nodes without session_id are bucketed as 'legacy'."""
        query = """
        MATCH (n) WHERE NOT n:Thought
        WITH coalesce(n.session_id, 'legacy') AS sid, count(n) AS cnt
        RETURN sid, cnt
        ORDER BY sid DESC
        """
        with self._session() as session:
            try:
                return [(r["sid"], r["cnt"]) for r in session.run(query)]
            except Exception as e:
                print(f"❌ Session list error: {e}")
                return []

    def get_graph_data(self, session_id=None):
        """Return (nodes, edges) as lists of dicts for visualization.
        If session_id is given, filter to that session ('legacy' = nodes without session_id)."""
        # Exclude Thought nodes (raw input archive) from the cognitive graph view
        if session_id is None:
            nodes_query = "MATCH (n) WHERE NOT n:Thought RETURN n, labels(n) AS labels"
            edges_query = (
                "MATCH (a)-[r]->(b) WHERE NOT a:Thought AND NOT b:Thought "
                "RETURN a.id AS source, type(r) AS rel, b.id AS target"
            )
            params = {}
        elif session_id == "legacy":
            nodes_query = "MATCH (n) WHERE n.session_id IS NULL AND NOT n:Thought RETURN n, labels(n) AS labels"
            edges_query = (
                "MATCH (a)-[r]->(b) WHERE a.session_id IS NULL AND b.session_id IS NULL "
                "AND NOT a:Thought AND NOT b:Thought "
                "RETURN a.id AS source, type(r) AS rel, b.id AS target"
            )
            params = {}
        else:
            nodes_query = "MATCH (n) WHERE n.session_id = $sid AND NOT n:Thought RETURN n, labels(n) AS labels"
            edges_query = (
                "MATCH (a)-[r]->(b) WHERE a.session_id = $sid AND b.session_id = $sid "
                "AND NOT a:Thought AND NOT b:Thought "
                "RETURN a.id AS source, type(r) AS rel, b.id AS target"
            )
            params = {"sid": session_id}
        nodes, edges = [], []
        with self._session() as session:
            try:
                for record in session.run(nodes_query, **params):
                    n = record["n"]
                    node_class = record["labels"][0] if record["labels"] else "UNKNOWN"
                    nid = n.get("id")
                    if not nid:
                        continue
                    nodes.append({
                        "id": nid,
                        "label": n.get("label") or nid,
                        "class": node_class,
                    })
                for record in session.run(edges_query, **params):
                    if record["source"] and record["target"]:
                        edges.append({
                            "source": record["source"],
                            "target": record["target"],
                            "rel": record["rel"],
                        })
            except Exception as e:
                print(f"❌ Graph fetch error: {e}")
        return nodes, edges

    def get_sample_nodes(self, limit=12):
        """Sample recent-ish nodes for greeting context, regardless of timestamps."""
        q = (
            "MATCH (n) WHERE NOT n:Thought "
            "RETURN n.id AS id, n.label AS label, labels(n)[0] AS class, "
            "coalesce(n.last_seen_at, n.created_at, '') AS seen_at "
            "ORDER BY seen_at DESC LIMIT $limit"
        )
        with self._session() as session:
            try:
                rows = []
                for r in session.run(q, limit=limit):
                    d = dict(r)
                    d["label"] = _display(d.get("label") or d.get("id"))
                    rows.append(d)
                return rows
            except Exception as e:
                print(f"❌ Sample nodes error: {e}")
                return []

    def get_node_details(self, node_id):
        """Return rich detail for one node: properties, source thoughts, neighbors."""
        node_q = (
            "MATCH (n {id: $nid}) WHERE NOT n:Thought "
            "RETURN n, labels(n)[0] AS class"
        )
        thoughts_q = (
            "MATCH (t:Thought)-[:EXTRACTED]->(n {id: $nid}) "
            "RETURN t.text AS text, t.created_at AS created_at, t.session_id AS session_id "
            "ORDER BY t.created_at DESC LIMIT 10"
        )
        neighbors_q = (
            "MATCH (n {id: $nid})-[r]-(m) WHERE NOT m:Thought "
            "RETURN type(r) AS rel, m.id AS id, m.label AS label, labels(m)[0] AS class, "
            "startNode(r).id = $nid AS outgoing "
            "LIMIT 50"
        )
        with self._session() as session:
            try:
                node_rec = session.run(node_q, nid=node_id).single()
                if not node_rec:
                    return None
                n = node_rec["n"]
                details = {
                    "id": n.get("id"),
                    "label": n.get("label"),
                    "class": node_rec["class"],
                    "created_at": n.get("created_at"),
                    "last_seen_at": n.get("last_seen_at"),
                    "times_seen": n.get("times_seen", 1),
                    "session_id": n.get("session_id"),
                    "thoughts": [dict(r) for r in session.run(thoughts_q, nid=node_id)],
                    "neighbors": [dict(r) for r in session.run(neighbors_q, nid=node_id)],
                }
                return details
            except Exception as e:
                print(f"❌ Node detail error: {e}")
                return None

    def reset(self):
        with self._session() as session:
            session.execute_write(lambda tx: tx.run("MATCH (n) DETACH DELETE n"))

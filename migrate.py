"""One-shot migration: copy all nodes + relationships from local Neo4j Desktop -> AuraDB.

Usage:
    python3 migrate.py

Reads SOURCE creds from constants below, TARGET creds from .env.
Safe to re-run: uses MERGE on element-id-key so duplicates are skipped.
"""
import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# --- SOURCE: your local Neo4j Desktop ---
SOURCE_URI = "bolt://localhost:7687"
SOURCE_USER = "neo4j"
SOURCE_PASSWORD = "Titanic@123"
SOURCE_DATABASE = "neo4j"

# --- TARGET: AuraDB (from .env) ---
TARGET_URI = os.getenv("NEO4J_URI")
TARGET_USER = os.getenv("NEO4J_USER")
TARGET_PASSWORD = os.getenv("NEO4J_PASSWORD")
TARGET_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def fetch_all(driver, database):
    """Pull every node and relationship from a database."""
    nodes, rels = [], []
    with driver.session(database=database) as s:
        for r in s.run("MATCH (n) RETURN n, labels(n) AS labels, elementId(n) AS eid"):
            n = r["n"]
            nodes.append({
                "eid": r["eid"],
                "labels": r["labels"],
                "props": dict(n),
            })
        for r in s.run(
            "MATCH (a)-[r]->(b) "
            "RETURN type(r) AS t, properties(r) AS props, "
            "elementId(a) AS a_eid, elementId(b) AS b_eid"
        ):
            rels.append({
                "type": r["t"],
                "props": r["props"],
                "a_eid": r["a_eid"],
                "b_eid": r["b_eid"],
            })
    return nodes, rels


def write_all(driver, database, nodes, rels):
    """Write nodes (MERGE on id if present, else create) + relationships into target.
    Returns a map from source elementId -> a stable key we can match on (id property)."""
    eid_to_key = {}

    with driver.session(database=database) as s:
        # 1. Nodes
        for n in nodes:
            labels = ":".join(n["labels"]) if n["labels"] else "Imported"
            props = n["props"]
            node_id = props.get("id")

            if node_id:
                # MERGE on id property
                s.execute_write(
                    lambda tx, l=labels, p=props, nid=node_id: tx.run(
                        f"MERGE (x:{l} {{id: $id}}) SET x += $props",
                        id=nid, props=p,
                    )
                )
                eid_to_key[n["eid"]] = ("id", node_id)
            else:
                # No id → create with synthetic id from elementId for re-matching
                synthetic = f"legacy_{n['eid'].replace(':', '_')}"
                props_with_id = {**props, "id": synthetic, "legacy_eid": n["eid"]}
                s.execute_write(
                    lambda tx, l=labels, p=props_with_id: tx.run(
                        f"MERGE (x:{l} {{id: $id}}) SET x += $props",
                        id=p["id"], props=p,
                    )
                )
                eid_to_key[n["eid"]] = ("id", synthetic)

        # 2. Relationships
        for r in rels:
            a_key = eid_to_key.get(r["a_eid"])
            b_key = eid_to_key.get(r["b_eid"])
            if not a_key or not b_key:
                continue
            s.execute_write(
                lambda tx, t=r["type"], p=r["props"], ak=a_key[1], bk=b_key[1]: tx.run(
                    f"MATCH (a {{id: $a_id}}), (b {{id: $b_id}}) "
                    f"MERGE (a)-[rel:{t}]->(b) "
                    f"SET rel += $props",
                    a_id=ak, b_id=bk, props=p,
                )
            )

    return len(nodes), len(rels)


def main():
    if not TARGET_URI or not TARGET_PASSWORD:
        print("❌ TARGET_URI / TARGET_PASSWORD not set in .env")
        sys.exit(1)

    print(f"📥 Source: {SOURCE_URI} (db={SOURCE_DATABASE})")
    print(f"📤 Target: {TARGET_URI} (db={TARGET_DATABASE})")

    src = GraphDatabase.driver(SOURCE_URI, auth=(SOURCE_USER, SOURCE_PASSWORD))
    try:
        src.verify_connectivity()
    except Exception as e:
        print(f"❌ Cannot reach source Neo4j Desktop: {e}")
        print("   → Make sure Neo4j Desktop is open and MindMirror DBMS is RUNNING.")
        sys.exit(1)

    tgt = GraphDatabase.driver(TARGET_URI, auth=(TARGET_USER, TARGET_PASSWORD))
    try:
        tgt.verify_connectivity()
    except Exception as e:
        print(f"❌ Cannot reach target AuraDB: {e}")
        sys.exit(1)

    print("\n🔍 Reading source...")
    nodes, rels = fetch_all(src, SOURCE_DATABASE)
    print(f"   Found {len(nodes)} nodes, {len(rels)} relationships.")

    if not nodes:
        print("Source is empty — nothing to migrate.")
        return

    print(f"\n📝 Writing to target...")
    n_count, r_count = write_all(tgt, TARGET_DATABASE, nodes, rels)
    print(f"   ✅ Migrated {n_count} nodes, {r_count} relationships.")

    src.close()
    tgt.close()
    print("\nDone. Refresh the Streamlit app to see your data in AuraDB.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Excel Brain (eb) — CSV가 지식의 원천인 타입 그래프 엔진.

마크다운 없음. 오직 3개의 CSV가 진실의 원천이다:
  - data/nodes.csv : 노드(타입 있는 지식 단위)  1행 = 1노드
  - data/edges.csv : 엣지(타입 있는 관계)       1행 = 1관계
  - data/meta.csv  : 스키마 문서(사람/에이전트용)

이 스크립트는 CSV를 SQLite(인메모리 또는 파일)로 로드해 그래프 연산을 수행한다.
서드파티 의존성 없음(파이썬 표준 라이브러리만). 그래프 탐색은 SQLite 재귀 CTE로 한다.

사용 예:
  python eb.py stats
  python eb.py node pillar-knowledge-graph
  python eb.py neighbors pillar-knowledge-graph --depth 2 --direction both
  python eb.py path decision-csv-source pillar-knowledge-graph
  python eb.py orphans
  python eb.py validate
  python eb.py types
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

NODES_FILE = "nodes.csv"
EDGES_FILE = "edges.csv"
META_FILE = "meta.csv"

NODE_COLS = [
    "id", "title", "type", "namespace", "visibility",
    "summary", "confidence", "tags", "body",
]
EDGE_COLS = ["source", "type", "target", "weight", "note"]


# --------------------------------------------------------------------------- #
# Load: 3 CSV -> SQLite ("csv를 db로")
# --------------------------------------------------------------------------- #
def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_db(data_dir: str = "data", db_path: str = ":memory:") -> sqlite3.Connection:
    """3개의 CSV를 SQLite로 적재하고 연결을 반환한다."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS nodes;
        DROP TABLE IF EXISTS edges;
        CREATE TABLE nodes(
            id TEXT PRIMARY KEY, title TEXT, type TEXT, namespace TEXT,
            visibility TEXT, summary TEXT, confidence REAL, tags TEXT, body TEXT
        );
        CREATE TABLE edges(
            source TEXT, type TEXT, target TEXT, weight REAL, note TEXT
        );
        """
    )

    base = Path(data_dir)
    for r in _read_csv(base / NODES_FILE):
        cur.execute(
            "INSERT OR REPLACE INTO nodes(id,title,type,namespace,visibility,"
            "summary,confidence,tags,body) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                (r.get("id") or "").strip(),
                r.get("title"), r.get("type"), r.get("namespace"),
                r.get("visibility"), r.get("summary"),
                _to_float(r.get("confidence")), r.get("tags"), r.get("body"),
            ),
        )
    for r in _read_csv(base / EDGES_FILE):
        cur.execute(
            "INSERT INTO edges(source,type,target,weight,note) VALUES(?,?,?,?,?)",
            (
                (r.get("source") or "").strip(), r.get("type"),
                (r.get("target") or "").strip(),
                _to_float(r.get("weight")), r.get("note"),
            ),
        )
    cur.execute("CREATE INDEX i_src ON edges(source)")
    cur.execute("CREATE INDEX i_tgt ON edges(target)")
    conn.commit()
    return conn


def _to_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Graph operations (SQLite 재귀 CTE)
# --------------------------------------------------------------------------- #
def _adjacency(direction: str) -> str:
    """방향에 따른 인접 관계 (a -> b)."""
    out = "SELECT source AS a, target AS b FROM edges"
    inn = "SELECT target AS a, source AS b FROM edges"
    if direction == "out":
        return out
    if direction == "in":
        return inn
    return f"{out} UNION {inn}"  # both


def neighbors(conn, node_id: str, depth: int = 1, direction: str = "both"):
    """node_id 에서 depth 홉 안에 도달 가능한 노드를 BFS(재귀 CTE)로 반환."""
    sql = f"""
    WITH RECURSIVE adj(a, b) AS ({_adjacency(direction)}),
    walk(id, dist) AS (
        SELECT ?, 0
        UNION
        SELECT adj.b, walk.dist + 1
        FROM adj JOIN walk ON adj.a = walk.id
        WHERE walk.dist < ?
    )
    SELECT id, MIN(dist) AS dist
    FROM walk
    WHERE id <> ?
    GROUP BY id
    ORDER BY dist, id
    """
    return conn.execute(sql, (node_id, depth, node_id)).fetchall()


def shortest_path(conn, src: str, dst: str, direction: str = "out"):
    """src -> dst 최단 경로(무가중 BFS). 노드 id 리스트 또는 None."""
    if src == dst:
        return [src]
    sql = f"""
    WITH RECURSIVE adj(a, b) AS ({_adjacency(direction)}),
    walk(id, path, depth) AS (
        SELECT ?, '>' || ? || '>', 0
        UNION ALL
        SELECT adj.b, walk.path || adj.b || '>', walk.depth + 1
        FROM adj JOIN walk ON adj.a = walk.id
        WHERE walk.depth < 64
          AND instr(walk.path, '>' || adj.b || '>') = 0
    )
    SELECT path, depth FROM walk WHERE id = ? ORDER BY depth LIMIT 1
    """
    row = conn.execute(sql, (src, src, dst)).fetchone()
    if not row:
        return None
    return [p for p in row["path"].split(">") if p]


def orphans(conn):
    """엣지가 하나도 없는 노드(고아)."""
    sql = """
    SELECT id FROM nodes
    WHERE id NOT IN (SELECT source FROM edges)
      AND id NOT IN (SELECT target FROM edges)
    ORDER BY id
    """
    return [r["id"] for r in conn.execute(sql).fetchall()]


def node_detail(conn, node_id: str):
    n = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    out_e = conn.execute(
        "SELECT type, target, weight, note FROM edges WHERE source = ? ORDER BY target",
        (node_id,),
    ).fetchall()
    in_e = conn.execute(
        "SELECT type, source, weight, note FROM edges WHERE target = ? ORDER BY source",
        (node_id,),
    ).fetchall()
    return n, out_e, in_e


def stats(conn):
    n = conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
    e = conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
    by_type = conn.execute(
        "SELECT type, COUNT(*) c FROM nodes GROUP BY type ORDER BY c DESC, type"
    ).fetchall()
    edge_type = conn.execute(
        "SELECT type, COUNT(*) c FROM edges GROUP BY type ORDER BY c DESC, type"
    ).fetchall()
    orph = orphans(conn)
    deg = (2 * e / n) if n else 0.0
    return {
        "nodes": n, "edges": e, "avg_degree": round(deg, 2),
        "orphans": len(orph), "by_node_type": by_type, "by_edge_type": edge_type,
    }


def validate(conn):
    """무결성 검사: 끊긴 엣지, 빈 필드 등."""
    issues = []
    dangling = conn.execute(
        """
        SELECT source, type, target FROM edges
        WHERE source NOT IN (SELECT id FROM nodes)
           OR target NOT IN (SELECT id FROM nodes)
        """
    ).fetchall()
    for d in dangling:
        issues.append(f"끊긴 엣지: {d['source']} -{d['type']}-> {d['target']} (없는 노드 참조)")
    no_type = conn.execute(
        "SELECT id FROM nodes WHERE type IS NULL OR type = ''"
    ).fetchall()
    for r in no_type:
        issues.append(f"type 누락: {r['id']}")
    no_title = conn.execute(
        "SELECT id FROM nodes WHERE title IS NULL OR title = ''"
    ).fetchall()
    for r in no_title:
        issues.append(f"title 누락: {r['id']}")
    return issues


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _print_node(n, out_e, in_e):
    if n is None:
        print("(노드 없음)")
        return
    print(f"# {n['title']}  [{n['id']}]")
    print(f"  type={n['type']}  namespace={n['namespace']}  "
          f"visibility={n['visibility']}  confidence={n['confidence']}")
    if n["tags"]:
        print(f"  tags: {n['tags']}")
    if n["summary"]:
        print(f"  summary: {n['summary']}")
    if n["body"]:
        print(f"  body: {n['body']}")
    print(f"  나가는 엣지({len(out_e)}):")
    for e in out_e:
        print(f"    -{e['type']}-> {e['target']}"
              + (f"  (w={e['weight']})" if e["weight"] is not None else "")
              + (f"  {e['note']}" if e["note"] else ""))
    print(f"  들어오는 엣지/백링크({len(in_e)}):")
    for e in in_e:
        print(f"    {e['source']} -{e['type']}->"
              + (f"  (w={e['weight']})" if e["weight"] is not None else "")
              + (f"  {e['note']}" if e["note"] else ""))


def main(argv=None):
    # Windows 콘솔(cp949)에서도 한국어/기호 출력이 깨지거나 죽지 않도록 UTF-8 고정
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(prog="eb", description="Excel Brain — CSV 그래프 엔진")
    p.add_argument("--data", default="data", help="CSV 디렉토리 (기본: data)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats", help="요약 통계")
    sub.add_parser("orphans", help="고아 노드 목록")
    sub.add_parser("validate", help="무결성 검사")
    sub.add_parser("types", help="노드/엣지 타입별 개수")

    sp = sub.add_parser("node", help="노드 상세 + 엣지/백링크")
    sp.add_argument("id")

    sp = sub.add_parser("neighbors", help="이웃 탐색(BFS, 재귀 CTE)")
    sp.add_argument("id")
    sp.add_argument("--depth", type=int, default=1)
    sp.add_argument("--direction", choices=["out", "in", "both"], default="both")

    sp = sub.add_parser("path", help="두 노드 간 최단 경로")
    sp.add_argument("src")
    sp.add_argument("dst")
    sp.add_argument("--direction", choices=["out", "in", "both"], default="out")

    args = p.parse_args(argv)
    conn = load_db(args.data)

    if args.cmd == "stats":
        s = stats(conn)
        print(f"노드: {s['nodes']}  엣지: {s['edges']}  "
              f"평균 차수: {s['avg_degree']}  고아: {s['orphans']}")
        print("노드 타입:")
        for r in s["by_node_type"]:
            print(f"  {r['type'] or '(없음)'}: {r['c']}")
        print("엣지 타입:")
        for r in s["by_edge_type"]:
            print(f"  {r['type'] or '(없음)'}: {r['c']}")

    elif args.cmd == "types":
        for label, rows in (("노드", stats(conn)["by_node_type"]),
                            ("엣지", stats(conn)["by_edge_type"])):
            print(f"[{label}]")
            for r in rows:
                print(f"  {r['type'] or '(없음)'}: {r['c']}")

    elif args.cmd == "orphans":
        o = orphans(conn)
        print("\n".join(o) if o else "(고아 노드 없음)")

    elif args.cmd == "validate":
        issues = validate(conn)
        if not issues:
            print("✓ 문제 없음")
        else:
            print(f"✗ {len(issues)}건:")
            for i in issues:
                print(f"  - {i}")
            return 1

    elif args.cmd == "node":
        _print_node(*node_detail(conn, args.id))

    elif args.cmd == "neighbors":
        rows = neighbors(conn, args.id, args.depth, args.direction)
        if not rows:
            print("(이웃 없음)")
        for r in rows:
            print(f"  [{r['dist']}] {r['id']}")

    elif args.cmd == "path":
        path = shortest_path(conn, args.src, args.dst, args.direction)
        if path is None:
            print("(경로 없음)")
            return 1
        print(" -> ".join(path) + f"   (홉 {len(path) - 1})")

    return 0


if __name__ == "__main__":
    sys.exit(main())

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
  python eb.py search 그래프
  python eb.py suggest pillar-knowledge-graph
  python eb.py export --format mermaid
  python eb.py node pillar-knowledge-graph
  python eb.py neighbors pillar-knowledge-graph --depth 2 --direction both
  python eb.py path decision-csv-source pillar-knowledge-graph
  python eb.py path decision-csv-source pillar-knowledge-graph --weighted
  python eb.py components
  python eb.py degree --top 5
  python eb.py orphans
  python eb.py validate
  python eb.py types
  python eb.py add-node --id playbook-x --title "엑스" --type playbook --tags "a;b"
  python eb.py add-edge --source playbook-x --type depends_on --target concept-typed-node
  python eb.py merge old-dup-id canonical-id
"""
from __future__ import annotations

import argparse
import csv
import heapq
import json
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

NAMESPACES_FILE = "namespaces.csv"
NAMESPACE_COLS = ["namespace", "default_visibility", "description"]
ALLOWED_VISIBILITY = ("public", "namespace", "private", "system")


# --------------------------------------------------------------------------- #
# Load: 3 CSV -> SQLite ("csv를 db로")
# --------------------------------------------------------------------------- #
def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def namespace_default_visibility(data_dir: str, namespace: str):
    """namespaces.csv 에 등록된 네임스페이스의 기본 visibility 를 돌려준다(없으면 None).

    네임스페이스별 디폴트 접근제어자 — add-node 가 --visibility 를 안 줬을 때 적용한다.
    """
    ns = (namespace or "").strip()
    if not ns:
        return None
    for r in _read_csv(Path(data_dir) / NAMESPACES_FILE):
        if (r.get("namespace") or "").strip() == ns:
            v = (r.get("default_visibility") or "").strip()
            return v or None
    return None


CACHE_FILE = ".eb-cache.sqlite"   # data_dir 안의 자동 캐시(.gitignore 대상)


def _has_tables(conn) -> bool:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('nodes','edges')"
    ).fetchall()
    return len(rows) == 2


def _source_sig(base: Path) -> str:
    """CSV 원천의 시그니처(크기 + 나노초 mtime). 내용이 바뀌면 달라진다."""
    parts = []
    for fn in (NODES_FILE, EDGES_FILE, META_FILE):
        f = base / fn
        if f.exists():
            st = f.stat()
            parts.append(f"{fn}:{st.st_size}:{st.st_mtime_ns}")
        else:
            parts.append(f"{fn}:-")
    return "|".join(parts)


def _stored_sig(conn) -> str:
    try:
        row = conn.execute("SELECT v FROM _eb_meta WHERE k='sig'").fetchone()
        return row["v"] if row else ""
    except sqlite3.Error:
        return ""


def _build_db(data_dir: str, db_path: str) -> sqlite3.Connection:
    """CSV 3개를 db_path(파일 또는 :memory:) SQLite로 적재한다."""
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
    cur.execute("CREATE INDEX i_etype ON edges(type)")
    cur.execute("CREATE INDEX i_ntype ON nodes(type)")
    conn.commit()
    return conn


def load_db(data_dir: str = "data") -> sqlite3.Connection:
    """CSV 3개를 SQLite로 올려 연결을 반환한다.

    캐시는 **자동**이다(사용자 설정 불필요): data_dir 안의 `.eb-cache.sqlite` 가
    있고 CSV 시그니처(크기+나노초 mtime)와 일치하면 그대로 재사용하고, 없거나
    CSV가 바뀌었으면 새로 만든다. CSV가 단일 원천이며 캐시는 파생물일 뿐이다.
    캐시 디렉토리가 읽기 전용이면 인메모리로 폴백한다(실패하지 않는다).
    """
    base = Path(data_dir)
    sig = _source_sig(base)
    cache = base / CACHE_FILE
    if cache.exists() and cache.stat().st_size > 0:
        try:
            conn = sqlite3.connect(str(cache))
            conn.row_factory = sqlite3.Row
            if _has_tables(conn) and _stored_sig(conn) == sig:
                return conn          # 캐시 적중
            conn.close()
        except sqlite3.Error:
            pass
    # 캐시 없음/오래됨/손상 → 재생성(쓰기 가능하면 파일, 아니면 인메모리)
    try:
        if cache.exists():
            cache.unlink()
        conn = _build_db(data_dir, str(cache))
        conn.execute("CREATE TABLE IF NOT EXISTS _eb_meta(k TEXT PRIMARY KEY, v TEXT)")
        conn.execute("INSERT OR REPLACE INTO _eb_meta(k,v) VALUES('sig',?)", (sig,))
        conn.commit()
        return conn
    except (sqlite3.Error, OSError):
        return _build_db(data_dir, ":memory:")


def _to_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Write: CSV 안전 추가 (add-node / add-edge)
# --------------------------------------------------------------------------- #
def _append_row(path: Path, cols: list[str], row: dict) -> None:
    """CSV에 1행 안전 추가. 파일이 없으면 헤더부터, 마지막 줄에 개행이 없으면 보강한다."""
    has_data = path.exists() and path.stat().st_size > 0
    need_nl = False
    if has_data:
        with path.open("rb") as f:
            f.seek(-1, 2)
            need_nl = f.read(1) != b"\n"
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        if not has_data:
            w.writeheader()
        elif need_nl:
            f.write("\n")
        w.writerow({c: row.get(c, "") for c in cols})


def add_node(data_dir: str, *, id: str, title: str, type: str = None,
             namespace: str = None, visibility: str = None, summary: str = None,
             confidence=None, tags: str = None, body: str = None) -> str:
    """nodes.csv 에 노드 1행을 추가한다. id 가 비었거나 이미 있으면 ValueError."""
    nid = (id or "").strip()
    if not nid:
        raise ValueError("id는 비어 있을 수 없습니다")
    path = Path(data_dir) / NODES_FILE
    existing = {(r.get("id") or "").strip() for r in _read_csv(path)}
    if nid in existing:
        raise ValueError(f"이미 존재하는 노드 id: {nid}")
    # visibility 미지정 시 네임스페이스 기본값(접근제어자)을 적용한다.
    vis = (visibility or "").strip()
    if not vis:
        vis = namespace_default_visibility(data_dir, namespace) or ""
    _append_row(path, NODE_COLS, {
        "id": nid, "title": title or "", "type": type or "",
        "namespace": namespace or "", "visibility": vis,
        "summary": summary or "",
        "confidence": "" if confidence is None else confidence,
        "tags": tags or "", "body": body or "",
    })
    return nid


def _write_all(path: Path, cols: list[str], rows: list[dict]) -> None:
    """CSV를 헤더부터 전체 재기록한다(병합 등 행 삭제/수정용)."""
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def add_namespace(data_dir: str, *, name: str, default_visibility: str = None,
                  description: str = None) -> str:
    """namespaces.csv 에 네임스페이스를 등록/갱신한다(멱등 upsert).

    default_visibility 는 그 네임스페이스에서 새 노드의 기본 접근제어자다 — add-node 가
    --visibility 를 생략하면 이 값이 적용된다. 잘못된 visibility 는 ValueError.
    """
    ns = (name or "").strip()
    if not ns:
        raise ValueError("namespace 이름은 비어 있을 수 없습니다")
    vis = (default_visibility or "").strip()
    if vis and vis not in ALLOWED_VISIBILITY:
        raise ValueError(
            f"default_visibility는 {'/'.join(ALLOWED_VISIBILITY)} 중 하나여야 합니다: {vis}")
    path = Path(data_dir) / NAMESPACES_FILE
    rows = _read_csv(path)
    for r in rows:
        if (r.get("namespace") or "").strip() == ns:
            if vis:
                r["default_visibility"] = vis
            if description is not None:
                r["description"] = description
            break
    else:
        rows.append({"namespace": ns, "default_visibility": vis,
                     "description": description or ""})
    _write_all(path, NAMESPACE_COLS, rows)
    return ns


def list_namespaces(data_dir: str) -> list[dict]:
    """등록된 네임스페이스 + 노드 수를 모은다(미등록이지만 노드가 쓰는 것도 포함)."""
    base = Path(data_dir)
    registered = {(r.get("namespace") or "").strip(): r
                  for r in _read_csv(base / NAMESPACES_FILE)
                  if (r.get("namespace") or "").strip()}
    counts: dict[str, int] = {}
    for n in _read_csv(base / NODES_FILE):
        ns = (n.get("namespace") or "").strip()
        if ns:
            counts[ns] = counts.get(ns, 0) + 1
    out = []
    for ns in sorted(set(registered) | set(counts)):
        reg = registered.get(ns)
        out.append({
            "namespace": ns,
            "default_visibility": (reg or {}).get("default_visibility", "") if reg else "",
            "description": (reg or {}).get("description", "") if reg else "",
            "nodes": counts.get(ns, 0),
            "registered": reg is not None,
        })
    return out


def merge(data_dir: str, from_id: str, into_id: str) -> dict:
    """from_id 의 모든 엣지를 into_id 로 재배선하고 from_id 노드를 삭제한다.

    같은 노드 병합·존재하지 않는 노드는 ValueError. 병합으로 생긴 자기 루프는 버린다.
    병합으로 생긴 평행 중복((source,type,target) 동일)도 제거한다(기존 멀티그래프
    중복은 보존 — 재배선으로 *생긴* 중복만 합친다).
    반환: {"into","repointed","dropped_selfloops","dropped_dups"}.
    """
    f = (from_id or "").strip()
    t = (into_id or "").strip()
    if not f or not t:
        raise ValueError("from_id와 into_id는 필수입니다")
    if f == t:
        raise ValueError("같은 노드는 병합할 수 없습니다")
    base = Path(data_dir)
    nodes = _read_csv(base / NODES_FILE)
    ids = {(r.get("id") or "").strip() for r in nodes}
    missing = [x for x in (f, t) if x not in ids]
    if missing:
        raise ValueError(f"없는 노드: {', '.join(missing)}")

    dropped = dups = repointed = 0
    # 1패스: 재배선 + 자기 루프 제거. 각 엣지를 (touched, key) 와 함께 보관.
    entries = []  # (행, key, touched)
    for e in _read_csv(base / EDGES_FILE):
        s = (e.get("source") or "").strip()
        tg = (e.get("target") or "").strip()
        touched = False
        if s == f:
            e["source"] = t; s = t; touched = True
        if tg == f:
            e["target"] = t; tg = t; touched = True
        if s == tg:  # 병합으로 생긴 자기 루프는 버린다
            dropped += 1
            continue
        entries.append((e, (s, (e.get("type") or "").strip(), tg), touched))
    # 2패스: 기존(untouched) 엣지는 모두 보존(멀티그래프). 재배선된 엣지는 기존/이미
    # 유지된 엣지와 키가 겹치면 합친다 — 병합으로 *생긴* 평행 중복만 제거(순서 무관).
    seen = {key for _, key, touched in entries if not touched}
    new_edges = []
    for e, key, touched in entries:
        if touched:
            if key in seen:
                dups += 1
                continue
            seen.add(key)
            repointed += 1
        new_edges.append(e)
    _write_all(base / EDGES_FILE, EDGE_COLS, new_edges)
    _write_all(base / NODES_FILE, NODE_COLS,
               [r for r in nodes if (r.get("id") or "").strip() != f])
    return {"into": t, "repointed": repointed,
            "dropped_selfloops": dropped, "dropped_dups": dups}


def add_edge(data_dir: str, *, source: str, type: str, target: str,
             weight=None, note: str = None, allow_missing: bool = False):
    """edges.csv 에 엣지 1행을 추가한다.

    source/target 노드가 nodes.csv 에 없으면 ValueError(allow_missing 이면 허용).
    """
    s = (source or "").strip()
    t = (target or "").strip()
    if not s or not t:
        raise ValueError("source와 target은 필수입니다")
    base = Path(data_dir)
    if not allow_missing:
        node_ids = {(r.get("id") or "").strip() for r in _read_csv(base / NODES_FILE)}
        missing = [x for x in (s, t) if x not in node_ids]
        if missing:
            raise ValueError(
                f"없는 노드 참조: {', '.join(missing)} (--allow-missing 으로 무시 가능)")
    _append_row(base / EDGES_FILE, EDGE_COLS, {
        "source": s, "type": type or "", "target": t,
        "weight": "" if weight is None else weight, "note": note or "",
    })
    return (s, type, t)


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


def _weighted_adjacency(conn, direction: str) -> dict:
    """방향별 가중 인접 리스트: {a: [(b, weight), ...]}."""
    adj: dict = {}
    for r in conn.execute("SELECT source, target, weight FROM edges").fetchall():
        s, t, w = r["source"], r["target"], r["weight"]
        if direction in ("out", "both"):
            adj.setdefault(s, []).append((t, w))
        if direction in ("in", "both"):
            adj.setdefault(t, []).append((s, w))
    return adj


def weighted_shortest_path(conn, src: str, dst: str, direction: str = "out",
                           default_weight: float = 1.0):
    """src -> dst 가중 최단 경로(다익스트라). weight 를 엣지 비용(거리)으로 사용한다.

    weight 가 None 이거나 양수가 아니면 default_weight 로 대체한다.
    반환: (경로 노드 id 리스트, 총비용) 또는 도달 불가 시 None.
    """
    if src == dst:
        return ([src], 0.0)
    adj = _weighted_adjacency(conn, direction)
    dist = {src: 0.0}
    prev: dict = {}
    pq = [(0.0, src)]
    visited = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u == dst:
            break
        for v, w in adj.get(u, []):
            cost = w if (w is not None and w > 0) else default_weight
            nd = d + cost
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    if dst not in dist:
        return None
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    path.reverse()
    return (path, dist[dst])


def orphans(conn):
    """엣지가 하나도 없는 노드(고아)."""
    sql = """
    SELECT id FROM nodes
    WHERE id NOT IN (SELECT source FROM edges)
      AND id NOT IN (SELECT target FROM edges)
    ORDER BY id
    """
    return [r["id"] for r in conn.execute(sql).fetchall()]


def components(conn):
    """약연결 요소(엣지를 무방향으로 간주). 각 요소는 정렬된 노드 id 리스트.

    크기 내림차순, 동률은 첫 id 사전순으로 정렬해 반환한다.
    없는 노드를 참조하는 끊긴 엣지는 무시한다.
    """
    node_ids = [r["id"] for r in conn.execute("SELECT id FROM nodes").fetchall()]
    parent = {nid: nid for nid in node_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # 경로 압축
            x = parent[x]
        return x

    for r in conn.execute("SELECT source, target FROM edges").fetchall():
        s, t = r["source"], r["target"]
        if s in parent and t in parent:
            ra, rb = find(s), find(t)
            if ra != rb:
                parent[rb] = ra

    groups: dict = {}
    for nid in node_ids:
        groups.setdefault(find(nid), []).append(nid)
    comps = [sorted(g) for g in groups.values()]
    comps.sort(key=lambda c: (-len(c), c[0]))
    return comps


def degree_distribution(conn):
    """노드별 in/out/total 차수 + 차수 히스토그램(차수 중심성 근거)."""
    deg = {r["id"]: {"in": 0, "out": 0}
           for r in conn.execute("SELECT id FROM nodes").fetchall()}
    for r in conn.execute("SELECT source, target FROM edges").fetchall():
        if r["source"] in deg:
            deg[r["source"]]["out"] += 1
        if r["target"] in deg:
            deg[r["target"]]["in"] += 1
    per_node = [
        {"id": nid, "in": d["in"], "out": d["out"], "total": d["in"] + d["out"]}
        for nid, d in deg.items()
    ]
    per_node.sort(key=lambda x: (-x["total"], x["id"]))
    hist: dict = {}
    for x in per_node:
        hist[x["total"]] = hist.get(x["total"], 0) + 1
    return {"per_node": per_node, "histogram": dict(sorted(hist.items()))}


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


SEARCH_FIELDS = ["title", "summary", "tags", "body"]


def search(conn, query: str, limit: int = 20):
    """title/summary/tags/body 에서 query 를 부분일치로 찾는다(대소문자 무시).

    일치한 필드 수를 score 로 랭크한다(많을수록 위, 동률은 id 사전순).
    반환: [{"id","title","type","score","fields":[...]}], 무매치면 [].
    """
    q = (query or "").strip()
    if not q:
        return []
    rows = conn.execute("SELECT id, title, type, summary, tags, body FROM nodes").fetchall()
    ql = q.lower()
    results = []
    for r in rows:
        hit = [f for f in SEARCH_FIELDS if r[f] and ql in r[f].lower()]
        if hit:
            results.append({
                "id": r["id"], "title": r["title"], "type": r["type"],
                "score": len(hit), "fields": hit,
            })
    results.sort(key=lambda x: (-x["score"], x["id"]))
    return results[:limit]


def _undirected_adj(conn) -> dict:
    """무방향 인접 집합: {id: {이웃 id, ...}}."""
    adj: dict = {}
    for r in conn.execute("SELECT source, target FROM edges").fetchall():
        s, t = r["source"], r["target"]
        adj.setdefault(s, set()).add(t)
        adj.setdefault(t, set()).add(s)
    return adj


def _tags_set(s) -> set:
    return {x.strip() for x in (s or "").split(";") if x.strip()}


def suggest(conn, node_id: str, limit: int = 10):
    """node_id 에 붙일 만한 연결 후보를 그래프 구조로 제안한다.

    점수 = 공통 이웃 수(무방향) + 태그 자카드 유사도.
    자기 자신과 이미 직접 연결된 노드는 제외하고, 점수>0 만 반환한다.
    반환: [{"id","title","score","common","jaccard"}], 후보 없으면 [].
    """
    nodes = {r["id"]: r for r in
             conn.execute("SELECT id, title, tags FROM nodes").fetchall()}
    if node_id not in nodes:
        return []
    adj = _undirected_adj(conn)
    my_nbrs = adj.get(node_id, set())
    my_tags = _tags_set(nodes[node_id]["tags"])
    exclude = set(my_nbrs) | {node_id}
    out = []
    for cid, r in nodes.items():
        if cid in exclude:
            continue
        common = len(my_nbrs & adj.get(cid, set()))
        ctags = _tags_set(r["tags"])
        union = my_tags | ctags
        jac = (len(my_tags & ctags) / len(union)) if union else 0.0
        score = common + jac
        if score > 0:
            out.append({
                "id": cid, "title": r["title"], "score": round(score, 4),
                "common": common, "jaccard": round(jac, 4),
            })
    out.sort(key=lambda x: (-x["score"], x["id"]))
    return out[:limit]


def _dangling_edges(conn):
    return conn.execute(
        """
        SELECT source, type, target FROM edges
        WHERE source NOT IN (SELECT id FROM nodes)
           OR target NOT IN (SELECT id FROM nodes)
        """
    ).fetchall()


def review_queue(conn, confidence_threshold: float = 0.6) -> dict:
    """그래프가 '약한 곳'을 스스로 드러내는 점검 대기열.

    - low_confidence: confidence 가 없거나(검토 필요) 임계값 미만인 노드
                      (불확실한 것 먼저: None → 낮은 값 순)
    - orphans:        엣지 없는 고아 노드
    - dangling:       없는 노드를 참조하는 끊긴 엣지
    - missing_fields: type/title 이 빈 노드
    """
    low = []
    for r in conn.execute("SELECT id, title, confidence FROM nodes").fetchall():
        c = r["confidence"]
        if c is None or c < confidence_threshold:
            low.append({"id": r["id"], "title": r["title"], "confidence": c})
    low.sort(key=lambda x: (x["confidence"] is not None,
                            x["confidence"] if x["confidence"] is not None else 0.0,
                            x["id"]))
    dangling = [f"{d['source']} -{d['type']}-> {d['target']}"
                for d in _dangling_edges(conn)]
    missing = [r["id"] for r in conn.execute(
        "SELECT id FROM nodes WHERE type IS NULL OR type='' "
        "OR title IS NULL OR title=''").fetchall()]
    return {"low_confidence": low, "orphans": orphans(conn),
            "dangling": dangling, "missing_fields": missing}


def _node_ids(conn) -> set:
    return {r["id"] for r in conn.execute("SELECT id FROM nodes").fetchall()}


def subgraph_ids(conn, center: str, depth: int = 1, direction: str = "both") -> set:
    """center 와 depth 홉 이내 이웃의 id 집합(대규모 그래프의 스코프 뷰용)."""
    ids = {center}
    for r in neighbors(conn, center, depth=depth, direction=direction):
        ids.add(r["id"])
    return ids


def _view_nodes(conn, only):
    rows = conn.execute("SELECT id, title, type, namespace, visibility, "
                        "confidence, tags FROM nodes ORDER BY id").fetchall()
    return [r for r in rows if only is None or r["id"] in only]


def _valid_edges(conn, only=None):
    """양 끝이 모두 노드인 엣지만(끊긴 엣지 제외). only 가 있으면 그 안의 엣지만 — 뷰 export 용."""
    ids = _node_ids(conn)
    rows = conn.execute(
        "SELECT source, type, target, weight FROM edges ORDER BY source, target"
    ).fetchall()
    out = [r for r in rows if r["source"] in ids and r["target"] in ids]
    if only is not None:
        out = [r for r in out if r["source"] in only and r["target"] in only]
    return out


def _mermaid_id(s: str) -> str:
    """mermaid 노드 id로 안전화(영숫자·밑줄만)."""
    return "".join(c if (c.isalnum() or c == "_") else "_" for c in s) or "n"


def _xml_escape(s) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def export_mermaid(conn, direction: str = "LR", only=None) -> str:
    """그래프를 Mermaid flowchart 텍스트로. (깃허브 마크다운에 바로 렌더, 소규모/스코프용)"""
    lines = [f"graph {direction}"]
    for n in _view_nodes(conn, only):
        label = (n["title"] or n["id"]).replace('"', "'")
        lines.append(f'  {_mermaid_id(n["id"])}["{label}"]')
    for e in _valid_edges(conn, only):
        lines.append(
            f'  {_mermaid_id(e["source"])} -->|{e["type"] or ""}| {_mermaid_id(e["target"])}')
    return "\n".join(lines)


def export_dot(conn, only=None) -> str:
    """그래프를 Graphviz DOT 텍스트로. (dot/sfdp 로 렌더, 대형은 sfdp)"""
    lines = ["digraph eb {", "  rankdir=LR;"]
    for n in _view_nodes(conn, only):
        label = (n["title"] or n["id"]).replace('"', "'")
        lines.append(f'  "{n["id"]}" [label="{label}"];')
    for e in _valid_edges(conn, only):
        lines.append(f'  "{e["source"]}" -> "{e["target"]}" [label="{e["type"] or ""}"];')
    lines.append("}")
    return "\n".join(lines)


def export_json(conn, only=None) -> dict:
    """그래프를 {nodes:[...], edges:[...]} 로. (d3/cytoscape.js/sigma.js)"""
    nodes = [dict(r) for r in _view_nodes(conn, only)]
    edges = [{"source": e["source"], "type": e["type"],
              "target": e["target"], "weight": e["weight"]}
             for e in _valid_edges(conn, only)]
    return {"nodes": nodes, "edges": edges}


def export_graphml(conn, only=None) -> str:
    """그래프를 GraphML(XML)로. (Gephi 등 전문 대규모 그래프 분석 도구용)"""
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
         '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
         '  <key id="ntype" for="node" attr.name="type" attr.type="string"/>',
         '  <key id="etype" for="edge" attr.name="type" attr.type="string"/>',
         '  <key id="weight" for="edge" attr.name="weight" attr.type="double"/>',
         '  <graph edgedefault="directed">']
    for n in _view_nodes(conn, only):
        L.append(f'    <node id="{_xml_escape(n["id"])}">'
                 f'<data key="label">{_xml_escape(n["title"] or n["id"])}</data>'
                 f'<data key="ntype">{_xml_escape(n["type"])}</data></node>')
    for e in _valid_edges(conn, only):
        w = e["weight"] if e["weight"] is not None else ""
        L.append(f'    <edge source="{_xml_escape(e["source"])}" '
                 f'target="{_xml_escape(e["target"])}">'
                 f'<data key="etype">{_xml_escape(e["type"])}</data>'
                 f'<data key="weight">{w}</data></edge>')
    L += ["  </graph>", "</graphml>"]
    return "\n".join(L)


def validate(conn):
    """무결성 검사: 끊긴 엣지, 빈 필드 등."""
    issues = []
    for d in _dangling_edges(conn):
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
    sub.add_parser("components", help="약연결 요소(무방향)")

    sp = sub.add_parser("health", help="건강도 점검 + 리뷰 큐(저신뢰/고아/끊긴 엣지)")
    sp.add_argument("--confidence", type=float, default=0.6,
                    help="이 값 미만(또는 없음)인 노드를 리뷰 큐에 (기본 0.6)")

    sp = sub.add_parser("search", help="노드 검색(title/summary/tags/body 부분일치)")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=20)

    sp = sub.add_parser("export", help="그래프를 다른 뷰로 추출(mermaid/dot/json/graphml)")
    sp.add_argument("--format", choices=["mermaid", "dot", "json", "graphml"],
                    default="mermaid")
    sp.add_argument("--direction", default="LR", help="mermaid 방향(LR/TB 등)")
    sp.add_argument("--center", help="이 노드 중심의 서브그래프만(대규모 스코프 뷰)")
    sp.add_argument("--depth", type=int, default=1, help="--center 이웃 깊이(기본 1)")

    sp = sub.add_parser("suggest", help="연결 후보 제안(공통 이웃 + 태그 자카드)")
    sp.add_argument("id")
    sp.add_argument("--limit", type=int, default=10)

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
    sp.add_argument("--weighted", action="store_true",
                    help="weight를 비용으로 한 가중 최단경로(다익스트라)")
    sp.add_argument("--default-weight", type=float, default=1.0,
                    help="weight 누락 시 사용할 기본 비용(기본 1.0)")

    sp = sub.add_parser("degree", help="차수 분포 / 차수 중심성")
    sp.add_argument("--top", type=int, default=10)

    sp = sub.add_parser("add-node", help="nodes.csv에 노드 추가(중복 id 검사)")
    sp.add_argument("--id", required=True)
    sp.add_argument("--title", required=True)
    sp.add_argument("--type")
    sp.add_argument("--namespace")
    sp.add_argument("--visibility")
    sp.add_argument("--summary")
    sp.add_argument("--confidence", type=float)
    sp.add_argument("--tags", help="세미콜론(;) 구분")
    sp.add_argument("--body")

    sp = sub.add_parser("add-namespace",
                        help="namespaces.csv에 네임스페이스 등록/갱신(기본 visibility 설정)")
    sp.add_argument("--name", required=True)
    sp.add_argument("--default-visibility", dest="default_visibility",
                    help="/".join(ALLOWED_VISIBILITY) + " 중 하나")
    sp.add_argument("--description")

    sub.add_parser("namespaces", help="등록된 네임스페이스 + 노드 수 목록")

    sp = sub.add_parser("merge", help="중복 노드 병합(from의 엣지를 into로 재배선 후 삭제)")
    sp.add_argument("from_id")
    sp.add_argument("into_id")

    sp = sub.add_parser("add-edge", help="edges.csv에 엣지 추가(노드 존재 검사)")
    sp.add_argument("--source", required=True)
    sp.add_argument("--type", required=True)
    sp.add_argument("--target", required=True)
    sp.add_argument("--weight", type=float)
    sp.add_argument("--note")
    sp.add_argument("--allow-missing", action="store_true",
                    help="source/target 노드가 없어도 추가 허용")

    args = p.parse_args(argv)

    # 쓰기 명령은 CSV를 직접 다루므로 DB 적재가 필요 없다.
    if args.cmd == "add-node":
        try:
            nid = add_node(
                args.data, id=args.id, title=args.title, type=args.type,
                namespace=args.namespace, visibility=args.visibility,
                summary=args.summary, confidence=args.confidence,
                tags=args.tags, body=args.body)
        except ValueError as ex:
            print(f"✗ {ex}")
            return 1
        print(f"✓ 노드 추가: {nid}")
        return 0

    if args.cmd == "add-edge":
        try:
            s, ty, t = add_edge(
                args.data, source=args.source, type=args.type, target=args.target,
                weight=args.weight, note=args.note, allow_missing=args.allow_missing)
        except ValueError as ex:
            print(f"✗ {ex}")
            return 1
        print(f"✓ 엣지 추가: {s} -{ty}-> {t}")
        return 0

    if args.cmd == "merge":
        try:
            r = merge(args.data, args.from_id, args.into_id)
        except ValueError as ex:
            print(f"✗ {ex}")
            return 1
        print(f"✓ 병합: {args.from_id} -> {r['into']} "
              f"(엣지 {r['repointed']}개 재배선, 자기 루프 {r['dropped_selfloops']}개 제거, "
              f"중복 {r['dropped_dups']}개 제거)")
        return 0

    if args.cmd == "add-namespace":
        try:
            ns = add_namespace(args.data, name=args.name,
                               default_visibility=args.default_visibility,
                               description=args.description)
        except ValueError as ex:
            print(f"✗ {ex}")
            return 1
        vis = namespace_default_visibility(args.data, ns) or "(없음)"
        print(f"✓ 네임스페이스 등록: {ns}  기본 visibility={vis}")
        return 0

    if args.cmd == "namespaces":
        rows = list_namespaces(args.data)
        if not rows:
            print("(등록된 네임스페이스 없음)")
            return 0
        for r in rows:
            mark = "" if r["registered"] else "  [미등록]"
            vis = r["default_visibility"] or "-"
            print(f"  {r['namespace']}  기본visibility={vis}  노드={r['nodes']}{mark}"
                  + (f"  — {r['description']}" if r["description"] else ""))
        return 0

    conn = load_db(args.data)   # 캐시는 자동(있고 최신이면 재사용, 아니면 재생성)

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
            conn.close()
            return 1

    elif args.cmd == "export":
        only = (subgraph_ids(conn, args.center, args.depth) if args.center else None)
        if args.format == "mermaid":
            print(export_mermaid(conn, args.direction, only=only))
        elif args.format == "dot":
            print(export_dot(conn, only=only))
        elif args.format == "graphml":
            print(export_graphml(conn, only=only))
        else:
            print(json.dumps(export_json(conn, only=only), ensure_ascii=False, indent=2))

    elif args.cmd == "search":
        res = search(conn, args.query, args.limit)
        if not res:
            print("(검색 결과 없음)")
        for r in res:
            print(f"  [{r['score']}] {r['id']}  {r['title']}"
                  f"  ({', '.join(r['fields'])})")

    elif args.cmd == "suggest":
        res = suggest(conn, args.id, args.limit)
        if not res:
            print("(연결 후보 없음)")
        for r in res:
            print(f"  [{r['score']}] {r['id']}  {r['title']}"
                  f"  (공통이웃 {r['common']}, 자카드 {r['jaccard']})")

    elif args.cmd == "node":
        _print_node(*node_detail(conn, args.id))

    elif args.cmd == "neighbors":
        rows = neighbors(conn, args.id, args.depth, args.direction)
        if not rows:
            print("(이웃 없음)")
        for r in rows:
            print(f"  [{r['dist']}] {r['id']}")

    elif args.cmd == "path":
        if args.weighted:
            res = weighted_shortest_path(conn, args.src, args.dst, args.direction,
                                         args.default_weight)
            if res is None:
                print("(경로 없음)")
                conn.close()
                return 1
            path, cost = res
            print(" -> ".join(path)
                  + f"   (홉 {len(path) - 1}, 비용 {round(cost, 4)})")
        else:
            path = shortest_path(conn, args.src, args.dst, args.direction)
            if path is None:
                print("(경로 없음)")
                conn.close()
                return 1
            print(" -> ".join(path) + f"   (홉 {len(path) - 1})")

    elif args.cmd == "health":
        s = stats(conn)
        print(f"노드: {s['nodes']}  엣지: {s['edges']}  "
              f"평균 차수: {s['avg_degree']}  고아: {s['orphans']}")
        q = review_queue(conn, args.confidence)
        print(f"\n리뷰 큐 — 저신뢰/미상 노드 (<{args.confidence}): {len(q['low_confidence'])}")
        for r in q["low_confidence"]:
            c = "없음" if r["confidence"] is None else r["confidence"]
            print(f"  [{c}] {r['id']}  {r['title']}")
        print(f"\n고아 노드: {len(q['orphans'])}")
        for o in q["orphans"]:
            print(f"  {o}")
        print(f"\n끊긴 엣지: {len(q['dangling'])}")
        for d in q["dangling"]:
            print(f"  {d}")
        if q["missing_fields"]:
            print(f"\ntype/title 누락: {', '.join(q['missing_fields'])}")

    elif args.cmd == "components":
        comps = components(conn)
        print(f"연결 요소: {len(comps)}개")
        for i, c in enumerate(comps, 1):
            head = ", ".join(c[:8]) + (" ..." if len(c) > 8 else "")
            print(f"  #{i} (크기 {len(c)}): {head}")

    elif args.cmd == "degree":
        dd = degree_distribution(conn)
        print("차수 히스토그램 (차수: 노드수):")
        for k, v in dd["histogram"].items():
            print(f"  {k}: {v}")
        print(f"상위 {args.top} (차수 중심성):")
        for x in dd["per_node"][:args.top]:
            print(f"  {x['total']:>3}  {x['id']}  (in={x['in']} out={x['out']})")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

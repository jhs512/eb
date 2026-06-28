"""eb.py 그래프 엔진 테스트 (네트워크/서드파티 의존성 없음).

실행: python -m pytest tests/ -q   또는   python -m unittest -q
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import eb  # noqa: E402


def write_graph(d: Path):
    """작은 결정적 그래프:  a -> b -> c,  a -> c,  d(고아),  e -> 없는노드(끊김)."""
    (d / "nodes.csv").write_text(
        "id,title,type,namespace,visibility,summary,confidence,tags,body\n"
        "a,A,pillar,personal,public,sa,0.9,t,ba\n"
        "b,B,concept,personal,public,sb,0.8,t,bb\n"
        "c,C,fact,personal,public,sc,0.7,t,bc\n"
        "d,D,note,personal,public,sd,0.5,t,bd\n"
        "e,E,note,personal,public,se,0.5,t,be\n",
        encoding="utf-8",
    )
    (d / "edges.csv").write_text(
        "source,type,target,weight,note\n"
        "a,part_of,b,0.9,n1\n"
        "b,supports,c,0.8,n2\n"
        "a,related_to,c,0.6,n3\n"
        "e,depends_on,zzz,0.5,n4\n",
        encoding="utf-8",
    )
    (d / "meta.csv").write_text("field,applies_to,description\nid,node,식별자\n", encoding="utf-8")


class EbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        write_graph(self.dir)
        self.conn = eb.load_db(str(self.dir))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_load_counts(self):
        s = eb.stats(self.conn)
        self.assertEqual(s["nodes"], 5)
        self.assertEqual(s["edges"], 4)

    def test_neighbors_out_depth1(self):
        ids = [r["id"] for r in eb.neighbors(self.conn, "a", depth=1, direction="out")]
        self.assertEqual(sorted(ids), ["b", "c"])

    def test_neighbors_out_depth2_dist(self):
        rows = {r["id"]: r["dist"] for r in eb.neighbors(self.conn, "a", depth=2, direction="out")}
        self.assertEqual(rows["b"], 1)
        self.assertEqual(rows["c"], 1)  # a->c 직접 엣지가 더 짧음

    def test_neighbors_in(self):
        ids = [r["id"] for r in eb.neighbors(self.conn, "c", depth=2, direction="in")]
        self.assertEqual(sorted(ids), ["a", "b"])

    def test_shortest_path_direct(self):
        self.assertEqual(eb.shortest_path(self.conn, "a", "c", "out"), ["a", "c"])

    def test_shortest_path_multi_hop_in_only(self):
        # out 방향 a->b->c 와 a->c. b->c 만 보려면 b 출발
        self.assertEqual(eb.shortest_path(self.conn, "b", "c", "out"), ["b", "c"])

    def test_shortest_path_none(self):
        self.assertIsNone(eb.shortest_path(self.conn, "c", "a", "out"))

    def test_shortest_path_self(self):
        self.assertEqual(eb.shortest_path(self.conn, "a", "a", "out"), ["a"])

    def test_orphans(self):
        self.assertEqual(eb.orphans(self.conn), ["d"])

    def test_validate_detects_dangling(self):
        issues = eb.validate(self.conn)
        self.assertTrue(any("zzz" in i for i in issues))

    def test_node_detail(self):
        n, out_e, in_e = eb.node_detail(self.conn, "b")
        self.assertEqual(n["title"], "B")
        self.assertEqual(len(out_e), 1)   # b->c
        self.assertEqual(len(in_e), 1)    # a->b

    # --- 백로그 1: 가중 최단경로 ------------------------------------------- #
    def test_weighted_path_self(self):
        self.assertEqual(eb.weighted_shortest_path(self.conn, "a", "a"), (["a"], 0.0))

    def test_weighted_path_none(self):
        self.assertIsNone(eb.weighted_shortest_path(self.conn, "c", "a", "out"))

    def test_weighted_path_prefers_cheaper_route(self):
        # 직접 a->c(0.6) 이 a->b->c(0.9+0.8=1.7) 보다 싸다
        path, cost = eb.weighted_shortest_path(self.conn, "a", "c", "out")
        self.assertEqual(path, ["a", "c"])
        self.assertAlmostEqual(cost, 0.6)

    def test_weighted_path_multi_hop_beats_direct(self):
        # 비용이 다르면 다익스트라는 홉 수가 많아도 더 싼 경로를 고른다(BFS와 구분)
        d = Path(tempfile.mkdtemp())
        (d / "nodes.csv").write_text(
            "id,title,type,namespace,visibility,summary,confidence,tags,body\n"
            "x,X,note,n,public,,,,\n"
            "y,Y,note,n,public,,,,\n"
            "z,Z,note,n,public,,,,\n",
            encoding="utf-8",
        )
        (d / "edges.csv").write_text(
            "source,type,target,weight,note\n"
            "x,related_to,z,9,direct-expensive\n"
            "x,related_to,y,1,\n"
            "y,related_to,z,1,\n",
            encoding="utf-8",
        )
        (d / "meta.csv").write_text("field,applies_to,description\nid,node,x\n", encoding="utf-8")
        conn = eb.load_db(str(d))
        path, cost = eb.weighted_shortest_path(conn, "x", "z", "out")
        self.assertEqual(path, ["x", "y", "z"])
        self.assertAlmostEqual(cost, 2.0)
        conn.close()

    # --- 백로그 2: 그래프 지표 --------------------------------------------- #
    def test_components(self):
        # {a,b,c} 연결, d 고아, e->zzz 는 끊긴 엣지라 e 단독
        comps = eb.components(self.conn)
        self.assertEqual(len(comps), 3)
        self.assertEqual(comps[0], ["a", "b", "c"])

    def test_degree_distribution(self):
        dd = eb.degree_distribution(self.conn)
        # d:0, e:1(e->zzz, zzz는 노드 아님), a/b/c:2
        self.assertEqual(dd["histogram"], {0: 1, 1: 1, 2: 3})
        self.assertEqual(dd["per_node"][0]["total"], 2)

    # --- 백로그 3: 쓰기 명령 ----------------------------------------------- #
    def test_add_node_and_duplicate(self):
        eb.add_node(str(self.dir), id="newx", title="NewX", type="note", tags="p;q")
        conn = eb.load_db(str(self.dir))
        row = conn.execute("SELECT tags FROM nodes WHERE id='newx'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["tags"], "p;q")
        conn.close()
        with self.assertRaises(ValueError):
            eb.add_node(str(self.dir), id="a", title="dup")  # 이미 존재

    def test_add_edge_and_missing_check(self):
        eb.add_edge(str(self.dir), source="a", type="related_to", target="b")
        conn = eb.load_db(str(self.dir))
        cnt = conn.execute(
            "SELECT COUNT(*) c FROM edges "
            "WHERE source='a' AND target='b' AND type='related_to'"
        ).fetchone()["c"]
        self.assertEqual(cnt, 1)
        conn.close()
        with self.assertRaises(ValueError):
            eb.add_edge(str(self.dir), source="a", type="related_to", target="nope")
        # allow_missing 이면 없는 노드여도 허용
        eb.add_edge(str(self.dir), source="a", type="related_to", target="nope",
                    allow_missing=True)

    # --- 백로그 6: 파일 SQLite 적재/재사용 --------------------------------- #
    def test_file_db_build_and_reuse(self):
        db = self.dir / "graph.sqlite"
        conn = eb.load_db(str(self.dir), str(db), rebuild=True)
        self.assertEqual(eb.stats(conn)["nodes"], 5)
        conn.close()
        self.assertTrue(db.exists())
        # rebuild=False 면 CSV 재적재 없이 기존 테이블 사용
        conn2 = eb.load_db(str(self.dir), str(db), rebuild=False)
        self.assertEqual(eb.stats(conn2)["edges"], 4)
        conn2.close()


def write_search_graph(d: Path):
    """검색 테스트용 그래프 — 필드별로 질의어가 흩어져 있다."""
    (d / "nodes.csv").write_text(
        "id,title,type,namespace,visibility,summary,confidence,tags,body\n"
        "graph-db,Graph Database,concept,personal,public,SQLite로 그래프를 저장,0.9,graph;sqlite,재귀 CTE로 그래프 탐색\n"
        "python-engine,Python 엔진,concept,personal,public,stdlib only,0.8,python;engine,sqlite 바인딩으로 그래프 연산\n"
        "csv-source,CSV 원천,decision,personal,public,CSV가 진실의 원천,0.7,csv;source,엑셀로 편집\n"
        "note-x,잡담,note,personal,public,,0.5,,관련 없는 내용\n",
        encoding="utf-8",
    )
    (d / "edges.csv").write_text("source,type,target,weight,note\n", encoding="utf-8")
    (d / "meta.csv").write_text("field,applies_to,description\nid,node,x\n", encoding="utf-8")


class SearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        write_search_graph(self.dir)
        self.conn = eb.load_db(str(self.dir))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_finds_node_by_title_word(self):
        ids = [r["id"] for r in eb.search(self.conn, "Database")]
        self.assertEqual(ids, ["graph-db"])

    def test_ranks_more_field_matches_higher(self):
        # "sqlite": graph-db는 summary+tags(2필드), python-engine은 body(1필드)
        res = eb.search(self.conn, "sqlite")
        self.assertEqual([r["id"] for r in res], ["graph-db", "python-engine"])
        self.assertEqual(res[0]["score"], 2)
        self.assertEqual(sorted(res[0]["fields"]), ["summary", "tags"])

    def test_no_match_returns_empty(self):
        self.assertEqual(eb.search(self.conn, "존재하지않는질의"), [])

    def test_empty_query_returns_empty(self):
        self.assertEqual(eb.search(self.conn, "   "), [])

    def test_case_insensitive_for_ascii(self):
        self.assertEqual(eb.search(self.conn, "SQLITE"), eb.search(self.conn, "sqlite"))

    def test_matches_korean_substring(self):
        ids = [r["id"] for r in eb.search(self.conn, "그래프")]
        self.assertEqual(ids, ["graph-db", "python-engine"])


def write_suggest_graph(d: Path):
    """연결 제안 테스트용 그래프.

    a-b, a-c, d-b, d-c  → a와 d는 공통 이웃 {b,c} 2개(직접 연결은 아님).
    e는 a와 태그가 같지만(자카드 1.0) 공통 이웃 없음.  f는 e에만 연결.
    """
    (d / "nodes.csv").write_text(
        "id,title,type,namespace,visibility,summary,confidence,tags,body\n"
        "a,A,concept,n,public,,0.9,graph;python,\n"
        "b,B,concept,n,public,,0.8,x,\n"
        "c,C,concept,n,public,,0.8,y,\n"
        "d,D,concept,n,public,,0.8,graph,\n"
        "e,E,concept,n,public,,0.8,graph;python,\n"
        "f,F,concept,n,public,,0.8,z,\n",
        encoding="utf-8",
    )
    (d / "edges.csv").write_text(
        "source,type,target,weight,note\n"
        "a,related_to,b,0.5,\n"
        "a,related_to,c,0.5,\n"
        "d,related_to,b,0.5,\n"
        "d,related_to,c,0.5,\n"
        "e,related_to,f,0.5,\n",
        encoding="utf-8",
    )
    (d / "meta.csv").write_text("field,applies_to,description\nid,node,x\n", encoding="utf-8")


class SuggestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        write_suggest_graph(self.dir)
        self.conn = eb.load_db(str(self.dir))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_suggests_common_neighbor_node(self):
        # a의 공통 이웃 노드 d가 후보로 나오고, 직접 이웃(b,c)·자기 자신(a)은 제외
        ids = [r["id"] for r in eb.suggest(self.conn, "a")]
        self.assertIn("d", ids)
        self.assertNotIn("a", ids)
        self.assertNotIn("b", ids)
        self.assertNotIn("c", ids)

    def test_suggests_by_tag_jaccard_without_common_neighbor(self):
        # e는 공통 이웃이 없어도 태그가 같아(자카드 1.0) 후보가 된다
        res = {r["id"]: r for r in eb.suggest(self.conn, "a")}
        self.assertIn("e", res)
        self.assertEqual(res["e"]["common"], 0)
        self.assertAlmostEqual(res["e"]["jaccard"], 1.0)

    def test_common_neighbor_ranks_above_tag_only(self):
        # d(공통이웃2 + 자카드0.5 = 2.5) 가 e(자카드1.0) 보다 위
        ids = [r["id"] for r in eb.suggest(self.conn, "a")]
        self.assertLess(ids.index("d"), ids.index("e"))

    def test_no_candidates_returns_empty(self):
        # f는 공통 이웃도, 겹치는 태그도 없다
        self.assertEqual(eb.suggest(self.conn, "f"), [])

    def test_unknown_node_returns_empty(self):
        self.assertEqual(eb.suggest(self.conn, "없는노드"), [])


def write_merge_graph(d: Path):
    """병합 테스트용. b를 a로 병합하면: p->b는 p->a, b->q는 a->q, a->b는 a->a(루프)→제거."""
    (d / "nodes.csv").write_text(
        "id,title,type,namespace,visibility,summary,confidence,tags,body\n"
        "a,A,concept,n,public,,0.9,,\n"
        "b,B,concept,n,public,,0.8,,\n"
        "p,P,concept,n,public,,0.8,,\n"
        "q,Q,concept,n,public,,0.8,,\n",
        encoding="utf-8",
    )
    (d / "edges.csv").write_text(
        "source,type,target,weight,note\n"
        "p,related_to,b,0.5,\n"
        "b,related_to,q,0.5,\n"
        "a,related_to,b,0.5,\n",
        encoding="utf-8",
    )
    (d / "meta.csv").write_text("field,applies_to,description\nid,node,x\n", encoding="utf-8")


class MergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        write_merge_graph(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def _edges(self):
        conn = eb.load_db(str(self.dir))
        rows = [(r["source"], r["target"]) for r in
                conn.execute("SELECT source, target FROM edges").fetchall()]
        conn.close()
        return rows

    def _node_ids(self):
        conn = eb.load_db(str(self.dir))
        ids = [r["id"] for r in conn.execute("SELECT id FROM nodes").fetchall()]
        conn.close()
        return ids

    def test_merge_repoints_edges_and_removes_node(self):
        eb.merge(str(self.dir), "b", "a")
        self.assertNotIn("b", self._node_ids())
        edges = self._edges()
        self.assertIn(("p", "a"), edges)
        self.assertIn(("a", "q"), edges)

    def test_merge_drops_resulting_self_loop(self):
        # a->b 는 b를 a로 병합하면 a->a 가 되어 버려진다
        res = eb.merge(str(self.dir), "b", "a")
        self.assertNotIn(("a", "a"), self._edges())
        self.assertEqual(res["dropped_selfloops"], 1)
        # p->b, b->q 는 살아남아 재배선(2), a->b 만 자기 루프로 제거
        self.assertEqual(res["repointed"], 2)

    def test_merge_dedupes_parallel_edges_it_creates(self):
        # p->b 와 p->a 가 모두 있을 때 b를 a로 병합하면 p->a 가 둘이 되어야 하지만,
        # 재배선으로 생긴 평행 중복은 합쳐 하나만 남는다.
        eb.add_edge(str(self.dir), source="p", type="related_to", target="a")
        res = eb.merge(str(self.dir), "b", "a")
        # p->b(related_to) 가 p->a 로 재배선되며 기존 p->a 와 중복 → 1개 제거
        self.assertEqual(res["dropped_dups"], 1)
        pa = [e for e in self._edges() if e == ("p", "a")]
        self.assertEqual(len(pa), 1)

    def test_merge_keeps_preexisting_multigraph_dups(self):
        # 병합과 무관한 기존 평행 중복은 보존된다(멀티그래프)
        eb.add_edge(str(self.dir), source="p", type="related_to", target="q")
        eb.add_edge(str(self.dir), source="p", type="related_to", target="q")
        eb.merge(str(self.dir), "b", "a")  # p,q 와 무관
        pq = [e for e in self._edges() if e == ("p", "q")]
        self.assertEqual(len(pq), 2)

    def test_merge_self_rejected(self):
        with self.assertRaises(ValueError):
            eb.merge(str(self.dir), "a", "a")

    def test_merge_missing_node_rejected(self):
        with self.assertRaises(ValueError):
            eb.merge(str(self.dir), "없는노드", "a")
        with self.assertRaises(ValueError):
            eb.merge(str(self.dir), "b", "없는노드")

    def test_merge_leaves_no_dangling(self):
        eb.merge(str(self.dir), "b", "a")
        conn = eb.load_db(str(self.dir))
        self.assertEqual([i for i in eb.validate(conn) if "끊긴" in i], [])
        conn.close()


def write_health_graph(d: Path):
    """점검 테스트용. hi(0.9) lo(0.3) unk(없음) orph(0.9, 고아). lo->ghost 는 끊긴 엣지."""
    (d / "nodes.csv").write_text(
        "id,title,type,namespace,visibility,summary,confidence,tags,body\n"
        "hi,Hi,concept,n,public,,0.9,,\n"
        "lo,Lo,concept,n,public,,0.3,,\n"
        "unk,Unk,concept,n,public,,,,\n"
        "orph,Orph,concept,n,public,,0.9,,\n",
        encoding="utf-8",
    )
    (d / "edges.csv").write_text(
        "source,type,target,weight,note\n"
        "hi,related_to,lo,0.5,\n"
        "lo,related_to,ghost,0.5,\n",
        encoding="utf-8",
    )
    (d / "meta.csv").write_text("field,applies_to,description\nid,node,x\n", encoding="utf-8")


class HealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        write_health_graph(self.dir)
        self.conn = eb.load_db(str(self.dir))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_low_confidence_below_threshold(self):
        q = eb.review_queue(self.conn, confidence_threshold=0.6)
        ids = {r["id"] for r in q["low_confidence"]}
        self.assertIn("lo", ids)     # 0.3 < 0.6
        self.assertNotIn("hi", ids)  # 0.9 >= 0.6

    def test_missing_confidence_flagged_for_review(self):
        q = eb.review_queue(self.conn, confidence_threshold=0.6)
        ids = {r["id"] for r in q["low_confidence"]}
        self.assertIn("unk", ids)    # confidence 없음 = 검토 필요

    def test_threshold_is_respected(self):
        ids = {r["id"] for r in
               eb.review_queue(self.conn, confidence_threshold=0.95)["low_confidence"]}
        self.assertIn("hi", ids)     # 0.9 < 0.95 이면 검토 대상
        self.assertIn("orph", ids)

    def test_orphans_in_queue(self):
        self.assertIn("orph", eb.review_queue(self.conn)["orphans"])

    def test_dangling_in_queue(self):
        q = eb.review_queue(self.conn)
        self.assertTrue(any("ghost" in d for d in q["dangling"]))


if __name__ == "__main__":
    unittest.main()

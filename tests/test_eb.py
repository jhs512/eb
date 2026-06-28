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


if __name__ == "__main__":
    unittest.main()

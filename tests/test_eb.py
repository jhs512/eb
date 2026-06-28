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


if __name__ == "__main__":
    unittest.main()

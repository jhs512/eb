"""eb.py CLI 레이어 테스트 (네트워크 없음, 결정적).

함수 레벨은 test_eb.py가 덮는다. 여기서는 스킬·CI가 실제로 호출하는 **CLI**
(eb.main(argv))의 종료코드·출력·새 명령 분기(export/search/merge/health/validate)를 박제한다.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import eb  # noqa: E402


def _write(d: Path):
    (d / "nodes.csv").write_text(
        "id,title,type,namespace,visibility,summary,confidence,tags,body\n"
        "a,A,pillar,n,public,추출 요약,0.9,그래프,바디\n"
        "b,B,concept,n,public,,0.8,,\n"
        "c,C,fact,n,public,,0.3,,\n"
        "dup,Dup,concept,n,public,,0.5,,\n",
        encoding="utf-8")
    (d / "edges.csv").write_text(
        "source,type,target,weight,note\n"
        "a,part_of,b,0.9,n1\n"
        "b,supports,c,0.8,n2\n"
        "a,related_to,zzz,0.5,dangling\n",   # 끊긴 엣지
        encoding="utf-8")
    (d / "meta.csv").write_text("field,applies_to,description\nid,node,x\n", encoding="utf-8")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        _write(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = eb.main(["--data", str(self.dir), *args])
        return code, buf.getvalue()

    # --- 읽기 명령: 종료코드 0 + 출력 ---------------------------------- #
    def test_stats_ok(self):
        code, out = self.run_cli("stats")
        self.assertEqual(code, 0)
        self.assertIn("노드", out)

    def test_search_ok(self):
        code, out = self.run_cli("search", "추출")
        self.assertEqual(code, 0)
        self.assertIn("a", out)

    def test_health_ok(self):
        code, out = self.run_cli("health")
        self.assertEqual(code, 0)
        self.assertIn("리뷰 큐", out)

    # --- export 3종 ---------------------------------------------------- #
    def test_export_mermaid_cli(self):
        code, out = self.run_cli("export", "--format", "mermaid")
        self.assertEqual(code, 0)
        self.assertTrue(out.lstrip().startswith("graph "))
        self.assertNotIn("zzz", out)              # 끊긴 엣지 제외

    def test_export_json_cli(self):
        code, out = self.run_cli("export", "--format", "json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(len(data["nodes"]), 4)

    def test_export_dot_cli(self):
        code, out = self.run_cli("export", "--format", "dot")
        self.assertEqual(code, 0)
        self.assertIn("digraph", out)

    # --- 종료코드로 실패를 알리는 명령 -------------------------------- #
    def test_validate_dangling_returns_1(self):
        code, out = self.run_cli("validate")
        self.assertEqual(code, 1)                 # 끊긴 엣지 존재
        self.assertIn("zzz", out)

    def test_merge_ok_then_selfmerge_fails(self):
        code, _ = self.run_cli("merge", "dup", "a")
        self.assertEqual(code, 0)
        code2, _ = self.run_cli("merge", "a", "a")
        self.assertEqual(code2, 1)                # self-merge 거부

    def test_add_node_duplicate_returns_1(self):
        code, _ = self.run_cli("add-node", "--id", "a", "--title", "dup")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

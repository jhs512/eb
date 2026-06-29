"""Cloudflare Pages 앱·배포 워크플로 계약 테스트 (네트워크 없음, 결정적).

브라우저 앱의 런타임 동작은 박제하지 않고, 정적 자산·워크플로의 구조적 계약만 본다 —
앱이 sql.js/cytoscape/CSV를 참조하는지, 배포가 경로 필터(최초·CSV·web 변경)로만 도는지.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
WF = ROOT / ".github" / "workflows" / "deploy-pages.yml"


class WebAppTest(unittest.TestCase):
    def test_app_files_exist(self):
        for f in ("index.html", "app.js", "style.css"):
            self.assertTrue((WEB / f).exists(), f"web/{f} 없음")

    def test_app_uses_expected_stack(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn("sql-wasm.js", html)      # sql.js (SQLite WASM)
        self.assertIn("cytoscape", html)        # 시각화
        app = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("initSqlJs", app)         # 클라이언트 사이드 SQLite
        self.assertIn("nodes.csv", app)         # CSV fetch
        self.assertIn("edges.csv", app)


class DeployWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WF.exists(), "deploy-pages.yml 없음")
        self.txt = WF.read_text(encoding="utf-8")

    def test_path_filtered_triggers(self):
        # 최초(수동) + CSV + 프론트 변경에만 — 매 push 아님
        self.assertIn("workflow_dispatch", self.txt)
        self.assertIn("paths:", self.txt)
        self.assertIn("data/**", self.txt)
        self.assertIn("web/**", self.txt)

    def test_deploys_to_cloudflare_pages(self):
        self.assertIn("cloudflare/wrangler-action", self.txt)
        self.assertIn("pages deploy web", self.txt)
        self.assertIn("CLOUDFLARE_API_TOKEN", self.txt)


if __name__ == "__main__":
    unittest.main()

"""sync.py 드리프트 감지(diff_rows) 테스트 — 네트워크/gspread 없이 동작.

gspread 는 sync._client() 안에서만 import 하므로 모듈 import 는 stdlib 만 필요하다.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sync  # noqa: E402


class DiffTest(unittest.TestCase):
    def test_in_sync_ignores_trailing_blanks(self):
        csv_rows = [["id", "title"], ["a", "A"]]
        sheet_rows = [["id", "title", ""], ["a", "A"], [], [""]]  # 시트 패딩
        d = sync.diff_rows(csv_rows, sheet_rows)
        self.assertTrue(d["in_sync"])

    def test_detects_changed(self):
        d = sync.diff_rows([["a", "A"]], [["a", "B"]])
        self.assertFalse(d["in_sync"])
        self.assertEqual(len(d["changed"]), 1)
        self.assertEqual(d["changed"][0][0], 0)

    def test_detects_sheet_only(self):
        d = sync.diff_rows([["a", "A"]], [["a", "A"], ["x", "X"]])
        self.assertEqual(len(d["only_in_sheet"]), 1)
        self.assertFalse(d["in_sync"])

    def test_detects_csv_only(self):
        d = sync.diff_rows([["a", "A"], ["b", "B"]], [["a", "A"]])
        self.assertEqual(len(d["only_in_csv"]), 1)
        self.assertFalse(d["in_sync"])


if __name__ == "__main__":
    unittest.main()

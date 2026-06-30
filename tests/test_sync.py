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


class PagesTest(unittest.TestCase):
    def _rows(self, n):
        return [["no", "id"]] + [[str(i), f"x{i}"] for i in range(1, n + 1)]

    def test_no_pagination_when_disabled(self):
        rows = self._rows(200)
        pages = sync._pages("_meta", rows, paginate=False)
        self.assertEqual([n for n, _ in pages], ["_meta"])
        self.assertEqual(len(pages[0][1]), 201)

    def test_single_page_at_or_below_limit(self):
        rows = self._rows(sync.ROWS_PER_PAGE)          # 정확히 한도
        pages = sync._pages("_data", rows, paginate=True)
        self.assertEqual([n for n, _ in pages], ["_data"])

    def test_splits_with_header_on_each_page(self):
        rows = self._rows(sync.ROWS_PER_PAGE * 2 + 3)  # 3페이지
        pages = sync._pages("_data", rows, paginate=True)
        self.assertEqual([n for n, _ in pages], ["_data", "_data2", "_data3"])
        # 각 페이지는 헤더 1줄 + 데이터, 마지막은 3줄
        self.assertEqual(pages[0][1][0], ["no", "id"])
        self.assertEqual(pages[1][1][0], ["no", "id"])
        self.assertEqual(len(pages[0][1]) - 1, sync.ROWS_PER_PAGE)
        self.assertEqual(len(pages[2][1]) - 1, 3)
        # no → 탭: no 61 은 _data2 의 첫 데이터
        self.assertEqual(pages[1][1][1], ["61", "x61"])

    def test_empty_rows(self):
        self.assertEqual(sync._pages("_data", [], paginate=True), [])


if __name__ == "__main__":
    unittest.main()

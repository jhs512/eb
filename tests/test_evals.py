"""evals 채점기 단위테스트 (네트워크/LLM 없음, 결정적).

evals 자체는 비결정적(모델 N회)이지만, 그 **채점 로직(rubric)** 은 결정적이라
여기서 박제한다. 또한 녹화된 fixture 후보들이 각 케이스 rubric을 통과하는지(회귀) 본다.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))
import run_evals as ev  # noqa: E402

GOOD = {
    "nodes": [
        {"id": "a", "title": "주의 잔류물", "type": "concept", "summary": "x"},
        {"id": "s", "title": "메모", "type": "source", "summary": ""},
    ],
    "edges": [
        {"source": "a", "type": "related_to", "target": "b"},
        {"source": "a", "type": "derived_from", "target": "s"},
    ],
}
RUBRIC = {"min_nodes": 2, "must_mention": ["주의 잔류물"],
         "must_have_source": True, "no_orphans": True,
         "valid_edge_types": True, "pass_score": 1.0}


class ScoreTest(unittest.TestCase):
    def test_good_candidate_passes(self):
        r = ev.score_candidate(GOOD, RUBRIC)
        self.assertTrue(r["passed"])
        self.assertEqual(r["score"], 1.0)

    def test_missing_source_fails(self):
        cand = {"nodes": [{"id": "a", "title": "주의 잔류물", "type": "concept"}],
                "edges": [{"source": "a", "type": "related_to", "target": "b"}]}
        r = ev.score_candidate(cand, RUBRIC)
        self.assertFalse(r["passed"])
        self.assertIn("has_source_node", [c["name"] for c in r["checks"] if not c["passed"]])

    def test_orphan_node_fails(self):
        cand = {"nodes": [{"id": "a", "title": "주의 잔류물", "type": "source"},
                          {"id": "orphan", "title": "외톨이", "type": "concept"}],
                "edges": [{"source": "a", "type": "related_to", "target": "b"}]}
        r = ev.score_candidate(cand, RUBRIC)
        self.assertFalse(r["passed"])
        names = [c["name"] for c in r["checks"] if not c["passed"]]
        self.assertIn("no_orphans", names)

    def test_invalid_edge_type_fails(self):
        cand = {"nodes": [{"id": "a", "title": "주의 잔류물", "type": "source"}],
                "edges": [{"source": "a", "type": "made_up", "target": "b"}]}
        r = ev.score_candidate(cand, RUBRIC)
        self.assertFalse(r["passed"])

    def test_must_mention_missing_fails(self):
        r = ev.score_candidate(GOOD, {"must_mention": ["존재하지않는용어"]})
        self.assertFalse(r["passed"])


class FixtureRegressionTest(unittest.TestCase):
    def test_recorded_candidates_pass_their_rubric(self):
        cases = ev.load_cases()
        self.assertGreaterEqual(len(cases), 2)
        for case in cases:
            cand = ev.fixture_solver(case)
            r = ev.score_candidate(cand, case["rubric"])
            self.assertTrue(r["passed"],
                            f"{case['id']} 후보가 rubric 미통과: "
                            + ", ".join(c["name"] for c in r["checks"] if not c["passed"]))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""eb evals — eb-learn(LLM 증류)의 비결정적 품질을 평가하는 하니스.

테스트 3층 중 **evals** 층(비결정적). 단위/골든/계약 테스트(tests/)와 달리,
같은 입력을 모델에 N회 돌려 rubric으로 채점하고 합격률을 본다. 단위테스트가 아니다.

구조(promptfoo식): **solver**(후보 그래프를 만든다) + **rubric 채점**(결정적).
- solver=fixture : evals/cases/<id>.candidate.json 을 읽는다(오프라인·CI에서 채점기 회귀).
- solver=anthropic: Claude API로 실제 증류(ANTHROPIC_API_KEY + `pip install anthropic` 필요).

채점은 결정적이라 tests/test_evals.py 가 단위테스트로 보호한다.

사용:
  python evals/run_evals.py                          # fixture solver(오프라인)
  python evals/run_evals.py --solver anthropic --runs 5
  python evals/run_evals.py --case deep-work-followup --threshold 1.0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
CASES_DIR = EVAL_DIR / "cases"

EB_EDGE_TYPES = {
    "supports", "depends_on", "part_of", "related_to", "derived_from",
    "contradicts", "preceded_by", "followed_by", "authored_by", "tagged_with",
}


# --------------------------------------------------------------------------- #
# 결정적 채점 (단위테스트 대상)
# --------------------------------------------------------------------------- #
def _text_blob(candidate) -> str:
    parts = []
    for n in candidate.get("nodes", []):
        parts += [str(n.get("title", "")), str(n.get("summary", ""))]
    return " ".join(parts)


def _node_ids_in_edges(candidate) -> set:
    ids = set()
    for e in candidate.get("edges", []):
        ids.add(e.get("source"))
        ids.add(e.get("target"))
    return ids


def score_candidate(candidate: dict, rubric: dict) -> dict:
    """후보 그래프를 rubric으로 채점. 반환: {checks:[...], score, passed}.

    각 check는 {name, passed, detail}. score = 통과 비율. passed = score>=rubric.pass_score(기본 1.0).
    """
    nodes = candidate.get("nodes", []) or []
    edges = candidate.get("edges", []) or []
    blob = _text_blob(candidate)
    in_edges = _node_ids_in_edges(candidate)
    checks = []

    def add(name, ok, detail=""):
        checks.append({"name": name, "passed": bool(ok), "detail": detail})

    if "min_nodes" in rubric:
        add("min_nodes", len(nodes) >= rubric["min_nodes"],
            f"{len(nodes)} >= {rubric['min_nodes']}")
    for term in rubric.get("must_mention", []):
        add(f"mention:{term}", term in blob, "" if term in blob else "누락")
    if rubric.get("must_have_source"):
        has = any((n.get("type") == "source") for n in nodes)
        add("has_source_node", has, "" if has else "source 타입 노드 없음")
    if rubric.get("no_orphans"):
        orphans = [n.get("id") for n in nodes if n.get("id") not in in_edges]
        add("no_orphans", not orphans, "" if not orphans else f"고아: {orphans}")
    if rubric.get("valid_edge_types"):
        bad = sorted({e.get("type") for e in edges if e.get("type") not in EB_EDGE_TYPES})
        add("valid_edge_types", not bad, "" if not bad else f"잘못된 엣지타입: {bad}")

    passed_n = sum(1 for c in checks if c["passed"])
    score = passed_n / len(checks) if checks else 1.0
    return {"checks": checks, "score": score,
            "passed": score >= rubric.get("pass_score", 1.0)}


# --------------------------------------------------------------------------- #
# solvers (후보 그래프 생성)
# --------------------------------------------------------------------------- #
def fixture_solver(case: dict) -> dict:
    p = CASES_DIR / f"{case['id']}.candidate.json"
    if not p.exists():
        raise RuntimeError(f"녹화된 후보 없음: {p.name} (anthropic solver로 생성하거나 추가하세요)")
    return json.loads(p.read_text(encoding="utf-8"))


_DISTILL_PROMPT = """\
다음 원자료를 Excel Brain(eb) 타입 지식 그래프의 후보 노드/엣지로 증류하라.
규칙: 노드 1개=원자적 아이디어 1개. id는 kebab-case ASCII. 출처가 있으면 type=source 노드를 만들고
새 노드를 derived_from으로 연결. 모든 새 노드는 최소 1개 엣지로 연결(고아 금지). 엣지 타입은
[supports, depends_on, part_of, related_to, derived_from, contradicts, preceded_by, followed_by,
authored_by, tagged_with] 중에서만.
기존 그래프(있으면 참고, 중복 생성 금지):
{seed}
원자료:
{raw}
오직 JSON만 출력: {{"nodes":[{{"id","title","type","tags","summary"}}],"edges":[{{"source","type","target","note"}}]}}
"""


def anthropic_solver(case: dict, model: str = "claude-opus-4-8") -> dict:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic 가 필요합니다: pip install anthropic (+ ANTHROPIC_API_KEY)")
    client = anthropic.Anthropic()
    prompt = _DISTILL_PROMPT.format(seed=case.get("seed", "(없음)"), raw=case["raw"])
    msg = client.messages.create(
        model=model, max_tokens=2000,
        messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1].lstrip("json").strip()
    return json.loads(text)


SOLVERS = {"fixture": fixture_solver, "anthropic": anthropic_solver}


# --------------------------------------------------------------------------- #
# 러너
# --------------------------------------------------------------------------- #
def load_cases(only=None):
    cases = []
    for p in sorted(CASES_DIR.glob("*.json")):
        if p.name.endswith(".candidate.json"):
            continue
        c = json.loads(p.read_text(encoding="utf-8"))
        if only is None or c["id"] == only:
            cases.append(c)
    return cases


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="run_evals", description="eb-learn 증류 품질 evals")
    ap.add_argument("--solver", choices=list(SOLVERS), default="fixture")
    ap.add_argument("--runs", type=int, default=1, help="케이스당 반복(비결정성 측정)")
    ap.add_argument("--case", help="특정 케이스 id만")
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--threshold", type=float, default=0.8,
                    help="전체 합격률 임계값(미만이면 종료코드 1)")
    args = ap.parse_args(argv)

    cases = load_cases(args.case)
    if not cases:
        print("케이스 없음")
        return 1
    solver = SOLVERS[args.solver]

    total_runs = total_pass = 0
    for case in cases:
        runs_passed = 0
        last_detail = ""
        for _ in range(args.runs):
            try:
                cand = (fixture_solver(case) if args.solver == "fixture"
                        else solver(case, args.model))
                res = score_candidate(cand, case.get("rubric", {}))
            except RuntimeError as ex:
                last_detail = f"solver 오류: {ex}"
                res = {"score": 0.0, "passed": False, "checks": []}
            runs_passed += 1 if res["passed"] else 0
            last_detail = "; ".join(
                f"{c['name']}✗" for c in res.get("checks", []) if not c["passed"]
            ) or last_detail or "ok"
        total_runs += args.runs
        total_pass += runs_passed
        rate = runs_passed / args.runs
        mark = "✓" if rate >= args.threshold else "✗"
        print(f"  {mark} {case['id']}: {runs_passed}/{args.runs} 합격  ({last_detail})")

    overall = total_pass / total_runs if total_runs else 0.0
    print(f"\n전체 합격률: {total_pass}/{total_runs} = {overall:.0%}  "
          f"(임계 {args.threshold:.0%}, solver={args.solver})")
    return 0 if overall >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())

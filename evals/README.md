# eb evals — eb-learn 증류 품질 평가

테스트 3층 중 **evals** 층. 단위/골든/계약 테스트(`tests/`)가 *결정적 substrate*(엔진·스킬 파일)를 박제한다면, evals는 **비결정적 LLM 판단**(eb-learn이 자연어를 얼마나 잘 증류하는가)을 평가한다. 같은 입력을 모델에 N회 돌려 rubric으로 채점하고 **합격률**을 본다 — CI 단위테스트가 아니다.

## 구조 (promptfoo식: provider + assertion)

- **case** (`cases/<id>.json`) — 원자료(`raw`) + 선택 `seed`(기존 그래프) + **rubric**(채점 기준)
- **solver** — 후보 그래프를 만든다:
  - `fixture` — `cases/<id>.candidate.json`(녹화된 출력)을 읽는다. **오프라인·결정적** → 채점기 회귀·예시용.
  - `anthropic` — Claude API로 실제 증류. `ANTHROPIC_API_KEY` + `pip install anthropic` 필요.
- **채점(rubric)** — 결정적. `tests/test_evals.py` 가 단위테스트로 보호한다.

## rubric 항목

| 키 | 의미 |
|----|------|
| `min_nodes` | 최소 노드 수 |
| `must_mention` | 노드 title/summary에 반드시 등장할 용어들 |
| `must_have_source` | 출처(type=source) 노드 존재(provenance) |
| `no_orphans` | 모든 노드가 최소 1개 엣지로 연결(엣지는 seed id를 가리켜도 됨) |
| `valid_edge_types` | 엣지 타입이 eb 10종 안에 있음 |
| `pass_score` | 케이스 합격 점수(기본 1.0 = 모든 체크 통과) |

## 실행

```bash
# 오프라인(녹화된 후보로 채점기·예시 확인)
python evals/run_evals.py

# 실제 모델로 비결정성 측정(케이스당 5회)
python evals/run_evals.py --solver anthropic --runs 5

python evals/run_evals.py --case deep-work-followup           # 특정 케이스
python evals/run_evals.py --solver anthropic --threshold 0.8  # 합격률 임계
```

종료코드: 전체 합격률 ≥ `--threshold` 면 0, 아니면 1(CI/게이트용).

## 케이스 추가

1. `cases/<id>.json` 작성(`raw` + `rubric`, 필요시 `seed`).
2. (선택) `cases/<id>.candidate.json` 에 모범 출력을 녹화하면 `fixture` solver로 오프라인 확인.
3. `python evals/run_evals.py --solver anthropic --case <id> --runs 5` 로 실제 품질 측정.

## 왜 이렇게?

eb는 로직을 결정적 엔진으로 밀어 LLM 책임을 최소화했다(테스트 쉬움). 그래도 "자연어 → 좋은 원자 노드"는 환원 불가능한 LLM 판단이라, 그 부분만 evals로 확률적으로 검증한다. 채점은 결정적이라 회귀로 보호하고, 모델 호출만 비결정적·선택적이다.

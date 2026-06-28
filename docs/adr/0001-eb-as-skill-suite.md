# eb를 Python 엔진 위의 5스킬 수트로 패키징

eb를 단일 `/eb` 헬퍼 스킬이 아니라, 결정적 `eb.py` 엔진 위에 올린 **5개의 작은 스킬 묶음**으로 제품화한다 — `eb-init`(부트스트랩) / `eb-capture`(증류) / `eb-recall`(조회) / `eb-curate`(정제) / `eb-health`(점검). 영감을 받은 [obsidian-infinite-brain](https://github.com/JotaSXBR/obsidian-infinite-brain)의 다섯 스킬(init-vault / convert-note / query-vault / organize-vault / vault-health)과 **1:1로 대응**시킨 것이다.

## Considered Options

- **단일 `/eb` 스킬 유지** — 가볍지만 "에이전트의 기억" 제품 서사를 담지 못하고, 수집→조회→정제 루프가 한 프롬프트에 뭉쳐 비대해진다.
- **엔진 우선 + 얇은 스킬 1개** — "CSV 그래프 도구"로 포지셔닝. 도구로서는 깔끔하나 원본 ib의 제품 정체성(스킬 묶음)과 멀어진다.

## Consequences

- eb의 차별점은 ib와 달리 그래프 탐색을 프롬프트가 아니라 **Python 엔진이 보증**한다는 점이다. 스킬은 얇게 유지하고 실제 연산은 `eb.py`(stdlib only)에 위임한다.
- 기존 `/eb` 스킬은 `eb-capture` + `eb-recall`로 분화된다.

# README 제품 서사 재작성 (문서)

Status: done

## Parent

[PRD: eb 5스킬 수트](../PRD.md)

## What to build

README를 도구 레퍼런스에서 **제품 서사 우선**으로 재작성한다([ADR-0001](../../../docs/adr/0001-eb-as-skill-suite.md)).

구조: 한 줄 가치("에이전트의 무한·구조화된 기억") → 문제(에이전트는 세션마다 잊는다) → **5스킬 소개** → 차별점(그래프 연산을 결정적 Python 엔진이 보증) → 빠른 시작(`skills-lock` 설치 → `/eb-setup` → `/eb-learn`·`/eb-ask`) → 레퍼런스(데이터 규약, 엔진 명령 전체, 시트 동기화). ref 핀 갱신 절차를 빠른 시작에 포함한다.

## Acceptance criteria

- [ ] README가 5스킬을 전면에 소개하고 각 역할을 명시한다.
- [ ] 빠른 시작이 실제 설치·`/eb-setup`·조회/캡처 명령과 일치한다.
- [ ] 엔진 명령 레퍼런스에 신규 `search`/`merge`/`suggest`가 포함된다.
- [ ] 구식 `/eb` 단일 스킬 참조가 남아 있지 않다.

## Blocked by

- [01-eb-ask-read-path](./01-eb-ask-read-path.md)
- [02-eb-learn-graph-aware-write](./02-eb-learn-graph-aware-write.md)
- [03-eb-clean-maintenance](./03-eb-clean-maintenance.md)
- [04-eb-check-review-queue](./04-eb-check-review-queue.md)
- [05-eb-setup-distribution](./05-eb-setup-distribution.md)

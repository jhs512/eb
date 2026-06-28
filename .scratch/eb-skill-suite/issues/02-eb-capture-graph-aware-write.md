# eb-capture — 그래프-인지 쓰기 (suggest 엔진 + 캡처 스킬)

Status: done

## Parent

[PRD: eb 5스킬 수트](../PRD.md)

## What to build

원자료(텍스트·대화)를 노드+엣지로 **증류**해 CSV에 반영하되, 추가 *전에* 그래프를 조회하는 **그래프-인지 캡처**를 끝까지 만든다([ADR-0003](../../../docs/adr/0003-graph-aware-capture.md)).

- 엔진(`eb.py`, stdlib only): `eb.suggest(conn, id, ...)` 함수와 CLI `suggest` 추가. 공통 이웃 수·태그 자카드 유사도·2홉 도달(직접 엣지 없는) 등 그래프 구조 신호로 연결 후보를 점수화해 제안한다.
- 스킬: `.claude/skills/eb-capture/SKILL.md` 신규. 파이프라인: ① 증류 → ② `search`/`neighbors`로 중복·연결 후보 조회 → ③ 사용자 **승인 게이트** → ④ `add-node`/`add-edge` 반영 → ⑤ `validate`. 매 캡처마다 `source` 타입 노드를 만들고 `derived_from`/`authored_by`로 연결(출처 추적). 지식 갱신 시 덮어쓰지 않고 새 노드 + `preceded_by`(모순이면 `contradicts`)로 잇는다(이력 보존).
- 프리팩터: 구식 `.claude/skills/eb`(단일 `/eb`) 제거 — recall + capture로 대체됨.

## Acceptance criteria

- [ ] `eb.suggest`가 대상 노드에 대해 점수화된 연결 후보를 반환한다(직접 연결된 노드는 제외).
- [ ] CLI `python eb.py suggest <id>`가 사람이 읽는 후보 목록을 낸다.
- [ ] `eb.suggest`에 대한 오프라인 단위테스트(공통 이웃·태그 자카드·직접 연결 제외)가 추가되고 CI 통과.
- [ ] `eb-capture` SKILL.md가 증류→조회→승인→반영→validate 흐름과 출처·supersede 규칙을 안내한다.
- [ ] 캡처 후 `validate`로 끊긴 엣지 0이 확인된다.
- [ ] 구식 `/eb` 스킬이 제거되고 README/문서의 참조가 정리된다.

## Blocked by

- [01-eb-recall-read-path](./01-eb-recall-read-path.md) (search 사용; suggest와 함께 조회에 의존)

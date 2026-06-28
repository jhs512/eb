# eb-clean — 정제 (merge 엔진 + 정제 스킬)

Status: done

## Parent

[PRD: eb 5스킬 수트](../PRD.md)

## What to build

그래프의 건강을 회복시키는 **정제(curate)** 경로를 끝까지 만든다 — 중복 병합, 고아 연결, 그래프 촘촘화.

- 엔진(`eb.py`, stdlib only): `eb.merge(data_dir, from_id, into_id)` 함수와 CLI `merge` 추가. `from_id`로/에서의 모든 엣지를 `into_id`로 **재배선**하고 `from_id` 노드를 삭제한다. CSV 안전 쓰기(`add-node`/`add-edge` 패턴 재사용). self-merge·존재하지 않는 id는 거부.
- 스킬: `.claude/skills/eb-clean/SKILL.md` 신규. `search`로 중복 탐지 → `merge`로 병합, `orphans` + `suggest`로 고아에 연결 제안, `suggest`로 기존 노드 촘촘화. 매 변경 후 `validate`.

## Acceptance criteria

- [ ] `eb.merge`가 양방향 엣지를 `into_id`로 재배선하고 `from_id` 노드를 삭제한다.
- [ ] self-merge와 존재하지 않는 id에 대해 거부한다.
- [ ] `eb.merge`에 대한 오프라인 단위테스트(재배선·삭제·거부·재로드 후 일관성)가 추가되고 CI 통과.
- [ ] CLI `python eb.py merge <from> <into>`가 동작하고 변경 결과를 보고한다.
- [ ] `eb-clean` SKILL.md가 병합·고아 연결·촘촘화 워크플로와 변경 후 `validate`를 안내한다.

## Blocked by

- [02-eb-learn-graph-aware-write](./02-eb-learn-graph-aware-write.md) (suggest 사용)

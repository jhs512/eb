# eb-ask — 읽기 경로 (search 엔진 + 조회 스킬)

Status: done

## Parent

[PRD: eb 5스킬 수트](../PRD.md)

## What to build

그래프를 탐색해 답을 얻는 **조회(recall)** 경로를 끝까지 만든다. 사용자가 키워드나 노드를 주면 관련 **서브그래프**(유사 노드 + 이웃/경로)를 사람이 읽기 좋은 형태로 돌려준다.

- 엔진(`eb.py`, stdlib only): `eb.search(conn, query, ...)` 함수와 CLI `search` 추가. `nodes.csv`의 `title·summary·tags·body`에서 질의어로 후보 노드를 찾고 일치 필드 수로 랭크한다(SQLite `LIKE`, 가용 시 FTS). `--data`/`--db` 컨벤션을 따른다.
- 스킬: `.claude/skills/eb-ask/SKILL.md` 신규 작성. 기존 `search`/`neighbors`/`path`/`components`/`degree`를 조합해 "관련 서브그래프"를 제시하는 얇은 오케스트레이터. 트리거(예: "조회", "이웃", "최단 경로", "recall")를 frontmatter에 둔다.

## Acceptance criteria

- [ ] `eb.search`가 제목·요약·태그·본문에서 질의어를 찾아 랭크된 노드 목록을 반환한다(빈 결과 포함 정상 처리).
- [ ] CLI `python eb.py search <질의>`가 사람이 읽는 출력을 낸다.
- [ ] `eb.search`에 대한 오프라인 단위테스트(필드 매칭·랭킹·빈 결과)가 `tests/`에 추가되고 CI에서 통과한다.
- [ ] `eb-ask` SKILL.md가 search/neighbors/path/components/degree를 활용해 조회 워크플로를 안내한다.
- [ ] 엔진 코어의 서드파티 의존성 0이 유지된다.

## Blocked by

None - can start immediately

## Comments

- TDD로 `eb.search(conn, query, limit)` 구현(red→green 6사이클): 필드 매칭·랭킹(일치 필드 수)·빈 결과·대소문자 무시·한국어 부분일치. `tests/test_eb.py`의 `SearchTest`(6케이스) 추가, 전체 30케이스 통과.
- CLI `python eb.py search <질의>` 배선. README·`/eb` SKILL·`eb.py` docstring에 반영.
- `eb-ask` SKILL.md 작성(search→neighbors→path→components/degree로 관련 서브그래프 제시, 읽기 전용).

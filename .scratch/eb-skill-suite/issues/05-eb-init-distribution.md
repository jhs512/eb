# eb-init + 배포 (부트스트랩 스킬 + skills-lock)

Status: done

## Parent

[PRD: eb 5스킬 수트](../PRD.md)

## What to build

빈/기존 저장소에 엔진과 씨앗 데이터를 깔아주는 **부트스트랩** 경로를 만든다([ADR-0002](../../../docs/adr/0002-distribution-skills-first-fetch.md)).

- 스킬: `.claude/skills/eb-init/SKILL.md` 신규. 실행 시 `jhs512/eb`의 **고정 ref(태그/커밋)** 에서 `eb.py`·씨앗 CSV 3종(+선택 `sync.py`·CI 워크플로)을 내려받아 사용자 저장소 루트에 기록한다. 기존 파일이 있으면 **덮어쓰기 전 확인**한다.
- 배포 규약: 5스킬(`eb-init`/`eb-capture`/`eb-recall`/`eb-curate`/`eb-health`)을 `skills-lock.json`에 `source: jhs512/eb`, `sourceType: github`, `skillPath`, `computedHash`로 잠가 설치할 수 있도록 정리한다(기존 `mattpocock/skills` 항목과 동일 형식).

## Acceptance criteria

- [ ] `eb-init` SKILL.md가 고정 ref에서 엔진·씨앗 CSV를 fetch해 저장소 루트에 기록하는 절차를 안내한다.
- [ ] 기존 `eb.py`/`data/*.csv`가 있을 때 덮어쓰기 전에 확인한다.
- [ ] 5스킬을 `source: jhs512/eb`로 설치하는 `skills-lock.json` 규약/예시가 문서화된다.
- [ ] init 후 `python eb.py stats`가 씨앗 그래프에 대해 동작한다.

## Blocked by

None - can start immediately (단, fetch할 ref 핀은 01~03 엔진 작업 완료 후 태깅)

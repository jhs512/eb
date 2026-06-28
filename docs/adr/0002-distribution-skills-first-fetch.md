# 배포: 스킬 우선 + eb-init이 엔진을 고정 ref에서 fetch

eb는 `skills-lock.json`에 `source: jhs512/eb`로 5스킬을 잠가 설치하는 **스킬 우선** 배포를 택한다(기존 `mattpocock/skills` 설치 방식과 동일). 엔진(`eb.py`)과 씨앗 CSV는 스킬에 동봉해 중복 보관하지 않고, `/eb-init` 실행 시 `jhs512/eb`의 **고정 ref(태그/커밋)** 에서 내려받아 사용자 저장소에 기록한다.

## Considered Options

- **템플릿 저장소(clone/fork)** — 가장 단순하나, 기존 저장소에 "스킬만" 들이는 경로가 없다.
- **엔진을 스킬 리소스로 번들** — 오프라인 가능하지만 `eb.py`가 루트와 스킬 폴더에 2벌로 존재해 동기화 부담이 생긴다.

## Consequences

- 엔진을 단일 원천(저장소 루트)에서만 관리하고, 버전 핀이 가능하다(`skills-lock.json`의 해시 핀 철학과 일치). 엔진 갱신은 재-`init`으로 따라간다.
- `/eb-init`은 init 시 네트워크가 필요하다(스킬 자체가 GitHub에서 설치되므로 일관된 전제).

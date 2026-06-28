# 작업지침
- 한국어 사용
- /caveman 스킬 사용
- 일반적인 작업 흐름 : /grill-with-docs, /to-prd, /to-issues, /tdd and /diagnose, /improve-codebase-architecture(이 스킬은 필요할 때만 사용)
- 최대한 mattpocock 스킬들을 활용

## Agent skills

### 이슈 트래커

이슈와 PRD는 로컬 마크다운 파일로 `.scratch/<feature>/` 아래에 보관합니다 (외부 PR은 트리아지 대상 아님). 자세한 내용은 `docs/agents/issue-tracker.md` 참고.

### 트리아지 라벨

표준 5개 역할 라벨을 기본 문자열 그대로 사용합니다: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. 자세한 내용은 `docs/agents/triage-labels.md` 참고.

### 도메인 문서

단일 컨텍스트 — 저장소 루트의 `CONTEXT.md` + `docs/adr/`. 자세한 내용은 `docs/agents/domain.md` 참고.

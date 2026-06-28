# 이슈 트래커: 로컬 마크다운

이 저장소의 이슈와 PRD는 `.scratch/` 아래 마크다운 파일로 보관합니다.

## 규칙

- 기능 하나당 디렉터리 하나: `.scratch/<feature-slug>/`
- PRD는 `.scratch/<feature-slug>/PRD.md`
- 구현 이슈는 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, `01`부터 번호 매김
- 트리아지 상태는 각 이슈 파일 상단 근처의 `Status:` 줄에 기록 (역할 문자열은 `triage-labels.md` 참고)
- 코멘트와 대화 기록은 파일 하단의 `## Comments` 제목 아래에 덧붙임

## 스킬이 "이슈 트래커에 게시(publish)"하라고 할 때

`.scratch/<feature-slug>/` 아래에 새 파일을 만듭니다 (필요하면 디렉터리도 생성).

## 스킬이 "관련 티켓을 가져오라(fetch)"고 할 때

참조된 경로의 파일을 읽습니다. 보통 사용자가 경로나 이슈 번호를 직접 전달합니다.

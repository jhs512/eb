---
name: eb-sheets
description: "현재 eb 저장소의 Google Sheets 미러를 연결한다 — (기본) `<NAME>`(기본값 `eb1`) 이름의 Google Sheet 생성, 서비스 계정과 공유, 동기화 도구(sync.py·workflow·requirements)가 있는지 확인, gh secret/variable 설정, 초기 동기화(CSV → 시트) 실행. CSV가 진실의 원천으로 유지되고 시트는 생성되는 뷰다. 브라우저 자동화(Claude in Chrome 등)가 하드 전제다 — 맨 처음 확인하고 꺼져 있으면 즉시 중단한다. eb-gcp 의 재사용 가능한 자격증명(먼저 1회 실행)과 gh 인증된 GitHub 레포를 요구한다. 트리거 - '지식 시트 등록', '구글 시트 연결', '시트 동기화 설정', 'eb-sheets'."
disable-model-invocation: true
---

# 이 저장소의 Google Sheets 미러 설정

Sheets 미러의 **저장소별** 절반이다. 재사용 가능한 계정 자격증명(GCP 프로젝트·서비스계정·JSON 키)은 **`/eb-gcp`** 에서 온다(먼저 1회 실행). 이 스킬은 *이* 저장소를 스프레드시트에 연결한다. **CSV가 원천**이고 시트는 단방향(CSV → 시트) 뷰다.

## 0. 브라우저 자동화 확인 — 가장 먼저 (하드 게이트)
**다른 무엇이든 하기 전에** 브라우저 구동 도구가 사용 가능·활성화돼 있는지 확인한다(`claude-in-chrome` 또는 Chrome/DevTools MCP).
- **활성화됨** → 계속.
- **활성화 안 됨** → **즉시 중단.** 브라우저 자동화를 켜고 다시 실행하라고 안내한다(공유·콘솔 단계에 필요). 미러를 절반만 연결하지 말 것.

## 1. 전제 조건
- **eb 데이터 존재** — 이 디렉터리에 `data/{nodes,edges,meta}.csv` 가 있어야 한다(없으면 먼저 `/eb-setup`).
- **GCP 자격증명 존재** — `~/.config/eb/sheets-sync.env` 를 읽는다. 없거나 불완전하면(`GCP_PROJECT_ID`·`SA_EMAIL`·`SA_KEY_PATH`) 중단하고 먼저 **`/eb-gcp`** 실행을 안내한다. 여기서 `SA_EMAIL`·`SA_KEY_PATH` 를 로드한다.
- **GitHub 레포 + `gh`** — CI 자동 동기화를 쓸 경우. `gh auth status`(`repo`+`workflow` 스코프). `gh` 미설치면 <https://cli.github.com/> 안내(Windows `winget install GitHub.cli`), 그다음 `! gh auth login`. git 레포가 아니거나 리모트가 없으면 생성 제안(`git init` / `gh repo create <name> --private --source=. --remote=origin`). (CI 없이 로컬 동기화만 할 거면 이 단계는 선택.)

## 2. 대상 스프레드시트 선택 (기본: 새 `<NAME>` 시트, 기본값 `eb1`)
시트 이름은 인스턴스 base 이름 **`<NAME>`** 을 따른다(기본 `eb1`; 큐 캘린더는 `<NAME>-queue`). 한 사람이 여러 비서를 두므로, 이름이 이미 있으면 다음 번호(`eb2`…)를 제안하거나 사용자가 정한 이름(예 `mye`)을 쓴다. ([eb-queue](../eb-queue/SKILL.md) 이름 규칙과 동일.)
탭은 이름으로 관리된다: `_data`(nodes.csv) · `_edges`(edges.csv) · `_meta`(meta.csv). 탭 이름은 나중에 `NODE_TAB`/`EDGE_TAB`/`META_TAB` 환경변수로 변경 가능.

생성/조회에는 **Google Drive MCP 도구** 우선, 없으면 브라우저로 `sheets.new` 구동(§0에서 확인됨).
1. **기존 시트 먼저 검색**(멱등) — `mcp__claude_ai_Google_Drive__search_files` 로 이름 `<NAME>`(예 `eb1`, mimeType `application/vnd.google-apps.spreadsheet`). 발견되면 **재사용** vs **번호를 올려 새로 생성**(eb2…)을 묻는다.
2. **기본 — `<NAME>` 새 시트 생성** — `mcp__claude_ai_Google_Drive__create_file`(mimeType spreadsheet, 이름 `<NAME>`, 기본 `eb1`). 사용자는 다른 이름 또는 기존 시트 URL/ID 제공 가능.
3. **`SPREADSHEET_ID` 확보** — id 또는 URL(`https://docs.google.com/spreadsheets/d/<ID>/edit`)에서.

## 3. 스프레드시트를 서비스 계정과 공유 — ★ 사람만
동기화는 서비스 계정으로 인증하므로 시트에 접근 권한이 필요하다(Drive MCP에 권한 추가 도구 없음 — 사용자가 직접):
1. 대상 스프레드시트를 연다 → **공유**.
2. `~/.config/eb/sheets-sync.env` 의 `SA_EMAIL` 붙여넣기 → 역할 **편집자** → (알림 해제) → 공유.
안 하면 동기화가 `403 PERMISSION_DENIED`. 완료 확인 후 진행.

## 4. 동기화 도구가 있는지 확인
이 저장소에 다음이 있어야 한다(이 eb 저장소엔 이미 있음; `/eb-setup` 로 부트스트랩한 소비자 저장소엔 없을 수 있음 → 고정 ref에서 가져온다):
```bash
# 없을 때만 (REF 는 릴리스 태그 권장)
curl -fsSL https://raw.githubusercontent.com/jhs512/eb/<REF>/sync.py -o sync.py
curl -fsSL https://raw.githubusercontent.com/jhs512/eb/<REF>/requirements.txt -o requirements.txt
mkdir -p .github/workflows
curl -fsSL https://raw.githubusercontent.com/jhs512/eb/<REF>/.github/workflows/sheets-sync.yml -o .github/workflows/sheets-sync.yml
pip install -r requirements.txt          # gspread, google-auth
```
- `.gitignore` 에 `*.json` 포함 재확인(서비스 계정 키 절대 커밋 금지).

## 5. `gh` 로 레포 연동 (CI 자동 동기화용, 선택)
```bash
gh secret set GOOGLE_SA_KEY < "$SA_KEY_PATH"      # 암호화 업로드(출력·커밋 안 됨)
gh variable set SPREADSHEET_ID --body <spreadsheet-id>
```

## 6. 초기 동기화
```bash
SPREADSHEET_ID=… GOOGLE_APPLICATION_CREDENTIALS="$SA_KEY_PATH" python sync.py --data data --dry-run   # 계획만
SPREADSHEET_ID=… GOOGLE_APPLICATION_CREDENTIALS="$SA_KEY_PATH" python sync.py --data data             # 실제(overwrite)
```
방식은 **단순 overwrite**(CSV가 원천이라 증분 불필요). 시트를 손편집했다면 `--check` 로 드리프트 감지(역기록 없음 — CSV를 고쳐 다시 sync). CI를 설정했다면 `data/*.csv` push 마다 Action이 자동 동기화한다.

## 7. CLAUDE.md 기록 — 자기 문서화 (필수)
저장소 루트 `CLAUDE.md`(없으면 생성; 보통 `/eb-setup` 이 이미 만듦)에 이 미러의 운영 사실을 **`eb:sheets` 블록**으로 기록한다. 재실행 시 이 블록만 통째로 교체(마커 유지):
````markdown
<!-- eb:sheets START -->
## Google Sheets 미러
- 시트: `<이름>` · SPREADSHEET_ID `<id>`
- 서비스 계정(편집자): `<SA_EMAIL>`
- 동기화: `SPREADSHEET_ID=<id> GOOGLE_APPLICATION_CREDENTIALS="$SA_KEY_PATH" python sync.py --data data`
- CSV가 원천 · 시트는 단방향 뷰. 키는 레포 밖(`$SA_KEY_PATH`). CI는 secret `GOOGLE_SA_KEY` / var `SPREADSHEET_ID`.
<!-- eb:sheets END -->
````

## 8. 완료
연결된 것 보고: 스프레드시트 URL/id, 공유한 서비스 계정 이메일, (설정 시) `gh` secret/variable. CSV가 단일 원천이고 시트는 단방향 뷰임을 알린다. 키 파일(`SA_KEY_PATH`)은 라이브 자격증명이니 안전 보관(필요시 `/eb-gcp` 로 회전). 자격증명은 재사용 가능 — *다른* 저장소 미러는 이 스킬만 다시 실행하면 되고 `/eb-gcp` 는 불필요.

---
name: eb-github
description: "현재 eb 저장소를 GitHub에 연결하고 CI를 부트스트랩하는 스킬 — git 저장소화(없으면 git init), 비공개 GitHub 리포 생성(확인 후, 멱등), (선택) jhs512/eb 서브모듈 추가, 그리고 이미 설정된 연동(eb-sheets / eb-pages)의 CI 시크릿·변수 등록 + 첫 동기화 확인. gh 인증이 하드 전제. 트리거 - 'github 연결', '깃허브 레포 만들기', 'CI 연결', 'eb-github'."
disable-model-invocation: true
---

# 이 저장소를 GitHub에 연결 + CI 부트스트랩

eb 저장소를 GitHub 리모트에 올리고, 이미 켜둔 연동(Sheets 미러·Pages 배포)의 **CI 자동화**가 돌도록 시크릿/변수를 등록한다. **CSV가 원천**이고 CI는 push마다 파생물(시트·페이지)을 갱신하는 단방향 자동화다.

## 단 하나의 규칙: 확인 후 생성 — 남의 리포 절대 임의 변경 금지
리포·시크릿·변수는 **확인 후 생성**한다. 이미 있으면 재사용한다. **동명 리포가 이미 있고 내용이 다르면** force-push·삭제·가시성 변경을 **절대 임의로 하지 말고 사용자에게 묻는다**(되돌리기 어려움).

## 0. gh 인증 확인 — 가장 먼저 (하드 게이트)
```bash
gh auth status        # 로그인 + 'repo','workflow' 스코프 필요
```
- **OK** → 계속. 활성 계정이 의도한 계정인지 확인(`gh api user --jq .login`).
- **gh 미설치** → <https://cli.github.com/> 안내(Windows `winget install GitHub.cli`), 그다음 `! gh auth login`.
- **스코프 부족** → `! gh auth refresh -h github.com -s repo,workflow`. 리포 **삭제**가 필요하면 `delete_repo` 스코프가 추가로 필요하며, 이는 대화형이라 **사용자가 직접** 실행한다.

## 1. git 저장소 확인/생성
```bash
git rev-parse --is-inside-work-tree 2>/dev/null || git init -b main
```
`.gitignore` 를 점검한다(없으면 만든다) — **자격증명·파생물은 절대 커밋 금지**:
```gitignore
*.json
.env
*.key
*.pem
!skills-lock.json          # 추적해야 할 설정은 허용
*.db
*.sqlite
**/.eb-cache.sqlite
__pycache__/
```
서비스 계정 키(`~/.config/eb/sa-key.json`)는 **레포 밖**에 있어야 한다. 스테이징 후 `git ls-files | grep -i 'sa-key\|\.json'` 로 키가 추적되지 않는지 확인한다.

## 2. (선택) jhs512/eb 서브모듈 — eb 엔진을 직접 개발할 때만
eb 엔진 자체를 계속 고쳐 push할 계획이면 서브모듈로 추가한다. 아니면 건너뛴다(eb-setup 의 고정-ref 사본으로 충분).
```bash
git submodule add https://github.com/jhs512/eb eb
( cd eb && git checkout main )      # 개발하기 쉽게 detached HEAD 대신 main
```

## 3. GitHub 리포 — 확인 후 생성 (멱등)
1. **이름 정하기**(기본: 현재 디렉터리명) 와 **가시성**(기본: `--private`)을 사용자에게 확인.
2. **이미 있는지 확인**: `gh repo view <owner>/<name> --json name,visibility,isEmpty,defaultBranchRef`.
   - **없음** → 생성:
     ```bash
     git add -A && git commit -m "Bootstrap eb repo"     # 첫 커밋(시크릿 없는지 재확인)
     gh repo create <name> --private --source=. --remote=origin --push
     ```
   - **있음** → 내용을 확인하고 사용자에게 묻는다:
     - 다른 이름으로 새 비공개 리포 (안전, 권장), 또는
     - 기존 리포 재사용/덮어쓰기(force-push·삭제·비공개 전환은 ★사용자 결정·사람 실행), 또는
     - GitHub 건너뛰기.
   - **리포 삭제**는 `delete_repo` 스코프가 필요하고 되돌릴 수 없으므로 **사용자가 직접** `gh repo delete`.

## 4. CI 시크릿/변수 등록 (설정된 연동만)
이 저장소에 해당 연동이 켜져 있을 때만 등록한다.
- **Sheets 미러(eb-sheets)** — `~/.config/eb/sheets-sync.env` 의 값을 쓴다:
  ```bash
  gh secret   set GOOGLE_SA_KEY  < "$SA_KEY_PATH"           # 서비스 계정 JSON(암호화 업로드)
  gh variable set SPREADSHEET_ID --body "<spreadsheet-id>"
  ```
- **Pages 배포(eb-pages)**:
  ```bash
  gh secret set CLOUDFLARE_API_TOKEN     # Pages:Edit 토큰(사람이 발급)
  gh secret set CLOUDFLARE_ACCOUNT_ID    # 계정 ID
  ```
시크릿은 `gh secret list`, 변수는 `gh variable list` 로 등록 확인. 워크플로 파일(`.github/workflows/*.yml`)이 참조하는 이름과 정확히 일치해야 한다.

## 5. 첫 푸시·CI 확인
```bash
gh run list --limit 3
```
첫 run이 **시크릿/변수 등록보다 먼저** 트리거되면 빈 값으로 실패할 수 있다(타이밍). 그때는 등록을 마친 뒤 `gh run rerun <run-id>` 로 재실행한다. 성공(`conclusion=success`)을 확인하고 보고한다.

## 6. 완료
보고: 리포 URL·가시성, (추가 시) eb 서브모듈, 등록한 시크릿/변수, CI 동기화 성공 여부. 키 파일은 **라이브 자격증명**이라 레포에 넣지 말 것(필요시 회전). 이후 `data/*.csv` push마다 CI가 시트·페이지를 자동 갱신한다.

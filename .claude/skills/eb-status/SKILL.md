---
name: eb-status
description: "현재 eb 저장소의 연동 배선 상태를 한 번에 점검·보고하는 읽기 전용 스킬 — 그래프 요약, Google Sheets 미러, Cloudflare Pages, GitHub/CI(시크릿·변수·최근 run), eb 서브모듈 최신 여부. 그래프 '내용 건강도'(저신뢰·고아)는 eb-check, 이건 '연결됐나/켜졌나'를 본다. 트리거 - '상태', 'status', '연동 상태', '뭐 켜져있어', 'eb-status'."
disable-model-invocation: true
---

# eb 연동 상태 점검 (읽기 전용)

이 저장소의 **배선 상태**를 한눈에 보고한다 — 무엇이 연결/배포/자동화돼 있는지. **아무것도 바꾸지 않는다(읽기 전용).** 그래프 **내용 건강도**(저신뢰·고아·끊긴 엣지)는 `eb-check`가 보고, 여기선 **연동이 켜졌나**를 본다.

> Windows에서 한국어가 깨지면 명령 앞에 `PYTHONUTF8=1`.

## 점검 항목

### 1. 그래프
```bash
python eb.py stats        # 노드/엣지/평균차수/고아
python eb.py validate     # 끊긴 엣지·빈 필드 (0이면 정상)
```

### 2. Google Sheets 미러 (eb-sheets)
- 자격증명: `~/.config/eb/sheets-sync.env` 존재 + `GCP_PROJECT_ID`/`SA_EMAIL`/`SA_KEY_PATH`.
- 도구: `sync.py`, `.github/workflows/sheets-sync.yml` 존재 여부.
- CI 배선: `gh variable list`(SPREADSHEET_ID), `gh secret list`(GOOGLE_SA_KEY).
- 미설정이면 → `/eb-gcp`(계정 1회) → `/eb-sheets` 안내.

### 3. Cloudflare Pages (eb-pages)
- `web/` 디렉터리, 배포 워크플로(`.github/workflows/*pages*` 또는 `*deploy*`), `wrangler.*` 존재.
- CI 배선: `gh secret list` 에 `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID`.
- 미설정이면 → `/eb-pages` 안내.

### 4. GitHub / CI
```bash
gh repo view --json nameWithOwner,visibility,defaultBranchRef
gh secret list ; gh variable list
gh run list --limit 5
```
가시성(**PUBLIC이면 경고**), 최근 run의 conclusion. 실패가 있으면 `gh run view <id> --log-failed` 로 원인 한 줄 요약. 미설정이면 → `/eb-github` 안내.

### 5. eb 서브모듈 최신 여부 (서브모듈일 때만)
```bash
[ -f .gitmodules ] && ( cd eb && git fetch -q origin main && echo "local $(git rev-parse --short HEAD) / origin $(git rev-parse --short origin/main)" )
```
로컬과 origin/main이 다르면 "업데이트 가능"으로 표시.

## 보고 형식
영역별로 **🟢연결됨 / 🟡부분 / 🔴미설정** + 한 줄 근거 + **다음 액션**(어떤 스킬을 돌리면 되는지)을 표로 보고한다. 설정이 필요하면 해당 스킬을 **안내만** 하고, 이 스킬 안에서 상태를 바꾸지 않는다.

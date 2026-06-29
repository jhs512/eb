---
name: eb-pages
description: "Excel Brain 그래프를 Cloudflare Pages에 클라이언트 사이드 정적 앱으로 배포하도록 셋업하는 스킬(선택). 브라우저가 CSV를 받아 sql.js로 조회하고 cytoscape.js로 그리는 web/ 앱 + GitHub Actions(최초·CSV변경·프론트변경 시에만 배포)를 연결한다. 브라우저 자동화(Claude in Chrome)가 하드 전제, wrangler/gh는 선택 가속기. 트리거 - 'eb 페이지 배포', 'cloudflare pages', '그래프 웹앱 배포', 'eb-pages'."
disable-model-invocation: true
---

# Cloudflare Pages 클라이언트 사이드 앱 배포 셋업

이 저장소의 그래프를 **서버 없이 브라우저에서** 보는 정적 앱(`web/`)을 Cloudflare Pages에 배포하도록 연결한다. 앱은 `data/*.csv`를 fetch → **sql.js(SQLite WASM)** 로 조회 → **cytoscape.js** 로 렌더한다(코어 `eb.py`와 무관, 별도 선택 기능).

## 0. 브라우저 자동화 확인 — 가장 먼저 (하드 게이트)
**무엇이든 하기 전에** 브라우저 구동 도구(`claude-in-chrome`/Chrome MCP) 가용성을 확인한다. 꺼져 있으면 **즉시 중단**하고 켜라고 안내한다(Cloudflare 대시보드·로그인은 사람이 필요). `wrangler`/`gh` 가 있으면 결정적 단계의 가속기로 쓴다.

## 1. 전제 조건
- **web/ 앱 + 워크플로 존재** — 이 저장소엔 이미 있음. `/eb-setup` 로 부트스트랩한 소비자 저장소엔 없을 수 있으니 고정 ref에서 가져온다:
  ```bash
  mkdir -p web .github/workflows
  for f in web/index.html web/app.js web/style.css web/README.md .github/workflows/deploy-pages.yml; do
    curl -fsSL "https://raw.githubusercontent.com/jhs512/eb/<REF>/$f" -o "$f"
  done
  ```
- **GitHub 레포 + `gh`** — `gh auth status`(repo 스코프). 시크릿/변수 설정에 필요.
- **Cloudflare 계정** — 무료 플랜으로 충분.

## 2. Cloudflare Pages 프로젝트 — 확인 후 생성
`wrangler` 가속(있으면): `npx wrangler pages project list` 로 기존 확인, 없으면
```bash
npx wrangler pages project create <project-name> --production-branch=main
```
없으면 브라우저로 Cloudflare 대시보드 → Workers & Pages → Create → Pages → "Direct Upload" 프로젝트를 만든다(이름을 기록). **계정 ID**도 대시보드 우측/`wrangler whoami` 로 확보.

## 3. API 토큰 — ★ 사람만
Cloudflare 대시보드 → My Profile → API Tokens → Create Token → **"Cloudflare Pages: Edit"** 권한으로 생성. 토큰은 라이브 자격증명이라 사람이 직접 발급·복사한다(레포에 넣지 말 것).

## 4. GitHub 레포에 시크릿/변수 등록
```bash
gh secret set CLOUDFLARE_API_TOKEN          # 위 토큰(암호화 업로드)
gh secret set CLOUDFLARE_ACCOUNT_ID         # 계정 ID
gh variable set CF_PAGES_PROJECT --body <project-name>
```

## 5. 최초 배포
워크플로는 **최초·CSV변경·web/변경 시에만** 돈다. 최초 배포는 수동으로:
```bash
gh workflow run deploy-pages.yml
gh run watch
```
이후엔 `data/*.csv`(지식 변경)나 `web/`(프론트 변경) push마다 자동 배포된다(다른 변경엔 안 돔).

## 6. 로컬 미리보기 (선택)
```bash
cp -r data web/data && (cd web && python -m http.server 8000)   # http://localhost:8000
```

## 7. CLAUDE.md 기록 — 자기 문서화 (필수)
저장소 루트 `CLAUDE.md`(없으면 생성)에 이 배포의 운영 사실을 **`eb:pages` 블록**으로 기록한다. 재실행 시 이 블록만 통째로 교체(마커 유지):
````markdown
<!-- eb:pages START -->
## Cloudflare Pages
- 배포 URL: `https://<project>.pages.dev` · 프로젝트 `<name>`
- 앱: `web/` (CSV → sql.js → cytoscape, **읽기 전용 뷰**)
- CI 시크릿: `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`. `data/*.csv`·`web/` push마다 자동 배포.
<!-- eb:pages END -->
````

## 8. 완료
배포 URL(`https://<project>.pages.dev`), GitHub 시크릿/변수 이름, 자동 배포 트리거(데이터·프론트 변경)를 보고한다. API 토큰은 라이브 자격증명이니 안전 보관(필요시 Cloudflare에서 회전).

## 주의
- 앱은 **읽기 전용 뷰**다(브라우저에서 CSV를 조회만, 쓰기 없음). 지식 변경은 `eb-learn`/`eb-clean` 으로 CSV에 하고, push하면 페이지가 갱신된다.
- 코어 `eb.py` 는 stdlib only 유지. 이 기능은 선택(브라우저·wrangler·gh·CDN 의존).

# Cloudflare Pages 클라이언트 사이드 그래프 앱 (선택)

그래프를 **서버 없이 브라우저에서** 보는 정적 앱(`web/`)을 추가하고, GitHub Actions로 Cloudflare Pages에 배포한다(선택 기능). 앱은 `data/*.csv`를 fetch → **sql.js(SQLite WASM)** 로 적재해 조회 → **cytoscape.js** 로 렌더한다. 빌드 단계 없음(CDN). 온보딩은 `eb-pages` 스킬.

## 왜

- **클라이언트 전용**: 사용자가 요청한 대로 백엔드 없이, 브라우저가 CSV를 받아 로컬에서 그래프 DB로 조회. 호스팅 비용·서버 운영 0(정적).
- **엔진 패리티**: 브라우저 sql.js도 SQLite라, eb.py와 같은 SQL/재귀 CTE 사고방식으로 조회한다(중복 구현 최소화).
- **배포 최소화**: 워크플로는 `on.push.paths`(`data/**`·`web/**`·워크플로 자신) + `workflow_dispatch` 로만 돈다 — 매 push가 아니라 **최초(수동)·지식(CSV) 변경·프론트(web/) 변경 시에만** 배포.
- **CSV 단일 원천 유지**: 앱은 읽기 전용 뷰. 배포 시 워크플로가 `data/*.csv`를 `web/data/`로 복사해 동일 출처에서 fetch.

## Considered Options

- **서버 사이드 API + DB** — 운영 부담·비용. (반려: 정적/클라이언트로 충분)
- **빌드 도구(Vite+React)** — 번들/툴체인 추가. (반려: CDN + 바닐라로 빌드 없이 충분, 정적 배포 단순)
- **eb.py로 정적 HTML 사전 렌더** — 인터랙션·대규모에 약함. (반려: 브라우저 sql.js+cytoscape가 인터랙티브)

## Consequences

- 코어 `eb.py`는 stdlib only 유지. 이 기능은 선택(브라우저·CDN·Cloudflare·gh 의존).
- 배포엔 Cloudflare 계정 + GitHub 시크릿(`CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID`) + 변수(`CF_PAGES_PROJECT`) 필요 — `eb-pages` 스킬이 셋업.
- 대규모 시 cytoscape cose 레이아웃이 느려질 수 있다(차후 sigma.js/WebGL 또는 스코프 뷰로 확장 여지).

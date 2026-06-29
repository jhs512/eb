# web — 클라이언트 사이드 지식 뷰어

서버 없이 **브라우저에서만** 동작하는 정적 앱. `data/*.csv`를 fetch → **sql.js(SQLite WASM)** 로 적재해 조회 → 렌더한다. 빌드 없음(CDN 라이브러리).

- `index.html` / `app.js` / `style.css`
- **두 모드** (상단 `[문서 | 그래프]` 토글):
  - **문서 본문 모드(기본)** — 중앙에 선택 노드의 **원문(body)** + 메타·요약·엣지 링크. 좌측 목록·검색으로 이동.
  - **그래프 모드(선택)** — **cytoscape.js** 그래프. 노드 클릭 → 그 노드의 원문을 문서 모드로 연다.
- 검색창: **클라이언트 사이드 SQLite**로 `title/summary/tags/body` 부분일치 조회 → 좌측 목록 필터.

## 로컬 미리보기
```bash
cp -r ../data ./data          # 앱은 ./data/*.csv 를 읽는다(배포 시 워크플로가 복사)
python -m http.server 8000    # http://localhost:8000
```

## 배포
`.github/workflows/deploy-pages.yml` 가 **최초(수동)·CSV 변경·web/ 변경 시에만** Cloudflare Pages로 배포한다. 셋업은 `/eb-pages` 스킬 참고. 설계는 [ADR-0008](../docs/adr/0008-cloudflare-pages-client-side-app.md).

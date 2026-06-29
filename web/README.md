# web — 클라이언트 사이드 지식 뷰어

서버 없이 **브라우저에서만** 동작하는 정적 앱. `data/*.csv`를 fetch → **sql.js(SQLite WASM)** 로 적재해 조회 → 렌더한다. 빌드 없음(CDN 라이브러리).

- `index.html` / `app.js` / `style.css`
- **두 패널 동시** (문서 위 / 그래프 아래) — 각 패널 헤더를 눌러 **접기(최소화)**, 사이 구분선을 **드래그해 크기조절**:
  - **문서 패널(기본 펼침)** — 선택 노드의 **원문(body)** + 메타·요약·엣지 링크.
  - **그래프 패널(기본 접힘)** — 펼치면 **cytoscape.js** 그래프(lazy 빌드). 노드 클릭 → 그 원문이 문서 패널에 뜬다.
- 좌측 목록·검색으로 노드 이동. 그래프에선 **현재 노드가 주황 테두리로 강조**된다.
- 헤더의 **`⬍ 상하 / ⬌ 좌우`** 버튼으로 분할 방향 전환.
- 패널 접힘·분할 방향·크기·선택 노드는 **`localStorage`에 기억**되어 새로고침해도 유지된다.
- 검색창: **클라이언트 사이드 SQLite**로 `title/summary/tags/body` 부분일치 조회 → 좌측 목록 필터.

## 로컬 미리보기
저장소 루트에서 서버를 띄우고 `/web/`을 연다(앱이 `./data/` 실패 시 `../data/`로 폴백 → 복사 불필요):
```bash
cd ..                         # 저장소 루트
python -m http.server 8000    # → http://localhost:8000/web/
```

## 배포
`.github/workflows/deploy-pages.yml` 가 **최초(수동)·CSV 변경·web/ 변경 시에만** Cloudflare Pages로 배포한다. 셋업은 `/eb-pages` 스킬 참고. 설계는 [ADR-0008](../docs/adr/0008-cloudflare-pages-client-side-app.md).

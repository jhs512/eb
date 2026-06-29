# web — 클라이언트 사이드 그래프 뷰어

서버 없이 **브라우저에서만** 동작하는 정적 앱. `data/*.csv`를 fetch → **sql.js(SQLite WASM)** 로 적재해 조회 → **cytoscape.js** 로 그린다. 빌드 없음(CDN 라이브러리).

- `index.html` / `app.js` / `style.css` — 앱
- 검색창: 입력하면 **클라이언트 사이드 SQLite**로 `title/summary/tags/body` 부분일치 조회 후 그래프에서 하이라이트
- 노드 클릭: sql.js로 나가는/들어오는 엣지를 조회해 상세 패널 표시
- 타입별 색, cose 레이아웃

## 로컬 미리보기
```bash
cp -r ../data ./data          # 앱은 ./data/*.csv 를 읽는다(배포 시 워크플로가 복사)
python -m http.server 8000    # http://localhost:8000
```

## 배포
`.github/workflows/deploy-pages.yml` 가 **최초(수동)·CSV 변경·web/ 변경 시에만** Cloudflare Pages로 배포한다. 셋업은 `/eb-pages` 스킬 참고. 설계는 [ADR-0008](../docs/adr/0008-cloudflare-pages-client-side-app.md).

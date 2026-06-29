# web — 클라이언트 사이드 지식 뷰어

서버 없이 **브라우저에서만** 동작하는 정적 앱. `data/*.csv`를 fetch → **sql.js(SQLite WASM)** 로 적재해 조회 → 렌더한다. 빌드 없음(CDN 라이브러리).

- `index.html` / `app.js` / `style.css`
- **두 패널 동시** (문서 위 / 그래프 아래) — 각 패널 헤더를 눌러 **접기(최소화)**, 사이 구분선을 **드래그해 크기조절**:
  - **문서 패널(기본 펼침)** — 선택 노드의 **원문(body)** + 메타·요약·엣지 링크.
  - **그래프 패널(기본 접힘)** — 펼치면 **cytoscape.js** 그래프(lazy 빌드). 노드 클릭 → 그 원문이 문서 패널에 뜬다.
- 좌측 목록·검색으로 노드 이동. 그래프에선 **현재 노드가 주황 테두리로 강조**된다.
- 헤더의 **`⬍ 상하 / ⬌ 좌우`** 버튼으로 분할 방향 전환.
- 패널 접힘·분할 방향·크기·선택 노드는 **`localStorage`에 기억**되어 새로고침해도 유지된다.
- **스마트 검색창**(전부 sql.js, 입력을 자동 감지):
  - **텍스트** — `분산락` 처럼 입력 → 부분일치(라이브).
  - **eb 명령** — `neighbors redis --depth 2 --direction both`, `path a b`, `degree --top 5`, `suggest id`, `orphans` (Enter). eb.py와 동일 결과.
  - **원시 SQL** — `SELECT id,title FROM nodes WHERE type='decision' AND confidence<0.7` (Enter). `id` 컬럼을 결과로.
  - 결과는 좌측 목록 + 그래프에서 강조(나머지는 흐리게).
- **🤖 AI(선택, WebLLM·CDN)** — 켜면 자연어 질문(예: "redis와 동시성이 어떻게 엮이지?")을 LLM이 위 질의로 변환해 실행. WebGPU 미지원/실패 시 텍스트 검색으로 폴백(키·서버 불필요, 모델은 첫 사용 시 브라우저로 다운로드).

## 로컬 미리보기
저장소 루트에서 서버를 띄우고 `/web/`을 연다(앱이 `./data/` 실패 시 `../data/`로 폴백 → 복사 불필요):
```bash
cd ..                         # 저장소 루트
python -m http.server 8000    # → http://localhost:8000/web/
```

## 배포
`.github/workflows/deploy-pages.yml` 가 **최초(수동)·CSV 변경·web/ 변경 시에만** Cloudflare Pages로 배포한다. 셋업은 `/eb-pages` 스킬 참고. 설계는 [ADR-0008](../docs/adr/0008-cloudflare-pages-client-side-app.md).

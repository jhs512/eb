<p align="center">
  <a href="https://github.com/jhs512/eb/actions/workflows/tests.yml"><img src="https://github.com/jhs512/eb/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <img src="https://img.shields.io/badge/Version-0.18.0-brightgreen.svg" alt="Version">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-3.10+-3776ab.svg" alt="Python">
  <img src="https://img.shields.io/badge/Deps-stdlib_only_(core)-orange.svg" alt="stdlib only">
</p>

# Excel Brain (eb) — 에이전트의 무한·구조화된 기억

> 원자료를 넣고, 질문하라. 에이전트가 **타입 지식 그래프**를 만들고·유지하고·탐색한다.
> 지식은 마크다운이 아니라 **스프레드시트(CSV) 묶음**에 살고,
> 그래프 탐색은 프롬프트가 아니라 **결정적 Python 엔진이 보증**한다.

[이 영상](https://www.youtube.com/watch?v=z02Y-1OvWSM)에서 영감을 받아, "타입 있는 노드 · 타입 있는 엣지" 지식 그래프를 **표(CSV)** 로 구현했다.

## 문제

AI 에이전트는 세션마다 잊는다. 개인 지식 시스템은 정보를 길고 느슨하게 연결된 문서 더미로 쌓아, 에이전트가 훑기 비싸고 부정확하다. eb는 지식을 **노드당 하나의 아이디어 + 방향·이유가 있는 엣지**의 그래프로 다뤄, 탐색과 검색을 싸고 정확하게 만든다.

## 5개의 스킬 (`.claude/skills/eb-*`)

각 스킬은 얇은 오케스트레이터이고, 실제 일은 `eb.py`가 한다.

| 스킬 | 역할 |
|---|---|
| **`eb-setup`** | 현재 저장소에 엔진·씨앗 데이터 부트스트랩 |
| **`eb-learn`** | 원자료(텍스트·파일·**유튜브·음성/영상**)를 노드+엣지로 증류해 CSV에 반영(그래프-인지 캡처) |
| **`eb-ask`** | 그래프 조회/탐색 — 관련 서브그래프 |
| **`eb-clean`** | 중복 병합·고아 연결·촘촘화 |
| **`eb-check`** | 신뢰도·고아·끊긴 엣지 점검(리뷰 큐) |

### 차별점 — 그래프 연산을 코드가 보증한다

eb는 조회뿐 아니라 **쓰기에도 그래프 탐색**을 쓴다: `eb-learn`는 추가 *전에* 그래프를 조회해 중복을 잡고 연결처를 제안하며(`search`/`suggest`), `eb-clean`는 `merge`로 결정적으로 병합한다. 그래프 연산을 프롬프트가 아니라 stdlib only `eb.py`가 결정적으로 보증한다.

## 설치

**권장 — 스킬 패키지 매니저** ([skills](https://www.npmjs.com/package/skills)). 8개 eb 스킬을 클론해 여러 에이전트(Claude Code 등)에 한 번에 설치한다:

```bash
npx skills@latest add jhs512/eb --all
```

**대안 — Node 없이 `curl`만.** 고정 ref에서 스킬을 현재 저장소의 `.claude/skills/`로 가져온다:

```bash
curl -fsSL https://raw.githubusercontent.com/jhs512/eb/v0.5.1/install.sh -o eb-install.sh
bash eb-install.sh               # 8개 eb 스킬을 .claude/skills/ 에 설치
```

받은 스크립트는 실행 전에 열어 봐도 된다([`install.sh`](install.sh)). `skills-lock.json`으로 잠가 관리하려면 [`eb-setup` 스킬](.claude/skills/eb-setup/SKILL.md)의 예시 참고.

## 빠른 시작

스킬을 설치했으면, 해당 저장소에서:

```bash
# 1) 엔진·씨앗 데이터 부트스트랩
/eb-setup                        # jhs512/eb 의 고정 ref에서 eb.py·씨앗 CSV를 깔아준다

# 2) 지식 쌓기 / 꺼내기 (에이전트가 스킬로 수행)
/eb-learn  <원자료 | 유튜브 URL | 음성·영상 파일>   # 증류 → 중복/연결 조회 → 승인 → CSV 반영 → validate
/eb-ask   <질문/키워드>      # 관련 서브그래프로 답
/eb-clean                      # 중복 병합·고아 연결
/eb-check                      # 건강도 + 리뷰 큐
```

`<REF>`(릴리스 태그)로 핀하는 것을 권장한다.

### 유튜브·음성/영상 흡수 (선택)

`eb-learn`은 텍스트뿐 아니라 미디어도 흡수한다. 전사는 서드파티가 필요해 **선택 도구 `ingest.py`** 로 분리돼 있다(코어 `eb.py`는 stdlib only — [ADR-0004](docs/adr/0004-media-ingestion-optional-captions-first.md)).

```bash
pip install -r requirements-ingest.txt          # 유튜브 자막(youtube-transcript-api)
python ingest.py "https://youtu.be/<id>"        # 자막 → 전사 텍스트(stdout)
python ingest.py talk.mp3                        # 음성/영상 → whisper 전사(pip install openai-whisper + ffmpeg)
```

자막 우선이라 자막 있는 유튜브는 ML·다운로드 없이 즉시 동작하고, 자막 없는 음성/영상만 whisper로 폴백한다. 전사 텍스트는 그대로 `eb-learn`의 그래프-인지 캡처에 들어가며, 그 미디어는 `source` 노드로 `derived_from` 추적된다.

> **바로 돌려보고 싶다면** → [`samples/`](samples/) 에 실행 가능한 예제 브레인이 있다. `cd samples && python eb.py search 집중` 으로 바로 동작한다. 지식을 추가하는 캡처 흐름은 [`samples/SCENARIO.md`](samples/SCENARIO.md) 참고.

---

## 레퍼런스

### 지식의 원천 — CSV 3개 (`data/`)

| 파일 | 1행 단위 | 컬럼 |
|---|---|---|
| `data/nodes.csv` | 노드 | `id, title, type, namespace, visibility, summary, confidence, tags, body` |
| `data/edges.csv` | 관계 | `source, type, target, weight, note` |
| `data/meta.csv` | 스키마 문서 | `field, applies_to, description` |

- `id`는 kebab-case ASCII, 고유. `tags`는 **세미콜론(`;`) 구분**(쉼표는 CSV 구분자라 피함).
- 엣지 타입: `supports / depends_on / part_of / related_to / derived_from / contradicts / preceded_by / followed_by / authored_by / tagged_with`.
- 지식 추가 = CSV에 행 추가. 엑셀/시트/에디터 무엇으로든.

### 그래프 엔진 — CSV를 DB로 (`eb.py`)

`eb.py`는 3개의 CSV를 SQLite로 올린 뒤, **재귀 CTE(`WITH RECURSIVE`)** 와 표준 라이브러리만으로 그래프 연산을 한다(SQLite는 파이썬 표준 라이브러리라 설치 불필요). **캐시는 자동**이다 — `data/.eb-cache.sqlite` 가 있고 CSV와 일치하면 재사용하고, 없거나 CSV가 바뀌면 다시 만든다(설정·플래그 없음). CSV가 단일 원천이고 캐시는 파생물이라 `.gitignore` 대상이다.

```bash
# 읽기 / 조회
python eb.py stats                                   # 노드/엣지 수, 평균 차수, 타입 분포
python eb.py search 그래프                            # title/summary/tags/body 부분일치(일치 필드 수로 랭크)
python eb.py node decision-csv-source                # 노드 상세 + 나가는 엣지 + 백링크
python eb.py neighbors pillar-knowledge-graph --depth 2 --direction both
python eb.py path fact-sqlite-cte pillar-knowledge-graph            # 무가중 최단경로(홉)
python eb.py path fact-sqlite-cte pillar-knowledge-graph --weighted # 가중 최단경로(다익스트라)
python eb.py suggest pillar-knowledge-graph          # 연결 후보(공통 이웃 + 태그 자카드)
python eb.py components                              # 약연결 요소(무방향)
python eb.py degree --top 5                          # 차수 분포 + 차수 중심성
python eb.py orphans                                 # 엣지 없는 고아 노드
python eb.py health                                  # 건강도 요약 + 리뷰 큐(저신뢰/고아/끊긴 엣지)
python eb.py export --format mermaid                  # 그래프를 다른 뷰로(mermaid/dot/json/graphml)
python eb.py export --format graphml > graph.graphml  # Gephi 등 전문 도구로 대규모 분석
python eb.py export --center pillar-knowledge-graph --depth 2   # 대규모는 스코프 서브그래프만
python eb.py validate                                # 끊긴 엣지/빈 필드 검사
python eb.py types                                   # 노드/엣지 타입별 개수

# 쓰기 (지식 추가/정제) — 추가 후 반드시 validate
python eb.py add-node --id playbook-x --title "엑스 플레이북" --type playbook --tags "graph;howto"
python eb.py add-edge --source playbook-x --type depends_on --target concept-typed-node --weight 0.6 --note "전제"
python eb.py merge old-dup-id canonical-id           # 중복 병합(from 엣지를 into로 재배선 후 삭제)

# CSV 디렉토리 변경: --data <경로> (기본 data)
```

- **search**: `title·summary·tags·body`에서 대소문자 무시 부분일치, 일치 필드 수로 랭크(한국어 포함).
- **suggest**: 공통 이웃 수 + 태그 자카드로 아직 직접 연결 안 된 후보를 점수화. `eb-learn`(붙일 곳)와 `eb-clean`(촘촘화)가 쓴다.
- **merge**: `from` 엣지를 `into`로 재배선하고 `from` 노드를 삭제. self-merge·없는 노드는 거부, 병합으로 생긴 자기 루프·평행 중복은 제거(기존 멀티그래프 중복은 보존).
- **health**: stats 요약 + 리뷰 큐(`--confidence` 임계값). 그래프가 스스로 약한 곳을 드러낸다.
- **export**: 그래프를 엑셀 말고 다른 뷰로 — `--format mermaid`(깃허브 마크다운에 바로 렌더, 소규모/스코프용) · `dot`(Graphviz, 대형은 `sfdp`) · `json`(d3/cytoscape.js/sigma.js) · `graphml`(**Gephi** 등 전문 도구). 끊긴 엣지는 제외. **대규모**는 `--center <id> --depth N`으로 서브그래프만 뽑는다(전체를 그리지 말고 쿼리 결과를 본다 — mermaid는 수백 노드부터 GitHub 렌더 한도·가독성에서 부적합). 렌더 예시는 [`samples/README.md`](samples/README.md#그래프-미리보기-엑셀-말고-다른-뷰), 설계는 [ADR-0006](docs/adr/0006-graph-export-views.md).
- **path**: 기본은 무가중 BFS(홉 최소). `--weighted` 면 `weight`를 비용으로 본 다익스트라.
- **add-node/add-edge**: 빈/중복 id, 없는 노드 참조를 거부(`--allow-missing`으로 우회).

### 캐시 (자동 — 설정 불필요)

조회는 항상 SQLite로 처리되며, **캐시는 자동**이다. 첫 조회 때 `data/.eb-cache.sqlite` 를 만들고, 이후엔 CSV가 그대로면 재사용, **CSV가 바뀌면(크기·나노초 mtime 시그니처 불일치) 자동 재생성**한다. 별도 명령·플래그가 없다. 캐시 디렉토리가 읽기 전용이면 조용히 인메모리로 폴백한다(실패하지 않음). CSV가 단일 원천이고 캐시는 파생물이라 `.gitignore` 대상이다.

### 선택: Google 스프레드시트 동기화 (`sync.py`)

CSV가 원천이고 시트는 파생되는 **뷰**다. 3개의 CSV를 같은 이름의 탭(`_data`/`_edges`/`_meta`)으로 단방향 동기화한다.

> **온보딩 스킬(가이드형 셋업)**: 서비스 계정·키 발급과 시트 등록이 처음이면 두 스킬이 브라우저(+gcloud)로 도와준다 — `/eb-gcp`(Google 계정당 1회: 프로젝트·API·서비스계정·JSON 키 → `~/.config/eb/sheets-sync.env`) → `/eb-sheets`(이 저장소: `지식` 시트 생성·서비스계정 공유·`gh` secret/variable·초기 동기화). 아래 수동 단계를 자동화한 것이다. 자세한 결정은 [ADR-0005](docs/adr/0005-sheets-onboarding-skills.md).

```bash
pip install -r requirements.txt        # gspread, google-auth (sync 전용)
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/eb/sa-key.json
export SPREADSHEET_ID=...
python sync.py --data data --dry-run    # 계획만
python sync.py --data data              # 동기화
python sync.py --data data --check      # 드리프트 감지(역기록 없음 — CSV를 고쳐 다시 sync)
```

- 동기화는 **CSV → 시트 단방향**. 시트를 손편집했다면 `--check`로 드리프트를 감지한다(보고만, 드리프트 시 종료코드 1).
- 대상 시트를 **서비스 계정 이메일과 편집자로 공유**해야 한다(안 하면 `403`).
- GitHub Action(`.github/workflows/sheets-sync.yml`): `data/*.csv` push 시 자동 동기화. Secret `GOOGLE_SA_KEY` + Variable `SPREADSHEET_ID`.

### 선택: 브라우저 그래프 앱 (Cloudflare Pages)

[`web/`](web/) 는 **서버 없이 브라우저에서만** 도는 정적 앱이다 — `data/*.csv`를 fetch → **sql.js(SQLite WASM)** 로 조회 → **cytoscape.js** 로 리치하게 렌더(검색·클릭 상세, 전부 클라이언트 사이드). GitHub Action(`.github/workflows/deploy-pages.yml`)이 **최초(수동 dispatch)·CSV 변경·`web/` 변경 시에만** Cloudflare Pages로 배포한다(매 push 아님). 셋업은 [`eb-pages` 스킬](.claude/skills/eb-pages/SKILL.md), 설계는 [ADR-0008](docs/adr/0008-cloudflare-pages-client-side-app.md).

```bash
python -m http.server 8000      # 저장소 루트에서 → http://localhost:8000/web/
```
(앱은 `./data/` 실패 시 `../data/`로 폴백하므로, 루트에서 띄우고 `/web/`을 열면 복사 없이 동작한다.)

## 테스트

네트워크/서드파티 없이 그래프 엔진과 sync 드리프트 로직을 전부 검증한다. `main`/PR push 마다 GitHub Actions(Python 3.10·3.12)에서 자동 실행([워크플로](.github/workflows/tests.yml)).

```bash
python -m unittest discover -s tests -p "test_*.py"
# 또는
python -m pytest tests/ -q
```

3층으로 검증한다: **단위/골든**(엔진·캡처 불변식) + **계약**(스킬↔엔진 명령 일치, `test_skills.py`) + **evals**(eb-learn 증류의 비결정적 품질 — [`evals/`](evals/), 합격률 채점). evals 채점기는 결정적이라 단위테스트로 보호하고, 모델 호출만 선택적이다:

```bash
python evals/run_evals.py                       # 오프라인(녹화된 후보로 채점)
python evals/run_evals.py --solver anthropic --runs 5   # 실제 모델 비결정성 측정
```

## 저장소 구조

```
eb/
├── data/
│   ├── nodes.csv      # 노드(지식의 원천)
│   ├── edges.csv      # 엣지(관계)
│   └── meta.csv       # 스키마 문서
├── eb.py              # 그래프 엔진(CSV -> SQLite -> 재귀 CTE/구조 연산), stdlib only
├── ingest.py          # (선택) 유튜브·음성/영상 -> 전사 텍스트(자막 우선 + whisper)
├── sync.py            # (선택) CSV -> Google 시트 동기화 + 드리프트 검사(--check)
├── web/               # (선택) 브라우저 그래프 앱(sql.js + cytoscape, 클라이언트 사이드)
├── evals/             # eb-learn 증류 품질 평가(비결정적, 합격률 채점)
├── tests/             # 오프라인 테스트(엔진 + sync)
├── CONTEXT.md         # 도메인 용어집
├── docs/adr/          # 아키텍처 결정 기록
├── samples/           # 실행 가능한 예제 브레인 + 캡처 시나리오(SCENARIO.md)
├── .claude/skills/eb-*/SKILL.md     # 5스킬(init/capture/recall/curate/health)
└── .github/workflows/
    ├── tests.yml       # 코어 테스트 CI (의존성 0)
    └── sheets-sync.yml # (선택) 자동 동기화
```

## 설계 한눈에

| 측면 | Excel Brain (eb) |
|---|---|
| 지식의 원천 | **CSV 3개** (엑셀/구글시트/에디터로 편집) |
| 엔진 | **Python(SQLite 재귀 CTE + 구조 연산) — 결정적**, stdlib only |
| 제품 | **5스킬** (init/capture/recall/curate/health) |
| 시트 | CSV → 시트 동기화(overwrite, 선택) |

[MIT](LICENSE)

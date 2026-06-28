# PRD: eb — 에이전트의 기억을 위한 5스킬 수트

Status: ready-for-agent

> 관련 결정: [ADR-0001](../../docs/adr/0001-eb-as-skill-suite.md) · [ADR-0002](../../docs/adr/0002-distribution-skills-first-fetch.md) · [ADR-0003](../../docs/adr/0003-graph-aware-capture.md) · 용어는 [CONTEXT.md](../../CONTEXT.md) 따름.

## Problem Statement

나는 [이 영상](https://www.youtube.com/watch?v=z02Y-1OvWSM)에서 영감을 받아 만든 `eb`(Excel Brain)를 가지고 있다. 지금은 `eb.py` 엔진 + CSV 3종 + `/eb` 스킬 **하나**로 구성된 "도구"에 가깝다. 하지만 내가 원하는 건 **"에이전트에게 무한·구조화된 기억을 주는 제품"** 이고, 그걸 다른 저장소에도 들일 수 있는 **스킬 저장소**다. 현재는 (1) 제품 서사가 없고, (2) 수집→조회→정제의 작업 루프가 한 스킬에 뭉쳐 있으며, (3) 다른 저장소에 "스킬만" 설치할 경로가 없고, (4) 지식 추가가 그래프를 보지 않아 고아·중복이 생기기 쉽다.

## Solution

`eb`를 결정적 `eb.py` 엔진 위에 올린 **5개의 작은 스킬 묶음**으로 제품화한다.

- `eb-init` — 사용자 저장소에 엔진·씨앗 데이터를 깔아주는 부트스트랩
- `eb-capture` — 원자료를 노드+엣지로 **증류**해 CSV에 반영, 추가 전 그래프를 조회하는 **그래프-인지 캡처**
- `eb-recall` — 그래프를 탐색해 답을 얻는 **조회**
- `eb-curate` — 중복 병합·고아 연결·드리프트 교정의 **정제**
- `eb-health` — 신뢰도·고아·끊긴 엣지를 모은 점검 리포트

배포는 **스킬 우선**: `skills-lock.json`에 `source: jhs512/eb`로 잠가 설치하고, `/eb-init`이 `jhs512/eb`의 고정 ref에서 `eb.py`·씨앗 CSV를 내려받는다. 차별점은 조회·추가의 그래프 연산을 프롬프트가 아니라 **Python 엔진이 보증**한다는 것이다. 이를 위해 엔진에 `search`/`merge`/`suggest` 세 명령을 추가한다(stdlib only 유지).

## User Stories

1. 에이전트로서, 나는 세션이 바뀌어도 잃지 않는 구조화된 기억을 원한다, 그래서 매번 처음부터 다시 배우지 않아도 된다.
2. 새 사용자로서, 나는 README 상단에서 "이게 무엇이고 왜 필요한지"를 30초 안에 이해하고 싶다, 그래서 도입을 빠르게 결정할 수 있다.
3. 사용자로서, 나는 `skills-lock.json`에 `source: jhs512/eb`로 5스킬을 잠가 설치하고 싶다, 그래서 기존 mattpocock 스킬과 동일한 방식으로 버전을 고정할 수 있다.
4. 사용자로서, 나는 빈 저장소에서 `/eb-init`을 실행해 `eb.py`·씨앗 CSV 3종을 한 번에 깔고 싶다, 그래서 곧바로 지식을 쌓기 시작할 수 있다.
5. 사용자로서, 나는 `/eb-init`이 고정 ref에서 엔진을 가져오게 하고 싶다, 그래서 엔진이 한 곳(저장소 루트)에서만 관리되고 중복 보관되지 않는다.
6. 사용자로서, 나는 이미 `eb.py`가 있는 저장소에서 `/eb-init`이 덮어쓰기 전에 확인하길 원한다, 그래서 기존 데이터를 잃지 않는다.
7. 지식 수집자로서, 나는 긴 텍스트·대화를 `/eb-capture`에 던지면 노드와 엣지로 **증류**되길 원한다, 그래서 직접 CSV 행을 짜지 않아도 된다.
8. 지식 수집자로서, 나는 캡처가 추가 *전에* 그래프를 조회해 **중복 후보**를 보여주길 원한다, 그래서 같은 개념을 두 번 만들지 않는다.
9. 지식 수집자로서, 나는 캡처가 새 노드를 붙일 **기존 노드(엣지 타깃)** 를 제안하길 원한다, 그래서 고아 노드가 생기지 않는다.
10. 지식 수집자로서, 나는 캡처가 추가하기 전에 후보 노드/엣지를 보여주고 **내 승인**을 받길 원한다, 그래서 잘못된 지식이 그래프에 들어가지 않는다.
11. 지식 수집자로서, 나는 캡처가 끝나면 자동으로 `validate`가 돌아 끊긴 엣지 0을 확인해주길 원한다, 그래서 그래프가 항상 일관된다.
12. 지식 수집자로서, 나는 캡처가 매 수집마다 **출처(source) 노드**를 만들고 새 지식을 `derived_from`/`authored_by`로 연결해주길 원한다, 그래서 "이 지식이 어디서 왔는지" 추적할 수 있다.
13. 조회자로서, 나는 키워드로 `/eb-recall`을 호출해 제목·요약·태그·본문에서 **유사 노드**를 찾고 싶다, 그래서 관련 지식을 빠르게 찾는다.
14. 조회자로서, 나는 두 노드 사이의 **최단 경로**(무가중/가중)를 묻고 싶다, 그래서 개념들이 어떻게 연결되는지 이해한다.
15. 조회자로서, 나는 한 노드의 **이웃**(깊이·방향 지정)을 보고 싶다, 그래서 한 주제 주변의 지식 지형을 본다.
16. 조회자로서, 나는 약연결 **요소**와 **차수 중심성**을 보고 싶다, 그래서 그래프의 큰 덩어리와 허브 노드를 파악한다.
17. 조회자로서, 나는 recall 결과가 다른 에이전트의 답변에 주입하기 좋은 **관련 서브그래프** 형태로 나오길 원한다, 그래서 기억을 RAG처럼 쓸 수 있다.
18. 정제자로서, 나는 중복 노드 둘을 `/eb-curate`로 **병합**하고 싶다, 그래서 엣지가 한쪽으로 재배선되고 중복이 사라진다.
19. 정제자로서, 나는 고아 노드 목록과 각 고아에 대한 **연결 제안**을 받고 싶다, 그래서 끊긴 지식을 그래프에 다시 잇는다.
20. 정제자로서, 나는 기존 노드에 대해 `suggest`로 **추가 연결 후보**를 받아 그래프를 촘촘하게 만들고 싶다, 그래서 시간이 지날수록 그래프가 풍부해진다.
21. 정제자로서, 나는 지식이 갱신될 때 옛 노드를 덮어쓰지 않고 새 노드를 만들어 `preceded_by`(모순이면 `contradicts`)로 잇고 싶다, 그래서 지식의 변천 이력이 보존된다.
22. 점검자로서, 나는 `/eb-health`로 노드/엣지 수·타입 분포·평균 차수 요약을 보고 싶다, 그래서 그래프 규모를 한눈에 안다.
23. 점검자로서, 나는 `eb-health`가 **신뢰도가 낮거나 오래된 노드**를 "리뷰 큐"로 모아주길 원한다, 그래서 약한 지식을 우선 보강한다.
24. 점검자로서, 나는 `eb-health`가 끊긴 엣지·빈 필드·고아를 한 리포트로 묶어주길 원한다, 그래서 정제 작업의 할 일 목록을 얻는다.
25. 사용자로서, 나는 모든 스킬이 결국 `eb.py`(stdlib only)를 호출하는 얇은 래퍼이길 원한다, 그래서 그래프 연산이 프롬프트가 아니라 결정적 코드로 보증된다.
26. 사용자로서, 나는 CSV를 엑셀/구글시트/에디터로 직접 열어 편집해도 스킬이 깨지지 않길 원한다, 그래서 CSV가 단일 원천이라는 약속이 지켜진다.
27. 사용자로서, 나는 선택적으로 `sync.py`로 CSV를 구글시트에 단방향 동기화하고 드리프트를 감지하고 싶다, 그래서 팀과 뷰를 공유하되 원천은 CSV로 유지한다.
28. 기여자로서, 나는 새 엔진 명령(`search`/`merge`/`suggest`)에 오프라인 단위테스트가 있길 원한다, 그래서 의존성·네트워크 없이 CI에서 검증된다.
29. 사용자로서, 나는 한국어가 깨지지 않게 동작하길 원한다, 그래서 Windows에서도 `PYTHONUTF8=1` 안내대로 쓸 수 있다.
30. 사용자로서, 나는 README가 5스킬 빠른 시작 → 엔진 명령 레퍼런스 순으로 정리되길 원한다, 그래서 "무엇/왜" 다음에 "어떻게"를 찾는다.

## Implementation Decisions

**스킬 묶음 (`.claude/skills/eb-*`)**
- 5개 스킬을 신규 생성: `eb-init`, `eb-capture`, `eb-recall`, `eb-curate`, `eb-health`. 각 SKILL.md는 **얇은 오케스트레이터**로, 실제 연산은 모두 `eb.py` 호출에 위임한다.
- 기존 `.claude/skills/eb`(단일 `/eb`)는 `eb-capture` + `eb-recall`로 분화한 뒤 제거한다.
- `writing-great-skills` 스킬의 규약을 따라 각 SKILL.md의 frontmatter(name/description/트리거)를 작성한다.

**배포 / `eb-init`**
- `skills-lock.json` 규약(`source`/`sourceType: github`/`skillPath`/`computedHash`)에 맞춰 5스킬을 `source: jhs512/eb`로 설치 가능하게 한다.
- `eb-init`은 실행 시 `jhs512/eb`의 **고정 ref(태그/커밋)** 에서 `eb.py`·씨앗 CSV 3종(+선택 `sync.py`·CI)을 내려받아 사용자 저장소 루트에 기록한다. 기존 파일이 있으면 **덮어쓰기 전 확인**한다.

**엔진 보강 (`eb.py`, stdlib only)**
- `eb.search(conn, query, ...) -> rows` / CLI `search`: `nodes.csv`의 `title·summary·tags·body`에서 질의어로 후보 노드를 찾는다. SQLite `LIKE`(또는 가용 시 FTS) 기반, 일치 필드 수로 랭크.
- `eb.merge(data_dir, from_id, into_id)` / CLI `merge`: `from_id`를 향하거나 출발하는 모든 엣지를 `into_id`로 **재배선**하고 `from_id` 노드를 삭제한다. CSV 안전 쓰기(기존 `add-node`/`add-edge` 패턴 재사용). self-merge·존재하지 않는 id는 거부.
- `eb.suggest(conn, id, ...) -> candidates` / CLI `suggest`: 대상 노드에 대해 **공통 이웃 수, 태그 자카드 유사도, 2홉 도달이나 직접 엣지 없음** 등 그래프 구조 신호로 연결 후보를 점수화해 제안한다.
- 새 명령 모두 `--data` 경로 인자와 기존 출력 컨벤션(사람이 읽는 텍스트)을 따른다. `--db` 캐시 경로와도 호환.

**캡처 파이프라인 (`eb-capture`)**
- 단계: (1) LLM이 원자료를 후보 노드/엣지로 증류 → (2) 각 후보에 대해 `eb.py search`/`neighbors`로 **중복·연결 후보 조회** → (3) 사용자에게 후보(중복 경고·제안 엣지 포함) 제시 후 **승인 게이트** → (4) `eb.py add-node`/`add-edge`로 반영 → (5) `eb.py validate`.
- 매 캡처 단위마다 `source` 타입 노드 1개를 만들고 새 노드들을 `derived_from`/`authored_by`로 연결한다(출처 추적).
- 지식 갱신 시 덮어쓰지 않고 새 노드 + `preceded_by`(모순이면 `contradicts`)로 잇는다(이력 보존).

**스키마 / 데이터 규약 (변경 없음)**
- `nodes.csv(id,title,type,namespace,visibility,summary,confidence,tags,body)`, `edges.csv(source,type,target,weight,note)`, `meta.csv`. `id`는 kebab-case ASCII 고유, `tags`는 세미콜론 구분. 엣지 타입 집합 유지.

**소개 문서 (README)**
- 제품 서사 우선으로 재작성: 한 줄 가치 → 문제 → 5스킬 → 결정적 엔진 차별점 → 빠른 시작(`skills-lock` → `/eb-init` → `/eb-capture`/`/eb-recall`) → 데이터 규약·엔진 명령 전체·시트 동기화(레퍼런스).

## Testing Decisions

- **좋은 테스트의 기준**: 외부 동작만 검증한다. `eb` 모듈 함수의 입력(임시 데이터 디렉토리)과 출력(반환 rows/구조, CSV 변경 결과)만 보고, 내부 SQL·구현 세부는 보지 않는다.
- **이음새(seam)**: 단일·기존 이음새인 **`eb` 모듈 함수 API**. 신규 `eb.search`/`eb.merge`/`eb.suggest`도 여기에 붙는다. 스킬(프롬프트)은 검증된 엔진을 호출만 하므로 단위테스트 대상이 아니다.
- **대상 모듈**: `eb.py`의 신규 함수 3종. `search`(랭킹·필드 매칭·빈 결과), `merge`(엣지 재배선·노드 삭제·self/존재X 거부·멱등), `suggest`(공통 이웃·태그 자카드 점수·직접 연결 제외).
- **선행 사례(prior art)**: `tests/test_eb.py`의 `write_graph` 픽스처 + `setUp`에서 `eb.load_db(tmp)` 후 함수 호출 후 단언하는 패턴을 그대로 따른다. CSV를 변경하는 `merge`는 변경 후 재로드해 결과를 단언한다(`add-node` 테스트가 있다면 그 패턴 재사용).
- **CI**: 기존 `.github/workflows/tests.yml`(의존성 0, Python 3.10·3.12)에서 그대로 실행되어야 한다.

## Out of Scope

- **시각화 export**(`eb.py export --mermaid`/정적 HTML 그래프 뷰): 가치 있으나 v1 이후. "CSV가 원천, 나머지는 파생 뷰" 원칙에 맞는 후속 항목.
- **recall의 정식 RAG 인터페이스**(다른 에이전트가 호출하는 표준 기억-주입 API): 개념은 user story 17에 남기되, v1은 사람이 읽는 recall 출력까지만.
- **템플릿 저장소(clone/fork) 배포 경로**: 배포는 스킬 우선으로 일원화([ADR-0002](../../docs/adr/0002-distribution-skills-first-fetch.md)).
- **인프라 스킬**(`setup-gcp`/`setup-sheets-sync` 류): 시트 동기화는 기존 `sync.py`로 충분, 별도 스킬은 만들지 않는다.
- **엔진의 영속 그래프 DB로의 전환**: 규모 한계 질문(`question-scale-limit`)은 열어 두되, 인메모리/파일 SQLite 범위 유지.

## Further Notes

- `eb.py`는 **stdlib only**를 절대 깨지 않는다. 서드파티가 필요한 기능(예: 시트 동기화)은 선택 의존으로 격리한다.
- 엔진이 `eb-init` 리소스로 중복 보관되지 않도록 fetch-from-ref를 택했으므로([ADR-0002](../../docs/adr/0002-distribution-skills-first-fetch.md)), ref 핀 갱신 절차를 README 빠른 시작에 함께 적는다.
- 다음 단계: `/to-issues`로 이 PRD를 (a) 엔진 3명령 + 테스트, (b) 5스킬 작성, (c) 배포/`eb-init`, (d) README 재작성 단위의 이슈로 분해 → `/tdd`로 엔진부터 구현.

<p align="center">
  <img src="https://img.shields.io/badge/Version-0.1.0-brightgreen.svg" alt="Version">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-3.10+-3776ab.svg" alt="Python">
  <img src="https://img.shields.io/badge/Deps-stdlib_only_(core)-orange.svg" alt="stdlib only">
</p>

# Excel Brain (eb) — CSV가 지식의 원천인 타입 그래프

> [Infinite Brain(ib)](https://github.com/jhs512/ib) 기반. 단, **마크다운이 없습니다.**
> 오직 **3개의 CSV 파일**이 지식의 단일 원천이고, **Python이 CSV를 DB로 올려 그래프 연산**을 합니다.
> 선택적으로 Google 스프레드시트에 동기화합니다.

ib가 마크다운 노드/엣지였다면, eb는 같은 "타입 있는 노드 · 타입 있는 엣지" 모델을 **표(CSV)** 로 다룹니다. 엑셀·구글시트로 바로 열어 편집하고, `eb.py` 로 그래프를 질의합니다. 코어는 **서드파티 의존성이 전혀 없습니다**(파이썬 표준 라이브러리만).

## 지식의 원천 — CSV 3개 (`data/`)

| 파일 | 1행 단위 | 컬럼 |
|---|---|---|
| `data/nodes.csv` | 노드 | `id, title, type, namespace, visibility, summary, confidence, tags, body` |
| `data/edges.csv` | 관계 | `source, type, target, weight, note` |
| `data/meta.csv` | 스키마 문서 | `field, applies_to, description` |

- `tags`는 **세미콜론(`;`) 구분**(쉼표는 CSV 구분자라 피함). 예: `graph;schema`.
- 엣지 타입: `supports / depends_on / part_of / related_to / derived_from / contradicts / preceded_by / followed_by / authored_by / tagged_with`.
- 지식 추가 = CSV에 행 추가. 엑셀/시트/에디터 무엇으로든.

## 그래프 엔진 — CSV를 DB로 (`eb.py`)

`eb.py`는 3개의 CSV를 **인메모리 SQLite**로 적재한 뒤, **SQLite 재귀 CTE(`WITH RECURSIVE`)** 로 그래프 연산을 합니다. 별도 그래프 라이브러리 없이 BFS 이웃 탐색·최단 경로가 됩니다.

```bash
python eb.py stats                                   # 요약: 노드/엣지 수, 평균 차수, 타입 분포
python eb.py node decision-csv-source                # 노드 상세 + 나가는 엣지 + 백링크
python eb.py neighbors pillar-knowledge-graph --depth 2 --direction both
python eb.py path fact-sqlite-cte pillar-knowledge-graph   # 최단 경로(홉 수)
python eb.py orphans                                 # 엣지 없는 고아 노드
python eb.py validate                                # 끊긴 엣지/빈 필드 검사
python eb.py types                                   # 노드/엣지 타입별 개수
# CSV 디렉토리 변경: --data <경로> (기본 data)
```

예시 출력:

```
$ python eb.py path fact-sqlite-cte pillar-knowledge-graph
fact-sqlite-cte -> decision-csv-source -> pillar-knowledge-graph   (홉 2)
```

`--direction`: `out`(나가는 엣지), `in`(들어오는/백링크), `both`(무방향). 사이클은 방문 경로 검사로 자동 회피합니다.

## 선택: Google 스프레드시트 동기화 (`sync.py`)

CSV가 원천이고 시트는 생성되는 **뷰**입니다. 3개의 CSV를 같은 이름의 탭(`_data`/`_edges`/`_meta`)으로 올립니다(단순 overwrite — CSV가 원천이라 증분 불필요).

```bash
pip install -r requirements.txt        # gspread, google-auth (sync 전용)
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/eb/sa-key.json   # 서비스 계정 키
export SPREADSHEET_ID=...               # 대상 시트 ID
python sync.py --data data --dry-run    # 계획만
python sync.py --data data              # 동기화
```

- 인증: 키 파일 경로(`GOOGLE_APPLICATION_CREDENTIALS`) 또는 키 내용(`GOOGLE_SA_KEY`, CI용).
- 대상 시트를 **서비스 계정 이메일과 편집자로 공유**해야 합니다(안 하면 `403`).
- GitHub Action(`.github/workflows/sheets-sync.yml`): `data/*.csv` push 시 자동 동기화. Secret `GOOGLE_SA_KEY` + Variable `SPREADSHEET_ID` 설정.
- GCP 프로젝트/서비스 계정/키 발급은 ib의 [`setup-gcp`](https://github.com/jhs512/ib) 절차와 동일합니다(키는 레포 밖에 두고 `.gitignore`의 `*.json`로 보호).

## 테스트

네트워크/서드파티 없이 그래프 연산을 전부 검증합니다(11 케이스):

```bash
python -m unittest discover -s tests -p "test_*.py"
# 또는
python -m pytest tests/ -q
```

## 저장소 구조

```
eb/
├── data/
│   ├── nodes.csv      # 노드(지식의 원천)
│   ├── edges.csv      # 엣지(관계)
│   └── meta.csv       # 스키마 문서
├── eb.py              # 그래프 엔진(CSV -> SQLite -> 재귀 CTE 연산), stdlib only
├── sync.py            # (선택) CSV -> Google 시트 동기화
├── requirements.txt   # sync 전용 의존성
├── tests/test_eb.py   # 오프라인 테스트
└── .github/workflows/sheets-sync.yml   # (선택) 자동 동기화
```

## ib와의 관계

| | Infinite Brain (ib) | Excel Brain (eb) |
|---|---|---|
| 원천 | 마크다운 노드 + frontmatter | **CSV 3개** |
| 엔진 | 스킬(프롬프트) 기반 그래프 탐색 | **Python(SQLite 재귀 CTE) 그래프 연산** |
| 편집 | 에디터/Obsidian | **엑셀/구글시트/에디터** |
| 시트 | 마크다운 → 시트 미러(증분) | CSV → 시트 동기화(overwrite) |

[MIT](LICENSE)

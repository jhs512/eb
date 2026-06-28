---
name: eb
description: Query and edit the Excel Brain (eb) CSV-native typed knowledge graph in this repo. Use when the user wants to look up/add knowledge nodes or relations, find paths/neighbors/components, check graph integrity, or otherwise operate on data/{nodes,edges,meta}.csv via eb.py. Triggers include "eb graph", "지식 그래프", "노드 추가", "엣지 추가", "최단 경로", "이웃", "고아 노드", "validate graph".
---

# eb — Excel Brain 그래프 조작

`eb.py`(stdlib only)는 `data/`의 CSV 3개를 인메모리 SQLite로 올려 그래프 연산을 한다.
**CSV가 단일 원천**이다. 지식 추가/수정은 CSV 행 추가/편집이고, 질의는 `eb.py`로 한다.

> Windows에서 한국어가 깨지면 명령 앞에 `PYTHONUTF8=1`을 붙인다.

## 데이터 규약 (어기면 끊긴 그래프가 됨)
- 노드(`data/nodes.csv`): `id,title,type,namespace,visibility,summary,confidence,tags,body`
- 엣지(`data/edges.csv`): `source,type,target,weight,note`
- `id`는 kebab-case ASCII, 고유. `tags`는 **세미콜론(`;`) 구분**(쉼표 금지 — CSV 구분자).
- 엣지 타입: `supports / depends_on / part_of / related_to / derived_from / contradicts / preceded_by / followed_by / authored_by / tagged_with`.

## 읽기 (질의)
```bash
python eb.py stats                                   # 노드/엣지 수, 평균 차수, 타입 분포
python eb.py node <id>                                # 노드 상세 + 나가는 엣지 + 백링크
python eb.py neighbors <id> --depth 2 --direction both
python eb.py path <src> <dst>                         # 무가중 최단경로(홉)
python eb.py path <src> <dst> --weighted              # 가중 최단경로(다익스트라, weight=비용)
python eb.py components                               # 약연결 요소(무방향)
python eb.py degree --top 5                           # 차수 분포 + 차수 중심성
python eb.py orphans                                  # 엣지 없는 노드
python eb.py types                                    # 타입별 개수
```

## 쓰기 (지식 추가) — 항상 검사 포함
직접 CSV를 편집해도 되지만, CLI가 중복/끊김을 막아준다. **추가 후 반드시 `validate`.**
```bash
python eb.py add-node --id <id> --title "<제목>" --type <type> --tags "a;b"
python eb.py add-edge --source <id> --type <엣지타입> --target <id> --weight 0.6 --note "<설명>"
python eb.py validate                                 # 끊긴 엣지/빈 필드 검사 (0이어야 정상)
```
- `add-node`: 빈/중복 id 거부.
- `add-edge`: `source`/`target`이 없는 노드면 거부(`--allow-missing`으로만 우회).

## 대규모 (선택)
```bash
python eb.py --db graph.sqlite build-db               # 파일 SQLite로 캐시
python eb.py --db graph.sqlite stats                  # CSV보다 최신이면 재적재 없이 재사용
python eb.py --db graph.sqlite --rebuild stats        # 강제 재적재
```

## 워크플로 권장
1. 추가 전 `python eb.py node <id>`로 중복/맥락 확인.
2. `add-node` → 관련 노드로 `add-edge`(고아 만들지 말 것).
3. `python eb.py validate`로 끊긴 엣지 0 확인.
4. 변경 파일은 `data/*.csv`. 커밋은 사용자가 요청할 때만.

## 주의
- 코어(`eb.py`/테스트)는 **의존성 0** 유지. 새 기능이 서드파티를 요구하면 선택 의존으로.
- Google 시트 동기화(`sync.py`)는 별개·선택이며 자격증명 필요.

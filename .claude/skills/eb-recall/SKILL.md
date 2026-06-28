---
name: eb-recall
description: Excel Brain(eb) 그래프를 탐색해 답을 얻는 조회 스킬. 키워드/노드로 관련 서브그래프(유사 노드 + 이웃/경로/요소)를 찾는다. 트리거 - "조회", "recall", "이웃", "최단 경로", "관련 노드 찾기", "그래프에서 찾아줘".
---

# eb-recall — 그래프 조회

`eb.py`(stdlib only)로 `data/`의 CSV 그래프를 **탐색해 답을 얻는다**. 이 스킬은 얇은 오케스트레이터이고, 실제 그래프 연산은 모두 `eb.py`가 결정적으로 보증한다. **읽기 전용** — CSV를 바꾸지 않는다(추가는 `eb-capture`, 정제는 `eb-curate`).

> Windows에서 한국어가 깨지면 명령 앞에 `PYTHONUTF8=1`.

## 조회 워크플로

1. **진입 노드 찾기** — 사용자의 질문에서 키워드를 뽑아 검색한다.
   ```bash
   python eb.py search <질의>          # title/summary/tags/body 부분일치, 일치 필드 수로 랭크
   ```
   id를 이미 알면 이 단계는 건너뛴다.

2. **주변 지형 보기** — 진입 노드에서 그래프를 펼친다.
   ```bash
   python eb.py node <id>                            # 상세 + 나가는 엣지 + 백링크
   python eb.py neighbors <id> --depth 2 --direction both
   ```

3. **개념 사이 관계** — 두 노드가 어떻게 이어지는지.
   ```bash
   python eb.py path <src> <dst>                     # 무가중 최단경로(홉)
   python eb.py path <src> <dst> --weighted          # 가중 최단경로(weight=비용)
   ```

4. **전체 구조** — 큰 덩어리와 허브.
   ```bash
   python eb.py components                           # 약연결 요소(무방향)
   python eb.py degree --top 5                       # 차수 분포 + 차수 중심성
   ```

## 출력: 관련 서브그래프

답할 때는 흩어진 노드 나열이 아니라 **관련 서브그래프**로 묶어 제시한다:
- 진입 노드(들)와 신뢰도(confidence)
- 그 이웃과 관계(엣지 타입·방향·note)
- 질문과 직접 닿는 경로

이렇게 하면 다른 에이전트가 답변 전에 주입할 수 있는 **기억 조각**이 된다.

## 주의
- 용어는 [CONTEXT.md](../../../CONTEXT.md)를 따른다(노드/엣지/조회 …).
- 코어(`eb.py`)는 의존성 0을 유지한다.
- 결과가 비면 질의어를 바꾸거나(`search`) 깊이/방향을 넓힌다(`neighbors --depth`/`--direction`).

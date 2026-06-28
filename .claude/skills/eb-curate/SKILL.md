---
name: eb-curate
description: Excel Brain(eb) 그래프의 건강을 회복시키는 정제 스킬 — 중복 노드 병합, 고아 노드 연결, 그래프 촘촘화. 트리거 - "정제", "curate", "중복 병합", "고아 정리", "그래프 정리", "노드 합치기".
---

# eb-curate — 그래프 정제

`eb.py`로 그래프의 **건강을 회복**시킨다 — 중복 병합, 고아 연결, 촘촘화. 쓰기 작업이므로 신중히, **변경 후 항상 `validate`**.

> Windows에서 한국어가 깨지면 명령 앞에 `PYTHONUTF8=1`.

## 1. 중복 병합
같은 개념이 두 노드로 나뉘어 있으면 하나로 합친다.
```bash
python eb.py search <개념 키워드>          # 중복 후보 찾기
python eb.py node <id1>                     # 두 노드 맥락 비교
python eb.py node <id2>
python eb.py merge <from_id> <into_id>      # from의 엣지를 into로 재배선 후 from 삭제
```
- `merge`는 `from_id` 엣지를 `into_id`로 옮기고 `from_id`를 지운다. 병합으로 생긴 자기 루프는 자동 제거.
- **남길 쪽을 `into_id`** 로(보통 신뢰도·연결이 더 많은 노드). 병합 전 어느 쪽을 남길지 사용자에게 확인.

## 2. 고아 연결
어떤 엣지와도 안 이어진 노드를 그래프에 다시 잇는다.
```bash
python eb.py orphans                        # 고아 노드 목록
python eb.py suggest <고아 id>              # 붙일 연결처 후보(공통 이웃 + 태그 자카드)
python eb.py add-edge --source <고아> --type <엣지타입> --target <후보> --note "<이유>"
```

## 3. 촘촘화
이미 연결된 노드도 더 자연스러운 연결을 놓치고 있을 수 있다.
```bash
python eb.py suggest <id>                   # 아직 직접 연결 안 된 강한 후보
```
제안을 사용자에게 보여주고 승인받은 것만 `add-edge`.

## 마무리
```bash
python eb.py validate                       # 끊긴 엣지/빈 필드 0이어야 정상
```

## 주의
- 용어는 [CONTEXT.md](../../../CONTEXT.md)를 따른다(정제/고아 노드/연결 제안 …).
- 병합은 되돌리기 어렵다 — 실행 전 두 노드를 사용자에게 보여주고 승인받는다.
- 점검은 `eb-health`, 추가는 `eb-capture`, 조회는 `eb-recall`.

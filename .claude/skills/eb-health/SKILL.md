---
name: eb-health
description: Excel Brain(eb) 그래프의 건강도를 점검하고 정제 할 일(리뷰 큐)을 뽑는 스킬 — 저신뢰/미상 노드, 고아, 끊긴 엣지, 빈 필드. 트리거 - "건강도", "health", "점검", "그래프 상태", "리뷰 큐", "약한 노드".
---

# eb-health — 그래프 점검

`eb.py`로 그래프의 건강도를 한 리포트로 본다. 규모 요약에 더해, 그래프가 스스로 "여기 약해요"를 말하게 하는 **리뷰 큐**를 뽑는다. **읽기 전용** — 발견 항목은 `eb-curate`로 넘겨 고친다.

> Windows에서 한국어가 깨지면 명령 앞에 `PYTHONUTF8=1`.

## 점검
```bash
python eb.py health                      # 요약 + 리뷰 큐(저신뢰<0.6 / 고아 / 끊긴 엣지 / 빈 필드)
python eb.py health --confidence 0.8     # 임계값을 올려 더 엄격히
```
개별 명령으로도 볼 수 있다:
```bash
python eb.py stats
python eb.py orphans
python eb.py validate
```

## 리뷰 큐 읽는 법
- **저신뢰/미상 노드** — `confidence`가 임계값 미만이거나 비어 있는 노드(미상이 먼저). 근거를 보강하거나 신뢰도를 갱신할 대상.
- **고아 노드** — 어떤 엣지와도 안 이어진 노드. `eb-curate`의 `suggest`로 연결처를 찾는다.
- **끊긴 엣지** — 없는 노드를 참조하는 엣지. 노드를 만들거나 엣지를 고친다.
- **빈 필드** — type/title 누락. 채운다.

## 인계
점검 결과를 정제 할 일 목록으로 정리해 `eb-curate`로 넘긴다(병합/연결/보강). 지식 보강이 필요하면 `eb-capture`.

## 주의
- 용어는 [CONTEXT.md](../../../CONTEXT.md)를 따른다(고아 노드/신뢰도/드리프트 …).
- 코어(`eb.py`)는 의존성 0 유지.

# eb-health — 점검 (리뷰 큐 + 점검 스킬)

Status: done

## Parent

[PRD: eb 5스킬 수트](../PRD.md)

## What to build

그래프의 건강도를 한 리포트로 보여주는 **점검(health)** 경로를 만든다. 규모 요약에 더해, 그래프가 스스로 "약한 곳"을 말하게 하는 **리뷰 큐**를 제공한다.

- 엔진(`eb.py`, stdlib only): 저신뢰도(`confidence` 낮음)·고아·끊긴 엣지·빈 필드를 모아 반환하는 "리뷰 큐" 헬퍼 함수 추가(기존 `stats`/`orphans`/`validate` 재사용). 정렬·임계값은 인자로.
- 스킬: `.claude/skills/eb-health/SKILL.md` 신규. stats 요약 + 리뷰 큐를 묶어 "정제 할 일 목록"으로 제시. 발견 항목을 `eb-curate`로 넘기는 흐름을 안내.

## Acceptance criteria

- [ ] 리뷰 큐 헬퍼가 저신뢰도 노드·고아·끊긴 엣지·빈 필드를 모아 반환한다(신뢰도 임계값 인자 지원).
- [ ] 리뷰 큐 헬퍼에 대한 오프라인 단위테스트가 추가되고 CI 통과.
- [ ] CLI에서 점검 리포트를 사람이 읽는 형태로 출력한다.
- [ ] `eb-health` SKILL.md가 점검 → 리뷰 큐 → `eb-curate` 인계 흐름을 안내한다.

## Blocked by

- [01-eb-recall-read-path](./01-eb-recall-read-path.md) (조회 기반 위에서 점검; 1 이후 권장)

# 골든 트랜스크립트 — eb-learn (캐싱 도메인)

`tests/test_eb.py`의 `CaptureGoldenTest`가 이 시나리오의 **엔진 불변식**을 박제한다.
증류(자연어 → 타입 노드) 자체는 LLM이 하는 비결정적 작업이라 strict assert 하지 않고,
"증류 결과(아래 plan)를 엔진에 넣었을 때 그래프가 일관되게 통합되는가"와
"엔진의 search/suggest가 캡처를 올바르게 안내하는가"만 검증한다.
**이 파일과 테스트의 plan은 함께 갱신한다.**

## 기존 브레인 (seed)

노드: `pillar-caching`, `concept-cache-invalidation`, `fact-ttl`
엣지: `cache-invalidation -part_of-> pillar-caching`, `ttl -supports-> cache-invalidation`

## 원자료 (LLM 입력)

> 팀 회의 메모(2026-06-28): 캐시는 결국 *신선도 vs 비용*의 트레이드오프다.
> Phil Karlton 말처럼 캐시 무효화는 가장 어려운 문제 중 하나. 우리는 읽기 비중이 큰
> 상품 API에 **LRU 캐시를 도입**하기로 결정했다. TTL만으론 stale 데이터가 새서,
> 쓰기 시 이벤트로 캐시를 깨는 **'이벤트 기반 무효화'**도 병행한다.

## 증류 결과 (LLM 판단 → capture plan)

신규 노드:
- `fact-cache-tradeoff` (fact)  — 신선도와 비용의 트레이드오프
- `decision-lru-product-api` (decision) — 상품 API에 LRU 도입
- `concept-event-invalidation` (concept) — 이벤트 기반 무효화
- `source-meeting-20260628` (source) — 출처

신규 엣지:
- `fact-cache-tradeoff -supports-> pillar-caching`
- `decision-lru-product-api -depends_on-> pillar-caching`
- `fact-cache-tradeoff -derived_from-> source-meeting-20260628`
- `decision-lru-product-api -derived_from-> source-meeting-20260628`
- `concept-event-invalidation -related_to-> concept-cache-invalidation`

"캐시 무효화"는 새 노드로 만들지 않는다 — 기존 `concept-cache-invalidation` 재사용.

## 엔진 불변식 (테스트가 박제)

1. **중복검사 신호**: seed에서 `search("무효화")` 가 `concept-cache-invalidation` 을 찾는다
   → LLM이 "무효화"를 새로 만들지 않을 근거.
2. **연결 제안**: 이벤트 노드를 (연결 엣지 없이) 추가한 뒤 `suggest("concept-event-invalidation")`
   최상위가 `concept-cache-invalidation` (태그 자카드 1.0) → 붙일 곳을 엔진이 안내.
3. **통합 일관성**: plan 전체 적용 후 `validate()` 무이슈, 고아 0, 기대 노드 7개 존재,
   `event -related_to-> cache-invalidation` 엣지 존재, `source-meeting` 백링크 =
   {`fact-cache-tradeoff`, `decision-lru-product-api`}.

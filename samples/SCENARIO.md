# 캡처 시나리오 — deep-work 브레인에 지식 더하기

`eb-capture`(그래프-인지 캡처)가 **이미 지식이 쌓인** 브레인에서 어떻게 동작하는지
실제 명령·출력으로 보여주는 워크스루. 아래 단계가 이 브레인의 `주의 잔류물`·`셧다운 의식`
노드를 만들었다. (`cd samples` 후 실행)

## 시작 상태 (이 캡처 이전)

`딥 워크` 그래프 6노드/5엣지: `pillar-deep-work`, `fact-focus-trainable`,
`concept-time-blocking`, `concept-multitasking`, `concept-pomodoro`, `source-book-deepwork`.

## 원자료 (LLM 입력)

> 딥 워크 후속 메모: 작업 전환 시 **'주의 잔류물'**이 남아 다음 일의 집중을 떨어뜨린다 —
> 이게 멀티태스킹이 해로운 이유다. 뉴포트는 하루 끝에 **'셧다운 의식'**으로 일을 닫으라고 한다.
> 그리고 시간 블록킹은 이미 적어둔 그 전략 맞다.

## 증류 결과 (LLM 판단)

- `concept-attention-residue` (주의 잔류물) — 멀티태스킹이 해로운 **메커니즘**
- `concept-shutdown-ritual` (셧다운 의식) — 딥워크 회복 **루틴**, 출처는 책
- "시간 블록킹"은 **새로 만들지 않는다** — 기존 `concept-time-blocking` 재사용

## 단계 (실제 출력)

### 1) 추가 전 중복검사 — 시간 블록킹은 이미 있다

```text
$ python eb.py search 블록킹
  [1] concept-time-blocking  시간 블록킹  (title)
```
→ 이미 존재. 새 노드를 만들지 않는다(그래프-인지 dedup).

### 2) 신규 노드 추가 + 붙일 곳 제안

```text
$ python eb.py add-node --id concept-attention-residue --title "주의 잔류물" \
    --type concept --confidence 0.8 --tags "집중;안티패턴" \
    --summary "작업 전환 후에도 이전 일에 주의가 남아 집중을 떨어뜨린다"
✓ 노드 추가: concept-attention-residue

$ python eb.py suggest concept-attention-residue
  [1.0] concept-multitasking  멀티태스킹  (공통이웃 0, 자카드 1.0)
  [0.5] fact-focus-trainable  집중은 단련된다  (공통이웃 0, 자카드 0.5)
  ...
```
→ 엔진이 **멀티태스킹(자카드 1.0)** 을 최상위로 제안. LLM 판단("멀티태스킹의 메커니즘")과 일치.

### 3) 제안대로 연결

```text
$ python eb.py add-edge --source concept-attention-residue --type related_to \
    --target concept-multitasking --note "멀티태스킹이 해로운 메커니즘"
✓ 엣지 추가: concept-attention-residue -related_to-> concept-multitasking
```

### 4) 셧다운 의식 + 연결 + 출처(provenance)

```text
$ python eb.py add-node --id concept-shutdown-ritual --title "셧다운 의식" \
    --type concept --confidence 0.75 --tags "집중;실천" \
    --summary "하루 끝에 일을 의식적으로 닫아 주의 잔류물을 줄인다"
$ python eb.py add-edge --source concept-shutdown-ritual --type supports --target pillar-deep-work
$ python eb.py add-edge --source concept-shutdown-ritual --type derived_from --target source-book-deepwork
```

### 5) 검증

```text
$ python eb.py validate
✓ 문제 없음
$ python eb.py stats
노드: 8  엣지: 8  평균 차수: 2.0  고아: 0
```

## 이 시나리오가 보여주는 것

- **그래프-인지 dedup**: 빈 브레인이 아니라서 `search`가 기존 노드를 잡아 중복 생성을 막았다.
- **연결 제안**: `suggest`가 태그 자카드로 새 노드의 자연스러운 연결처를 결정적으로 제시했다.
- **출처 추적**: 새 지식이 `source-book-deepwork`로 `derived_from` 연결돼 추적 가능.

## 직접 더 해보기

이 브레인엔 위 결과가 이미 반영돼 있다(같은 id 재추가는 거부됨). 새 지식은 새 id로:

```bash
cd samples
python eb.py add-node --id concept-flow --title "몰입(플로우)" --type concept --tags "집중"
python eb.py suggest concept-flow                 # 붙일 곳 확인 후
python eb.py add-edge --source concept-flow --type related_to --target pillar-deep-work
python eb.py validate
```

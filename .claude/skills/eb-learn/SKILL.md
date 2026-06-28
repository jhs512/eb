---
name: eb-learn
description: 원자료(텍스트·대화·파일, 그리고 유튜브·음성/영상)를 Excel Brain(eb)의 타입 노드+엣지로 증류해 CSV에 반영하는 그래프-인지 캡처 스킬. 추가 전에 그래프를 조회해 중복을 피하고 연결처를 찾는다. 트리거 - "지식 추가", "이거 기억해", "그래프에 넣어줘", "이 영상에서 배워", "유튜브 정리해줘", "녹음 흡수".
---

# eb-learn — 그래프-인지 캡처

원자료를 노드+엣지로 **증류**해 `data/`의 CSV에 반영한다. 핵심은 **추가하기 전에 그래프를 먼저 조회**해 고아·중복을 만들지 않는 것이다([ADR-0003](../../../docs/adr/0003-graph-aware-capture.md)). 실제 연산은 모두 `eb.py`가 보증한다.

> Windows에서 한국어가 깨지면 명령 앞에 `PYTHONUTF8=1`.

## 데이터 규약 (어기면 끊긴 그래프)
- 노드: `id,title,type,namespace,visibility,summary,confidence,tags,body`
- 엣지: `source,type,target,weight,note`
- `id`는 kebab-case ASCII 고유. `tags`는 **세미콜론(`;`) 구분**. 엣지 타입: `supports / depends_on / part_of / related_to / derived_from / contradicts / preceded_by / followed_by / authored_by / tagged_with`.

## 0단계 — 소스에서 텍스트 얻기 (입력 감지)

입력이 무엇이든 결국 **텍스트로 모아 같은 파이프라인**을 탄다.

- **텍스트/붙여넣기·파일(.md/.txt)** → 그대로 사용(제로 의존성).
- **유튜브 URL / 음성·영상 파일** → 선택 도구 `ingest.py`로 **전사** 후 사용:
  ```bash
  python ingest.py "<유튜브 URL>"      # 자막 우선(youtube-transcript-api)
  python ingest.py path/to/audio.mp3   # whisper 로컬 전사(자막 없는 음성/영상)
  ```
  - 코어 `eb.py`는 stdlib only. 전사는 **선택 의존**이다: `pip install -r requirements-ingest.txt`(자막), 음성 파일은 `pip install openai-whisper`(+ ffmpeg). 없으면 `ingest.py`가 설치 안내를 낸다.
  - 미디어를 흡수할 때는 **그 미디어를 `source` 노드로** 만들고(아래 출처 추적), 추출한 지식을 `derived_from`으로 잇는다.

전사 텍스트를 손에 쥐면 아래 1~5단계는 동일하다.

## 캡처 파이프라인 (5단계)

1. **증류** — 원자료(또는 전사 텍스트)를 후보 노드(원자적 아이디어 1개=노드 1개)와 후보 엣지로 쪼갠다. 각 후보에 type·summary·tags 초안을 단다.

2. **그래프 조회 (추가 전!)** — 후보마다 기존 그래프를 확인한다.
   ```bash
   python eb.py search <후보 제목/키워드>     # 중복 후보 탐지
   python eb.py suggest <관련 기존 id>        # 새 노드를 붙일 연결처 후보
   python eb.py node <id>                      # 맥락 확인
   ```

3. **승인 게이트** — 사용자에게 제시: 추가할 노드/엣지, **중복 경고**(search 결과), **제안 연결**(suggest 결과). 승인받기 전에는 쓰지 않는다. 중복이면 새로 만들지 말고 기존 노드에 엣지만 잇는다.

4. **반영** — 승인된 것만 CSV에 쓴다. 고아를 만들지 말 것(노드는 최소 1개 엣지로 기존 그래프에 연결).
   ```bash
   python eb.py add-node --id <id> --title "<제목>" --type <type> --tags "a;b"
   python eb.py add-edge --source <id> --type <엣지타입> --target <id> --weight 0.6 --note "<이유>"
   ```

5. **검증** — 항상 마지막에:
   ```bash
   python eb.py validate        # 끊긴 엣지/빈 필드 0이어야 정상
   ```

## 출처 추적 (provenance)
매 캡처 단위마다 `source` 타입 노드 1개를 만들고(어디서 온 지식인지), 새로 만든 노드들을 거기에 `derived_from` 또는 `authored_by`로 잇는다. 나중에 "이 지식 어디서 왔지?"를 그래프로 추적할 수 있다.

## 갱신은 덮어쓰지 말고 잇기 (supersede)
기존 지식이 바뀌면 옛 노드를 수정/삭제하지 말고 **새 노드**를 만들어 `preceded_by`(옛→새 순서)로 잇는다. 옛 주장과 모순되면 `contradicts`도 추가한다. CSV가 원천이므로 변천 이력이 그래프에 보존된다.

## 주의
- 용어는 [CONTEXT.md](../../../CONTEXT.md)를 따른다(증류/연결 제안/그래프-인지 캡처 …).
- 코어(`eb.py`)는 의존성 0 유지. 조회는 `eb-ask`, 정제는 `eb-clean`.
- 직접 CSV를 엑셀/에디터로 편집해도 되지만, CLI가 중복/끊김을 막아준다. **추가 후 반드시 `validate`.**

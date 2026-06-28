# 미디어 흡수는 선택 도구 ingest.py로 분리, 자막 우선

eb-learn이 유튜브·음성/영상에서도 지식을 흡수할 수 있게 하되, 전사(transcription)는 서드파티가 필요하므로 코어에 넣지 않고 **선택 도구 `ingest.py`** 로 분리한다(`sync.py`와 같은 위치·철학). 전사는 **자막 우선**: 유튜브는 기존 자막을 `youtube-transcript-api`로 가져오고(가볍고 ML 불필요), 자막 없는 음성/영상 파일만 `whisper` 로컬 전사(무거운 선택 설치)로 처리한다. `ingest.py`는 전사 텍스트를 stdout으로 내고, eb-learn은 그 텍스트를 **기존 그래프-인지 캡처 파이프라인**(증류→search/suggest→add→validate)에 그대로 태운다.

## 왜

- 입력이 텍스트든 미디어든 어려운 일(증류·그래프-인지 추가)은 동일하다. 미디어는 "소스→텍스트" 앞단계만 추가되므로, 별도 스킬로 쪼개지 않고 eb-learn 하나가 입력을 감지한다.
- 코어 `eb.py`의 **stdlib only** 불변식을 지키기 위해 전사 의존성은 선택으로 격리한다([ADR 없음 — sync.py 선례와 동일]).
- 자막 우선은 대부분의 유튜브에서 ML·다운로드 없이 즉시 동작해 가장 가볍다. whisper는 자막이 없을 때만 쓰는 폴백.

## Consequences

- 텍스트 흡수는 의존성 0으로 항상 동작하고, 미디어 흡수는 `pip install -r requirements-ingest.txt`(+음성은 whisper) 후 동작한다.
- 흡수한 미디어는 `source` 노드로 만들어 `derived_from`으로 추적한다(provenance).
- `ingest.py`의 순수 파싱(URL id 추출·전사 정리·세그먼트 결합)은 오프라인 단위테스트로 보호하고, 네트워크·whisper 호출은 얇은 어댑터로 둔다.

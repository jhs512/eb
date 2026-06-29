# 자동 SQLite 캐시 (사용자 노출 --db/build-db 제거)

조회용 SQLite 캐시를 **사용자 플래그 없이 자동**으로 동작하게 한다. `load_db()`는 `data_dir` 안의 `.eb-cache.sqlite` 가 있고 CSV 시그니처와 일치하면 재사용하고, 없거나 CSV가 바뀌었으면 새로 만든다. 기존의 `--db PATH` / `--rebuild` / `build-db` CLI 표면은 **제거**한다.

## 왜

- `--db`는 "SQLite가 선택"처럼 읽혀 혼란스러웠고, 명시적 경로/빌드 단계를 사용자가 관리해야 했다. 캐시는 순수 성능 최적화이지 사용자가 신경 쓸 개념이 아니다 → 자동화.
- **정확성**: staleness를 mtime 1초 granularity 대신 **크기 + 나노초 mtime 시그니처**(`st_size`+`st_mtime_ns`)로 판정해, 같은 초 안의 편집도 재생성으로 잡는다. CSV를 외부(엑셀/시트)에서 바꿔도 다음 조회에서 자동 반영.
- **안전**: 캐시 디렉토리가 읽기 전용이면 조용히 인메모리로 폴백한다(읽기 명령이 쓰기 실패로 죽지 않음). 쓰기 명령(add-node/edge/merge)은 CSV를 직접 바꾸므로 다음 조회에서 캐시가 자동 재생성된다.
- CSV가 단일 원천, 캐시는 파생물 — `.eb-cache.sqlite` 는 `.gitignore` 대상.

## Considered Options

- **자동 캐시 없이 항상 인메모리(제거)** — 가장 단순하나, 대규모에서 매 호출 CSV 재파싱 비용. (반려: 캐시를 자동·안전하게 둘 수 있음)
- **명시적 자동 캐시 유지(`--db`)** — 혼란·관리 부담. (반려)
- **읽기에도 쓰기 부작용 우려** — 인메모리 폴백 + gitignore + 시그니처 정확성으로 완화.

## Consequences

- CLI에서 `--db`/`--rebuild`/`build-db` 가 사라진다(파일 SQLite를 직접 다루던 사용자에겐 표면 변경).
- `eb.load_db(data_dir)` 시그니처 단순화(`db_path`/`rebuild` 인자 제거). 코어는 여전히 stdlib only.

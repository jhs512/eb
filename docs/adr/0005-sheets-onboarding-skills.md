# Sheets 온보딩을 두 스킬(eb-gcp / eb-sheets)로 추가 — 브라우저 + gcloud

Google Sheets 연동의 셋업을 도와주는 온보딩 스킬을 추가한다. 자격증명 프로비저닝과 저장소 연결을 **두 스킬로 분리**한다: `eb-gcp`(Google 계정당 1회 — 프로젝트·Sheets/Drive API·서비스 계정·JSON 키, `~/.config/eb/sheets-sync.env` 에 영속) + `eb-sheets`(저장소별 — `지식` 시트 생성·서비스계정 공유·gh secret/variable·초기 동기화). 둘 다 **브라우저 자동화(Claude in Chrome 등)를 하드 게이트**로 맨 앞에서 확인하고, `gcloud` CLI는 있으면 결정적 단계의 선택적 가속기로 쓴다.

## 왜

- 초기 PRD는 "인프라 스킬"을 범위 밖으로 두고 시트 셋업을 README 수동 안내로 남겼다. 사용자가 **가이드형 온보딩**을 원해 이 결정을 뒤집는다.
- **계정/저장소 분리**: 자격증명은 Google 계정당 1회면 충분한데, 한 스킬로 묶으면 저장소마다 GCP 프로젝트를 중복 생성하는 실패가 난다. `eb-gcp` 는 멱등(확인 후 생성)으로 이를 막는다.
- **브라우저 하드 게이트**: 키 다운로드 등 사람만 가능한·콘솔 의존 단계가 있어, 절반만 프로비저닝하고 실패하는 것을 막기 위해 시작 시 브라우저 가용성을 강제한다. `gcloud` 는 대체가 아니라 가속기.
- 검증된 절차를 흡수해 eb에 맞게 적응시켰다(프로젝트 슬러그 `excel-brain`, SA `eb-sheets-sync`, `~/.config/eb/*`, eb `sync.py` 의 `_data/_edges/_meta`·`--data`·overwrite).

## Consequences

- 코어 `eb.py` 는 여전히 stdlib only. 온보딩·동기화는 선택(서드파티·브라우저·gh 필요).
- 서비스 계정 JSON 키는 라이브 자격증명 — `.gitignore` 의 `*.json` 으로 차단, CI는 `gh secret`(GOOGLE_SA_KEY)로만.

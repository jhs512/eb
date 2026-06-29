---
name: eb-gcp
description: "eb의 Google Sheets 미러에 필요한 재사용 가능한 Google Cloud 자격증명을 프로비저닝한다 — GCP 프로젝트(기본 슬러그 excel-brain), Sheets + Drive API 활성화, 서비스 계정(기본 eb-sheets-sync), 다운로드한 JSON 키 — 그리고 ~/.config/eb/sheets-sync.env 에 저장해 모든 저장소에서 재사용한다. 멱등: 기존 프로젝트/서비스계정/키가 있으면 재사용한다. Google 계정당 1회만 실행하면 되고, 이후 eb-sheets 가 저장된 자격증명을 재사용한다. 브라우저 자동화(Claude in Chrome 등)가 하드 전제다 — 맨 처음 활성화 여부를 확인하고 꺼져 있으면 즉시 중단한다. gcloud CLI는 있으면 결정적 단계를 위한 선택적 가속기다. 트리거 - 'eb 시트 연동 준비', '서비스 계정 만들기', 'GCP 자격증명', 'eb-gcp'."
disable-model-invocation: true
---

# eb Sheets 미러용 Google Cloud 자격증명 설정

이 스킬은 **Google 계정당 1회**, 모든 저장소의 Sheets 미러가 공유할 자격증명을 만든다:
- **GCP 프로젝트**(기본 슬러그 `excel-brain`)
- 그 프로젝트의 **Google Sheets API** + **Google Drive API** 활성화
- **서비스 계정**(기본 `eb-sheets-sync`)
- 그 서비스 계정의 **JSON 키**(레포 밖에 저장)

그리고 `~/.config/eb/sheets-sync.env` 에 기록해 `eb-sheets`(및 이후 저장소)가 재사용하게 한다.

## 단 하나의 규칙: 확인 후 생성 — 절대 중복 금지
각 리소스는 **확인 후 생성**한다. 이미 있으면 재사용한다. 새 키는 디스크에 키가 하나도 없거나 사용자가 명시적으로 회전(rotate)을 요청할 때만 만든다.

## 0. 이미 프로비저닝됐으면 단축 종료
`~/.config/eb/sheets-sync.env` 가 있고 `GCP_PROJECT_ID`·`SA_EMAIL`·(실제 파일을 가리키는)`SA_KEY_PATH` 가 정의돼 있으면 계정은 이미 설정된 것 — 값을 보고하고 중단한다(재프로비저닝/키 회전을 명시적으로 원하면 예외). (브라우저가 필요 없는 유일한 경로다.)

**단, 단축 종료 전에도 자기 문서화는 한다(멱등):** 현재 디렉터리가 eb 저장소(루트에 `CLAUDE.md`)면 §5의 `eb:gcp` 블록을 기록/갱신한 뒤 종료한다(키·키경로 값은 적지 않는다). 이미 설정된 계정으로 다른 저장소에서 돌릴 때 그 저장소의 CLAUDE.md가 비지 않도록 하기 위함이다.

## 1. 브라우저 자동화 확인 — 가장 먼저 (하드 게이트)
**무엇이든 만들기 전에** 브라우저 구동 도구가 사용 가능·활성화돼 있는지 확인한다 — `claude-in-chrome` 스킬 또는 Chrome/DevTools MCP. 클릭을 가정·위조하지 말 것.
- **활성화됨** → 계속.
- **활성화 안 됨** → **즉시 중단.** 프로젝트·서비스계정·키를 만들지 말 것. 사용자에게 브라우저 자동화(Claude in Chrome 확장 / Chrome MCP)를 켜고 다시 실행하라고 안내한다. GCP 콘솔 작업(특히 사람만 가능한 키 다운로드)에 브라우저가 필요함을 분명히 한다.

그다음 프로젝트 슬러그(기본 `excel-brain`)와 서비스 계정 이름(기본 `eb-sheets-sync`)을 사용자에게 묻는다.

**선택적 가속기 — `gcloud`.** 설치·인증돼 있으면(`gcloud --version`, `gcloud auth list`) §2의 결정적 단계에 써도 된다(멱등 확인이 정확해짐). 단 브라우저 게이트를 대체하지는 않는다. 없으면 전부 브라우저 콘솔(§3)로 처리한다.

## 2. gcloud 가속 경로 (선택, 멱등)
`SLUG`=프로젝트 슬러그(기본 `excel-brain`), `SA`=서비스 계정 이름(기본 `eb-sheets-sync`).

1. **프로젝트 — 재사용 또는 생성.**
   ```bash
   gcloud projects list --filter="name:$SLUG OR projectId:$SLUG" --format="value(projectId)"
   ```
   결과가 있으면 그 `projectId` 재사용(여러 개면 확인). 없으면 생성(전역 고유라 충돌 시 짧은 숫자 접미사):
   ```bash
   gcloud projects create "$SLUG" --name="$SLUG"     # 충돌 시 "$SLUG-NNNNNN" 재시도
   gcloud config set project "$GCP_PROJECT_ID"
   ```
2. **API 활성화**(재활성화는 no-op):
   ```bash
   gcloud services enable sheets.googleapis.com drive.googleapis.com --project="$GCP_PROJECT_ID"
   ```
3. **서비스 계정 — 재사용 또는 생성.**
   ```bash
   gcloud iam service-accounts list --project="$GCP_PROJECT_ID" --format="value(email)"
   gcloud iam service-accounts create "$SA" --display-name="eb sheets sync" --project="$GCP_PROJECT_ID"
   ```
   이메일을 `SA_EMAIL` 로 기록.
4. **JSON 키 — 있으면 재사용, 없을 때만 생성.** 정규 위치 `~/.config/eb/sa-key.json`.
   ```bash
   mkdir -p ~/.config/eb
   gcloud iam service-accounts keys create ~/.config/eb/sa-key.json --iam-account="$SA_EMAIL"
   ```
   라이브 자격증명이 어디 기록됐는지 사용자에게 알린다.

## 3. 브라우저 콘솔 경로 (기본, 검사 기반 멱등)
`gcloud` 가 없으면 이 경로. **생성 전에 매번 확인**한다.
1. **프로젝트** — 프로젝트 선택기/`console.cloud.google.com/cloud-resource-manager` 에서 슬러그 검색 → 있으면 선택, 없을 때만 `console.cloud.google.com/projectcreate`.
2. **API 활성화** — `console.cloud.google.com/apis/library` 에서 **Google Sheets API** + **Google Drive API**(이미 Enabled면 건너뜀).
3. **서비스 계정** — `console.cloud.google.com/iam-admin/serviceaccounts` 에서 `eb-sheets-sync@…` 있으면 재사용, 없으면 생성. `client_email` 기록.
4. **JSON 키 생성 — ★ 사람이 "만들기" 클릭.** 서비스 계정 → Keys → Add key → Create new key → **JSON**(P12 아님) → 만들기. 다운로드 파일을 `~/.config/eb/sa-key.json` 로 저장(레포 밖). **왜 안전한지 안내**: `.gitignore` 의 `*.json` 으로 절대 커밋되지 않고, CI용은 `gh secret set GOOGLE_SA_KEY` 암호화 시크릿으로만 들어간다.

## 4. 재사용을 위해 영속화
`~/.config/eb/sheets-sync.env` 작성(먼저 `~/.config/eb/` 생성):
```sh
GCP_PROJECT_ID=<project id>
SA_EMAIL=<service-account email>
SA_KEY_PATH=<JSON 키 절대 경로, 예: ~/.config/eb/sa-key.json>
```
이미 있으면 중복 추가 말고 값만 갱신.

## 5. CLAUDE.md 기록 — 자기 문서화 (선택, 저장소 안일 때만)
이 스킬은 **구글 계정 전역**(`~/.config/eb`)을 만든다 — 특정 저장소 소유가 아니다. 따라서 현재 디렉터리가 eb 저장소이고 루트에 `CLAUDE.md` 가 있을 때만, **키 값 없이** `eb:gcp` 블록으로 한 줄 남긴다(키·키경로는 절대 적지 않는다). 재실행 시 이 블록만 통째로 교체(마커 유지):
````markdown
<!-- eb:gcp START -->
## GCP 자격증명 (계정 전역)
- 프로젝트 `<project id>` · 서비스 계정 `<SA_EMAIL>`. 키·env 는 레포 밖 `~/.config/eb/`.
- 시트 미러는 `/eb-sheets`, 이 값은 자동 재사용(재실행 불필요).
<!-- eb:gcp END -->
````

## 6. 완료
프로젝트 id·서비스계정 이메일·키 경로를 보고하고, 키 파일은 **라이브 자격증명**이라 어떤 레포에도 넣지 말 것을 상기시킨다(필요시 GCP에서 회전). 재사용 가능: 각 저장소의 `/eb-sheets` 가 이 값을 자동으로 가져오므로 `/eb-gcp` 를 다시 실행할 필요는 없다. 다음 단계: **`/eb-sheets`**.

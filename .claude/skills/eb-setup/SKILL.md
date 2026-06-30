---
name: eb-setup
description: 현재 저장소에 Excel Brain(eb) 엔진(eb.py)과 씨앗 CSV를 깔아 지식 그래프를 부트스트랩하는 스킬. 트리거 - "eb 초기화", "init eb", "eb 셋업", "지식 그래프 시작", "eb.py 깔아줘".
---

# eb-setup — Excel Brain 부트스트랩

현재 저장소에 eb **엔진과 씨앗 데이터**를 깔아 곧바로 지식을 쌓을 수 있게 한다. 엔진은 스킬에 동봉하지 않고, `jhs512/eb`의 **고정 ref에서 내려받는다**([ADR-0002](../../../docs/adr/0002-distribution-skills-first-fetch.md)) — 엔진은 한 곳에서만 관리되고 버전 핀이 가능하다.

> Windows에서 한국어가 깨지면 명령 앞에 `PYTHONUTF8=1`.

## 0. 덮어쓰기 확인 (먼저!)
저장소에 이미 `eb.py` 또는 `data/`가 있으면 **덮어쓰기 전에 사용자에게 확인**한다. 기존 그래프를 잃지 않도록, 이미 쓰던 그래프면 init 대신 그대로 둔다.

**이미 부트스트랩된 경우에도** 엔진/CSV 재다운로드(§1~3)만 건너뛰고, **§5(CLAUDE.md 시드)와 §6(연동 물어보기)은 멱등으로 계속 수행**한다 — 옛 버전으로 셋업해 CLAUDE.md가 없거나 블록이 빠진 저장소를 self-heal 하기 위함이다.

## 1. ref 고르기
`<REF>`는 `jhs512/eb`의 **릴리스 태그**(권장, 예: `v0.2.0`)나 커밋 SHA로 핀한다. 태그가 없으면 `main`을 쓰되, 재현성을 위해 가능하면 태그/SHA로 고정한다.

## 2. 엔진·스키마 내려받기
`<REF>`에서 `eb.py`와 스키마 문서 `data/meta.csv`를 가져온다(raw):
```bash
mkdir -p data
curl -fsSL https://raw.githubusercontent.com/jhs512/eb/<REF>/eb.py -o eb.py
curl -fsSL https://raw.githubusercontent.com/jhs512/eb/<REF>/data/meta.csv -o data/meta.csv
```
시트 동기화(`sync.py`)나 CI(`.github/workflows/`)도 원하면 같은 방식으로 가져온다(선택).

유튜브·음성/영상 흡수를 쓸 거면 미디어 도구도 가져온다(선택, 서드파티 필요):
```bash
curl -fsSL https://raw.githubusercontent.com/jhs512/eb/<REF>/ingest.py -o ingest.py
curl -fsSL https://raw.githubusercontent.com/jhs512/eb/<REF>/requirements-ingest.txt -o requirements-ingest.txt
pip install -r requirements-ingest.txt   # 유튜브 자막. 음성 파일은 추가로 openai-whisper(+ffmpeg)
```

## 3. 씨앗 CSV 만들기 (빈 그래프)
`nodes.csv`/`edges.csv`는 헤더만 둔 **빈 그래프**로 시작한다(엑셀/시트/에디터로도 열림):
```bash
printf 'id,title,type,namespace,visibility,summary,confidence,tags,body\n' > data/nodes.csv
printf 'source,type,target,weight,note\n' > data/edges.csv
```

## 4. 검증
```bash
python eb.py stats        # 노드 0, 엣지 0 이면 정상 부트스트랩
python eb.py validate     # 문제 없음
```

## 5. CLAUDE.md 시드 — 자기 문서화 (필수)
저장소 루트 `CLAUDE.md` 를 만든다(이미 있으면 보존하고 블록만 갱신). 이후 모든 setup 계열 스킬은 이 파일에 **구분 주석 블록**으로 자기 사실을 남기고, 재실행 시 **그 블록만 통째로 교체**(마커 유지)해 멱등 갱신한다 — 마커 밖 내용은 건드리지 않는다.

eb 핵심 블록을 적는다:
````markdown
<!-- eb:core START -->
## eb (Excel Brain) 지식 그래프
- `data/{nodes,edges,meta}.csv` 가 그래프(=단일 원천). 엔진 `eb.py`(stdlib only).
- 추가 `eb-learn` · 조회 `eb-ask` · 정제 `eb-clean` · 건강 `eb-check` · 상태 `eb-status`.
- 연동(선택): `eb-gcp`/`eb-sheets`(시트) · `eb-pages`(웹) · `eb-github`(레포+CI) · `eb-queue`(작업큐·워처·폰 제미나이 비서). 셋업하면 각 스킬이 이 파일에 자기 블록을 남긴다.
<!-- eb:core END -->
````
`eb/` 가 git 서브모듈이면(=eb 엔진을 직접 개발) 개발 워크플로 블록도 추가한다:
````markdown
<!-- eb:dev START -->
## eb 스킬 개발 워크플로
eb 스킬은 `eb/.claude/skills/` 에서 고쳐 jhs512/eb 에 push한 뒤, 이 저장소의 `.claude/skills`·`.agents/skills` 로 동기화한다. 스킬 추가/삭제 시 `eb/tests/test_skills.py`·`eb/install.sh` 목록도 갱신.
<!-- eb:dev END -->
````

## 6. 선택 연동 셋업 — 사용자에게 물어본다 (필수)
부트스트랩·검증이 끝나면 **곧바로 사용자에게 물어본다**: 아래 선택 연동을 지금 같이 설정할지. 임의로 진행하지 말고, 원하는 것만 고르게 한 뒤 **의존 순서대로** 해당 스킬을 실행/안내한다. 모두 브라우저나 외부 인증이 필요하므로, 시작 전에 전제(브라우저 자동화·gh 인증)를 확인한다.

- **eb-gcp** — Google Sheets 미러용 GCP 자격증명(구글 계정당 1회). `~/.config/eb/sheets-sync.env` 가 이미 있으면 건너뛸 수 있음. (eb-sheets 선행)
- **eb-sheets** — 이 저장소를 Google Sheet에 단방향 미러(=eb-gcp 필요).
- **eb-pages** — 그래프를 Cloudflare Pages 정적 웹앱으로 배포.
- **eb-github** — 저장소를 GitHub에 올리고 위 연동들의 CI 자동화를 켠다(=연동 설정 후에 하면 시크릿/변수를 함께 등록).
- **eb-queue** — 작업큐(Google Calendar 보조 캘린더)·소비자 워처·폰 제미나이 맞춤 Gem 비서를 연결한다. 음성/폰으로 지식 추가·정제 요청을 큐잉하면 워처가 안전정책 안에서 처리한다. 지식 조회가 시트를 읽으므로 `eb-sheets`(+가능하면 `eb-pages`)가 선행이면 좋다.

권장 순서: **eb-gcp → eb-sheets → eb-pages → eb-github → eb-queue**. 아무것도 원치 않으면 건너뛴다.

## 7. 다음
- 지식 추가는 `eb-learn`, 조회는 `eb-ask`, 정제는 `eb-clean`, 점검은 `eb-check`.
- 엔진을 갱신하려면 `<REF>`를 올려 다시 이 절차를 돌린다(데이터 CSV는 보존).

## 부록: 스킬 설치 (skills-lock)
다른 저장소에서 eb 스킬을 쓰려면 `skills-lock.json`에 `source: jhs512/eb`로 잠근다(기존 `mattpocock/skills` 항목과 동일 형식). 핵심 4종(`eb-learn`/`eb-ask`/`eb-clean`/`eb-check`)에 더해, 부트스트랩 `eb-setup`과 선택 연동(`eb-gcp`/`eb-sheets`/`eb-pages`/`eb-github`)을 함께 잠근다:
```json
{
  "version": 1,
  "skills": {
    "eb-setup":  { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-setup/SKILL.md" },
    "eb-learn":  { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-learn/SKILL.md" },
    "eb-ask":    { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-ask/SKILL.md" },
    "eb-clean":  { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-clean/SKILL.md" },
    "eb-check":  { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-check/SKILL.md" },
    "eb-gcp":    { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-gcp/SKILL.md" },
    "eb-sheets": { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-sheets/SKILL.md" },
    "eb-pages":  { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-pages/SKILL.md" },
    "eb-github": { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-github/SKILL.md" },
    "eb-status": { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-status/SKILL.md" },
    "eb-queue":  { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-queue/SKILL.md" }
  }
}
```
설치 후 그 저장소에서 `/eb-setup`을 실행하면 엔진·씨앗 데이터가 깔린다.

---
name: eb-init
description: 현재 저장소에 Excel Brain(eb) 엔진(eb.py)과 씨앗 CSV를 깔아 지식 그래프를 부트스트랩하는 스킬. 트리거 - "eb 초기화", "init eb", "eb 셋업", "지식 그래프 시작", "eb.py 깔아줘".
---

# eb-init — Excel Brain 부트스트랩

현재 저장소에 eb **엔진과 씨앗 데이터**를 깔아 곧바로 지식을 쌓을 수 있게 한다. 엔진은 스킬에 동봉하지 않고, `jhs512/eb`의 **고정 ref에서 내려받는다**([ADR-0002](../../../docs/adr/0002-distribution-skills-first-fetch.md)) — 엔진은 한 곳에서만 관리되고 버전 핀이 가능하다.

> Windows에서 한국어가 깨지면 명령 앞에 `PYTHONUTF8=1`.

## 0. 덮어쓰기 확인 (먼저!)
저장소에 이미 `eb.py` 또는 `data/`가 있으면 **덮어쓰기 전에 사용자에게 확인**한다. 기존 그래프를 잃지 않도록, 이미 쓰던 그래프면 init 대신 그대로 둔다.

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

## 5. 다음
- 지식 추가는 `eb-capture`, 조회는 `eb-recall`, 정제는 `eb-curate`, 점검은 `eb-health`.
- 엔진을 갱신하려면 `<REF>`를 올려 다시 이 절차를 돌린다(데이터 CSV는 보존).

## 부록: 5스킬 설치 (skills-lock)
다른 저장소에서 eb 스킬을 쓰려면 `skills-lock.json`에 `source: jhs512/eb`로 잠근다(기존 `mattpocock/skills` 항목과 동일 형식):
```json
{
  "version": 1,
  "skills": {
    "eb-init":    { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-init/SKILL.md" },
    "eb-capture": { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-capture/SKILL.md" },
    "eb-recall":  { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-recall/SKILL.md" },
    "eb-curate":  { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-curate/SKILL.md" },
    "eb-health":  { "source": "jhs512/eb", "sourceType": "github", "skillPath": ".claude/skills/eb-health/SKILL.md" }
  }
}
```
설치 후 그 저장소에서 `/eb-init`을 실행하면 엔진·씨앗 데이터가 깔린다.

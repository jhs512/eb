#!/usr/bin/env bash
# eb 스킬 설치 — jhs512/eb 의 고정 ref에서 스킬(SKILL.md)을 현재 저장소의
# .claude/skills/ 로 가져온다. 별도 설치 도구 불필요(curl 만 필요).
#
#   curl -fsSL https://raw.githubusercontent.com/jhs512/eb/v0.5.1/install.sh -o eb-install.sh
#   bash eb-install.sh            # 기본 ref(아래 REF)로 설치
#   bash eb-install.sh v0.5.0     # 특정 릴리스 태그 핀
#
# 엔진(eb.py)·씨앗 데이터는 설치하지 않는다 — 설치 후 /eb-setup 이 고정 ref에서 가져온다.
set -euo pipefail

REF="${1:-v0.5.1}"
# 핵심 5스킬 + 온보딩 4스킬(시트 연동·페이지 배포·GitHub/CI) + 상태 점검 1스킬. tests/test_skills.py 가 실제 스킬과 대조한다.
SKILLS="eb-setup eb-learn eb-ask eb-clean eb-check eb-gcp eb-sheets eb-pages eb-github eb-status"
BASE="https://raw.githubusercontent.com/jhs512/eb/${REF}/.claude/skills"

echo "eb 스킬 설치 (ref=${REF}) → .claude/skills/"
for s in $SKILLS; do
  mkdir -p ".claude/skills/${s}"
  curl -fsSL "${BASE}/${s}/SKILL.md" -o ".claude/skills/${s}/SKILL.md"
  echo "  ✓ ${s}"
done
echo
echo "완료. 다음: /eb-setup 으로 엔진(eb.py)·씨앗 CSV를 부트스트랩하세요."
echo "  (유튜브/음성 흡수는 eb-learn + ingest.py, 시트 연동은 /eb-gcp → /eb-sheets)"

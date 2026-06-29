"""스킬·문서 계약 테스트 (네트워크/LLM 없음, 결정적).

LLM 출력은 박제하지 않는다. 대신 스킬 파일의 구조적 무결성과 "문서↔엔진 일치"만
검증한다 — 스킬/README가 **존재하지 않는 eb.py 명령**을 참조하면(예: 명령 rename
후 갱신 누락) 실패시킨다. 이게 스킬에서 가장 흔한 회귀다.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SKILL_DIRS = sorted((ROOT / ".claude" / "skills").glob("eb-*"))
DOC_FILES = (
    [d / "SKILL.md" for d in SKILL_DIRS]
    + [ROOT / "README.md"]
    + sorted((ROOT / "samples").glob("*.md"))
    + sorted((ROOT / "tests" / "fixtures").glob("*.md"))
)


def _frontmatter(text):
    """첫 '---' 블록을 key->value(첫 줄만)로 파싱."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else ""
    fm = {}
    for line in block.splitlines():
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


def _eb_commands():
    """eb.py 소스에서 실제 서브커맨드 집합을 뽑는다."""
    src = (ROOT / "eb.py").read_text(encoding="utf-8")
    return set(re.findall(r'add_parser\(\s*["\']([a-z][a-z-]*)["\']', src))


class SkillMetadataTest(unittest.TestCase):
    def test_skills_exist(self):
        names = {d.name for d in SKILL_DIRS}
        self.assertEqual(
            names,
            {"eb-setup", "eb-learn", "eb-ask", "eb-clean", "eb-check",
             "eb-gcp", "eb-sheets", "eb-pages", "eb-github"})

    def test_frontmatter_name_matches_dir(self):
        for d in SKILL_DIRS:
            fm = _frontmatter((d / "SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual(fm.get("name"), d.name, f"{d.name}: name 불일치")
            self.assertTrue(fm.get("description"), f"{d.name}: description 비어있음")


class InstallScriptTest(unittest.TestCase):
    def test_install_lists_all_skills(self):
        import re as _re
        txt = (ROOT / "install.sh").read_text(encoding="utf-8")
        m = _re.search(r'SKILLS="([^"]+)"', txt)
        self.assertIsNotNone(m, "install.sh 에 SKILLS= 목록 없음")
        listed = set(m.group(1).split())
        actual = {d.name for d in SKILL_DIRS}
        self.assertEqual(listed, actual,
                         "install.sh 스킬 목록이 실제 .claude/skills/eb-* 와 불일치")


class DocCommandConsistencyTest(unittest.TestCase):
    def test_referenced_eb_commands_exist(self):
        valid = _eb_commands()
        self.assertIn("search", valid)   # 파서가 제대로 읽혔는지 가드
        bad = []
        for f in DOC_FILES:
            if not f.exists():
                continue
            for ln in f.read_text(encoding="utf-8").splitlines():
                s = ln.strip()
                if s.startswith("$ "):
                    s = s[2:]
                if not s.startswith("python eb.py"):
                    continue
                rest = s[len("python eb.py"):].split("#", 1)[0]
                tokens = rest.split()
                # 명령처럼 보이는 토큰(소문자-하이픈, 플래그/플레이스홀더 아님)
                cmds = [t for t in tokens if re.fullmatch(r"[a-z][a-z-]+", t)]
                if not cmds:
                    continue  # 전부 플래그/플레이스홀더(예: --db ...): 건너뜀
                if not any(t in valid for t in cmds):
                    bad.append(f"{f.relative_to(ROOT)}: {s}")
        self.assertEqual(bad, [], "존재하지 않는 eb.py 명령 참조:\n" + "\n".join(bad))

    def test_referenced_scripts_exist(self):
        joined = "\n".join(
            f.read_text(encoding="utf-8") for f in DOC_FILES if f.exists())
        if "python ingest.py" in joined:
            self.assertTrue((ROOT / "ingest.py").exists())
        if "python sync.py" in joined:
            self.assertTrue((ROOT / "sync.py").exists())


if __name__ == "__main__":
    unittest.main()

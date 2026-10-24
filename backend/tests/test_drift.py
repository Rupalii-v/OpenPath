import json

from app.drift_scan import RepoContext, apply_replacements, rule_line, scan_readme

CTX = RepoContext(
    ["package.json", "src/index.js", "requirements.txt", "README.md", "docs/guide.md", "Makefile"],
    {"package.json": json.dumps({"scripts": {"dev": "vite", "build": "vite build"}}), "Makefile": "build:\n\techo\n"},
)

README = """# Demo
```bash
git clone https://github.com/a/demo.git
cd demo
npm install
npm run develop
pip install -r requirements-dev.txt
make biuld
```
See [guide](docs/guid.md).
"""


def test_detects_confirmed_drift_with_evidence():
    kinds = {(f.kind, f.target) for f in scan_readme(README, CTX)}
    assert ("missing_script", "develop") in kinds
    assert ("missing_file", "requirements-dev.txt") in kinds
    assert ("missing_make_target", "biuld") in kinds
    assert ("broken_link", "docs/guid.md") in kinds


def test_clean_readme_has_no_findings():
    clean = "```bash\nnpm install\nnpm run dev\npip install -r requirements.txt\nmake build\n```\nSee `docs/guide.md`.\n"
    assert scan_readme(clean, CTX) == []


def test_rule_fix_removes_the_finding():
    findings = [f for f in scan_readme(README, CTX) if f.kind == "missing_script"]
    fixed = rule_line("npm run develop", findings)
    assert fixed == "npm run dev"
    assert not [f for f in scan_readme(apply_replacements(README, {6: fixed}), CTX) if f.kind == "missing_script"]


def test_generated_and_placeholder_paths_are_ignored():
    assert scan_readme("Create `.env`, then `venv/` and `your_file.py`.\n", CTX) == []

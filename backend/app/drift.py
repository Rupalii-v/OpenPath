"""Documentation-drift pipeline: deterministic scan -> Gemma proposes fixes -> code verifies them."""
from __future__ import annotations

import asyncio
import posixpath
import re
from collections import defaultdict

from . import github_client as gh
from . import llm
from .drift_scan import (Finding, RepoContext, apply_replacements, rule_line, scan_readme, unified_diff)

MAX_AI_LINES = 10


def parse_repo(ref: str) -> tuple[str, str]:
    m = re.match(r"^(?:https?://github\.com/)?([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/.*)?$", ref.strip())
    if not m:
        raise ValueError("Enter a repository as owner/name or a github.com URL.")
    return m.group(1), m.group(2)


async def load_context(owner: str, repo: str):
    info = await gh.get_repo(owner, repo)
    branch = info["default_branch"]
    (paths, truncated), (readme_path, readme) = await asyncio.gather(
        gh.get_tree_paths(owner, repo, branch), gh.get_readme(owner, repo))
    wanted = [p for p in paths if posixpath.basename(p) in ("package.json", "Makefile", "makefile", "GNUmakefile")
              and "node_modules" not in p and p.count("/") <= 2][:8]
    texts = await asyncio.gather(*[gh.get_file_text(owner, repo, p, branch) for p in wanted], return_exceptions=True)
    files = {p: t for p, t in zip(wanted, texts) if isinstance(t, str)}
    return info, RepoContext(paths, files), readme_path, readme, truncated


def _keys(findings: list[Finding]) -> set:
    return {f.key() for f in findings}


async def analyze(repo_ref: str) -> dict:
    owner, repo = parse_repo(repo_ref)
    info, ctx, readme_path, readme, truncated = await load_context(owner, repo)
    lines = readme.split("\n")

    findings = scan_readme(readme, ctx)
    for i, f in enumerate(findings):
        f.id = f"f{i}"
    keys0 = _keys(findings)

    by_line: dict[int, list[Finding]] = defaultdict(list)
    for f in findings:
        by_line[f.line].append(f)

    # 1) Gemma proposes corrected lines (confirmed problems first).
    ai_repl: dict[int, str] = {}
    ai_notes: dict[int, str] = {}
    ai_used, ai_error = False, None
    if findings:
        ordered = sorted(by_line.items(), key=lambda kv: (all(f.severity != "confirmed" for f in kv[1]), kv[0]))[:MAX_AI_LINES]
        items = [{"line": ln, "original": lines[ln - 1],
                  "problems": [f"{f.title}. {f.evidence}" + (f" Hint: replace '{f.replace_from}' with '{f.replace_to}'." if f.replace_to else "") for f in fs]}
                 for ln, fs in ordered]
        try:
            fixes = await llm.propose_fixes(items)
            ai_used = True
            for ln, fx in fixes.items():
                new = fx["fixed_line"].rstrip("\n")
                orig = lines[ln - 1] if 1 <= ln <= len(lines) else None
                if orig is None or "\n" in new or not new.strip() or new == orig or len(new) > 4 * len(orig) + 200:
                    continue
                if orig[:1].isspace() and not new[:1].isspace():
                    new = orig[: len(orig) - len(orig.lstrip())] + new
                ai_repl[ln], ai_notes[ln] = new, fx["note"]
        except llm.LLMError as exc:
            ai_error = str(exc)

    # 2) Code verifies each AI line; anything unverified falls back to a rule-based fix.
    final = dict(ai_repl)
    remaining = _keys(scan_readme(apply_replacements(readme, final), ctx))
    source: dict[int, str] = {ln: "ai" for ln in final}
    for ln, fs in by_line.items():
        if any(f.key() in remaining for f in fs) or ln not in final:
            rl = rule_line(lines[ln - 1], fs)
            if rl != lines[ln - 1]:
                final[ln], source[ln] = rl, "rule"
            else:
                final.pop(ln, None)
                source.pop(ln, None)

    # 3) Never accept a patch that introduces new problems.
    for _ in range(2):
        after = scan_readme(apply_replacements(readme, final), ctx)
        new_lines = {k[2] for k in _keys(after) - keys0}
        if not new_lines:
            break
        for ln in new_lines:
            final.pop(ln, None)
            source.pop(ln, None)
    patched = apply_replacements(readme, final)
    remaining = _keys(scan_readme(patched, ctx))

    for f in findings:
        if f.key() not in remaining:
            f.fix_status, f.fix_source = "fixed", source.get(f.line)
            f.ai_note = ai_notes.get(f.line) if source.get(f.line) == "ai" else None
        else:
            f.fix_status = "needs_human"

    fixed = sum(1 for f in findings if f.fix_status == "fixed")
    return {
        "repo": info["full_name"],
        "default_branch": info["default_branch"],
        "readme_path": readme_path,
        "tree_truncated": truncated,
        "files_checked": len(ctx.paths),
        "findings": [f.to_dict() for f in findings],
        "patch": unified_diff(readme, patched, readme_path) if final else None,
        "summary": {
            "total": len(findings),
            "confirmed": sum(1 for f in findings if f.severity == "confirmed"),
            "uncertain": sum(1 for f in findings if f.severity == "uncertain"),
            "fixed_in_patch": fixed,
            "needs_human": len(findings) - fixed,
            "ai_used": ai_used,
            "ai_error": ai_error,
        },
    }


async def compare(repo_ref: str, snippet: str, source_path: str) -> dict:
    owner, repo = parse_repo(repo_ref)
    info = await gh.get_repo(owner, repo)
    source = await gh.get_file_text(owner, repo, source_path.strip().lstrip("/"), info["default_branch"])
    analysis = await llm.compare_doc_code(snippet, source_path, source)
    return {"repo": info["full_name"], "source_path": source_path, "analysis": analysis,
            "verified": False, "note": "AI analysis - unverified. Review before changing any documentation."}

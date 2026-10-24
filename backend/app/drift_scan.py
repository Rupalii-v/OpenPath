"""Deterministic documentation-drift checks (standard library only).

Reads a README and verifies what it claims against the repository's real file
tree, package.json scripts and Makefile targets. No AI is involved: every
"confirmed" finding comes with the exact evidence that was checked.
"""
from __future__ import annotations

import difflib
import json
import posixpath
import re
import shlex
from dataclasses import dataclass
from typing import Callable, Optional

FENCE = re.compile(r"^(```+|~~~+)\s*([\w+-]*)")
SHELL_LANGS = {"", "sh", "bash", "shell", "console", "zsh", "terminal"}
INLINE = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
PATHLIKE = re.compile(r"^[\w@.\-]+(/[\w@.\-]+)*/?$")
PLACEHOLDER = re.compile(r"^(your|my|foo|bar|example|xxx|path|name)[-_.]|yourfile|<|>", re.I)
KNOWN_EXT = {
    "py", "js", "jsx", "ts", "tsx", "json", "md", "yml", "yaml", "toml", "txt", "sh", "cfg", "ini",
    "lock", "html", "css", "go", "rs", "java", "kt", "rb", "php", "c", "cpp", "h", "cs", "sql", "xml",
    "gradle", "mjs", "cjs",
}
GENERATED = {
    ".env", "venv", ".venv", "env", "node_modules", "dist", "build", "out", "coverage",
    "__pycache__", ".git", "target", "bin", "obj", ".next", "site", "tmp", "output",
}
NODE_BUILTINS = {
    "install", "i", "add", "remove", "rm", "init", "create", "audit", "update", "upgrade", "up",
    "publish", "link", "unlink", "config", "cache", "help", "version", "info", "why", "list", "ls",
    "dlx", "exec", "x", "pack", "outdated", "login", "logout", "whoami", "global", "workspaces",
    "workspace", "set", "node", "bin", "import", "patch", "store", "rebuild", "prune", "dedupe",
    "fetch", "env", "setup", "run",
}
MANIFESTS = {  # command -> (subcommands that need the file or None for any, files)
    "cargo": ({"build", "run", "test", "check"}, ["Cargo.toml"]),
    "mvn": (None, ["pom.xml"]),
    "bundle": ({"install", "exec"}, ["Gemfile"]),
    "composer": ({"install", "update"}, ["composer.json"]),
    "poetry": ({"install"}, ["pyproject.toml"]),
    "go": ({"run", "build", "test"}, ["go.mod"]),
}
COMPOSE_FILES = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]


def _norm(path: str) -> str:
    p = posixpath.normpath(path.strip().replace("\\", "/"))
    if p == ".":
        return ""
    return p[2:] if p.startswith("./") else p


def _join(cwd: str, path: str) -> str:
    return _norm(posixpath.join(cwd, path)) if cwd else _norm(path)


class RepoContext:
    """Everything the scanner needs to know about a repository."""

    def __init__(self, paths, files: Optional[dict] = None):
        self.paths = set(paths)
        self.files = files or {}
        self.dirs: set[str] = set()
        self.by_name: dict[str, list[str]] = {}
        for p in self.paths:
            parts = p.split("/")
            for i in range(1, len(parts)):
                self.dirs.add("/".join(parts[:i]))
            self.by_name.setdefault(parts[-1].lower(), []).append(p)

    def exists(self, path: str) -> bool:
        p = _norm(path)
        return p == "" or p in self.paths or p in self.dirs

    def is_dir(self, path: str) -> bool:
        p = _norm(path)
        return p == "" or p in self.dirs

    def scripts(self, cwd: str) -> Optional[dict]:
        text = self.files.get(_join(cwd, "package.json"))
        if text is None:
            return None
        try:
            return dict(json.loads(text).get("scripts") or {})
        except (ValueError, AttributeError):
            return {}

    def make_targets(self, cwd: str) -> Optional[set]:
        for name in ("Makefile", "makefile", "GNUmakefile"):
            text = self.files.get(_join(cwd, name))
            if text is not None:
                return set(re.findall(r"^([A-Za-z0-9_.\-]+)\s*:(?!=)", text, re.M))
        return None

    def moved(self, token: str) -> Optional[str]:
        """If a missing file exists exactly once elsewhere in the repo, return that path."""
        hits = self.by_name.get(posixpath.basename(token.rstrip("/")).lower(), [])
        return hits[0] if len(hits) == 1 else None


@dataclass
class Finding:
    kind: str
    severity: str          # "confirmed" (checked against the repo) or "uncertain"
    line: int
    text: str
    title: str
    evidence: str
    target: str
    replace_from: Optional[str] = None
    replace_to: Optional[str] = None
    id: str = ""
    fix_status: str = "unfixed"       # unfixed | fixed | needs_human
    fix_source: Optional[str] = None  # ai | rule
    ai_note: Optional[str] = None

    def key(self) -> tuple:
        return (self.kind, self.target, self.line)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "severity": self.severity, "line": self.line,
            "text": self.text, "title": self.title, "evidence": self.evidence,
            "suggestion": (f"Replace `{self.replace_from}` with `{self.replace_to}`"
                           if self.replace_from and self.replace_to else None),
            "fix_status": self.fix_status, "fix_source": self.fix_source, "ai_note": self.ai_note,
        }


Emit = Callable[[Finding], None]


def _close(name: str, options) -> Optional[str]:
    m = difflib.get_close_matches(name, list(options), n=1, cutoff=0.6)
    return m[0] if m else None


# --------------------------------------------------------------------------- scanning
def scan_readme(readme: str, ctx: RepoContext) -> list[Finding]:
    findings: list[Finding] = []
    seen: set = set()

    def emit(f: Finding) -> None:
        if f.key() not in seen:
            seen.add(f.key())
            findings.append(f)

    in_block, fence, lang, cwd, cloned = False, "", "", "", None
    for no, raw in enumerate(readme.splitlines(), 1):
        s = raw.strip()
        m = FENCE.match(s)
        if m:
            if in_block and s.startswith(fence[:3]):
                in_block = False
            elif not in_block:
                in_block, fence, lang, cwd, cloned = True, m.group(1), m.group(2).lower(), "", None
            continue
        if in_block:
            if lang in SHELL_LANGS:
                cwd, cloned = _scan_command_line(no, raw, cwd, cloned, ctx, emit)
        else:
            _scan_prose(no, raw, ctx, emit)
    return findings


def _scan_command_line(no, raw, cwd, cloned, ctx, emit):
    cmd = re.sub(r"^\s*(\$|>|PS>)\s+", "", raw).strip()
    if not cmd or cmd.startswith("#"):
        return cwd, cloned
    for part in re.split(r"\s*(?:&&|;|\|\|)\s*", cmd):
        try:
            tokens = shlex.split(part)
        except ValueError:
            continue
        while tokens and (tokens[0] == "sudo" or re.match(r"^[A-Z_][A-Z0-9_]*=", tokens[0])):
            tokens = tokens[1:]
        if not tokens:
            continue
        exe, args = tokens[0], tokens[1:]

        if exe == "git" and args[:1] == ["clone"]:
            pos = [a for a in args[1:] if not a.startswith("-")]
            if pos:
                cloned = pos[1] if len(pos) > 1 else re.sub(r"\.git$", "", pos[0].rstrip("/").split("/")[-1]).split(":")[-1]
            continue
        if exe == "mkdir":
            cloned = (args[-1] if args else cloned)
            continue
        if exe == "cd" and args:
            target = args[0]
            if cloned and target.rstrip("/") == cloned:
                cwd, cloned = "", None
                continue
            if target[0] in "~/$" or target == "-":
                continue
            new = _join(cwd, target)
            if ctx.is_dir(new):
                cwd = new
            elif not cloned:
                emit(Finding("missing_dir", "uncertain", no, raw.strip(), f"Directory `{target}` not found",
                             f"Line {no} runs `cd {target}` but `{new}` is not a directory in the repository.",
                             new, target, ctx.moved(target)))
            continue
        _check_command(no, raw, exe, args, cwd, ctx, emit)
    return cwd, cloned


def _need_file(no, raw, path, cwd, ctx, emit, what="references"):
    if not path or any(c in path for c in "$*<>{}") or path[0] in "~/" or "://" in path:
        return
    full = _join(cwd, path)
    if ctx.exists(full):
        return
    moved = ctx.moved(path)
    to = None
    if moved:
        to = posixpath.relpath(moved, cwd or ".")
    evidence = f"Line {no} {what} `{path}` (resolved to `{full}`), but that file does not exist on the default branch."
    if moved:
        evidence += f" A file with that name exists at `{moved}`."
    emit(Finding("missing_file", "confirmed", no, raw.strip(), f"`{path}` does not exist", evidence, full, path, to))


def _check_command(no, raw, exe, args, cwd, ctx, emit):
    pos = [a for a in args if not a.startswith("-")]
    need = lambda p, what="references": _need_file(no, raw, p, cwd, ctx, emit, what)

    if exe in ("npm", "yarn", "pnpm", "bun"):
        _check_node(no, raw, exe, pos, cwd, ctx, emit)
    elif exe in ("pip", "pip3") or (exe in ("python", "python3", "py") and args[:2] == ["-m", "pip"]):
        a = args if exe.startswith("pip") else args[2:]
        if a[:1] == ["install"]:
            for flag in ("-r", "--requirement"):
                if flag in a and a.index(flag) + 1 < len(a):
                    need(a[a.index(flag) + 1], "installs from")
                    return
            if any(x == "." or x.startswith(".[") for x in a):
                if not any(ctx.exists(_join(cwd, f)) for f in ("pyproject.toml", "setup.py", "setup.cfg")):
                    emit(Finding("missing_manifest", "confirmed", no, raw.strip(), "No Python package definition found",
                                 f"Line {no} runs `pip install .` but there is no pyproject.toml, setup.py or setup.cfg in `{cwd or '/'}`.",
                                 f"{cwd}:pyproject"))
    elif exe in ("python", "python3", "py"):
        first = next((a for a in args if not a.startswith("-")), None)
        if first and first.endswith(".py"):
            need(first, "runs")
    elif exe == "make":
        targets = ctx.make_targets(cwd)
        target = pos[0] if pos else None
        if targets is None:
            emit(Finding("missing_manifest", "confirmed", no, raw.strip(), "No Makefile found",
                         f"Line {no} runs `make` but there is no Makefile in `{cwd or '/'}`.", f"{cwd}:Makefile"))
        elif target and target not in targets:
            to = _close(target, targets)
            emit(Finding("missing_make_target", "confirmed", no, raw.strip(), f"Make target `{target}` not found",
                         f"Line {no} runs `make {target}`. Targets in the Makefile: {', '.join(sorted(targets)) or 'none'}.",
                         target, target, to))
    elif exe in ("bash", "sh", "zsh") and pos and pos[0].endswith(".sh"):
        need(pos[0], "runs")
    elif exe.startswith("./") or exe.startswith("../"):
        need(exe, "runs")
    elif exe == "cp" and len(pos) >= 2:
        need(pos[0], "copies")
    elif exe in ("docker", "docker-compose"):
        if exe == "docker" and pos[:1] != ["compose"]:
            return
        explicit = False
        for i, a in enumerate(args):
            if a in ("-f", "--file") and i + 1 < len(args):
                need(args[i + 1], "uses")
                explicit = True
        if not explicit and pos and pos[-1] in ("up", "build", "down") and not any(ctx.exists(_join(cwd, f)) for f in COMPOSE_FILES):
            emit(Finding("missing_manifest", "confirmed", no, raw.strip(), "No Docker Compose file found",
                         f"Line {no} runs docker compose but `{cwd or '/'}` has no compose file.", f"{cwd}:compose"))
    elif exe in MANIFESTS:
        subs, files = MANIFESTS[exe]
        if (subs is None or (pos and pos[0] in subs)) and not any(ctx.exists(_join(cwd, f)) for f in files):
            emit(Finding("missing_manifest", "confirmed", no, raw.strip(), f"`{files[0]}` not found",
                         f"Line {no} runs `{exe}` but `{files[0]}` does not exist in `{cwd or '/'}`.", f"{cwd}:{files[0]}"))


def _check_node(no, raw, exe, pos, cwd, ctx, emit):
    scripts = ctx.scripts(cwd)
    sub = pos[0] if pos else None
    script = None
    if exe == "npm":
        if sub in ("run", "run-script") and len(pos) > 1:
            script = pos[1]
        elif sub in ("test", "t", "start", "stop", "restart"):
            script = "test" if sub == "t" else sub
    else:
        if sub == "run" and len(pos) > 1:
            script = pos[1]
        elif sub and sub not in NODE_BUILTINS:
            script = sub
    if script is None:
        if sub in ("install", "i", "ci") and len(pos) == 1 and scripts is None and not ctx.exists(_join(cwd, "package.json")):
            emit(Finding("missing_manifest", "confirmed", no, raw.strip(), "No package.json found",
                         f"Line {no} runs `{exe} {sub}` but there is no package.json in `{cwd or '/'}`.", f"{cwd}:package.json"))
        return
    if scripts is None:
        emit(Finding("missing_manifest", "confirmed", no, raw.strip(), "No package.json found",
                     f"Line {no} runs `{exe} {script}` but there is no package.json in `{cwd or '/'}`.", f"{cwd}:package.json"))
    elif script not in scripts:
        to = _close(script, scripts)
        emit(Finding("missing_script", "confirmed", no, raw.strip(), f"npm script `{script}` does not exist",
                     f"Line {no} runs `{exe} {script}`. package.json defines these scripts: {', '.join(sorted(scripts)) or 'none'}.",
                     script, script, to))


def _scan_prose(no, raw, ctx, emit):
    for m in LINK.finditer(raw):
        target = m.group(1)
        if re.match(r"^([a-z][a-z0-9+.-]*:|#|//)", target, re.I):
            continue
        path = target.split("#")[0].split("?")[0]
        if not path or path.startswith("/") or any(c in path for c in "*<>{}") or path.endswith("badge.svg"):
            continue
        if not ctx.exists(path):
            moved = ctx.moved(path)
            emit(Finding("broken_link", "confirmed", no, raw.strip(), f"Link target `{path}` does not exist",
                         f"Line {no} links to `{path}`, which is not in the repository." + (f" A file with that name exists at `{moved}`." if moved else ""),
                         path, path, moved))

    for m in INLINE.finditer(raw):
        tok = m.group(1).strip()
        if not PATHLIKE.match(tok) or tok.startswith(("/", "..", "-")) or PLACEHOLDER.search(tok):
            continue
        is_dir = tok.endswith("/")
        base = posixpath.basename(tok.rstrip("/"))
        ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
        if not (is_dir or ext in KNOWN_EXT):
            continue
        if base.lower() in GENERATED or any(seg.lower() in GENERATED for seg in tok.split("/")):
            continue
        if ctx.exists(tok):
            continue
        if "/" not in tok.rstrip("/") and ctx.by_name.get(base.lower()):
            continue  # same name exists elsewhere; not clearly wrong
        moved = None if is_dir else ctx.moved(tok)
        emit(Finding("missing_path", "uncertain", no, raw.strip(), f"`{tok}` not found in the repository",
                     f"Line {no} mentions `{tok}` but it is not in the file tree. It may be a file the reader is meant to create, so please check." +
                     (f" A file with that name exists at `{moved}`." if moved else ""),
                     _norm(tok), tok, moved))


# --------------------------------------------------------------------------- patching
def apply_replacements(readme: str, replacements: dict[int, str]) -> str:
    lines = readme.split("\n")
    for ln, text in replacements.items():
        if 1 <= ln <= len(lines):
            lines[ln - 1] = text
    return "\n".join(lines)


def rule_line(original: str, findings: list[Finding]) -> str:
    """Deterministic fix: apply each finding's suggested substitution to the line."""
    out = original
    for f in findings:
        if f.replace_from and f.replace_to and f.replace_from in out:
            out = out.replace(f.replace_from, f.replace_to, 1)
    return out


def unified_diff(original: str, patched: str, path: str) -> str:
    return "".join(difflib.unified_diff(
        original.splitlines(True), patched.splitlines(True), fromfile=f"a/{path}", tofile=f"b/{path}"))

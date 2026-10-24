"""Deterministic matching and readiness checks.

Everything in this file is plain Python: the score, the breakdown and every
readiness flag are computed from GitHub data, never by the language model.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

ALIASES = {
    "js": "javascript", "ts": "typescript", "py": "python", "reactjs": "react",
    "react.js": "react", "nodejs": "node", "node.js": "node", "golang": "go",
    "cpp": "c++", "csharp": "c#",
}
# Short words that also appear in normal English; only match them in labels/topics.
AMBIGUOUS = {"go", "c", "r"}

BEGINNER_LABELS = (
    "good first issue", "good-first-issue", "first-timers-only", "first timers only",
    "beginner", "starter", "easy", "low-hanging-fruit", "newcomer",
)
HELP_LABELS = ("help wanted", "help-wanted")
DOC_LABELS = ("documentation", "docs", "typo")

CLAIM_RE = re.compile(
    r"\b(i['’]?ll (take|work on|do|try)|i can (take|work on|do)|can i (work on|take|be assigned|try)"
    r"|may i (work on|take)|i(?:['’]m| am) (working on|on it|taking)|working on (this|it)"
    r"|assign (this |it )?to me|i would like to (work|take|contribute)|i want to (work|take)"
    r"|taking this|let me (work|take|try))\b",
    re.I,
)


def norm(term: str) -> str:
    t = term.strip().lower()
    return ALIASES.get(t, t)


def contains_term(haystack: str, term: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9+#])"
    return re.search(pattern, haystack) is not None


def days_since(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, (datetime.now(timezone.utc) - dt).days)


# --------------------------------------------------------------------------- readiness
def assess_readiness(issue: dict, comments: Optional[list], timeline: Optional[list]) -> dict:
    """Facts about whether an issue is really open and free to take.

    `comments` / `timeline` are None when the GitHub call failed; those checks
    are then reported as "unknown" instead of guessed.
    """
    pr_status, pr_urls = "unknown", []
    if timeline is not None:
        for ev in timeline:
            src = (ev.get("source") or {}).get("issue") or {}
            if ev.get("event") == "cross-referenced" and "pull_request" in src and src.get("state") == "open":
                pr_urls.append(src.get("html_url"))
        pr_status = "open" if pr_urls else "none"

    claim_status, claim_by = "unknown", None
    if comments is not None:
        claim_status = "none"
        for c in comments:
            user = c.get("user") or {}
            if user.get("type") == "Bot":
                continue
            if CLAIM_RE.search(c.get("body") or ""):
                claim_status, claim_by = "found", user.get("login")
                break

    labels = [l.lower() for l in issue.get("labels", [])]
    return {
        "is_open": issue.get("state") == "open",
        "unassigned": issue.get("assignees", 0) == 0,
        "pr_status": pr_status,
        "pr_urls": pr_urls,
        "claim_status": claim_status,
        "claim_by": claim_by,
        "days_since_update": days_since(issue.get("updated_at")),
        "beginner_label": any(b in l for l in labels for b in BEGINNER_LABELS),
    }


def exclusion_reasons(readiness: dict) -> list[str]:
    reasons = []
    if not readiness["is_open"]:
        reasons.append("Issue is closed")
    if not readiness["unassigned"]:
        reasons.append("Already assigned to someone")
    if readiness["pr_status"] == "open":
        reasons.append("An open pull request already references it")
    return reasons


# --------------------------------------------------------------------------- scoring
def score_issue(issue: dict, profile: Any, repo_info: Optional[dict] = None,
                readiness: Optional[dict] = None) -> dict:
    """Return {"score": 0-100, "breakdown": [...], "reasons": [...]}.

    `profile` only needs .skills, .languages, .interests and .level attributes.
    """
    repo_info = repo_info or {}
    labels = [l.lower() for l in issue.get("labels", [])]
    topics = [t.lower() for t in repo_info.get("topics", [])]
    language = (issue.get("language") or repo_info.get("language") or "").strip()

    hay = " ".join([
        issue.get("title", ""), issue.get("body", ""), " ".join(labels),
        issue.get("repo", ""), repo_info.get("description") or "", " ".join(topics),
    ]).lower()
    strict = " ".join(labels + topics + ([language.lower()] if language else []))

    def matched(terms: list[str]) -> list[str]:
        hits = []
        for raw in terms:
            t = norm(raw)
            target = strict if t in AMBIGUOUS else hay
            if contains_term(target, t):
                hits.append(raw)
        return hits

    breakdown, reasons = [], []

    # 1. Language (25)
    wanted = [norm(l) for l in profile.languages]
    if not wanted:
        pts, detail = 12, "No language preference set"
    elif language and norm(language) in wanted:
        pts, detail = 25, f"Repository language is {language}"
        reasons.append(f"Uses {language}, one of your languages")
    else:
        pts, detail = 0, f"Repository language is {language or 'unknown'}"
    breakdown.append({"key": "language", "label": "Language", "points": pts, "max": 25, "detail": detail})

    # 2. Skills (30)
    skills = profile.skills
    hits = matched(skills)
    if skills:
        pts = round(30 * min(1, len(hits) / min(len(skills), 3)))
        detail = f"Mentions: {', '.join(hits)}" if hits else "None of your skills appear in the issue or repo"
        if hits:
            reasons.append(f"Mentions your skills: {', '.join(hits)}")
    else:
        pts, detail = 0, "No skills entered"
    breakdown.append({"key": "skills", "label": "Skills", "points": pts, "max": 30, "detail": detail})

    # 3. Interests (10)
    ihits = matched(profile.interests)
    if profile.interests:
        pts = round(10 * min(1, len(ihits) / min(len(profile.interests), 2)))
        detail = f"Related to: {', '.join(ihits)}" if ihits else "No interest keywords found"
        if ihits:
            reasons.append(f"Matches your interests: {', '.join(ihits)}")
    else:
        pts, detail = 0, "No interests entered"
    breakdown.append({"key": "interests", "label": "Interests", "points": pts, "max": 10, "detail": detail})

    # 4. Difficulty signal from labels (15)
    beginner = any(b in l for l in labels for b in BEGINNER_LABELS)
    helpw = any(h in l for l in labels for h in HELP_LABELS)
    docs = any(d in l for l in labels for d in DOC_LABELS)
    if profile.level == "intermediate":
        pts = 15 if helpw else 8 if beginner else 5 if docs else 0
    else:
        pts = 15 if beginner else 10 if helpw else 8 if docs else 0
    names = [l for l in issue.get("labels", []) if any(k in l.lower() for k in BEGINNER_LABELS + HELP_LABELS + DOC_LABELS)]
    detail = f"Labels: {', '.join(names)}" if names else "No beginner-friendly label"
    if pts >= 10:
        reasons.append("Labelled as suitable for newcomers" if profile.level == "beginner" else "Maintainers want help on it")
    breakdown.append({"key": "difficulty", "label": "Difficulty fit", "points": pts, "max": 15, "detail": detail})

    # 5. Readiness (15)
    if readiness is None:
        pts, detail = 7, "Not verified yet"
    else:
        pts = 4 if readiness["unassigned"] else 0
        pts += {"none": 4, "unknown": 2, "open": 0}[readiness["pr_status"]]
        pts += {"none": 4, "unknown": 2, "found": 0}[readiness["claim_status"]]
        d = readiness["days_since_update"]
        pts += 3 if d is not None and d <= 30 else 2 if d is not None and d <= 90 else 0
        detail = "Unassigned, no linked PR, recent activity" if pts >= 14 else "Some readiness checks failed or are unknown"
        if pts >= 14:
            reasons.append("Verified open, unassigned and recently active")
    breakdown.append({"key": "readiness", "label": "Ready to work on", "points": pts, "max": 15, "detail": detail})

    # 6. Clarity (5)
    n = len((issue.get("body") or "").strip())
    pts = 5 if n >= 200 else 3 if n >= 60 else 0
    detail = "Detailed description" if n >= 200 else "Short description" if n >= 60 else "Almost no description - ask the maintainer first"
    breakdown.append({"key": "clarity", "label": "Clarity", "points": pts, "max": 5, "detail": detail})

    return {"score": sum(b["points"] for b in breakdown), "breakdown": breakdown, "reasons": reasons}

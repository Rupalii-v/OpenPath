"""Local Gemma client (Ollama). Gemma explains and suggests; it never decides facts."""
from __future__ import annotations

import json
import re
from typing import Optional

import httpx

from .config import OLLAMA_HOST, OLLAMA_MODEL


class LLMError(Exception):
    pass


async def chat(messages: list[dict], *, json_mode: bool = False, temperature: float = 0.2, timeout: float = 180) -> str:
    payload = {"model": OLLAMA_MODEL, "messages": messages, "stream": False, "options": {"temperature": temperature}}
    if json_mode:
        payload["format"] = "json"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
    except httpx.ConnectError as exc:
        raise LLMError(f"Cannot reach Ollama at {OLLAMA_HOST}. Start it with `ollama serve`.") from exc
    except httpx.TimeoutException as exc:
        raise LLMError("The local model timed out. Try a smaller Gemma variant via OLLAMA_MODEL.") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"Ollama request failed: {exc}") from exc

    if resp.status_code == 404:
        raise LLMError(f"Model '{OLLAMA_MODEL}' is not installed. Run `ollama pull {OLLAMA_MODEL}` or set OLLAMA_MODEL in backend/.env.")
    if resp.status_code >= 400:
        raise LLMError(f"Ollama error {resp.status_code}: {resp.text[:200]}")
    content = (resp.json().get("message") or {}).get("content", "").strip()
    if not content:
        raise LLMError("The model returned an empty response.")
    return content


def parse_json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except ValueError:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None
    return None


async def status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
        names = [m.get("name", "") for m in resp.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return {"reachable": False, "model": OLLAMA_MODEL, "installed": False, "available": []}
    installed = any(n == OLLAMA_MODEL or n.startswith(OLLAMA_MODEL + ":") for n in names)
    return {"reachable": True, "model": OLLAMA_MODEL, "installed": installed, "available": names[:12]}


# --------------------------------------------------------------------------- prompts
EXPLAIN_SYSTEM = (
    "You are a friendly open-source mentor helping a first-time contributor. "
    "Use ONLY the facts in the message. If something is not in the facts, say you cannot tell. "
    "Never invent file names, repository details, issue status or scores; those are verified separately. "
    "Be concrete and short. Answer in Markdown with exactly these sections:\n"
    "## Why this fits you\n## What you need to learn\n## First steps\n## Ask the maintainer"
)


async def explain_issue(issue: dict, profile) -> str:
    r = issue.get("readiness") or {}
    facts = {
        "issue_title": issue.get("title"),
        "repository": issue.get("repo"),
        "repository_description": (issue.get("repo_info") or {}).get("description"),
        "labels": issue.get("labels"),
        "issue_description": (issue.get("body") or "")[:2000],
        "verified_by_code": {
            "match_score": issue.get("score"),
            "score_breakdown": [f"{b['label']}: {b['points']}/{b['max']} ({b['detail']})" for b in issue.get("breakdown", [])],
            "linked_open_pr": r.get("pr_status"),
            "claim_comment": r.get("claim_status"),
            "days_since_update": r.get("days_since_update"),
        },
        "contributor": {"skills": profile.skills, "languages": profile.languages,
                        "interests": profile.interests, "level": profile.level},
    }
    user = ("Explain this issue to the contributor.\n"
            "- 'First steps' must be 4-6 numbered steps (fork, read CONTRIBUTING, reproduce, change, test, open PR) adapted to this issue.\n"
            "- 'Ask the maintainer' gives 1-2 clarifying questions if the description is vague.\n\nFACTS:\n"
            + json.dumps(facts, indent=2))
    return await chat([{"role": "system", "content": EXPLAIN_SYSTEM}, {"role": "user", "content": user}], temperature=0.3)


FIX_SYSTEM = (
    "You repair outdated lines in a README. Each item has the original line, problems found by an automated "
    "checker (verified facts), and an optional hint. Change only what is needed to fix the listed problems. "
    "Only use file names, scripts and paths that appear in the facts or the hint - never invent new ones. "
    "If you cannot fix a line with the given facts, return the original line unchanged. "
    'Reply with JSON only: {"fixes":[{"line":<number>,"fixed_line":"<full corrected line>","note":"<one short sentence>"}]}'
)


async def propose_fixes(items: list[dict]) -> dict[int, dict]:
    """items: [{"line": int, "original": str, "problems": [str]}] -> {line: {"fixed_line", "note"}}"""
    text = await chat(
        [{"role": "system", "content": FIX_SYSTEM}, {"role": "user", "content": json.dumps({"items": items}, indent=2)}],
        json_mode=True, temperature=0.1,
    )
    data = parse_json(text) or {}
    out = {}
    for fx in data.get("fixes", []):
        try:
            out[int(fx["line"])] = {"fixed_line": str(fx["fixed_line"]), "note": str(fx.get("note", ""))}
        except (KeyError, ValueError, TypeError):
            continue
    return out


COMPARE_SYSTEM = (
    "You compare a documentation snippet with the source file it describes. Report only mismatches you can "
    "support by quoting BOTH the doc text and the code (short quotes). If everything matches, say so. "
    "Label each item 'Likely mismatch' or 'Possible mismatch'. These are unverified suggestions for a human reviewer. "
    "Finish with a corrected version of the snippet in a fenced block, or write 'No change needed'."
)


async def compare_doc_code(snippet: str, path: str, source: str) -> str:
    user = f"DOC SNIPPET:\n{snippet}\n\nSOURCE FILE `{path}` (may be truncated):\n{source[:10000]}"
    return await chat([{"role": "system", "content": COMPARE_SYSTEM}, {"role": "user", "content": user}], temperature=0.1)

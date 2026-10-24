"""Thin async wrapper around the GitHub REST API (public data only)."""
from __future__ import annotations

import asyncio
import base64
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from . import cache
from .config import GITHUB_TOKEN

API = "https://api.github.com"


class GitHubError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def _headers() -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ContribScout-AI",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


async def _get(path: str, params: Optional[dict] = None, ttl: Optional[int] = None) -> Any:
    url = f"{API}{path}"
    key = f"{url}?{sorted((params or {}).items())}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params, headers=_headers())
    except httpx.HTTPError as exc:
        raise GitHubError(f"Could not reach GitHub: {exc}", 502) from exc

    if resp.status_code == 429 or (resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0"):
        hint = "" if GITHUB_TOKEN else " Add GITHUB_TOKEN to backend/.env to raise the limit."
        raise GitHubError("GitHub API rate limit reached." + hint, 429)
    if resp.status_code == 401:
        raise GitHubError("GitHub token is invalid. Check GITHUB_TOKEN in backend/.env.", 401)
    if resp.status_code == 404:
        raise GitHubError("Not found on GitHub. Check the repository name (private repos are not supported).", 404)
    if resp.status_code >= 400:
        raise GitHubError(f"GitHub API error {resp.status_code}.", 502)

    data = resp.json()
    cache.put(key, data, ttl)
    return data


async def _safe(coro) -> Optional[Any]:
    """Return None instead of raising, so one failed check does not sink a search."""
    try:
        return await coro
    except GitHubError:
        return None


# --------------------------------------------------------------------------- issues
def _quote(value: str) -> str:
    return f'"{value}"' if re.search(r"[^A-Za-z0-9]", value) else value


def normalize_issue(item: dict, language: Optional[str]) -> dict:
    owner, repo = item["repository_url"].split("/")[-2:]
    return {
        "id": item["id"],
        "number": item["number"],
        "title": item["title"],
        "body": (item.get("body") or "")[:3000],
        "url": item["html_url"],
        "repo": f"{owner}/{repo}",
        "labels": [l["name"] for l in item.get("labels", [])],
        "comments": item.get("comments", 0),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "assignees": len(item.get("assignees") or []),
        "state": item.get("state"),
        "author": (item.get("user") or {}).get("login"),
        "language": language,
    }


async def search_issues(language: Optional[str], level: str = "beginner", per_page: int = 30) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    labels = '"help wanted"' if level == "intermediate" else '"good first issue","help wanted"'
    q = [
        "is:issue", "is:open", "no:assignee", "archived:false", "-linked:pr",
        "comments:<6", f"updated:>={cutoff}", f"label:{labels}",
    ]
    if language:
        q.append(f"language:{_quote(language)}")
    data = await _get("/search/issues", {"q": " ".join(q), "sort": "updated", "order": "desc", "per_page": per_page})
    return [normalize_issue(i, language) for i in data.get("items", []) if "pull_request" not in i]


async def get_repo(owner: str, repo: str) -> dict:
    d = await _get(f"/repos/{owner}/{repo}")
    return {
        "full_name": d["full_name"],
        "description": d.get("description"),
        "language": d.get("language"),
        "stars": d.get("stargazers_count", 0),
        "topics": d.get("topics", []),
        "default_branch": d.get("default_branch", "main"),
        "archived": d.get("archived", False),
    }


async def enrich_issue(issue: dict, sem: asyncio.Semaphore) -> dict:
    """Fetch repo info, comments and timeline for one issue (None where a call failed)."""
    owner, repo = issue["repo"].split("/")
    base = f"/repos/{owner}/{repo}/issues/{issue['number']}"
    async with sem:
        info, comments, timeline = await asyncio.gather(
            _safe(get_repo(owner, repo)),
            _safe(_get(f"{base}/comments", {"per_page": 30})),
            _safe(_get(f"{base}/timeline", {"per_page": 50})),
        )
    return {"issue": issue, "repo_info": info, "comments": comments, "timeline": timeline}


async def get_rate_limit() -> Optional[dict]:
    data = await _safe(_get("/rate_limit", ttl=15))
    if not data:
        return None
    core = data.get("resources", {}).get("core", {})
    return {"remaining": core.get("remaining"), "limit": core.get("limit")}


# --------------------------------------------------------------------------- repository content
async def get_tree_paths(owner: str, repo: str, branch: str) -> tuple[list[str], bool]:
    data = await _get(f"/repos/{owner}/{repo}/git/trees/{branch}", {"recursive": "1"})
    paths = [t["path"] for t in data.get("tree", []) if t.get("type") == "blob"]
    return paths, bool(data.get("truncated"))


def _decode(data: dict) -> str:
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return data.get("content", "")


async def get_readme(owner: str, repo: str) -> tuple[str, str]:
    data = await _get(f"/repos/{owner}/{repo}/readme")
    return data.get("path", "README.md"), _decode(data)


async def get_file_text(owner: str, repo: str, path: str, ref: str) -> str:
    data = await _get(f"/repos/{owner}/{repo}/contents/{path}", {"ref": ref})
    if isinstance(data, list):
        raise GitHubError(f"{path} is a directory, not a file.", 400)
    return _decode(data)

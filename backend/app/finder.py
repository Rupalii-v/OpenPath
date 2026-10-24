"""Issue-finder pipeline: search -> pre-rank -> verify readiness -> exclude -> final rank."""
from __future__ import annotations

import asyncio

from . import github_client as gh
from .matcher import assess_readiness, exclusion_reasons, score_issue
from .sample_data import SAMPLE_ISSUES

VERIFY_LIMIT = 14


def _public(issue: dict, repo_info, readiness, result) -> dict:
    return {**issue, "repo_info": repo_info, "readiness": readiness, **result}


async def find_issues(profile, limit: int) -> dict:
    languages = profile.languages[:3] or [None]
    try:
        batches = await asyncio.gather(*[gh.search_issues(lang, profile.level) for lang in languages])
    except gh.GitHubError as exc:
        if exc.status == 429:
            return sample_response(profile, limit, exc.message)
        raise

    unique = {}
    for batch in batches:
        for issue in batch:
            unique.setdefault(issue["id"], issue)
    fetched = len(unique)

    pre = sorted(unique.values(), key=lambda i: score_issue(i, profile)["score"], reverse=True)[:max(VERIFY_LIMIT, limit)]
    sem = asyncio.Semaphore(4)
    enriched = await asyncio.gather(*[gh.enrich_issue(i, sem) for i in pre])

    kept, excluded = [], []
    for e in enriched:
        issue, info = e["issue"], e["repo_info"]
        readiness = assess_readiness(issue, e["comments"], e["timeline"])
        reasons = exclusion_reasons(readiness)
        if info and info.get("archived"):
            reasons.append("Repository is archived")
        result = score_issue(issue, profile, info, readiness)
        item = _public(issue, info, readiness, result)
        if reasons:
            excluded.append({"title": issue["title"], "url": issue["url"], "repo": issue["repo"], "reasons": reasons})
        else:
            kept.append(item)

    kept.sort(key=lambda i: i["score"], reverse=True)
    return {
        "source": "github",
        "warning": None,
        "issues": kept[:limit],
        "filtered_out": excluded,
        "stats": {"fetched": fetched, "verified": len(enriched), "excluded": len(excluded), "returned": min(len(kept), limit)},
    }


def sample_response(profile, limit: int, reason: str) -> dict:
    items = []
    for issue in SAMPLE_ISSUES:
        readiness = {"is_open": True, "unassigned": True, "pr_status": "unknown", "pr_urls": [], "claim_status": "unknown",
                     "claim_by": None, "days_since_update": 5, "beginner_label": "good first issue" in issue["labels"]}
        items.append(_public(issue, None, readiness, score_issue(issue, profile, None, readiness)))
    items.sort(key=lambda i: i["score"], reverse=True)
    return {
        "source": "sample",
        "warning": f"{reason} Showing clearly-labelled SAMPLE issues instead - they are not real GitHub issues.",
        "issues": items[:limit],
        "filtered_out": [],
        "stats": {"fetched": len(items), "verified": 0, "excluded": 0, "returned": min(len(items), limit)},
    }

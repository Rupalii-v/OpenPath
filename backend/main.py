from __future__ import annotations
import os, re, json
from datetime import datetime, timezone
from typing import Any
import requests
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITHUB_API = "https://api.github.com/search/issues"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma3:4b")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

app = FastAPI(title="Orbit OSS API", version="1.0.0", description="Beginner-friendly open-source issue finder powered by GitHub and Gemma.")
app.mount("/static", StaticFiles(directory=os.path.join(ROOT, "static")), name="static")

class Profile(BaseModel):
    skills: list[str] = Field(default_factory=lambda: ["Python"], max_length=12)
    level: str = "beginner"
    time: str = "1-2 hours"
    interest: str = ""

class ExplainRequest(BaseModel):
    issue: dict[str, Any]
    profile: Profile

DEMO_ISSUES = [
    {"repo":"first-contributions/first-contributions","number":1284,"title":"Add a beginner-friendly contribution guide","body":"Help new contributors understand the first pull request workflow. Improve the getting-started instructions and add clear examples.","labels":["good first issue","documentation","help wanted"],"language":"Documentation","updated_at":"2026-10-22T10:00:00Z","html_url":"https://github.com/firstcontributions/first-contributions/issues","comments":4},
    {"repo":"public-apis/public-apis","number":4217,"title":"Improve API entry validation and examples","body":"Review API entries for missing descriptions and improve contribution examples so new contributors can validate their changes locally.","labels":["good first issue","documentation"],"language":"Python","updated_at":"2026-10-21T12:00:00Z","html_url":"https://github.com/public-apis/public-apis/issues","comments":7},
    {"repo":"huggingface/transformers","number":34821,"title":"Add a missing example to the docs","body":"Find a documentation gap and add a short, tested example. Check the repository contribution guide and run relevant documentation checks.","labels":["good first issue"],"language":"Python","updated_at":"2026-10-20T08:30:00Z","html_url":"https://github.com/huggingface/transformers/issues","comments":3},
]

def match_score(item: dict, profile: Profile) -> int:
    labels = " ".join(item.get("labels", [])).lower()
    text = " ".join([str(item.get(k, "")) for k in ("title", "body", "repo", "language")]).lower()
    score = 45
    if "good first issue" in labels or "beginner" in labels or "first-timers-only" in labels: score += 25
    if "help wanted" in labels: score += 10
    if any(s.lower().replace("html/css", "html") in text for s in profile.skills): score += 14
    if any(s.lower() in text for s in profile.skills): score += 5
    if "documentation" in labels and "documentation" in [x.lower() for x in profile.skills]: score += 8
    if item.get("comments", 99) < 15: score += 4
    return min(score, 99)

def reason(item: dict, profile: Profile) -> str:
    labels = " ".join(item.get("labels", [])).lower()
    text = " ".join([str(item.get(k, "")) for k in ("title", "body", "language")]).lower()
    if "good first issue" in labels or "beginner" in labels: return "Marked as beginner-friendly by the project maintainers."
    matching = [s for s in profile.skills if s.lower() in text]
    if matching: return f"Relevant to your {', '.join(matching)} skills or interests."
    if "documentation" in labels: return "Documentation work can be a manageable first contribution."
    return "Review activity, scope, and project guidance before starting."

def demo(profile: Profile) -> list[dict]:
    out = []
    for raw in DEMO_ISSUES:
        item = dict(raw)
        item["match"] = match_score(item, profile)
        item["reason"] = reason(item, profile)
        out.append(item)
    return sorted(out, key=lambda x: x["match"], reverse=True)

def github_headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Orbit-OSS-Finder"}
    if GITHUB_TOKEN: h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h

@app.get("/api/health")
def health():
    return {"ok": True, "github_token_configured": bool(GITHUB_TOKEN), "ollama_url": OLLAMA_URL, "gemma_model": GEMMA_MODEL}

@app.post("/api/search")
def search(profile: Profile):
    skills = [s.strip() for s in profile.skills if s.strip()][:6]
    # GitHub search syntax: look for currently open issues with explicit beginner signals.
    skill_terms = " OR ".join(f'"{s}"' for s in skills if re.fullmatch(r"[A-Za-z0-9+#./ -]{1,30}", s))
    terms = 'is:issue is:open archived:false (label:"good first issue" OR label:"good-for-beginners" OR label:"help wanted")'
    if skill_terms: terms += f" {skill_terms}"
    if profile.interest.strip():
        clean = re.sub(r"[^\w -]", " ", profile.interest.strip())[:50].strip()
        if clean: terms += f' "{clean}"'
    try:
        response = requests.get(GITHUB_API, params={"q": terms, "sort": "updated", "order": "desc", "per_page": 18}, headers=github_headers(), timeout=9)
        if response.status_code == 403:
            return {"source":"demo", "issues":demo(profile), "warning":"GitHub API rate limit reached. Configure GITHUB_TOKEN for a higher limit."}
        response.raise_for_status()
        payload = response.json()
        items = []
        for raw in payload.get("items", []):
            # Search/issues includes pull requests too; exclude them and only show open issues.
            if "pull_request" in raw or raw.get("state") != "open": continue
            labels = [x.get("name", "") for x in raw.get("labels", [])]
            repo = raw.get("repository_url", "").replace("https://api.github.com/repos/", "")
            issue = {"repo":repo, "number":raw.get("number"), "title":raw.get("title", "Untitled issue"), "body":(raw.get("body") or "")[:1200], "labels":labels, "updated_at":raw.get("updated_at"), "html_url":raw.get("html_url"), "comments":raw.get("comments", 0), "language":" / ".join(skills[:2]) or "Open source"}
            issue["match"] = match_score(issue, profile)
            issue["reason"] = reason(issue, profile)
            items.append(issue)
        items.sort(key=lambda x: x["match"], reverse=True)
        return {"source":"github", "total":payload.get("total_count", len(items)), "issues":items[:12]}
    except (requests.RequestException, ValueError) as exc:
        return {"source":"demo", "issues":demo(profile), "warning":"Live GitHub search is temporarily unavailable. Showing preview issues instead."}

@app.post("/api/explain")
def explain(request: ExplainRequest):
    issue = request.issue
    p = request.profile
    system = ("You are Orbit, a careful open-source contribution mentor. Explain issues honestly for beginners. "
              "Never claim an issue is unassigned, active, or beginner-safe unless the provided data proves it. "
              "Use the provided issue only. Return valid JSON with keys fit (string), difficulty (string), steps (array of 3-5 concise strings), cautions (array of 2-4 strings). "
              "Mention that the user should verify the issue is still open/unassigned and read CONTRIBUTING.md.")
    user = {"contributor":{"skills":p.skills,"experience":p.level,"time_available":p.time,"interests":p.interest},
            "issue":{"repository":issue.get("repo"),"number":issue.get("number"),"title":issue.get("title"),"body":(issue.get("body") or "")[:3500],"labels":issue.get("labels", []),"updated_at":issue.get("updated_at"),"comments":issue.get("comments")}}
    try:
        response = requests.post(OLLAMA_URL, json={"model":GEMMA_MODEL,"stream":False,"format":"json","messages":[{"role":"system","content":system},{"role":"user","content":json.dumps(user)}],"options":{"temperature":0.25}}, timeout=75)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        try: parsed = json.loads(content)
        except json.JSONDecodeError: parsed = {"fit":content,"difficulty":"Review the scope and repository setup before beginning.","steps":["Read the full issue and discussion.","Read CONTRIBUTING.md and set up the project.","Ask a focused question if requirements are unclear.","Make a small change and run relevant tests."],"cautions":["Confirm the issue is still open and unassigned.","Follow the repository contribution guide."]}
        return {"model":GEMMA_MODEL,"provider":"ollama","explanation":parsed}
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Gemma is not reachable. Start Ollama and pull the configured model, then try again.")

@app.get("/{path:path}")
def frontend(path: str):
    candidate = os.path.join(ROOT, path)
    if path and os.path.isfile(candidate) and os.path.commonpath([ROOT, os.path.abspath(candidate)]) == ROOT:
        return FileResponse(candidate)
    return FileResponse(os.path.join(ROOT, "static", "index.html"))

"""ContribScout AI - FastAPI entry point."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import config, drift, finder, github_client as gh, llm
from .models import CompareRequest, DriftRequest, ExplainRequest, SearchRequest

app = FastAPI(title="ContribScout AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(gh.GitHubError)
async def github_error_handler(_, exc: gh.GitHubError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status if exc.status in (401, 404, 429) else 502, content={"detail": exc.message})


@app.exception_handler(llm.LLMError)
async def llm_error_handler(_, exc: llm.LLMError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/api/health")
async def health():
    ollama = await llm.status()
    rate = await gh.get_rate_limit()
    return {"github": {"token_configured": bool(config.GITHUB_TOKEN), "rate_limit": rate}, "ollama": ollama}


@app.post("/api/issues/search")
async def search_issues(req: SearchRequest):
    if not req.profile.skills and not req.profile.languages:
        raise HTTPException(400, "Add at least one skill or language so we can match issues to you.")
    return await finder.find_issues(req.profile, req.limit)


@app.post("/api/issues/explain")
async def explain_issue(req: ExplainRequest):
    markdown = await llm.explain_issue(req.issue, req.profile)
    return {"markdown": markdown, "model": config.OLLAMA_MODEL}


@app.post("/api/docs/drift")
async def docs_drift(req: DriftRequest):
    try:
        return await drift.analyze(req.repo)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/docs/compare")
async def docs_compare(req: CompareRequest):
    try:
        return await drift.compare(req.repo, req.doc_snippet, req.source_path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

# ContribScout AI

**Find an issue you can actually take. Understand it. Check that the docs still match the code.**

Hacktoberfest Hack Day 2026 (NST.ADYPU x NSTSDC) - Track 1: Best Open-Source AI Project.
Primary problem statement: **#20 Open-Source Contribution Finder.** Supporting feature: **#18 Documentation Drift Detector.**

## What it does

1. **Issue finder (#20).** Searches live GitHub issues for your languages and skills. For each candidate it checks, through the GitHub API, that the issue is open, unassigned, has no open linked pull request, has no "I'll take this" comment and was recently active. Issues that fail are removed and listed with the reason. The rest get a 0-100 match score with a visible breakdown.
2. **Explain with Gemma.** A local Gemma model turns the verified facts into "why it fits you", what to learn, first steps and questions for the maintainer.
3. **Docs drift detector (#18).** Reads a repository's README and verifies the commands, file paths and links it mentions against the real file tree, `package.json` scripts and Makefile targets. Gemma proposes corrected lines; code then re-scans the patched README and keeps only fixes that actually remove the problem without creating new ones. Output is a unified diff for a human to review.

## Who decides what

| Decision | Made by |
|---|---|
| Is the issue open / assigned / linked to a PR? | GitHub API + code |
| The match score and its breakdown | Rule-based Python (`matcher.py`) |
| Does a README command, file or link exist? | Code (`drift_scan.py`) |
| Is an AI-suggested README fix valid? | Code re-scans the patched README |
| Explanations, first steps, proposed wording | Gemma |
| Whether to apply anything | The human |

Anything the code could not check is shown as unknown or "needs your judgement", never as verified.

## Models, tools and licenses

| Component | Use | License |
|---|---|---|
| Gemma (open-weight, via Ollama) | Explanations and README fix proposals, run locally | Gemma Terms of Use |
| Ollama | Local model runtime | MIT |
| FastAPI, Uvicorn, Pydantic, HTTPX | Backend | MIT / BSD |
| React, Vite, Tailwind CSS, react-markdown | Frontend | MIT |
| GitHub REST API | Public issue and repository data | GitHub Terms |

This project: MIT (see `LICENSE`). No model output is sent to any cloud AI service; only GitHub API calls leave your machine.

## Project structure

```
contribscout-ai/
  backend/
    app/
      main.py           API routes
      finder.py         search -> verify -> exclude -> rank
      matcher.py        scoring + readiness checks (no AI)
      github_client.py  GitHub REST wrapper with caching
      drift_scan.py     README vs repository checks (no AI)
      drift.py          scan -> Gemma proposes -> code verifies -> patch
      llm.py            Ollama client and prompts
      sample_data.py    labelled sample issues, used only when rate limited
      models.py, config.py, cache.py
    tests/              pytest tests for the deterministic logic
    requirements.txt, .env.example
  frontend/
    src/App.jsx, api.js, index.css
    src/components/     ProfileForm, IssueCard, DriftPanel, StatusBar
    package.json, vite.config.js, tailwind.config.js
```

## Setup

You need Python 3.10+, Node 18+, Git and [Ollama](https://ollama.com).

### 1. Local model

```bash
ollama pull gemma4        # use the exact Gemma 4 tag shown on ollama.com/library
ollama list               # confirm the name
```

If your tag differs (for example a size suffix), set `OLLAMA_MODEL` in `backend/.env`.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then edit: add GITHUB_TOKEN and check OLLAMA_MODEL
uvicorn app.main:app --reload --port 8000
```

Create a GitHub token at https://github.com/settings/tokens (no scopes needed). Without one GitHub allows only 60 requests per hour.

### 3. Frontend (second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The status line under the title shows whether the GitHub token and the local model are ready.

### Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## Demo script (4 minutes)

1. **Find.** Pick Python, add `fastapi, testing`, search. Show the "Checked on GitHub" rows and the "Removed because they were not ready" list.
2. **Score.** Click "How is this scored?" and explain that the number comes from fixed rules.
3. **Explain.** Click "Explain with Gemma" on the top result.
4. **Detect.** Open "Check documentation", enter a repository, show a confirmed finding, its evidence and the generated patch. Then explain that code re-checks every AI fix.

Tip: run each search once before presenting. Responses are cached for 10 minutes.

## Limitations

- GitHub search only returns issues labelled `good first issue` or `help wanted`.
- Linked-PR and claim detection use the issue timeline and comment text, so unusual wording can be missed.
- Drift detection covers shell commands, file paths and links in READMEs. It does not yet compare prose descriptions with code behaviour (the optional "compare with Gemma" box does that, and is labelled unverified).
- Match scores are a heuristic, not a promise of difficulty.

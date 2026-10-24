"""Clearly-labelled sample issues, shown ONLY when GitHub is rate-limited so a demo never dies."""

SAMPLE_ISSUES = [
    {
        "id": -1, "number": 1, "title": "[SAMPLE] Add input validation to the /users endpoint",
        "body": "The POST /users endpoint accepts empty names. Add validation with pydantic and a test. "
                "A good first issue for anyone who knows Python and FastAPI. See tests/test_users.py for the existing style.",
        "url": "#", "repo": "sample-org/sample-api", "labels": ["good first issue", "python", "api"],
        "comments": 1, "created_at": None, "updated_at": None, "assignees": 0, "state": "open", "author": "sample", "language": "Python",
    },
    {
        "id": -2, "number": 2, "title": "[SAMPLE] Dark mode toggle flickers on page load",
        "body": "In the React dashboard the theme toggle flashes the light theme before applying dark mode. "
                "Persist the choice in localStorage and apply it before first paint.",
        "url": "#", "repo": "sample-org/sample-dashboard", "labels": ["help wanted", "react", "ui"],
        "comments": 2, "created_at": None, "updated_at": None, "assignees": 0, "state": "open", "author": "sample", "language": "JavaScript",
    },
    {
        "id": -3, "number": 3, "title": "[SAMPLE] Fix typo in installation docs",
        "body": "The installation guide says `pip instal`. Fix the typo.",
        "url": "#", "repo": "sample-org/sample-cli", "labels": ["good first issue", "documentation"],
        "comments": 0, "created_at": None, "updated_at": None, "assignees": 0, "state": "open", "author": "sample", "language": "Python",
    },
]

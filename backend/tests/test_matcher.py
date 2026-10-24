from types import SimpleNamespace

from app.matcher import assess_readiness, exclusion_reasons, score_issue

PROFILE = SimpleNamespace(skills=["python", "fastapi"], languages=["Python"], interests=["api"], level="beginner")


def make_issue(**kw):
    base = {"title": "Add validation to the FastAPI users endpoint", "body": "x" * 250, "repo": "o/r",
            "labels": ["good first issue"], "language": "Python", "state": "open", "assignees": 0,
            "updated_at": None}
    base.update(kw)
    return base


def test_score_is_explainable_and_bounded():
    r = score_issue(make_issue(), PROFILE)
    assert 0 <= r["score"] <= 100
    assert sum(b["points"] for b in r["breakdown"]) == r["score"]
    assert {b["key"] for b in r["breakdown"]} == {"language", "skills", "interests", "difficulty", "readiness", "clarity"}


def test_wrong_language_scores_lower():
    good = score_issue(make_issue(), PROFILE)["score"]
    bad = score_issue(make_issue(language="Rust", title="Fix lifetime bug", body="y" * 250), PROFILE)["score"]
    assert good > bad


def test_ambiguous_short_terms_do_not_match_english_words():
    p = SimpleNamespace(skills=["go"], languages=[], interests=[], level="beginner")
    r = score_issue(make_issue(title="Let's go fix this", labels=[], language="Python"), p)
    assert next(b for b in r["breakdown"] if b["key"] == "skills")["points"] == 0


def test_open_pr_and_claims_are_detected():
    issue = make_issue()
    timeline = [{"event": "cross-referenced", "source": {"issue": {"pull_request": {}, "state": "open", "html_url": "u"}}}]
    comments = [{"user": {"login": "bob", "type": "User"}, "body": "Hi, I'll work on this!"}]
    r = assess_readiness(issue, comments, timeline)
    assert r["pr_status"] == "open" and r["claim_status"] == "found" and r["claim_by"] == "bob"
    assert "An open pull request already references it" in exclusion_reasons(r)


def test_failed_checks_are_reported_as_unknown_not_guessed():
    r = assess_readiness(make_issue(), None, None)
    assert r["pr_status"] == "unknown" and r["claim_status"] == "unknown"

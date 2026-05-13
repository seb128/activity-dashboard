"""GitHub adapter — fetches PRs authored by or requested for review from the subject."""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..item import Item

NAME = "github"


def _create_client(settings):
    from github import Github, Auth
    token_file = settings.credentials.github_token_file
    if token_file and Path(token_file).exists():
        token = Path(token_file).read_text().strip()
        return Github(auth=Auth.Token(token))
    return Github()


def _pr_to_item(pr, subject_role: str) -> Item:
    status = "merged" if (subject_role == "author" and getattr(pr, "merged", False)) else pr.state
    return Item(
        source=NAME,
        kind="pr",
        title=pr.title,
        url=pr.html_url,
        subject_role=subject_role,
        status=status,
        last_activity_at=pr.updated_at,
        bucket=None,
        raw={"number": pr.number, "repo": pr.base.repo.full_name},
    )


def fetch(subject, settings, *, _client=None) -> list[Item]:
    client = _client if _client is not None else _create_client(settings)
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.rules.window_days)
    cutoff_date = cutoff.date().isoformat()

    items: list[Item] = []

    authored_query = f"author:{subject.github_id} is:pr updated:>={cutoff_date}"
    for issue in client.search_issues(authored_query):
        items.append(_pr_to_item(issue.as_pull_request(), "author"))

    review_query = f"review-requested:{subject.github_id} is:pr is:open"
    for issue in client.search_issues(review_query):
        items.append(_pr_to_item(issue.as_pull_request(), "reviewer"))

    return items

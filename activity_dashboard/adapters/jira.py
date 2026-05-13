"""Jira adapter — tickets where the subject is assignee, within the activity window."""

from __future__ import annotations
from datetime import datetime
from pathlib import Path

from ..item import Item

NAME = "jira"


def _create_client(settings):
    from atlassian import Jira
    email = Path(settings.credentials.jira.email_file).read_text().strip()
    token = Path(settings.credentials.jira.token_file).read_text().strip()
    return Jira(
        url=settings.credentials.jira.base_url,
        username=email,
        password=token,
        cloud=True,
    )


def _parse_jira_datetime(s: str) -> datetime:
    # Jira returns "2026-05-10T12:00:00.000+0000" — Python's fromisoformat doesn't accept
    # +0000 without a colon prior to 3.11. We strip it cleanly.
    if s.endswith("+0000"):
        s = s[:-5] + "+00:00"
    return datetime.fromisoformat(s)


def fetch(subject, settings, *, _client=None) -> list[Item]:
    client = _client if _client is not None else _create_client(settings)

    window = settings.rules.window_days
    jql = (
        f'assignee = "{subject.canonical_email}" '
        f"AND updated >= -{window}d "
        "ORDER BY updated DESC"
    )
    response = client.jql(jql, fields=["summary", "status", "updated"], limit=200)
    base_url = settings.credentials.jira.base_url.rstrip("/")

    items: list[Item] = []
    for issue in response.get("issues", []):
        key = issue["key"]
        fields = issue["fields"]
        items.append(Item(
            source=NAME,
            kind="ticket",
            title=fields["summary"],
            url=f"{base_url}/browse/{key}",
            subject_role="assignee",
            status=fields["status"]["name"],
            last_activity_at=_parse_jira_datetime(fields["updated"]),
            bucket=None,
            raw={"key": key},
        ))
    return items

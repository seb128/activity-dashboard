"""Jira adapter — tickets where the subject is assignee, within the activity window."""

from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

from ..item import Item

_log = logging.getLogger("activity_dashboard")

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
    try:
        response = client.jql(jql, fields=["summary", "status", "updated"], limit=200)
    except Exception as e:
        # atlassian-python-api wraps HTTP errors in requests.HTTPError; when the
        # response body is empty (common on 401/403), the wrapped message is "".
        # Surface the status code and a slice of the body so the warning log is useful.
        resp = getattr(e, "response", None)
        status = getattr(resp, "status_code", None)
        body = (getattr(resp, "text", "") or "")[:300]
        detail = f"HTTP {status}: {body!r}" if status else f"{type(e).__name__}"
        raise RuntimeError(f"Jira API request failed ({detail}); JQL was: {jql}") from e
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

    # Optional stale-in-pulse second query
    pulse_jql = settings.credentials.jira.pulse_jql
    if pulse_jql:
        stale_days = settings.rules.needs_attention.pulse_stale_days
        stale_q = (
            f'({pulse_jql}) '
            f'AND assignee = "{subject.canonical_email}" '
            f'AND updated < -{stale_days}d '
            'ORDER BY updated DESC'
        )
        try:
            stale_response = client.jql(stale_q, fields=["summary", "status", "updated"], limit=200)
        except Exception as e:
            resp = getattr(e, "response", None)
            status = getattr(resp, "status_code", None)
            body = (getattr(resp, "text", "") or "")[:300]
            _log.warning(
                "jira: stale-in-pulse query failed (HTTP %s body=%r); JQL was: %s",
                status, body, stale_q,
            )
        else:
            seen_keys = {it.raw["key"] for it in items}
            for issue in stale_response.get("issues", []):
                key = issue["key"]
                if key in seen_keys:
                    continue  # dedupe across the two queries
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
                    raw={"key": key, "stale_in_pulse": True},
                ))

    return items

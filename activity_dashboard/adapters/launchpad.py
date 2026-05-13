"""Launchpad adapter — bugs and merge proposals authored/assigned by the subject."""

from __future__ import annotations
from datetime import datetime, timedelta, timezone

from ..item import Item

NAME = "launchpad"


def _create_client(settings):
    from launchpadlib.launchpad import Launchpad
    return Launchpad.login_anonymously("activity-dashboard", "production", version="devel")


def fetch(subject, settings, *, _client=None) -> list[Item]:
    client = _client if _client is not None else _create_client(settings)
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.rules.window_days)

    person = client.people[subject.launchpad_id]
    items: list[Item] = []

    # Bug tasks (assignee, reporter, commenter)
    for task in person.searchTasks(assignee=person, modified_since=cutoff):
        bug = task.bug
        items.append(Item(
            source=NAME,
            kind="bug",
            title=bug.title,
            url=task.web_link,
            subject_role="assignee",
            status=task.status,
            last_activity_at=task.date_last_updated or bug.date_last_updated,
            bucket=None,
            raw={"bug_title": bug.title},
        ))

    # Merge proposals
    for mp in person.getMergeProposals(status=["Work in progress", "Needs review", "Approved",
                                                "Rejected", "Merged"]):
        last = mp.date_review_requested or mp.date_created
        title = mp.description_or_fallback() if hasattr(mp, "description_or_fallback") else mp.web_link
        items.append(Item(
            source=NAME,
            kind="mp",
            title=title,
            url=mp.web_link,
            subject_role="author",
            status=mp.queue_status,
            last_activity_at=last,
            bucket=None,
            raw={"target": getattr(mp, "target_branch_link", None)},
        ))

    return items

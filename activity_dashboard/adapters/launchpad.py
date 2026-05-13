"""Launchpad adapter — bugs and merge proposals authored/assigned by the subject."""

from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone

from ..item import Item

NAME = "launchpad"

_LAUNCHPAD_CODE_BASE = "https://code.launchpad.net"
_MATCH_MP_HREF = re.compile(r"^/.*/\+merge/\d+$")
# Matches section headings: "Requested reviews by <name>" or "Reviews <name> can do"
_MATCH_CAN_DO = re.compile(r"^(Requested reviews)|(Reviews) .* can do$")


def _create_client(settings):
    from launchpadlib.launchpad import Launchpad
    return Launchpad.login_anonymously("activity-dashboard", "production", version="devel")


def _parse_active_reviews(html: str) -> list[Item]:
    """Parse a Launchpad +activereviews HTML page; return reviewer-side MP Items.

    Walks the document looking for section-heading <td>s matching
    "Requested reviews" / "Reviews ... can do" and merge-proposal <a> links.
    Each MP link found inside a matching section becomes an Item with
    subject_role="reviewer", status="Needs review".
    """
    import bs4
    from datetime import datetime, timezone

    soup = bs4.BeautifulSoup(html, features="lxml")
    items: list[Item] = []
    in_can_do_section = False
    now = datetime.now(timezone.utc)

    def _match(tag):
        if tag.name == "td" and "section-heading" in tag.get("class", []):
            return True
        if tag.name == "a" and _MATCH_MP_HREF.search(tag.get("href", "")):
            return True
        return False

    for tag in soup(_match):
        if tag.name == "td":
            in_can_do_section = bool(_MATCH_CAN_DO.search(tag.string or ""))
        elif in_can_do_section:
            href = tag.get("href", "")
            title = (tag.text or "").strip() or href
            items.append(Item(
                source=NAME,
                kind="mp",
                title=title,
                url=f"{_LAUNCHPAD_CODE_BASE}{href}",
                subject_role="reviewer",
                status="Needs review",
                last_activity_at=now,
                bucket=None,
                raw={"href": href},
            ))
    return items


def _fetch_reviewer_mps(subject, http_get) -> list[Item]:
    url = f"{_LAUNCHPAD_CODE_BASE}/~{subject.launchpad_id}/+activereviews"
    response = http_get(url, timeout=60)
    response.raise_for_status()
    return _parse_active_reviews(response.text)


def fetch(subject, settings, *, _client=None, _http_get=None) -> list[Item]:
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

    # NEW: reviewer-side MPs via web scrape (works around LP API gap for Git MPs)
    import requests
    http_get = _http_get if _http_get is not None else requests.get
    items.extend(_fetch_reviewer_mps(subject, http_get))

    return items

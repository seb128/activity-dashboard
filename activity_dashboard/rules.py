"""Rules engine: deterministic bucket assignment per item.

Bucket semantics:
- ``item.bucket is None``: not yet classified. ``assign_bucket`` should classify it.
- ``Bucket.NONE``: intentionally unclassified (e.g. gdocs action items that live
  in their own UI panel). ``assign_bucket`` leaves these alone.
The two states are NOT interchangeable.
"""

from __future__ import annotations
from datetime import datetime, timedelta

from .config import Rules
from .item import Item, Bucket


JIRA_DONE_STATUSES = {"Done", "Closed", "Resolved", "Completed"}
JIRA_ACTIVE_STATUSES = {"In Progress", "In Review", "Reviewing"}
LAUNCHPAD_BUG_DONE = {"Fix Released", "Fix Committed", "Invalid", "Won't Fix"}
LAUNCHPAD_MP_DONE = {"Merged", "Rejected", "Superseded"}


def _age_days(item: Item, now: datetime) -> float:
    return (now - item.last_activity_at).total_seconds() / 86400.0


def _bucket_for_github(item: Item, rules: Rules, now: datetime) -> Bucket:
    if item.subject_role == "reviewer":
        age = _age_days(item, now)
        if age >= rules.needs_attention.pr_awaiting_review_days:
            return Bucket.NEEDS_ATTENTION
        return Bucket.ACTIVE
    # author
    if item.status in {"merged", "closed"}:
        return Bucket.DONE
    age = _age_days(item, now)
    if age > rules.needs_attention.stalled_pr_days:
        return Bucket.NEEDS_ATTENTION
    return Bucket.ACTIVE


def _bucket_for_jira(item: Item, rules: Rules, now: datetime) -> Bucket:
    if item.status in JIRA_DONE_STATUSES:
        return Bucket.DONE
    age = _age_days(item, now)
    if item.status in JIRA_ACTIVE_STATUSES:
        if age > rules.needs_attention.stalled_jira_days:
            return Bucket.NEEDS_ATTENTION
        return Bucket.ACTIVE
    # Any other "open-ish" status (e.g. "To Do", "Backlog"): needs attention if not moving
    if age >= rules.needs_attention.jira_assigned_no_movement_days:
        return Bucket.NEEDS_ATTENTION
    return Bucket.ACTIVE


def _bucket_for_launchpad(item: Item, rules: Rules, now: datetime) -> Bucket:
    if item.kind == "mp":
        if item.status in LAUNCHPAD_MP_DONE:
            return Bucket.DONE
        return Bucket.ACTIVE
    # bug
    if item.status in LAUNCHPAD_BUG_DONE:
        return Bucket.DONE
    age = _age_days(item, now)
    if age > rules.needs_attention.stalled_launchpad_days:
        return Bucket.NEEDS_ATTENTION
    return Bucket.ACTIVE


def assign_bucket(item: Item, rules: Rules, now: datetime) -> Bucket:
    """Return the bucket for an item.

    Items with ``kind="action_item"`` keep ``Bucket.NONE`` (they were intentionally
    marked unclassified by the gdocs adapter and live in their own UI panel).
    All other items get classified by source-specific rules.
    """
    if item.kind == "action_item":
        return Bucket.NONE
    if item.source == "github":
        return _bucket_for_github(item, rules, now)
    if item.source == "jira":
        return _bucket_for_jira(item, rules, now)
    if item.source == "launchpad":
        return _bucket_for_launchpad(item, rules, now)
    return Bucket.ACTIVE

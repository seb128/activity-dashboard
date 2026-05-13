from datetime import datetime, timedelta, timezone
from activity_dashboard.item import Item, Bucket
from activity_dashboard.rules import assign_bucket
from activity_dashboard.config import Rules, NeedsAttentionThresholds


def _now():
    return datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)


def _settings(window=7):
    return Rules(window_days=window, needs_attention=NeedsAttentionThresholds(
        pr_awaiting_review_days=0,
        jira_assigned_no_movement_days=2,
        stalled_pr_days=5,
        stalled_jira_days=5,
        stalled_launchpad_days=5,
    ))


def _item(**kw):
    defaults = dict(
        source="github", kind="pr", title="t", url="u",
        subject_role="author", status="open",
        last_activity_at=_now(), bucket=None, raw={},
    )
    defaults.update(kw)
    return Item(**defaults)


def test_action_item_stays_none():
    it = _item(source="gdocs", kind="action_item", bucket=Bucket.NONE)
    assert assign_bucket(it, _settings(), _now()) == Bucket.NONE


# GitHub PR author
def test_pr_author_merged_is_done():
    it = _item(subject_role="author", status="merged",
               last_activity_at=_now() - timedelta(days=1))
    assert assign_bucket(it, _settings(), _now()) == Bucket.DONE


def test_pr_author_closed_is_done():
    it = _item(subject_role="author", status="closed",
               last_activity_at=_now() - timedelta(days=2))
    assert assign_bucket(it, _settings(), _now()) == Bucket.DONE


def test_pr_author_open_recent_is_active():
    it = _item(subject_role="author", status="open",
               last_activity_at=_now() - timedelta(days=2))
    assert assign_bucket(it, _settings(), _now()) == Bucket.ACTIVE


def test_pr_author_open_stale_is_needs_attention():
    it = _item(subject_role="author", status="open",
               last_activity_at=_now() - timedelta(days=10))
    assert assign_bucket(it, _settings(), _now()) == Bucket.NEEDS_ATTENTION


# GitHub PR reviewer
def test_pr_reviewer_open_is_needs_attention():
    it = _item(subject_role="reviewer", status="open",
               last_activity_at=_now() - timedelta(days=1))
    assert assign_bucket(it, _settings(), _now()) == Bucket.NEEDS_ATTENTION


# Jira
def test_jira_done_status_is_done():
    it = _item(source="jira", kind="ticket", status="Done",
               last_activity_at=_now() - timedelta(days=1))
    assert assign_bucket(it, _settings(), _now()) == Bucket.DONE


def test_jira_closed_status_is_done():
    it = _item(source="jira", kind="ticket", status="Closed",
               last_activity_at=_now() - timedelta(days=2))
    assert assign_bucket(it, _settings(), _now()) == Bucket.DONE


def test_jira_in_progress_recent_is_active():
    it = _item(source="jira", kind="ticket", status="In Progress",
               last_activity_at=_now() - timedelta(days=1))
    assert assign_bucket(it, _settings(), _now()) == Bucket.ACTIVE


def test_jira_in_progress_stale_is_needs_attention():
    it = _item(source="jira", kind="ticket", status="In Progress",
               last_activity_at=_now() - timedelta(days=6))
    assert assign_bucket(it, _settings(), _now()) == Bucket.NEEDS_ATTENTION


def test_jira_open_status_old_is_needs_attention():
    it = _item(source="jira", kind="ticket", status="To Do",
               last_activity_at=_now() - timedelta(days=3))
    assert assign_bucket(it, _settings(), _now()) == Bucket.NEEDS_ATTENTION


# Launchpad
def test_launchpad_fix_released_is_done():
    it = _item(source="launchpad", kind="bug", status="Fix Released",
               last_activity_at=_now() - timedelta(days=2))
    assert assign_bucket(it, _settings(), _now()) == Bucket.DONE


def test_launchpad_open_recent_is_active():
    it = _item(source="launchpad", kind="bug", status="Confirmed",
               last_activity_at=_now() - timedelta(days=2))
    assert assign_bucket(it, _settings(), _now()) == Bucket.ACTIVE


def test_launchpad_open_stale_is_needs_attention():
    it = _item(source="launchpad", kind="bug", status="Confirmed",
               last_activity_at=_now() - timedelta(days=10))
    assert assign_bucket(it, _settings(), _now()) == Bucket.NEEDS_ATTENTION


def test_launchpad_mp_merged_is_done():
    it = _item(source="launchpad", kind="mp", status="Merged",
               last_activity_at=_now() - timedelta(days=1))
    assert assign_bucket(it, _settings(), _now()) == Bucket.DONE


def test_launchpad_mp_needs_review_is_active():
    it = _item(source="launchpad", kind="mp", status="Needs review",
               subject_role="author",
               last_activity_at=_now() - timedelta(days=1))
    assert assign_bucket(it, _settings(), _now()) == Bucket.ACTIVE

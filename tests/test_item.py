from datetime import datetime, timezone
from activity_dashboard.item import Item, Bucket


def test_bucket_values():
    assert Bucket.DONE.value == "done"
    assert Bucket.ACTIVE.value == "active"
    assert Bucket.NEEDS_ATTENTION.value == "needs_attention"
    assert Bucket.NONE.value == "none"


def test_item_construction():
    item = Item(
        source="github",
        kind="pr",
        title="Fix the foo",
        url="https://github.com/x/y/pull/1",
        subject_role="author",
        status="open",
        last_activity_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        bucket=None,
        raw={"number": 1},
    )
    assert item.source == "github"
    assert item.bucket is None
    assert item.raw["number"] == 1


def test_item_bucket_can_be_set():
    item = Item(
        source="github", kind="pr", title="t", url="u",
        subject_role="author", status="open",
        last_activity_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        bucket=None, raw={},
    )
    item.bucket = Bucket.ACTIVE
    assert item.bucket == Bucket.ACTIVE

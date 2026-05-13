from datetime import datetime, timezone
from pathlib import Path
from activity_dashboard.render import render_report
from activity_dashboard.item import Item, Bucket
from activity_dashboard.config import Settings, Credentials, JiraCredentials, Rules, NeedsAttentionThresholds, SubjectConfig


def _settings():
    return Settings(
        credentials=Credentials(
            github_token_file=None,
            jira=JiraCredentials(base_url="https://x.atlassian.net",
                                  email_file=Path("/dev/null"), token_file=Path("/dev/null")),
            google_credentials_file=Path("/dev/null"), google_token_file=Path("/dev/null"),
        ),
        rules=Rules(window_days=7, needs_attention=NeedsAttentionThresholds()),
        subjects={},
    )


def _subject():
    return SubjectConfig(
        name="alice", display_name="Alice Smith", canonical_email="a@c.com",
        launchpad_id="alice-lp", github_id="alice-gh",
        one_on_one_doc="https://docs.google.com/document/d/AAA/edit",
    )


def _item(source, title, bucket, **kw):
    defaults = dict(
        kind="pr", url="https://example.com/1", subject_role="author",
        status="open", last_activity_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        raw={},
    )
    defaults.update(kw)
    return Item(source=source, title=title, bucket=bucket, **defaults)


def test_render_writes_html_file(tmp_path):
    out = tmp_path / "report.html"
    render_report({}, _subject(), _settings(), out)
    assert out.exists()
    text = out.read_text()
    assert "<html" in text


def test_render_includes_subject_display_name(tmp_path):
    out = tmp_path / "report.html"
    render_report({}, _subject(), _settings(), out)
    assert "Alice Smith" in out.read_text()


def test_render_includes_vanilla_framework_css(tmp_path):
    out = tmp_path / "report.html"
    render_report({}, _subject(), _settings(), out)
    assert "vanilla-framework" in out.read_text().lower()


def test_render_bucket_columns_present(tmp_path):
    out = tmp_path / "report.html"
    render_report({}, _subject(), _settings(), out)
    text = out.read_text()
    assert "Done" in text
    assert "Active" in text
    assert "Needs attention" in text


def test_render_groups_items_by_bucket(tmp_path):
    results = {
        "github": [
            _item("github", "Merged work", Bucket.DONE, status="merged"),
            _item("github", "Open work", Bucket.ACTIVE),
            _item("github", "Stale work", Bucket.NEEDS_ATTENTION),
        ],
    }
    out = tmp_path / "report.html"
    render_report(results, _subject(), _settings(), out)
    text = out.read_text()
    # Each title appears.
    assert "Merged work" in text
    assert "Open work" in text
    assert "Stale work" in text


def test_render_per_source_panels(tmp_path):
    results = {
        "github": [_item("github", "PR thing", Bucket.ACTIVE)],
        "jira": [_item("jira", "Ticket thing", Bucket.ACTIVE, kind="ticket")],
        "launchpad": [_item("launchpad", "Bug thing", Bucket.ACTIVE, kind="bug")],
    }
    out = tmp_path / "report.html"
    render_report(results, _subject(), _settings(), out)
    text = out.read_text()
    assert "GitHub" in text
    assert "Jira" in text
    assert "Launchpad" in text


def test_render_one_on_one_panel(tmp_path):
    results = {
        "gdocs": [
            _item("gdocs", "Talk to bob", Bucket.NONE, kind="action_item",
                  status="pending", raw={"section": "for_next_week"}),
            _item("gdocs", "Review alpha doc", Bucket.NONE, kind="action_item",
                  status="pending", raw={"section": "carried_over"}),
        ],
    }
    out = tmp_path / "report.html"
    render_report(results, _subject(), _settings(), out)
    text = out.read_text()
    assert "1-1 notes" in text or "1:1 notes" in text
    assert "For next week" in text
    assert "Carried over" in text
    assert "Talk to bob" in text
    assert "Review alpha doc" in text


def test_render_action_items_not_in_top_buckets(tmp_path):
    # Action items have Bucket.NONE; they must not appear in Done/Active/Needs attention.
    results = {
        "gdocs": [_item("gdocs", "ACTION_ITEM_UNIQUE_TITLE", Bucket.NONE,
                       kind="action_item", status="pending",
                       raw={"section": "for_next_week"})],
    }
    out = tmp_path / "report.html"
    render_report(results, _subject(), _settings(), out)
    text = out.read_text()
    # Ensure it shows up exactly once (only in the 1-1 panel, not also in a top bucket).
    assert text.count("ACTION_ITEM_UNIQUE_TITLE") == 1


def test_render_adapter_failure_panel(tmp_path):
    results = {"github": RuntimeError("network down")}
    out = tmp_path / "report.html"
    render_report(results, _subject(), _settings(), out)
    text = out.read_text()
    assert "network down" in text or "failed" in text.lower()

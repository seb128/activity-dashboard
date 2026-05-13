from datetime import datetime, timezone
from activity_dashboard.adapters import launchpad as lp_adapter
from activity_dashboard.config import Settings, Credentials, JiraCredentials, Rules, NeedsAttentionThresholds, SubjectConfig


class FakeBug:
    def __init__(self, title, web_link, status, last_updated):
        self.title = title
        self.web_link = web_link
        self.status = status
        self.date_last_updated = last_updated


class FakeBugTask:
    def __init__(self, bug, status, last_updated):
        self.bug = bug
        self.status = status
        self.date_last_updated = last_updated
        self.web_link = bug.web_link


class FakeMP:
    def __init__(self, title, web_link, status, last_updated):
        self.web_link = web_link
        self.queue_status = status
        self.date_review_requested = last_updated
        self.date_created = last_updated
        self.target_branch_link = "lp:foo"
        self.source_branch_link = "lp:bar"
        # We use a callable to derive a title since LP MPs don't have a title field.
        self._title = title
    def description_or_fallback(self):
        return self._title


class FakePerson:
    def __init__(self, bug_tasks=(), merge_proposals=()):
        self._bug_tasks = list(bug_tasks)
        self._merge_proposals = list(merge_proposals)
    def searchTasks(self, **kwargs):
        return self._bug_tasks
    def getMergeProposals(self, **kwargs):
        return self._merge_proposals


class FakeLaunchpad:
    def __init__(self, people: dict[str, FakePerson]):
        self.people = people  # subscript access


def _settings():
    return Settings(
        credentials=Credentials(
            github_token_file=None,
            jira=JiraCredentials(base_url="x", email_file=None, token_file=None),
            google_credentials_file=None, google_token_file=None,
        ),
        rules=Rules(window_days=7, needs_attention=NeedsAttentionThresholds()),
        subjects={},
    )


def _subject():
    return SubjectConfig(
        name="alice", display_name="Alice", canonical_email="a@c.com",
        launchpad_id="alice-lp", github_id="alice-gh",
        one_on_one_doc="https://docs.google.com/document/d/AAA/edit",
    )


class _NoOpResponse:
    text = "<html></html>"
    def raise_for_status(self): pass


def _no_http_get(*args, **kwargs):
    return _NoOpResponse()


def test_name_constant():
    assert lp_adapter.NAME == "launchpad"


def test_fetch_bugs():
    bug = FakeBug("Crash on startup", "https://bugs.launchpad.net/x/+bug/1", "In Progress",
                  datetime(2026, 5, 10, tzinfo=timezone.utc))
    task = FakeBugTask(bug, "In Progress", datetime(2026, 5, 10, tzinfo=timezone.utc))
    client = FakeLaunchpad({"alice-lp": FakePerson(bug_tasks=[task])})
    items = lp_adapter.fetch(_subject(), _settings(), _client=client, _http_get=_no_http_get)
    bugs = [i for i in items if i.kind == "bug"]
    assert len(bugs) == 1
    assert bugs[0].title == "Crash on startup"
    assert bugs[0].url.startswith("https://bugs.launchpad.net")
    assert bugs[0].status == "In Progress"


def test_fetch_merge_proposals():
    mp = FakeMP("Land new feature", "https://code.launchpad.net/~alice-lp/x/+merge/1",
                "Needs review", datetime(2026, 5, 11, tzinfo=timezone.utc))
    client = FakeLaunchpad({"alice-lp": FakePerson(merge_proposals=[mp])})
    items = lp_adapter.fetch(_subject(), _settings(), _client=client, _http_get=_no_http_get)
    mps = [i for i in items if i.kind == "mp"]
    assert len(mps) == 1
    assert mps[0].title.startswith("Land new feature")
    assert mps[0].status == "Needs review"
    assert mps[0].subject_role in {"author", "reviewer"}


def test_fetch_empty():
    client = FakeLaunchpad({"alice-lp": FakePerson()})
    items = lp_adapter.fetch(_subject(), _settings(), _client=client, _http_get=_no_http_get)
    assert items == []


# Sample HTML matching the structure of a Launchpad +activereviews page:
# two reviewer-queue sections (with MP links we should capture) and one
# unrelated section (with an MP link we should ignore).
_SAMPLE_ACTIVE_REVIEWS_HTML = """
<html><body><table>
  <tr><td class="section-heading">Requested reviews by alice-lp</td></tr>
  <tr><td><a href="/~bob/foo/+merge/12345">Land feature foo</a></td></tr>
  <tr><td><a href="/~carol/bar/+merge/12346">Refactor bar</a></td></tr>
  <tr><td class="section-heading">Reviews alice-lp can do</td></tr>
  <tr><td><a href="/~dave/baz/+merge/22222">Optimize baz</a></td></tr>
  <tr><td class="section-heading">Mine to land</td></tr>
  <tr><td><a href="/~alice-lp/own/+merge/33333">Ignored - my own MP</a></td></tr>
</table></body></html>
"""


def test_parse_active_reviews_extracts_mps_in_reviewer_sections():
    items = lp_adapter._parse_active_reviews(_SAMPLE_ACTIVE_REVIEWS_HTML)
    titles = [i.title for i in items]
    assert "Land feature foo" in titles
    assert "Refactor bar" in titles
    assert "Optimize baz" in titles
    # MP under "Mine to land" must NOT appear.
    assert "Ignored - my own MP" not in titles


def test_parse_active_reviews_items_have_reviewer_role_and_needs_review_status():
    items = lp_adapter._parse_active_reviews(_SAMPLE_ACTIVE_REVIEWS_HTML)
    assert all(i.source == "launchpad" for i in items)
    assert all(i.kind == "mp" for i in items)
    assert all(i.subject_role == "reviewer" for i in items)
    assert all(i.status == "Needs review" for i in items)


def test_parse_active_reviews_url_is_absolute():
    items = lp_adapter._parse_active_reviews(_SAMPLE_ACTIVE_REVIEWS_HTML)
    foo = next(i for i in items if i.title == "Land feature foo")
    assert foo.url == "https://code.launchpad.net/~bob/foo/+merge/12345"


def test_parse_active_reviews_empty_html():
    assert lp_adapter._parse_active_reviews("<html></html>") == []


def test_fetch_includes_reviewer_mps(monkeypatch):
    """End-to-end: fetch() composes registered MPs + reviewer MPs."""
    class FakeResponse:
        text = _SAMPLE_ACTIVE_REVIEWS_HTML
        def raise_for_status(self): pass
    captured = {}
    def fake_http_get(url, timeout=None):
        captured["url"] = url
        return FakeResponse()

    client = FakeLaunchpad({"alice-lp": FakePerson()})  # no registered MPs, no bugs
    items = lp_adapter.fetch(_subject(), _settings(), _client=client, _http_get=fake_http_get)

    # URL was the expected +activereviews page
    assert captured["url"] == "https://code.launchpad.net/~alice-lp/+activereviews"
    # Reviewer MPs were extracted
    reviewer_mps = [i for i in items if i.subject_role == "reviewer"]
    assert len(reviewer_mps) == 3


def test_fetch_reviewer_scrape_failure_does_not_destroy_lp_data(caplog):
    """If +activereviews scrape fails, bugs/registered-MPs are still returned."""
    import logging
    from datetime import datetime, timezone

    bug = FakeBug("Crash on startup", "https://bugs.launchpad.net/x/+bug/1",
                  "In Progress", datetime(2026, 5, 10, tzinfo=timezone.utc))
    task = FakeBugTask(bug, "In Progress", datetime(2026, 5, 10, tzinfo=timezone.utc))
    client = FakeLaunchpad({"alice-lp": FakePerson(bug_tasks=[task])})

    def failing_http_get(url, timeout=None):
        raise RuntimeError("simulated 404")

    caplog.set_level(logging.WARNING)
    items = lp_adapter.fetch(_subject(), _settings(),
                             _client=client, _http_get=failing_http_get)

    # The bug from launchpadlib is still present
    bug_items = [i for i in items if i.kind == "bug"]
    assert len(bug_items) == 1
    # No reviewer-MP items (scrape failed)
    reviewer_items = [i for i in items if i.subject_role == "reviewer"]
    assert reviewer_items == []
    # Warning was logged
    assert any("scrape reviewer MPs" in rec.message for rec in caplog.records)


def test_merged_mp_outside_window_is_excluded():
    """Completed MPs older than window_days must not appear in the results."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    old_mp = FakeMP(
        "Old merged MP",
        "https://code.launchpad.net/~alice-lp/x/+merge/99",
        "Merged",
        now - timedelta(days=30),
    )
    client = FakeLaunchpad({"alice-lp": FakePerson(merge_proposals=[old_mp])})
    items = lp_adapter.fetch(_subject(), _settings(), _client=client, _http_get=_no_http_get)
    assert not any(i.title == "Old merged MP" for i in items)


def test_open_mp_outside_window_is_included():
    """Open MPs older than window_days must still be included (stale = Needs Attention)."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    stale_mp = FakeMP(
        "Stale open MP",
        "https://code.launchpad.net/~alice-lp/x/+merge/98",
        "Needs review",
        now - timedelta(days=30),
    )
    client = FakeLaunchpad({"alice-lp": FakePerson(merge_proposals=[stale_mp])})
    items = lp_adapter.fetch(_subject(), _settings(), _client=client, _http_get=_no_http_get)
    assert any(i.title == "Stale open MP" for i in items)

from datetime import datetime, timezone
from activity_dashboard.adapters import jira as jira_adapter
from activity_dashboard.config import Settings, Credentials, JiraCredentials, Rules, NeedsAttentionThresholds, SubjectConfig


class FakeJira:
    def __init__(self, response):
        # `response` is the single dict returned for any query (backward compatible).
        self.single = response
        self.queries = []

    @property
    def last_jql(self):
        """Backward-compatible accessor for tests that check the most recent query."""
        return self.queries[-1] if self.queries else None

    def jql(self, query, fields=None, limit=None):
        self.queries.append(query)
        return self.single


def _settings():
    return Settings(
        credentials=Credentials(
            github_token_file=None,
            jira=JiraCredentials(
                base_url="https://example.atlassian.net",
                email_file=None, token_file=None,
            ),
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


def test_name_constant():
    assert jira_adapter.NAME == "jira"


def test_fetch_returns_ticket_items():
    response = {"issues": [
        {
            "key": "PROJ-1",
            "fields": {
                "summary": "Implement widget",
                "status": {"name": "In Progress"},
                "updated": "2026-05-10T12:00:00.000+0000",
            },
        },
        {
            "key": "PROJ-2",
            "fields": {
                "summary": "Fix bug",
                "status": {"name": "Done"},
                "updated": "2026-05-11T12:00:00.000+0000",
            },
        },
    ]}
    client = FakeJira(response)
    items = jira_adapter.fetch(_subject(), _settings(), _client=client)
    assert len(items) == 2
    titles = [i.title for i in items]
    assert "Implement widget" in titles
    statuses = {i.status for i in items}
    assert "In Progress" in statuses and "Done" in statuses


def test_fetch_url_built_from_base_url():
    response = {"issues": [{
        "key": "PROJ-1",
        "fields": {
            "summary": "Implement widget",
            "status": {"name": "In Progress"},
            "updated": "2026-05-10T12:00:00.000+0000",
        },
    }]}
    client = FakeJira(response)
    items = jira_adapter.fetch(_subject(), _settings(), _client=client)
    assert items[0].url == "https://example.atlassian.net/browse/PROJ-1"


def test_fetch_jql_uses_subject_email_and_window():
    client = FakeJira({"issues": []})
    jira_adapter.fetch(_subject(), _settings(), _client=client)
    assert 'assignee = "a@c.com"' in client.last_jql
    assert "updated" in client.last_jql
    assert "-7d" in client.last_jql


def test_fetch_empty():
    client = FakeJira({"issues": []})
    items = jira_adapter.fetch(_subject(), _settings(), _client=client)
    assert items == []


def test_fetch_does_not_run_pulse_query_when_unset():
    client = FakeJira({"issues": []})
    jira_adapter.fetch(_subject(), _settings(), _client=client)
    # Only the first query ran
    assert len(client.queries) == 1


def test_fetch_runs_pulse_query_when_set():
    settings = _settings()
    settings.credentials.jira.pulse_jql = "project = DCR AND sprint in openSprints()"
    client = FakeJira({"issues": []})
    jira_adapter.fetch(_subject(), settings, _client=client)
    assert len(client.queries) == 2
    # Second query wraps the pulse_jql, adds the assignee + window constraint
    stale_q = client.queries[1]
    assert "project = DCR AND sprint in openSprints()" in stale_q
    assert 'assignee = "a@c.com"' in stale_q
    assert "updated < -7d" in stale_q


def test_fetch_stale_in_pulse_items_are_tagged():
    settings = _settings()
    settings.credentials.jira.pulse_jql = "project = DCR"
    stale_response = {"issues": [{
        "key": "DCR-99",
        "fields": {
            "summary": "Long-stalled card",
            "status": {"name": "In Progress"},
            "updated": "2026-04-30T12:00:00.000+0000",
        },
    }]}

    class _SeqJira:
        def __init__(self):
            self.queries = []

        def jql(self, query, fields=None, limit=None):
            self.queries.append(query)
            # First call: assignee/window query (no stale)
            # Second call: pulse-stale query
            if "updated < -" in query:
                return stale_response
            return {"issues": []}

    client = _SeqJira()
    items = jira_adapter.fetch(_subject(), settings, _client=client)
    stale = [i for i in items if i.raw.get("stale_in_pulse")]
    assert len(stale) == 1
    assert stale[0].title == "Long-stalled card"
    assert stale[0].raw["key"] == "DCR-99"


def test_fetch_dedupes_overlap_between_queries():
    """If the same key appears in both queries, the second occurrence is dropped."""
    settings = _settings()
    settings.credentials.jira.pulse_jql = "project = DCR"
    same_ticket = {
        "key": "DCR-1",
        "fields": {
            "summary": "Borderline",
            "status": {"name": "In Progress"},
            "updated": "2026-05-10T12:00:00.000+0000",
        },
    }

    class _SeqJira:
        def __init__(self):
            self.queries = []

        def jql(self, query, fields=None, limit=None):
            self.queries.append(query)
            return {"issues": [same_ticket]}

    client = _SeqJira()
    items = jira_adapter.fetch(_subject(), settings, _client=client)
    assert len(items) == 1
    # The original (not stale) wins; raw should NOT have stale_in_pulse
    assert not items[0].raw.get("stale_in_pulse")


def test_fetch_pulse_query_failure_does_not_drop_first_query_items(caplog):
    import logging
    settings = _settings()
    settings.credentials.jira.pulse_jql = "project = DCR"
    good_ticket = {
        "key": "PROJ-1",
        "fields": {
            "summary": "Normal ticket",
            "status": {"name": "In Progress"},
            "updated": "2026-05-12T12:00:00.000+0000",
        },
    }

    class _FlakyJira:
        def __init__(self):
            self.calls = 0

        def jql(self, query, fields=None, limit=None):
            self.calls += 1
            if self.calls == 1:
                return {"issues": [good_ticket]}
            raise RuntimeError("pulse query exploded")

    caplog.set_level(logging.WARNING, logger="activity_dashboard")
    items = jira_adapter.fetch(_subject(), settings, _client=_FlakyJira())
    # First-query item still returned
    assert any(i.raw.get("key") == "PROJ-1" for i in items)
    # Warning emitted
    assert any("stale-in-pulse" in rec.message for rec in caplog.records)

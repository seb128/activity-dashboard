from datetime import datetime, timezone
from activity_dashboard.adapters import jira as jira_adapter
from activity_dashboard.config import Settings, Credentials, JiraCredentials, Rules, NeedsAttentionThresholds, SubjectConfig


class FakeJira:
    def __init__(self, response):
        self.response = response
        self.last_jql = None
    def jql(self, query, fields=None, limit=None):
        self.last_jql = query
        return self.response


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

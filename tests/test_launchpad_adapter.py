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


def test_name_constant():
    assert lp_adapter.NAME == "launchpad"


def test_fetch_bugs():
    bug = FakeBug("Crash on startup", "https://bugs.launchpad.net/x/+bug/1", "In Progress",
                  datetime(2026, 5, 10, tzinfo=timezone.utc))
    task = FakeBugTask(bug, "In Progress", datetime(2026, 5, 10, tzinfo=timezone.utc))
    client = FakeLaunchpad({"alice-lp": FakePerson(bug_tasks=[task])})
    items = lp_adapter.fetch(_subject(), _settings(), _client=client)
    bugs = [i for i in items if i.kind == "bug"]
    assert len(bugs) == 1
    assert bugs[0].title == "Crash on startup"
    assert bugs[0].url.startswith("https://bugs.launchpad.net")
    assert bugs[0].status == "In Progress"


def test_fetch_merge_proposals():
    mp = FakeMP("Land new feature", "https://code.launchpad.net/~alice-lp/x/+merge/1",
                "Needs review", datetime(2026, 5, 11, tzinfo=timezone.utc))
    client = FakeLaunchpad({"alice-lp": FakePerson(merge_proposals=[mp])})
    items = lp_adapter.fetch(_subject(), _settings(), _client=client)
    mps = [i for i in items if i.kind == "mp"]
    assert len(mps) == 1
    assert mps[0].title.startswith("Land new feature")
    assert mps[0].status == "Needs review"
    assert mps[0].subject_role in {"author", "reviewer"}


def test_fetch_empty():
    client = FakeLaunchpad({"alice-lp": FakePerson()})
    items = lp_adapter.fetch(_subject(), _settings(), _client=client)
    assert items == []

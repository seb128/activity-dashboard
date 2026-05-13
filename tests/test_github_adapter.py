from datetime import datetime, timezone
from activity_dashboard.adapters import github as gh_adapter
from activity_dashboard.config import Settings, Credentials, JiraCredentials, Rules, NeedsAttentionThresholds, SubjectConfig


class FakeRepo:
    def __init__(self, full_name): self.full_name = full_name


class FakeBase:
    def __init__(self, repo_full_name): self.repo = FakeRepo(repo_full_name)


class FakePR:
    def __init__(self, *, title, url, state, merged, updated_at, number, repo):
        self.title = title
        self.html_url = url
        self.state = state
        self.merged = merged
        self.updated_at = updated_at
        self.number = number
        self.base = FakeBase(repo)


class FakeIssue:
    def __init__(self, pr): self._pr = pr
    def as_pull_request(self): return self._pr


class FakeGithub:
    def __init__(self, results_by_query: dict[str, list]):
        self.results_by_query = results_by_query
    def search_issues(self, query):
        for key, results in self.results_by_query.items():
            if key in query:
                return results
        return []


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
    assert gh_adapter.NAME == "github"


def test_fetch_authored_prs():
    pr = FakePR(
        title="Fix the foo", url="https://github.com/x/y/pull/1",
        state="open", merged=False,
        updated_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        number=1, repo="x/y",
    )
    client = FakeGithub({
        "author:alice-gh": [FakeIssue(pr)],
        "review-requested:alice-gh": [],
    })
    items = gh_adapter.fetch(_subject(), _settings(), _client=client)
    assert any(i.subject_role == "author" and i.kind == "pr" for i in items)
    a = [i for i in items if i.subject_role == "author"][0]
    assert a.source == "github"
    assert a.title == "Fix the foo"
    assert a.url == "https://github.com/x/y/pull/1"
    assert a.status == "open"
    assert a.raw == {"number": 1, "repo": "x/y"}


def test_fetch_merged_pr_marks_status_merged():
    pr = FakePR(
        title="Merged work", url="https://github.com/x/y/pull/2",
        state="closed", merged=True,
        updated_at=datetime(2026, 5, 11, tzinfo=timezone.utc),
        number=2, repo="x/y",
    )
    client = FakeGithub({
        "author:alice-gh": [FakeIssue(pr)],
        "review-requested:alice-gh": [],
    })
    items = gh_adapter.fetch(_subject(), _settings(), _client=client)
    a = [i for i in items if i.subject_role == "author"][0]
    assert a.status == "merged"


def test_fetch_review_requested():
    pr = FakePR(
        title="Please review", url="https://github.com/x/y/pull/3",
        state="open", merged=False,
        updated_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        number=3, repo="x/y",
    )
    client = FakeGithub({
        "author:alice-gh": [],
        "review-requested:alice-gh": [FakeIssue(pr)],
    })
    items = gh_adapter.fetch(_subject(), _settings(), _client=client)
    rev = [i for i in items if i.subject_role == "reviewer"]
    assert len(rev) == 1
    assert rev[0].status == "open"


def test_fetch_empty_when_no_results():
    client = FakeGithub({"author:alice-gh": [], "review-requested:alice-gh": []})
    items = gh_adapter.fetch(_subject(), _settings(), _client=client)
    assert items == []

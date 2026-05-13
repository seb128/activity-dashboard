# activity-dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local CLI that aggregates recent activity for one subject across GitHub, Launchpad, Jira, and a per-subject Google Doc (1-1 notes), assigns each item to a Done/Active/Needs-attention bucket via deterministic rules, and renders one static HTML report styled with Vanilla Framework.

**Architecture:** Linear pipeline: `config → parallel adapter fetch (ThreadPoolExecutor) → list[Item] → rules engine → Jinja2 + Vanilla Framework → report.html`. Adapters are plain modules exposing `fetch(subject, settings, *, _client=None) -> list[Item]`. Failure isolation: an adapter exception becomes an error card in its panel; other sources still render. No LLM at runtime.

**Tech Stack:** Python 3.11+, `PyGithub`, `launchpadlib`, `atlassian-python-api`, `google-api-python-client`, `google-auth-oauthlib`, `Jinja2`, `PyYAML`. Testing: `pytest`. Concurrency: `concurrent.futures.ThreadPoolExecutor`. Styling: Vanilla Framework via CDN.

---

## File structure

```
activity-dashboard/
├── pyproject.toml                                  # Task 1
├── config.example.yaml                             # Task 12
├── activity_dashboard/
│   ├── __init__.py                                 # Task 1
│   ├── cli.py                                      # Task 10
│   ├── config.py                                   # Task 3
│   ├── item.py                                     # Task 2
│   ├── rules.py                                    # Task 9
│   ├── render.py                                   # Task 11
│   ├── adapters/
│   │   ├── __init__.py                             # Task 1
│   │   ├── github.py                               # Task 4
│   │   ├── launchpad.py                            # Task 5
│   │   ├── jira.py                                 # Task 6
│   │   ├── gdocs.py                                # Task 7
│   │   └── gmail.py                                # Task 8
│   └── templates/
│       └── report.html.j2                          # Task 11
└── tests/
    ├── __init__.py                                 # Task 1
    ├── test_item.py                                # Task 2
    ├── test_config.py                              # Task 3
    ├── test_github_adapter.py                      # Task 4
    ├── test_launchpad_adapter.py                   # Task 5
    ├── test_jira_adapter.py                        # Task 6
    ├── test_gdocs_adapter.py                       # Task 7
    ├── test_gmail_adapter.py                       # Task 8
    ├── test_rules.py                               # Task 9
    ├── test_cli.py                                 # Task 10
    └── test_render.py                              # Task 11
```

**Adapter contract (uniform):**

```python
NAME: str  # source identifier, e.g. "github"

def fetch(subject: SubjectConfig, settings: Settings, *, _client=None) -> list[Item]:
    """Fetch activity for a subject; if _client is provided, use it (for tests)."""
```

Tests inject a `_client` (a lightweight fake) so they never call real APIs. Production paths construct the real client when `_client is None`.

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `activity_dashboard/__init__.py`
- Create: `activity_dashboard/adapters/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "activity-dashboard"
version = "0.1.0"
description = "Personal activity dashboard aggregating GitHub, Launchpad, Jira, and 1-1 notes."
requires-python = ">=3.11"
dependencies = [
    "PyGithub>=2.1",
    "launchpadlib>=1.11",
    "atlassian-python-api>=3.41",
    "google-api-python-client>=2.100",
    "google-auth-oauthlib>=1.0",
    "Jinja2>=3.1",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
activity-dashboard = "activity_dashboard.cli:main"

[tool.setuptools.packages.find]
include = ["activity_dashboard*"]

[tool.setuptools.package-data]
activity_dashboard = ["templates/*.j2"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create package init files**

`activity_dashboard/__init__.py`:
```python
"""activity-dashboard: aggregate recent activity for one subject into a static HTML report."""

__version__ = "0.1.0"
```

`activity_dashboard/adapters/__init__.py`:
```python
"""Source adapters. Each module exposes NAME: str and fetch(subject, settings, *, _client=None)."""
```

`tests/__init__.py`:
```python
```

- [ ] **Step 3: Write a smoke test**

`tests/test_smoke.py`:
```python
def test_package_imports():
    import activity_dashboard
    assert activity_dashboard.__version__ == "0.1.0"
```

- [ ] **Step 4: Create venv and install**

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Expected: clean install, no errors.

- [ ] **Step 5: Run smoke test**

```bash
pytest tests/test_smoke.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Update `.gitignore` to exclude .venv**

Append to `.gitignore`:
```
.venv/
*.egg-info/
```

(Already present — verify by `grep '.venv' .gitignore`. If absent, add.)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml activity_dashboard tests .gitignore
git commit -m "scaffold: package layout, pyproject.toml, smoke test"
```

---

## Task 2: Item dataclass and Bucket enum

**Files:**
- Create: `activity_dashboard/item.py`
- Create: `tests/test_item.py`

- [ ] **Step 1: Write the failing test**

`tests/test_item.py`:
```python
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
```

- [ ] **Step 2: Run the test — expect import failure**

```bash
pytest tests/test_item.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'activity_dashboard.item'`.

- [ ] **Step 3: Implement `item.py`**

`activity_dashboard/item.py`:
```python
"""Common item schema returned by all adapters."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Bucket(Enum):
    DONE = "done"
    ACTIVE = "active"
    NEEDS_ATTENTION = "needs_attention"
    NONE = "none"


@dataclass
class Item:
    source: str
    kind: str
    title: str
    url: str
    subject_role: str
    status: str
    last_activity_at: datetime
    bucket: Bucket | None = None
    raw: dict = field(default_factory=dict)
```

- [ ] **Step 4: Run the test — expect pass**

```bash
pytest tests/test_item.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add activity_dashboard/item.py tests/test_item.py
git commit -m "feat(item): add Item dataclass and Bucket enum"
```

---

## Task 3: Config schema and loader

**Files:**
- Create: `activity_dashboard/config.py`
- Create: `tests/test_config.py`
- Create: `tests/fixtures/config_minimal.yaml`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from pathlib import Path
import pytest
import yaml
from activity_dashboard.config import load_config, SubjectConfig, Settings


def write_config(tmp_path: Path, contents: dict) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(contents))
    return p


def minimal_config() -> dict:
    return {
        "credentials": {
            "github_token_file": "~/gh.token",
            "jira": {
                "base_url": "https://example.atlassian.net",
                "email_file": "~/jira.email",
                "token_file": "~/jira.token",
            },
            "google_credentials_file": "~/google-creds.json",
            "google_token_file": "~/google-token.json",
        },
        "rules": {
            "window_days": 7,
            "needs_attention": {
                "pr_awaiting_review_days": 0,
                "jira_assigned_no_movement_days": 2,
                "stalled_pr_days": 5,
                "stalled_jira_days": 5,
                "stalled_launchpad_days": 5,
            },
        },
        "subjects": {
            "alice": {
                "display_name": "Alice Smith",
                "canonical_email": "alice@canonical.com",
                "launchpad_id": "alice-lp",
                "github_id": "alice-gh",
                "one_on_one_doc": "https://docs.google.com/document/d/AAA/edit",
            },
        },
    }


def test_load_config_returns_settings(tmp_path: Path):
    p = write_config(tmp_path, minimal_config())
    settings = load_config(p)
    assert isinstance(settings, Settings)
    assert settings.rules.window_days == 7
    assert settings.rules.needs_attention.stalled_pr_days == 5


def test_load_config_returns_subject_by_name(tmp_path: Path):
    p = write_config(tmp_path, minimal_config())
    settings = load_config(p)
    alice = settings.subject("alice")
    assert isinstance(alice, SubjectConfig)
    assert alice.display_name == "Alice Smith"
    assert alice.github_id == "alice-gh"
    assert alice.canonical_email == "alice@canonical.com"


def test_load_config_missing_subject_raises(tmp_path: Path):
    p = write_config(tmp_path, minimal_config())
    settings = load_config(p)
    with pytest.raises(KeyError):
        settings.subject("nope")


def test_load_config_optional_ubuntu_alias(tmp_path: Path):
    cfg = minimal_config()
    cfg["subjects"]["alice"]["ubuntu_alias"] = "alice@ubuntu.com"
    p = write_config(tmp_path, cfg)
    settings = load_config(p)
    assert settings.subject("alice").ubuntu_alias == "alice@ubuntu.com"


def test_load_config_resolves_home_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = write_config(tmp_path, minimal_config())
    settings = load_config(p)
    assert str(settings.credentials.github_token_file).startswith(str(tmp_path))
```

- [ ] **Step 2: Run the test — expect failure**

```bash
pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `config.py`**

`activity_dashboard/config.py`:
```python
"""YAML config loader and dataclasses."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


def _expand(p: str | None) -> Path | None:
    if p is None:
        return None
    return Path(p).expanduser()


@dataclass
class JiraCredentials:
    base_url: str
    email_file: Path
    token_file: Path


@dataclass
class Credentials:
    github_token_file: Path | None
    jira: JiraCredentials
    google_credentials_file: Path
    google_token_file: Path


@dataclass
class NeedsAttentionThresholds:
    pr_awaiting_review_days: int = 0
    jira_assigned_no_movement_days: int = 2
    stalled_pr_days: int = 5
    stalled_jira_days: int = 5
    stalled_launchpad_days: int = 5


@dataclass
class Rules:
    window_days: int = 7
    needs_attention: NeedsAttentionThresholds = field(default_factory=NeedsAttentionThresholds)


@dataclass
class SubjectConfig:
    name: str
    display_name: str
    canonical_email: str
    launchpad_id: str
    github_id: str
    one_on_one_doc: str
    ubuntu_alias: str | None = None


@dataclass
class Settings:
    credentials: Credentials
    rules: Rules
    subjects: dict[str, SubjectConfig]

    def subject(self, name: str) -> SubjectConfig:
        if name not in self.subjects:
            raise KeyError(f"subject '{name}' not in config")
        return self.subjects[name]


def load_config(path: Path) -> Settings:
    raw = yaml.safe_load(Path(path).read_text())

    c = raw["credentials"]
    creds = Credentials(
        github_token_file=_expand(c.get("github_token_file")),
        jira=JiraCredentials(
            base_url=c["jira"]["base_url"],
            email_file=_expand(c["jira"]["email_file"]),
            token_file=_expand(c["jira"]["token_file"]),
        ),
        google_credentials_file=_expand(c["google_credentials_file"]),
        google_token_file=_expand(c["google_token_file"]),
    )

    r = raw.get("rules", {})
    na = r.get("needs_attention", {})
    rules = Rules(
        window_days=r.get("window_days", 7),
        needs_attention=NeedsAttentionThresholds(
            pr_awaiting_review_days=na.get("pr_awaiting_review_days", 0),
            jira_assigned_no_movement_days=na.get("jira_assigned_no_movement_days", 2),
            stalled_pr_days=na.get("stalled_pr_days", 5),
            stalled_jira_days=na.get("stalled_jira_days", 5),
            stalled_launchpad_days=na.get("stalled_launchpad_days", 5),
        ),
    )

    subjects: dict[str, SubjectConfig] = {}
    for name, s in raw["subjects"].items():
        subjects[name] = SubjectConfig(
            name=name,
            display_name=s["display_name"],
            canonical_email=s["canonical_email"],
            launchpad_id=s["launchpad_id"],
            github_id=s["github_id"],
            one_on_one_doc=s["one_on_one_doc"],
            ubuntu_alias=s.get("ubuntu_alias"),
        )

    return Settings(credentials=creds, rules=rules, subjects=subjects)
```

- [ ] **Step 4: Run the test — expect pass**

```bash
pytest tests/test_config.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add activity_dashboard/config.py tests/test_config.py
git commit -m "feat(config): YAML loader with Settings/SubjectConfig dataclasses"
```

---

## Task 4: GitHub adapter

**Files:**
- Create: `activity_dashboard/adapters/github.py`
- Create: `tests/test_github_adapter.py`

The adapter takes a `_client` kwarg for tests. Real client is built via `github.Github(auth=Auth.Token(...))`. We use `client.search_issues(query)` and convert the search result via `.as_pull_request()`.

- [ ] **Step 1: Write failing tests with a fake client**

`tests/test_github_adapter.py`:
```python
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
```

- [ ] **Step 2: Run the test — expect failure**

```bash
pytest tests/test_github_adapter.py -v
```
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `github.py`**

`activity_dashboard/adapters/github.py`:
```python
"""GitHub adapter — fetches PRs authored by or requested for review from the subject."""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..item import Item

NAME = "github"


def _create_client(settings):
    from github import Github, Auth
    token_file = settings.credentials.github_token_file
    if token_file and Path(token_file).exists():
        token = Path(token_file).read_text().strip()
        return Github(auth=Auth.Token(token))
    return Github()


def _pr_to_item(pr, subject_role: str) -> Item:
    status = "merged" if (subject_role == "author" and getattr(pr, "merged", False)) else pr.state
    return Item(
        source=NAME,
        kind="pr",
        title=pr.title,
        url=pr.html_url,
        subject_role=subject_role,
        status=status,
        last_activity_at=pr.updated_at,
        bucket=None,
        raw={"number": pr.number, "repo": pr.base.repo.full_name},
    )


def fetch(subject, settings, *, _client=None) -> list[Item]:
    client = _client if _client is not None else _create_client(settings)
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.rules.window_days)
    cutoff_date = cutoff.date().isoformat()

    items: list[Item] = []

    authored_query = f"author:{subject.github_id} is:pr updated:>={cutoff_date}"
    for issue in client.search_issues(authored_query):
        items.append(_pr_to_item(issue.as_pull_request(), "author"))

    review_query = f"review-requested:{subject.github_id} is:pr is:open"
    for issue in client.search_issues(review_query):
        items.append(_pr_to_item(issue.as_pull_request(), "reviewer"))

    return items
```

- [ ] **Step 4: Run the test — expect pass**

```bash
pytest tests/test_github_adapter.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add activity_dashboard/adapters/github.py tests/test_github_adapter.py
git commit -m "feat(adapters): GitHub adapter with author + review-requested queries"
```

---

## Task 5: Launchpad adapter

**Files:**
- Create: `activity_dashboard/adapters/launchpad.py`
- Create: `tests/test_launchpad_adapter.py`

The Launchpad client is `launchpadlib.Launchpad.login_anonymously(...)` (or `login_with(...)` for auth). The interface exposes `people[id]`, `.searchTasks(...)`, `.getMergeProposals(...)`. We test against a fake.

- [ ] **Step 1: Write failing tests**

`tests/test_launchpad_adapter.py`:
```python
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
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_launchpad_adapter.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `launchpad.py`**

`activity_dashboard/adapters/launchpad.py`:
```python
"""Launchpad adapter — bugs and merge proposals authored/assigned by the subject."""

from __future__ import annotations
from datetime import datetime, timedelta, timezone

from ..item import Item

NAME = "launchpad"


def _create_client(settings):
    from launchpadlib.launchpad import Launchpad
    return Launchpad.login_anonymously("activity-dashboard", "production", version="devel")


def fetch(subject, settings, *, _client=None) -> list[Item]:
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

    return items
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_launchpad_adapter.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add activity_dashboard/adapters/launchpad.py tests/test_launchpad_adapter.py
git commit -m "feat(adapters): Launchpad adapter for bugs and merge proposals"
```

---

## Task 6: Jira adapter

**Files:**
- Create: `activity_dashboard/adapters/jira.py`
- Create: `tests/test_jira_adapter.py`

Atlassian client: `from atlassian import Jira`. Use `client.jql(query, fields=[...])` which returns `{"issues": [...]}` with each issue containing `key`, `fields.summary`, `fields.status.name`, `fields.updated`, etc.

- [ ] **Step 1: Write failing tests**

`tests/test_jira_adapter.py`:
```python
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
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_jira_adapter.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `jira.py`**

`activity_dashboard/adapters/jira.py`:
```python
"""Jira adapter — tickets where the subject is assignee, within the activity window."""

from __future__ import annotations
from datetime import datetime
from pathlib import Path

from ..item import Item

NAME = "jira"


def _create_client(settings):
    from atlassian import Jira
    email = Path(settings.credentials.jira.email_file).read_text().strip()
    token = Path(settings.credentials.jira.token_file).read_text().strip()
    return Jira(
        url=settings.credentials.jira.base_url,
        username=email,
        password=token,
        cloud=True,
    )


def _parse_jira_datetime(s: str) -> datetime:
    # Jira returns "2026-05-10T12:00:00.000+0000" — Python's fromisoformat doesn't accept
    # +0000 without a colon prior to 3.11. We strip it cleanly.
    if s.endswith("+0000"):
        s = s[:-5] + "+00:00"
    return datetime.fromisoformat(s)


def fetch(subject, settings, *, _client=None) -> list[Item]:
    client = _client if _client is not None else _create_client(settings)

    window = settings.rules.window_days
    jql = (
        f'assignee = "{subject.canonical_email}" '
        f"AND updated >= -{window}d "
        "ORDER BY updated DESC"
    )
    response = client.jql(jql, fields=["summary", "status", "updated"], limit=200)
    base_url = settings.credentials.jira.base_url.rstrip("/")

    items: list[Item] = []
    for issue in response.get("issues", []):
        key = issue["key"]
        fields = issue["fields"]
        items.append(Item(
            source=NAME,
            kind="ticket",
            title=fields["summary"],
            url=f"{base_url}/browse/{key}",
            subject_role="assignee",
            status=fields["status"]["name"],
            last_activity_at=_parse_jira_datetime(fields["updated"]),
            bucket=None,
            raw={"key": key},
        ))
    return items
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_jira_adapter.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add activity_dashboard/adapters/jira.py tests/test_jira_adapter.py
git commit -m "feat(adapters): Jira adapter using JQL assignee + window"
```

---

## Task 7: Google Docs (1-1 notes) adapter

**Files:**
- Create: `activity_dashboard/adapters/gdocs.py`
- Create: `tests/test_gdocs_adapter.py`

Adapter resolves `subject.one_on_one_doc` to a doc ID, fetches the doc, walks the body, and extracts paragraphs under the headings "For next week" and "Carried over from last week" until the next heading. Each item becomes `kind="action_item"` with `bucket=Bucket.NONE`.

The Docs API returns a tree like:
```json
{"body": {"content": [
    {"paragraph": {"elements": [{"textRun": {"content": "Carried over from last week\n"}}],
                   "paragraphStyle": {"namedStyleType": "HEADING_2"}}},
    {"paragraph": {"elements": [{"textRun": {"content": "• do the foo\n"}}],
                   "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}}},
    ...
]}}
```

- [ ] **Step 1: Write failing tests**

`tests/test_gdocs_adapter.py`:
```python
from activity_dashboard.adapters import gdocs as gdocs_adapter
from activity_dashboard.item import Bucket
from activity_dashboard.config import Settings, Credentials, JiraCredentials, Rules, NeedsAttentionThresholds, SubjectConfig


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


def _subject(doc_url="https://docs.google.com/document/d/abc123XYZ/edit"):
    return SubjectConfig(
        name="alice", display_name="Alice", canonical_email="a@c.com",
        launchpad_id="alice-lp", github_id="alice-gh",
        one_on_one_doc=doc_url,
    )


def _para(text, style="NORMAL_TEXT"):
    return {"paragraph": {
        "elements": [{"textRun": {"content": text + "\n"}}],
        "paragraphStyle": {"namedStyleType": style},
    }}


class FakeDocsAPI:
    def __init__(self, doc):
        self.doc = doc
        self.last_doc_id = None
    def documents(self):
        return self
    def get(self, documentId):
        self.last_doc_id = documentId
        return self
    def execute(self):
        return self.doc


def test_name_constant():
    assert gdocs_adapter.NAME == "gdocs"


def test_extract_doc_id_from_url():
    assert gdocs_adapter._extract_doc_id(
        "https://docs.google.com/document/d/abc123XYZ/edit"
    ) == "abc123XYZ"
    assert gdocs_adapter._extract_doc_id("abc123XYZ") == "abc123XYZ"


def test_fetch_action_items_under_for_next_week():
    doc = {"body": {"content": [
        _para("For next week", "HEADING_2"),
        _para("Talk to bob about widget"),
        _para("File launchpad bug for crash"),
        _para("Other section", "HEADING_2"),
        _para("ignored content"),
    ]}}
    client = FakeDocsAPI(doc)
    items = gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    titles = [i.title for i in items]
    assert "Talk to bob about widget" in titles
    assert "File launchpad bug for crash" in titles
    assert "ignored content" not in titles


def test_fetch_action_items_under_carried_over():
    doc = {"body": {"content": [
        _para("Carried over from last week", "HEADING_2"),
        _para("Review the alpha doc"),
        _para("For next week", "HEADING_2"),
        _para("Schedule architecture sync"),
    ]}}
    client = FakeDocsAPI(doc)
    items = gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    sections = {i.raw["section"] for i in items}
    assert "carried_over" in sections
    assert "for_next_week" in sections


def test_action_items_have_bucket_none_and_correct_kind():
    doc = {"body": {"content": [
        _para("For next week", "HEADING_2"),
        _para("do the thing"),
    ]}}
    client = FakeDocsAPI(doc)
    items = gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    assert all(i.kind == "action_item" for i in items)
    assert all(i.bucket == Bucket.NONE for i in items)
    assert items[0].source == "gdocs"


def test_fetch_empty_when_no_matching_sections():
    doc = {"body": {"content": [
        _para("Topics to discuss", "HEADING_2"),
        _para("random note"),
    ]}}
    client = FakeDocsAPI(doc)
    items = gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    assert items == []


def test_fetch_uses_subject_doc_id():
    doc = {"body": {"content": []}}
    client = FakeDocsAPI(doc)
    gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    assert client.last_doc_id == "abc123XYZ"


def test_fetch_ignores_empty_paragraphs():
    doc = {"body": {"content": [
        _para("For next week", "HEADING_2"),
        _para(""),
        _para("   "),
        _para("real item"),
    ]}}
    client = FakeDocsAPI(doc)
    items = gdocs_adapter.fetch(_subject(), _settings(), _client=client)
    assert [i.title for i in items] == ["real item"]
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_gdocs_adapter.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `gdocs.py`**

`activity_dashboard/adapters/gdocs.py`:
```python
"""Google Docs adapter — extracts 'For next week' and 'Carried over' action items
from a per-subject 1-1 notes document."""

from __future__ import annotations
import re
from datetime import datetime, timezone

from ..item import Item, Bucket

NAME = "gdocs"

_DOC_ID_RE = re.compile(r"/document/d/([A-Za-z0-9_-]+)")

_SECTION_HEADERS = {
    "for next week": "for_next_week",
    "carried over from last week": "carried_over",
}
_HEADING_STYLES = {"HEADING_1", "HEADING_2", "HEADING_3", "TITLE"}


def _extract_doc_id(url_or_id: str) -> str:
    m = _DOC_ID_RE.search(url_or_id)
    if m:
        return m.group(1)
    return url_or_id


def _create_client(settings):
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials as OAuthCredentials
    from google.auth.transport.requests import Request
    from pathlib import Path
    import json

    scopes = ["https://www.googleapis.com/auth/documents.readonly"]
    creds_path = settings.credentials.google_credentials_file
    token_path = settings.credentials.google_token_file

    creds = None
    if Path(token_path).exists():
        creds = OAuthCredentials.from_authorized_user_file(str(token_path), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
            creds = flow.run_local_server(port=0)
        Path(token_path).write_text(creds.to_json())
    return build("docs", "v1", credentials=creds)


def _paragraph_text(paragraph: dict) -> str:
    parts = []
    for el in paragraph.get("elements", []):
        run = el.get("textRun")
        if run:
            parts.append(run.get("content", ""))
    return "".join(parts).strip()


def _paragraph_style(paragraph: dict) -> str:
    return paragraph.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")


def fetch(subject, settings, *, _client=None) -> list[Item]:
    client = _client if _client is not None else _create_client(settings)
    doc_id = _extract_doc_id(subject.one_on_one_doc)
    doc = client.documents().get(documentId=doc_id).execute()

    items: list[Item] = []
    current_section: str | None = None
    now = datetime.now(timezone.utc)

    for entry in doc.get("body", {}).get("content", []):
        paragraph = entry.get("paragraph")
        if not paragraph:
            continue
        text = _paragraph_text(paragraph)
        style = _paragraph_style(paragraph)

        if style in _HEADING_STYLES:
            current_section = _SECTION_HEADERS.get(text.lower())
            continue

        if current_section and text:
            items.append(Item(
                source=NAME,
                kind="action_item",
                title=text,
                url=subject.one_on_one_doc,
                subject_role="assignee",
                status="pending",
                last_activity_at=now,
                bucket=Bucket.NONE,
                raw={"section": current_section},
            ))

    return items
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_gdocs_adapter.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add activity_dashboard/adapters/gdocs.py tests/test_gdocs_adapter.py
git commit -m "feat(adapters): Google Docs adapter parsing For next week + Carried over"
```

---

## Task 8: Gmail scaffold

**Files:**
- Create: `activity_dashboard/adapters/gmail.py`
- Create: `tests/test_gmail_adapter.py`

- [ ] **Step 1: Write the test**

`tests/test_gmail_adapter.py`:
```python
import pytest
from activity_dashboard.adapters import gmail as gmail_adapter


def test_name_constant():
    assert gmail_adapter.NAME == "gmail"


def test_fetch_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        gmail_adapter.fetch(subject=None, settings=None)
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_gmail_adapter.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement scaffold**

`activity_dashboard/adapters/gmail.py`:
```python
"""Gmail adapter — scaffolded for v1. The orchestrator catches NotImplementedError
and hides this adapter from the UI."""

NAME = "gmail"


def fetch(subject, settings, *, _client=None):
    raise NotImplementedError(
        "Gmail adapter is not implemented in v1. Planned approach: a Workspace "
        "automation generates a daily summary Google Doc that the gdocs adapter parses."
    )
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_gmail_adapter.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add activity_dashboard/adapters/gmail.py tests/test_gmail_adapter.py
git commit -m "feat(adapters): Gmail scaffold raising NotImplementedError"
```

---

## Task 9: Rules engine

**Files:**
- Create: `activity_dashboard/rules.py`
- Create: `tests/test_rules.py`

The rules engine assigns each `Item` to a `Bucket`. Items with `kind="action_item"` keep `Bucket.NONE` (from gdocs adapter) and are not reassigned.

- [ ] **Step 1: Write the failing tests**

`tests/test_rules.py`:
```python
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
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_rules.py -v
```
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `rules.py`**

`activity_dashboard/rules.py`:
```python
"""Rules engine: deterministic bucket assignment per item."""

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
    """Return the bucket for an item. Items with kind='action_item' keep Bucket.NONE."""
    if item.kind == "action_item":
        return Bucket.NONE
    if item.source == "github":
        return _bucket_for_github(item, rules, now)
    if item.source == "jira":
        return _bucket_for_jira(item, rules, now)
    if item.source == "launchpad":
        return _bucket_for_launchpad(item, rules, now)
    return Bucket.ACTIVE
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_rules.py -v
```
Expected: 16 passed.

- [ ] **Step 5: Commit**

```bash
git add activity_dashboard/rules.py tests/test_rules.py
git commit -m "feat(rules): per-source bucket assignment with thresholds"
```

---

## Task 10: CLI and orchestrator

**Files:**
- Create: `activity_dashboard/cli.py`
- Create: `tests/test_cli.py`

The CLI: `activity-dashboard --subject NAME [--config PATH] [--out PATH]`. Orchestrator builds adapter list, fetches in parallel, applies rules, calls render, writes file.

For this task we test orchestration without the full render path. We stub out the render function with monkeypatch.

- [ ] **Step 1: Write failing tests**

`tests/test_cli.py`:
```python
from datetime import datetime, timezone
from pathlib import Path
import yaml
from activity_dashboard import cli
from activity_dashboard.item import Item, Bucket


def _write_config(tmp_path):
    cfg = {
        "credentials": {
            "github_token_file": None,
            "jira": {"base_url": "https://x.atlassian.net",
                     "email_file": None, "token_file": None},
            "google_credentials_file": None, "google_token_file": None,
        },
        "rules": {"window_days": 7, "needs_attention": {
            "pr_awaiting_review_days": 0, "jira_assigned_no_movement_days": 2,
            "stalled_pr_days": 5, "stalled_jira_days": 5, "stalled_launchpad_days": 5,
        }},
        "subjects": {"alice": {
            "display_name": "Alice", "canonical_email": "a@c.com",
            "launchpad_id": "alice-lp", "github_id": "alice-gh",
            "one_on_one_doc": "https://docs.google.com/document/d/AAA/edit",
        }},
    }
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def _fake_item(source, status="open"):
    return Item(
        source=source, kind="pr", title=f"{source} item", url="u",
        subject_role="author", status=status,
        last_activity_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        bucket=None, raw={},
    )


def test_run_calls_each_adapter_and_applies_rules(tmp_path, monkeypatch):
    cfg = _write_config(tmp_path)

    # Replace each adapter's fetch with a stub.
    def gh_fetch(s, settings, *, _client=None): return [_fake_item("github", "merged")]
    def lp_fetch(s, settings, *, _client=None): return [_fake_item("launchpad", "Confirmed")]
    def jira_fetch(s, settings, *, _client=None): return [_fake_item("jira", "Done")]
    def gdocs_fetch(s, settings, *, _client=None): return []

    from activity_dashboard.adapters import github, launchpad, jira, gdocs
    monkeypatch.setattr(github, "fetch", gh_fetch)
    monkeypatch.setattr(launchpad, "fetch", lp_fetch)
    monkeypatch.setattr(jira, "fetch", jira_fetch)
    monkeypatch.setattr(gdocs, "fetch", gdocs_fetch)

    captured = {}
    def fake_render(results, subject, settings, out_path):
        captured["results"] = results
        captured["out_path"] = out_path
        Path(out_path).write_text("<html>fake</html>")
    monkeypatch.setattr("activity_dashboard.cli.render_report", fake_render)

    out_path = tmp_path / "report.html"
    exit_code = cli.main(["--subject", "alice", "--config", str(cfg), "--out", str(out_path)])

    assert exit_code == 0
    assert out_path.exists()
    assert "github" in captured["results"]
    assert "launchpad" in captured["results"]
    assert "jira" in captured["results"]

    # Rules applied — github merged → DONE
    gh_items = captured["results"]["github"]
    assert gh_items[0].bucket == Bucket.DONE


def test_run_skips_gmail_with_not_implemented(tmp_path, monkeypatch, caplog):
    import logging
    cfg = _write_config(tmp_path)

    from activity_dashboard.adapters import github, launchpad, jira, gdocs
    monkeypatch.setattr(github, "fetch", lambda s, st, *, _client=None: [])
    monkeypatch.setattr(launchpad, "fetch", lambda s, st, *, _client=None: [])
    monkeypatch.setattr(jira, "fetch", lambda s, st, *, _client=None: [])
    monkeypatch.setattr(gdocs, "fetch", lambda s, st, *, _client=None: [])

    rendered = {}
    monkeypatch.setattr("activity_dashboard.cli.render_report",
                       lambda r, s, st, p: rendered.update({"r": r, "p": p}) or Path(p).write_text(""))

    caplog.set_level(logging.INFO)
    out_path = tmp_path / "report.html"
    cli.main(["--subject", "alice", "--config", str(cfg), "--out", str(out_path)])

    assert "gmail" not in rendered["r"]  # gmail skipped
    assert any("gmail" in rec.message and "skipped" in rec.message for rec in caplog.records)


def test_run_isolates_failures(tmp_path, monkeypatch):
    cfg = _write_config(tmp_path)

    def fail_fetch(s, st, *, _client=None): raise RuntimeError("network down")
    def ok_fetch(s, st, *, _client=None): return [_fake_item("launchpad", "Confirmed")]

    from activity_dashboard.adapters import github, launchpad, jira, gdocs
    monkeypatch.setattr(github, "fetch", fail_fetch)
    monkeypatch.setattr(launchpad, "fetch", ok_fetch)
    monkeypatch.setattr(jira, "fetch", lambda s, st, *, _client=None: [])
    monkeypatch.setattr(gdocs, "fetch", lambda s, st, *, _client=None: [])

    captured = {}
    def fake_render(results, subject, settings, out_path):
        captured["results"] = results
        Path(out_path).write_text("")
    monkeypatch.setattr("activity_dashboard.cli.render_report", fake_render)

    out_path = tmp_path / "report.html"
    exit_code = cli.main(["--subject", "alice", "--config", str(cfg), "--out", str(out_path)])

    assert exit_code == 0
    assert isinstance(captured["results"]["github"], Exception)
    assert isinstance(captured["results"]["launchpad"], list)
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_cli.py -v
```
Expected: FAIL — `cli.main` not found.

- [ ] **Step 3: Implement `cli.py`**

`activity_dashboard/cli.py`:
```python
"""CLI entrypoint and orchestrator."""

from __future__ import annotations
import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .item import Item
from .rules import assign_bucket
from .render import render_report
from .adapters import github, launchpad, jira, gdocs, gmail


log = logging.getLogger("activity_dashboard")

ADAPTERS = [github, launchpad, jira, gdocs, gmail]


def _fetch_all(subject, settings) -> dict[str, list[Item] | Exception]:
    results: dict[str, list[Item] | Exception] = {}
    with ThreadPoolExecutor(max_workers=len(ADAPTERS)) as ex:
        futures = {ex.submit(mod.fetch, subject, settings): mod.NAME for mod in ADAPTERS}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except NotImplementedError:
                log.info("adapter %s skipped (not implemented)", name)
            except Exception as e:
                log.warning("adapter %s failed: %s", name, e)
                results[name] = e
    return results


def _apply_rules(results, settings, now) -> None:
    for source, value in results.items():
        if isinstance(value, list):
            for item in value:
                item.bucket = assign_bucket(item, settings.rules, now)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="activity-dashboard")
    parser.add_argument("--subject", required=True, help="subject name from config")
    parser.add_argument("--config", default="~/.config/activity-dashboard/config.yaml")
    parser.add_argument("--out", default="report.html")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config_path = Path(args.config).expanduser()
    settings = load_config(config_path)
    subject = settings.subject(args.subject)
    out_path = Path(args.out).expanduser()

    results = _fetch_all(subject, settings)
    now = datetime.now(timezone.utc)
    _apply_rules(results, settings, now)

    render_report(results, subject, settings, out_path)
    log.info("wrote %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_cli.py -v
```
Expected: 3 passed.

NOTE: the tests import `render_report`. The render module doesn't exist yet — we need a stub for tests to import. Create a placeholder render module:

`activity_dashboard/render.py` (temporary stub, completed in Task 11):
```python
"""Render module — full implementation in Task 11."""

from pathlib import Path


def render_report(results, subject, settings, out_path: Path) -> None:
    Path(out_path).write_text("<html><body>placeholder</body></html>")
```

After creating the stub, re-run the tests.

- [ ] **Step 5: Commit**

```bash
git add activity_dashboard/cli.py activity_dashboard/render.py tests/test_cli.py
git commit -m "feat(cli): orchestrator with parallel fetch and failure isolation"
```

---

## Task 11: Template and renderer

**Files:**
- Modify: `activity_dashboard/render.py` (replace stub with full implementation)
- Create: `activity_dashboard/templates/report.html.j2`
- Create: `tests/test_render.py`

The renderer groups items by bucket (top tier), by source (bottom tier), and renders Vanilla Framework HTML.

- [ ] **Step 1: Write failing tests**

`tests/test_render.py`:
```python
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
                                  email_file=None, token_file=None),
            google_credentials_file=None, google_token_file=None,
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
    assert "vanillaframework" in out.read_text().lower()


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
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_render.py -v
```
Expected: FAIL — template not found / stub doesn't include required output.

- [ ] **Step 3: Create the Jinja2 template**

`activity_dashboard/templates/report.html.j2`:
```jinja
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>activity-dashboard — {{ subject.display_name }}</title>
  <link rel="stylesheet" href="https://assets.ubuntu.com/v1/vanilla-framework-version-4.20.0.min.css">
  <style>
    body { padding: 1.5rem 2rem; }
    .source-badge { display: inline-block; padding: 0 0.4em; margin-right: 0.4em;
                    border-radius: 4px; font-size: 0.75em; color: #fff; vertical-align: middle; }
    .source-badge.github   { background: #24292e; }
    .source-badge.launchpad{ background: #772953; }
    .source-badge.jira     { background: #0052cc; }
    .source-badge.gdocs    { background: #1a73e8; }
    .item { padding: 0.3em 0; }
    .meta { color: #666; font-size: 0.85em; margin-left: 0.4em; }
    .error-card { background: #fdecea; border: 1px solid #f5c2c0;
                  padding: 0.7em 1em; border-radius: 4px; }
    .one-on-one-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
    @media (max-width: 768px) { .one-on-one-cols { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header class="p-strip is-shallow">
    <div class="u-fixed-width">
      <h1>{{ subject.display_name }}</h1>
      <p class="p-text--small">Generated {{ generated_at }}</p>
    </div>
  </header>

  <section class="p-strip is-shallow">
    <div class="row">
      {% for bucket_name, bucket_label in buckets %}
      <div class="col-4">
        <h2 class="p-heading--4">{{ bucket_label }}</h2>
        {% set items = grouped_by_bucket.get(bucket_name, []) %}
        {% if items %}
        <ul class="p-list">
          {% for it in items %}
          <li class="p-list__item item">
            <span class="source-badge {{ it.source }}">{{ source_labels[it.source] }}</span>
            <a href="{{ it.url }}">{{ it.title }}</a>
            <span class="meta">{{ relative_age(it.last_activity_at) }} · {{ it.status }}</span>
          </li>
          {% endfor %}
        </ul>
        {% else %}
        <p class="p-text--small u-text--muted">Nothing here.</p>
        {% endif %}
      </div>
      {% endfor %}
    </div>
  </section>

  <section class="p-strip is-shallow">
    <div class="u-fixed-width">
      <h2 class="p-heading--3">Per-source feed</h2>
    </div>
    <div class="row">
      {% for source_name, source_label in active_sources %}
      <div class="col-3">
        <h3 class="p-heading--5">{{ source_label }}</h3>
        {% set value = results.get(source_name) %}
        {% if value is iterable and value is not string %}
          {% if value %}
          <ul class="p-list">
            {% for it in value %}
            <li class="p-list__item item">
              <a href="{{ it.url }}">{{ it.title }}</a>
              <span class="meta">{{ it.status }}</span>
            </li>
            {% endfor %}
          </ul>
          {% else %}
          <p class="p-text--small u-text--muted">No activity.</p>
          {% endif %}
        {% else %}
          <div class="error-card">{{ source_label }} fetch failed: {{ value }}</div>
        {% endif %}
      </div>
      {% endfor %}

      {% if one_on_one_items %}
      <div class="col-12">
        <h3 class="p-heading--5">1-1 notes</h3>
        <div class="one-on-one-cols">
          <div>
            <h4 class="p-heading--6">Carried over from last week</h4>
            {% if carried_over %}
            <ul class="p-list">
              {% for it in carried_over %}
              <li class="p-list__item item"><a href="{{ it.url }}">{{ it.title }}</a></li>
              {% endfor %}
            </ul>
            {% else %}
            <p class="p-text--small u-text--muted">Nothing carried over.</p>
            {% endif %}
          </div>
          <div>
            <h4 class="p-heading--6">For next week</h4>
            {% if for_next_week %}
            <ul class="p-list">
              {% for it in for_next_week %}
              <li class="p-list__item item"><a href="{{ it.url }}">{{ it.title }}</a></li>
              {% endfor %}
            </ul>
            {% else %}
            <p class="p-text--small u-text--muted">Nothing planned.</p>
            {% endif %}
          </div>
        </div>
      </div>
      {% endif %}
    </div>
  </section>
</body>
</html>
```

- [ ] **Step 4: Replace the stub `render.py` with the full implementation**

`activity_dashboard/render.py`:
```python
"""HTML rendering with Jinja2 + Vanilla Framework."""

from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .item import Item, Bucket


_TEMPLATE_DIR = Path(__file__).parent / "templates"

BUCKETS = [
    ("done", "Done"),
    ("active", "Active"),
    ("needs_attention", "Needs attention"),
]

SOURCE_LABELS = {
    "github": "GitHub",
    "launchpad": "Launchpad",
    "jira": "Jira",
    "gdocs": "1-1 notes",
    "gmail": "Gmail",
}


def _relative_age(when: datetime) -> str:
    now = datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = now - when
    secs = int(delta.total_seconds())
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _group_by_bucket(results) -> dict[str, list[Item]]:
    grouped: dict[str, list[Item]] = {b: [] for b, _ in BUCKETS}
    for source, value in results.items():
        if not isinstance(value, list):
            continue
        for item in value:
            if item.bucket is None or item.bucket == Bucket.NONE:
                continue
            grouped[item.bucket.value].append(item)
    for items in grouped.values():
        items.sort(key=lambda i: i.last_activity_at, reverse=True)
    return grouped


def render_report(results, subject, settings, out_path: Path) -> None:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["relative_age"] = _relative_age

    grouped = _group_by_bucket(results)

    # Per-source feed: include sources we got results from (success or failure),
    # excluding gdocs (it's handled by the 1-1 panel).
    active_sources = [(name, SOURCE_LABELS[name])
                      for name in results.keys()
                      if name != "gdocs"]

    # 1-1 panel data
    one_on_one_items = []
    raw = results.get("gdocs")
    if isinstance(raw, list):
        one_on_one_items = [i for i in raw if i.kind == "action_item"]
    carried_over = [i for i in one_on_one_items if i.raw.get("section") == "carried_over"]
    for_next_week = [i for i in one_on_one_items if i.raw.get("section") == "for_next_week"]

    template = env.get_template("report.html.j2")
    html = template.render(
        subject=subject,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        buckets=BUCKETS,
        grouped_by_bucket=grouped,
        results=results,
        active_sources=active_sources,
        source_labels=SOURCE_LABELS,
        one_on_one_items=one_on_one_items,
        carried_over=carried_over,
        for_next_week=for_next_week,
    )
    Path(out_path).write_text(html)
```

- [ ] **Step 5: Run — expect pass**

```bash
pytest tests/test_render.py -v
```
Expected: 9 passed.

- [ ] **Step 6: Run full test suite**

```bash
pytest -v
```
Expected: all tests pass across every module.

- [ ] **Step 7: Commit**

```bash
git add activity_dashboard/render.py activity_dashboard/templates/ tests/test_render.py
git commit -m "feat(render): Jinja2 template + Vanilla Framework HTML output"
```

---

## Task 12: Polish — example config, README, dry run

**Files:**
- Create: `config.example.yaml`
- Modify: `README.md`

- [ ] **Step 1: Create `config.example.yaml`**

`config.example.yaml`:
```yaml
# Copy this file to ~/.config/activity-dashboard/config.yaml and fill in your details.
# This file is safe to commit; the real one is gitignored.

# Paths to your credentials.
credentials:
  # Optional: GitHub personal access token (boosts rate limits, exposes private repos you can see).
  github_token_file: ~/.config/activity-dashboard/github.token

  jira:
    base_url: https://canonical.atlassian.net
    email_file: ~/.config/activity-dashboard/jira.email
    token_file: ~/.config/activity-dashboard/jira.token

  # Google OAuth — get the client secret JSON from Google Cloud Console
  # (Docs API enabled, OAuth consent screen configured, desktop app credentials).
  google_credentials_file: ~/.config/activity-dashboard/google-creds.json
  # The tool writes/updates this on first run after the OAuth consent dance.
  google_token_file: ~/.config/activity-dashboard/google-token.json

# Rules engine thresholds. All day-counts are knobs.
rules:
  window_days: 7
  needs_attention:
    pr_awaiting_review_days: 0          # 0 = any open PR you're requested on counts
    jira_assigned_no_movement_days: 2
    stalled_pr_days: 5
    stalled_jira_days: 5
    stalled_launchpad_days: 5

# Subjects the dashboard can be run against.
subjects:
  me:
    display_name: Your Name
    canonical_email: you@canonical.com
    ubuntu_alias: you@ubuntu.com            # optional, reserved for future Gmail adapter
    launchpad_id: your-lp-id
    github_id: your-gh-id
    one_on_one_doc: https://docs.google.com/document/d/REPLACE_WITH_DOC_ID/edit

  alice:
    display_name: Alice Smith
    canonical_email: alice.smith@canonical.com
    launchpad_id: alice-lp-id
    github_id: alice-gh
    one_on_one_doc: https://docs.google.com/document/d/REPLACE_WITH_DOC_ID/edit
```

- [ ] **Step 2: Update `README.md`**

`README.md`:
```markdown
# activity-dashboard

A local command-line tool that aggregates recent activity for one *subject* (yourself or someone you manage) across GitHub, Launchpad, Jira, and 1-1 meeting notes, and renders a single static HTML report.

Built for personal week-in-review and 1-1 preparation. Runs entirely on your machine with your credentials — no third-party services, no LLM calls.

## Quick start

```bash
# 1. Install
python3 -m venv .venv
. .venv/bin/activate
pip install -e .

# 2. Copy & fill the example config
mkdir -p ~/.config/activity-dashboard
cp config.example.yaml ~/.config/activity-dashboard/config.yaml
# Edit ~/.config/activity-dashboard/config.yaml — subjects, credentials paths.

# 3. Drop your tokens
echo "<your-github-pat>" > ~/.config/activity-dashboard/github.token
echo "<your-email>" > ~/.config/activity-dashboard/jira.email
echo "<your-jira-api-token>" > ~/.config/activity-dashboard/jira.token
# Download the Google OAuth client JSON to ~/.config/activity-dashboard/google-creds.json

# 4. Run
activity-dashboard --subject me --out ~/report.html
xdg-open ~/report.html
```

The first run triggers a browser OAuth flow for Google Docs. Subsequent runs use the cached token.

## What it shows

**Top tier** — three intent buckets, mixed across sources:
- **Done** — recently merged PRs, resolved tickets, fix-released bugs.
- **Active** — work currently in progress with recent movement.
- **Needs attention** — PR reviews waiting on you, stalled tickets, idle bugs.

**Bottom tier** — per-source panels with the raw feed, plus a **1-1 notes** panel showing "Carried over from last week" and "For next week" action items from a configured Google Doc.

## Sources

| Source     | v1 status              |
| ---------- | ---------------------- |
| GitHub     | ✅ live                |
| Launchpad  | ✅ live                |
| Jira       | ✅ live                |
| 1-1 notes  | ✅ live (Google Docs)  |
| Gmail      | 🪪 scaffolded          |

Gmail in v1.1: planned via a Google Workspace automation that generates a daily summary Doc — the existing `gdocs` adapter parses it.

## Design spec

See `docs/superpowers/specs/2026-05-13-activity-dashboard-design.md`.

## License

TBD.
```

- [ ] **Step 3: Re-run the full test suite as a final sanity check**

```bash
pytest -v
```
Expected: all tests across all modules pass.

- [ ] **Step 4: Commit**

```bash
git add config.example.yaml README.md
git commit -m "polish: example config, README quick-start, source status table"
```

- [ ] **Step 5: Manual smoke test (optional, recommended before demo)**

Run against real data once tokens are placed:
```bash
activity-dashboard --subject me --out report.html -v
xdg-open report.html
```

Confirm:
- All four source panels populate (or show a clean error card if a token is wrong).
- Top buckets contain reasonable items.
- 1-1 notes panel shows the right action items from your doc.
- Visual layout looks clean in Firefox/Chromium.

---

## Self-review notes

**Spec coverage check:**
- §2 Goals & non-goals → met by overall plan (no LLM, no persistence, no server).
- §3 Users & lens → covered in Task 3 (SubjectConfig) and Task 10 (CLI accepts `--subject`).
- §4 UI design → covered in Task 11 (template).
- §5 Configuration → covered in Task 3 (loader) and Task 12 (example).
- §6 Data model → covered in Task 2.
- §7 Adapters (5 sources) → Tasks 4–8.
- §8 Rules engine → Task 9.
- §9 Rendering → Task 11.
- §10 Failure handling → covered in Task 10 (orchestrator) and Task 11 (error-card path).
- §11 Project layout → matches the structure section at the top of this plan.
- §12 Build phases → mirrored in the 12 tasks.

**Type consistency check:**
- `Item` fields used across adapters, rules, and render — consistent: `source, kind, title, url, subject_role, status, last_activity_at, bucket, raw`.
- `Bucket` enum referenced by rules and render — consistent values `done, active, needs_attention, none`.
- Adapter signature `fetch(subject, settings, *, _client=None)` consistent across all 5 adapters.
- `Settings` / `Rules` / `NeedsAttentionThresholds` field names consistent between config loader, rules engine, and tests.

No placeholders, no TBDs, no "similar to Task N" references. Every code step contains complete code.

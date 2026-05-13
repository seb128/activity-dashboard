# activity-dashboard — Design Spec

**Date:** 2026-05-13

## 1. Overview

A local command-line tool that aggregates recent activity for one *subject* (the user themself, or someone they manage) across the team's primary tools, and renders a single static HTML report. The report shows three intent-based buckets at a glance plus a per-source feed for digging in.

The dashboard is a personal tool, not a service. It runs on the user's laptop, uses their credentials, and never sends data to a third party.

## 2. Goals & non-goals

### Goals
- One command, one HTML file, opens in a browser, looks clean.
- Truthful: never shows data the user couldn't already see manually in the underlying tools.
- Deterministic: same inputs → same buckets. No LLM, no random ranking.
- Extensible: adding a fifth source later is a single new module.
- Resilient: one source failing doesn't break the whole report.

### Non-goals (v1)
- Multi-user deployment, hosting, accounts.
- Live updates, websockets, server.
- Persistence between runs (no DB, no cache).
- LLM summaries or AI ranking.
- Notifications, scheduling, alerts.

## 3. Users & lens

- **Operator:** the user. Always the authenticated principal.
- **Subject:** specified via `--subject <name>` flag. Looked up in config to resolve to per-system identifiers.
- All API queries use the user's credentials. When the subject is someone else (e.g. a direct report), the query parameters (assignee, author, reviewer, etc.) are scoped to that subject's identifiers — but the *access scope* is still the user's (e.g. Gmail searches happen in the user's inbox regardless of subject).

## 4. UI design

### 4.1 Layout (option D)

Single scrollable HTML page, two visual tiers:

```
┌──────────────────────────────────────────────────────────────┐
│ Report for: Alice Smith     Generated 2026-05-13 10:38 UTC   │
├──────────────────────────────────────────────────────────────┤
│ ┌────────────┐  ┌────────────┐  ┌──────────────────────────┐ │
│ │ Done       │  │ Active     │  │ Needs attention          │ │
│ │ (this week)│  │            │  │                          │ │
│ │ • item     │  │ • item     │  │ • item  [GitHub] 3d idle │ │
│ │ • item     │  │ • item     │  │ • item  [Jira]   5d idle │ │
│ │ ...        │  │ ...        │  │ ...                      │ │
│ └────────────┘  └────────────┘  └──────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ Per-source feed                                              │
│ ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│ │ GitHub   │  │ Launchpad│  │ Jira     │  │ 1-1 notes     │  │
│ │ all PRs  │  │ all bugs │  │ all tix  │  │ For next week │  │
│ │ ...      │  │ ...      │  │ ...      │  │ Carried over  │  │
│ └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

- Top tier: 3 columns, equal width on desktop, stacked on narrow viewports (Vanilla Framework grid).
- Bottom tier: 1 panel per active source. Gmail adapter is scaffolded but hidden from UI in v1.

### 4.2 Item rendering

Every item shows:
- **Title** linked to the source URL.
- **Source badge** (small colored tag: GitHub, Launchpad, Jira).
- **Last activity** as relative time ("3 days ago").
- **Status hint** (e.g., "Awaiting your review", "In Progress", "Fix Released").

### 4.3 Styling

Vanilla Framework via CDN. Default color palette. Headings sans-serif. Source badges use Vanilla's `p-status-label` colors.

## 5. Configuration

Single YAML file. Default location: `~/.config/activity-dashboard/config.yaml`. Override with `--config <path>`.

### 5.1 Schema

```yaml
# Paths to the user's credentials.
credentials:
  github_token_file: ~/.config/activity-dashboard/github.token       # optional, for rate limits
  jira:
    base_url: https://canonical.atlassian.net
    email_file: ~/.config/activity-dashboard/jira.email
    token_file: ~/.config/activity-dashboard/jira.token
  google_credentials_file: ~/.config/activity-dashboard/google-creds.json   # OAuth client secret
  google_token_file: ~/.config/activity-dashboard/google-token.json         # cached after first auth

# Rules engine thresholds.
rules:
  window_days: 7
  needs_attention:
    pr_awaiting_review_days: 0          # any PR you're requested on counts
    jira_assigned_no_movement_days: 2
    stalled_pr_days: 5
    stalled_jira_days: 5
    stalled_launchpad_days: 5

# Subjects the dashboard can be run against.
subjects:
  me:
    display_name: Your Name
    canonical_email: you@canonical.com
    ubuntu_alias: you@ubuntu.com   # optional, reserved for future Gmail adapter
    launchpad_id: your-lp-id
    github_id: your-gh-id
    one_on_one_doc: https://docs.google.com/document/d/XXXX/edit   # self — likely unused
  alice:
    display_name: Alice Smith
    canonical_email: alice.smith@canonical.com
    launchpad_id: alice-smith-lp-id
    github_id: alice-gh
    one_on_one_doc: https://docs.google.com/document/d/YYYY/edit
  # ...one entry per direct report
```

The YAML file is gitignored; the example shipped in the repo is `config.example.yaml`.

### 5.2 Token files

Each token file is a single line of text. The user generates and places them manually. The tool never writes them (except `google-token.json`, which the OAuth library refreshes on its own).

## 6. Data model

Common item schema produced by every adapter:

```python
@dataclass
class Item:
    source: str              # "github" | "launchpad" | "jira" | "gdocs"
    kind: str                # "pr" | "issue" | "bug" | "mp" | "ticket" | "action_item"
    title: str
    url: str
    subject_role: str        # "author" | "reviewer" | "assignee" | "mentioned"
    status: str              # source-native status string ("open", "merged", "in_progress", "fix_released", ...)
    last_activity_at: datetime
    bucket: Bucket | None    # filled in by rules engine
    raw: dict                # source-specific dict for the per-source feed
```

```python
class Bucket(Enum):
    DONE = "done"
    ACTIVE = "active"
    NEEDS_ATTENTION = "needs_attention"
    NONE = "none"   # 1-1 action items — shown in own panel, not in top buckets
```

## 7. Adapters

Every adapter is a module exposing:

```python
NAME: str  # e.g., "github"

def fetch(subject: SubjectConfig, settings: Settings) -> list[Item]:
    ...
```

No abstract base class. Tests stub these as plain functions.

### 7.1 GitHub adapter

- Library: `PyGithub`.
- Auth: optional token from `credentials.github_token_file` (raises rate limit ceiling).
- Queries:
  - PRs authored by `subject.github_id` in last `window_days`.
  - PRs where `subject.github_id` is a requested reviewer (open, not yet reviewed).
- Maps to:
  - `kind="pr"`, `status` ∈ {open, merged, closed}.
  - `subject_role` ∈ {author, reviewer}.

### 7.2 Launchpad adapter

- Library: `launchpadlib`.
- Auth: anonymous read OK for public bugs and MPs; OAuth for private data (use the user's cached credentials if present).
- Queries:
  - Bugs where `subject.launchpad_id` is assignee, reporter, or commenter in `window_days`.
  - Merge proposals where `subject.launchpad_id` is registrant or reviewer.
- Maps to:
  - `kind="bug"` or `"mp"`, status from Launchpad-native values.

### 7.3 Jira adapter

- Library: `atlassian-python-api`.
- Auth: email + API token from config.
- Query: JQL `assignee = "<subject.canonical_email>" AND updated >= -<window_days>d`.
  - Plus: `reporter = "<email>"` for items they raised.
- Maps to:
  - `kind="ticket"`, status from Jira workflow.

### 7.4 Google Docs (1-1 notes) adapter

- Library: `google-api-python-client` (Docs API).
- Auth: OAuth (the user runs an installed-app flow first time; token cached).
- Behavior:
  - Resolve `subject.one_on_one_doc` (URL or ID) to a document ID.
  - Fetch the document structure.
  - Walk top-level paragraphs; find headings (style `HEADING_1` or `HEADING_2`) matching:
    - "For next week" → collect following bullets/paragraphs until next heading.
    - "Carried over from last week" → same.
  - Each bullet/paragraph becomes one `Item` with:
    - `kind="action_item"`, `bucket=Bucket.NONE` (lives in per-source panel only).
    - `subject_role="assignee"`, `title=<text>`, `url=<doc URL with section anchor if possible>`.
    - `raw={"section": "for_next_week" | "carried_over"}`.

### 7.5 Gmail adapter (scaffold only)

Module exists at `activity_dashboard/adapters/gmail.py`:

```python
NAME = "gmail"

def fetch(subject, settings):
    raise NotImplementedError(
        "Gmail adapter is not implemented in v1. "
        "See spec section 13 for the planned Workspace-summary approach."
    )
```

`cli.py` skips adapters that raise `NotImplementedError` with a single log line.

## 8. Rules engine (bucket assignment)

A single function:

```python
def assign_bucket(item: Item, settings: Settings, now: datetime) -> Bucket:
    ...
```

Decision logic per source:

| Source / kind | Done | Active | Needs attention |
|---|---|---|---|
| GitHub PR (author) | `status="merged"` or `"closed"` in window | `status="open"` with activity in window | `status="open"`, no activity > `stalled_pr_days` |
| GitHub PR (reviewer) | — | — | always → "awaiting your review" once age ≥ `pr_awaiting_review_days` (default 0 = immediately) |
| Jira ticket (assignee) | status transitioned to Done/Closed/Resolved in window | "In Progress" or "In Review" with activity in window | "In Progress" with no movement > `stalled_jira_days`; or any status with no movement > `jira_assigned_no_movement_days` |
| Launchpad bug | Fix Released / Fix Committed in window | status updates or comments in window | open, no comment > `stalled_launchpad_days` |
| Launchpad MP | Approved / Merged / Rejected in window | open with recent activity | open, awaiting the user's review (subject_role="reviewer") |
| 1-1 action item | — | — | — *(always `Bucket.NONE`)* |

Tie-breaking: each item goes to exactly one bucket. The function evaluates in order Done → Needs attention → Active → falls through to None.

## 9. Rendering

- Templates: Jinja2, in `activity_dashboard/templates/`.
- One root template `report.html.j2`, partials for each bucket and each source panel.
- Vanilla Framework loaded via CDN `<link>` in the template head.
- Items in top buckets sorted by `last_activity_at` descending.
- Per-source panels sorted same way.
- Output written to `--out` path (default: `./report.html` in CWD).

## 10. Failure handling

The orchestrator wraps each adapter call:

```python
results: dict[str, list[Item] | Exception] = {}
with ThreadPoolExecutor() as ex:
    futures = {ex.submit(mod.fetch, subject, settings): mod.NAME for mod in adapters}
    for fut in as_completed(futures):
        name = futures[fut]
        try:
            results[name] = fut.result()
        except NotImplementedError:
            log.info(f"adapter {name} skipped (not implemented)")
        except Exception as e:
            log.warning(f"adapter {name} failed: {e}")
            results[name] = e
```

In templates, any source whose result is an `Exception` renders a small error card in its per-source panel ("GitHub fetch failed: <message>"). The intent buckets simply omit items from that source.

## 11. Project layout

```
activity-dashboard/
├── README.md
├── pyproject.toml
├── config.example.yaml
├── .gitignore                       # excludes config.yaml, token files
├── activity_dashboard/
│   ├── __init__.py
│   ├── cli.py                       # argparse, orchestrator
│   ├── config.py                    # YAML loader + dataclasses
│   ├── item.py                      # Item dataclass, Bucket enum
│   ├── rules.py                     # assign_bucket()
│   ├── render.py                    # Jinja2 orchestration
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── github.py
│   │   ├── launchpad.py
│   │   ├── jira.py
│   │   ├── gdocs.py
│   │   └── gmail.py                 # NotImplementedError scaffold
│   └── templates/
│       ├── report.html.j2
│       ├── _bucket.html.j2
│       └── _source_panel.html.j2
└── tests/
    ├── test_rules.py                # rules engine unit tests
    ├── test_config.py
    └── fixtures/
        └── sample_items.json
```

## 12. Build phases & time budget

| Phase | Work | Hours |
|---|---|---|
| 1 | Project scaffold, `pyproject.toml`, config loader, `Item` dataclass, CLI skeleton, ThreadPoolExecutor orchestrator | 2.0 |
| 2 | GitHub adapter + smoke test against the user's real account | 2.5 |
| 3 | Launchpad adapter + smoke test | 2.5 |
| 4 | Jira adapter + smoke test | 2.5 |
| 5 | Google Docs 1-1 notes adapter + smoke test (OAuth setup is the risk) | 2.0 |
| 6 | Rules engine + unit tests | 2.5 |
| 7 | Jinja2 templates + Vanilla Framework styling | 3.0 |
| 8 | Polish, README, demo prep, dry runs | 1.5 |
| **Total** | | **~18.5h** |

~5.5h slack inside the 24h window for surprises.

## 13. Future (out of scope for v1)

1. **Gmail adapter** — most pragmatic path: a separate Workspace automation generates a daily summary Google Doc; the tool parses it via a second `gdocs`-style adapter. Sidesteps the OAuth scope-expansion required for Gmail API.
2. **Discourse adapter** — "browse recent posts for reminders of things to know/do."
3. **Multi-subject report** — render N reports side-by-side or as a tabbed view for full-team scan.
4. **Local persistence** — remember which items have been seen, surface only deltas.
5. **Trend view** — week-over-week change in active/needs-attention counts.

## 14. Open questions

None at design time. All major forks closed during brainstorming.

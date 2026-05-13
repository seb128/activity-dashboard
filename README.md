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

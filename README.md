# activity-dashboard

A local command-line tool that aggregates recent activity for one *subject* (yourself or someone you manage) across GitHub, Launchpad, Jira, and 1-1 meeting notes, and renders a single static HTML report.

Built for personal week-in-review and 1-1 preparation. Runs entirely on your machine with your credentials — no third-party services, no LLM calls.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
# 1. Install (requires uv: https://docs.astral.sh/uv/)
uv sync

# 2. Copy & fill the example config
mkdir -p ~/.config/activity-dashboard
cp config.example.yaml ~/.config/activity-dashboard/config.yaml
# Edit ~/.config/activity-dashboard/config.yaml — subjects, credentials paths.

# 3. Generate and install your tokens (GitHub, Jira, Google OAuth)
# See "Authentication setup" below for the step-by-step.

# 4. Run
uv run activity-dashboard --subject me --out ~/report.html
xdg-open ~/report.html
```

The first run triggers a browser OAuth flow for Google Docs. Subsequent runs use the cached token.

## Authentication setup

The tool needs read access to your GitHub, Jira, and Google Docs accounts. All credentials live in `~/.config/activity-dashboard/` and never leave your machine. Launchpad needs no token (anonymous API + public-page scrape).

### GitHub personal access token

Used to raise the API rate limit (60 → 5000 req/hour) and to surface private repos / private PRs you have visibility into.

1. Visit <https://github.com/settings/tokens> and click **Generate new token → Tokens (classic)**.
2. Give it a name (e.g. *activity-dashboard*) and an expiration date.
3. Scope: tick **`repo`** for full access (including private). Use **`public_repo`** if you only care about public repos.
4. Click *Generate token*, copy the value, then:
   ```bash
   echo "<paste-token-here>" > ~/.config/activity-dashboard/github.token
   chmod 600 ~/.config/activity-dashboard/github.token
   ```

### Jira API token (Atlassian Cloud)

1. Visit <https://id.atlassian.com/manage-profile/security/api-tokens>.
2. Click **Create API token**, label it (e.g. *activity-dashboard*), and copy the value.
3. Drop your Atlassian email and the token:
   ```bash
   echo "you@canonical.com" > ~/.config/activity-dashboard/jira.email
   echo "<paste-token-here>"  > ~/.config/activity-dashboard/jira.token
   chmod 600 ~/.config/activity-dashboard/jira.{email,token}
   ```
4. If your org uses a non-default Jira URL, update `credentials.jira.base_url` in `config.yaml`.

### Google OAuth (Docs API, for 1-1 notes)

Slightly more involved because Google requires a project + consent flow:

1. Visit <https://console.cloud.google.com/> and either pick an existing personal project or create a new one (it's free).
2. In **APIs & Services → Library**, find and **enable** the *Google Docs API*.
3. In **APIs & Services → OAuth consent screen**, configure:
   - User type: **External** (or **Internal** if your org has Workspace).
   - Add yourself as a test user so the unverified app will let you through.
4. In **APIs & Services → Credentials**, click **Create credentials → OAuth client ID**:
   - Application type: **Desktop app**.
   - Download the resulting JSON.
5. Save the file as:
   ```bash
   mv ~/Downloads/client_secret_*.json ~/.config/activity-dashboard/google-creds.json
   chmod 600 ~/.config/activity-dashboard/google-creds.json
   ```
6. On first `make run`, a browser tab opens for consent. After you allow, the tool caches the refresh token at `~/.config/activity-dashboard/google-token.json`, which is reused on subsequent runs.

### Launchpad

No setup. The Launchpad adapter uses anonymous `launchpadlib` for bugs and authored merge proposals, and scrapes the public `+activereviews` page for review requests (works around [LP bug 1979817](https://bugs.launchpad.net/launchpad/+bug/1979817), which excludes Git MPs from the API).

## Common tasks

A `Makefile` wraps the `uv` commands for convenience:

```bash
make install         # uv sync
make install-dev     # uv sync --extra dev (adds pytest)
make test            # uv run pytest -v
make test-quick      # uv run pytest -q
make run             # uv run activity-dashboard --subject me --out report.html
make run SUBJECT=alice OUT=alice.html
make clean           # remove .venv, caches, and build artifacts
make help            # list all targets
```

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

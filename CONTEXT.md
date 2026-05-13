# Context — activity-dashboard

## What we're building
A local command-line tool that aggregates recent activity for one *subject* (Sebastien or one of his direct reports) across the team's tools, and renders a single static HTML report.

Works for both personal week-in-review and 1-1 preparation — same code, different `--subject` value.

24-hour MVP. Hackathon-style — "wow the judges."

## Repo
- **Path:** `/home/ubuntu/activity-dashboard/`
- **Branch:** `main`
- **Initial commit:** `f9bc139` (design spec + README + .gitignore)
- **Spec:** `docs/superpowers/specs/2026-05-13-activity-dashboard-design.md`

## Decided

### User & lens
- **Operator:** Sebastien runs the tool locally.
- **Subject:** configurable per run — self or any direct report.
- **Auth lens:** always Sebastien's credentials. The dashboard only ever surfaces what Sebastien could see manually. No "perspective flip" logic; Sebastien being the authenticated principal naturally creates the right filtering.

### Layout
1. **Top tier — 3 intent buckets:** *Done* / *Active* / *Needs attention*. Sources mixed within each bucket.
2. **Bottom tier — per-source feed:** one panel per source, plus a dedicated 1-1 notes panel.

(Originally 4 buckets; *Stalled* merged into *Needs attention*.)

### Sources — v1 scope (option B')
**Live (4 sources):**
- **GitHub** — PRs authored / requested for review, with review state and last activity.
- **Launchpad** — bugs and merge proposals authored/assigned/in-review by subject.
- **Jira** — board tickets where subject is assignee, recent activity.
- **Google Docs 1-1 notes** — *one specific document per subject*, referenced in config. Parses two sections:
  - "For next week" (fresh commitments)
  - "Carried over from last week" (implicitly stalled)
  - Rendered as own panel in per-source feed; not folded into intent buckets (no auto status).

**Scaffolded only (1 source):**
- **Gmail** — adapter module exists with `NotImplementedError`, hidden from UI. Config key reserved.

**Parked entirely:**
- **Discourse** — future "browse recent posts for reminders."
- **Gmail-via-Workspace-summary** — clever v1.1 idea: a Workspace automation generates a daily email-summary Google Doc; the tool parses it like any other doc. Sidesteps Gmail OAuth complexity.

### Intelligence
- **No LLM at runtime.** Pure rules. Deterministic, demo-stable, free to run.
- Claude (this agent) writes the code; Sebastien doesn't paste real private content into the dev conversation.

### Time window
Last **7 days** rolling. Configurable in YAML.

### Architecture (Approach 1: linear pipeline)
```
config.yaml → load → [4 adapters fetch in parallel via ThreadPoolExecutor]
                  → list[Item]  (common @dataclass)
                  → rules engine → bucket assignment
                  → Jinja2 template + Vanilla Framework CSS (CDN)
                  → report.html
```

- **Adapters** are plain modules exposing `fetch(subject, config) -> list[Item]` — no ABC, no plugin registry (overkill for 4 sources).
- **Failure isolation:** an adapter exception is caught, logged, rendered as a "fetch failed" panel. Other sources still render.
- **Caching:** none in v1 — fresh data each run.
- **Concurrency:** `ThreadPoolExecutor` for parallel fetch (I/O-bound).

### Styling
**Vanilla Framework** (Canonical's open-source design system), via CDN. Native house aesthetic.

### Config
- Single YAML file at `~/.config/activity-dashboard/config.yaml` (overridable with `--config`).
- Holds: per-subject identifiers (canonical email, optional Ubuntu alias, Launchpad ID, GitHub ID, 1-1 notes doc URL).
- Holds: paths to Sebastien's token files (Jira, Google OAuth, optional GitHub).
- Holds: rule thresholds.
- Gitignored. Repo ships a `config.example.yaml`.

### Deliverable
- CLI: `activity-dashboard --subject <name>`
- Output: `report.html` in CWD (or `--out` flag).
- Re-run to refresh. No server, no persisted state.

### Language / stack
- **Python 3.x**
- `PyGithub`, `launchpadlib`, `atlassian-python-api`, `google-api-python-client`, `Jinja2`, `PyYAML`
- `ThreadPoolExecutor` from stdlib for parallel fetch

## Time budget
~17–18h estimated for B' scope. ~5.5h slack inside the 24h window.

## Current status
- ✅ Brainstorming complete.
- ✅ Design spec written, self-reviewed, committed.
- 📝 **Awaiting:** Sebastien's review of the spec.
- ⏭️ **Next:** invoke `writing-plans` skill to translate the spec into an executable implementation plan.

## Process notes
- Brainstorming skill in use — design first, no code until spec is approved.
- CONTEXT.md is updated on explicit request.

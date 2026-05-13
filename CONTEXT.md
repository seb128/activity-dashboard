# Context — activity-dashboard

## What we're building
A local command-line tool that aggregates recent activity for one *subject* (the user themself, or someone they manage) across the team's tools, and renders a single static HTML report.

Works for both personal week-in-review and 1-1 preparation — same code, different `--subject` value.

24-hour MVP. Hackathon-style — "wow the judges."

## Repo
- **Path:** `/home/ubuntu/hackhathon/activity-dashboard/` (under the hackhathon share, mounted from the user's real system)
- **Branch:** `main`
- **Initial commit:** `f9bc139` (design spec + README + .gitignore)
- **Spec:** `docs/superpowers/specs/2026-05-13-activity-dashboard-design.md`

## Decided

### User & lens
- **Operator:** the user, running the tool locally on their laptop.
- **Subject:** configurable per run — self or any direct report.
- **Auth lens:** always the user's credentials. The dashboard only ever surfaces what the user could see manually. No "perspective flip" logic; the user being the authenticated principal naturally creates the right filtering.

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
- Claude (this agent) writes the code; the user doesn't paste real private content into the dev conversation.

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
- Holds: paths to the user's token files (Jira, Google OAuth, optional GitHub).
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
- ✅ Spec reviewed and approved by Sebastien.
- ✅ Implementation plan written (`docs/superpowers/plans/2026-05-13-activity-dashboard.md`) — 12 TDD tasks, complete code in every step.
- ✅ Execution mode chosen: **Subagent-Driven** (fresh subagent per task, review between tasks).
- ⏸️ **Paused** before kicking off execution. Sebastien is at lunch; will confirm when ready to start.
- ⏭️ **Next:** on confirmation, invoke `superpowers:subagent-driven-development` skill to execute Task 1 of the plan.

## Resume instructions (for any future Claude session)
If this conversation died and you're picking up cold:

1. **Read these files first**, in order:
   - `CONTEXT.md` (this file) — overall context and decisions.
   - `docs/superpowers/specs/2026-05-13-activity-dashboard-design.md` — the design spec.
   - `docs/superpowers/plans/2026-05-13-activity-dashboard.md` — the 12-task execution plan.
2. **Check the repo state:** `git log --oneline` to see how many tasks are already done. Each task ends in a commit with a `feat(...)`, `scaffold:`, or `polish:` prefix. Count those and you'll know which Task # to start from.
3. **Ask Sebastien for confirmation** before kicking off subagents (he asked to be in control of when execution starts).
4. **When green-lit:** invoke `superpowers:subagent-driven-development` skill. Dispatch one subagent per task, in plan order, reviewing between tasks. Don't batch.

## Latest commits
```
99d210c Add implementation plan: 12 TDD tasks for v1
6691971 Restore spec author line; mark spec approved in CONTEXT.md
ff8c610 Genericize spec and CONTEXT.md for sharing
c53f591 Update CONTEXT.md repo path after moving under hackhathon dir
3b9432d Add CONTEXT.md tracking design decisions
f9bc139 Initial commit: design spec for activity-dashboard
```

## Author / operator distinction
- **Author of spec & commits:** Sebastien Bacher (designing the tool with Claude).
- **"the user" in spec body:** generic — anyone who runs the tool. Genericized so the tool can be shared with others.

## Process notes
- Brainstorming skill in use — design first, no code until spec is approved.
- CONTEXT.md is updated on explicit request.

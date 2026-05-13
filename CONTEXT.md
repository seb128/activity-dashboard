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
- **Python 3.11+** (CI/dev currently runs 3.14)
- Runtime deps: `PyGithub`, `launchpadlib`, `atlassian-python-api`, `google-api-python-client`, `google-auth-oauthlib`, `Jinja2`, `PyYAML`, `requests`, `beautifulsoup4`, `lxml`
- `ThreadPoolExecutor` from stdlib for parallel fetch
- Build backend: `setuptools`

### Workflow / packaging
- **Package manager:** `uv` (Astral). `uv.lock` committed for reproducible installs.
- **Install:** `uv sync` (runtime) or `uv sync --extra dev` (adds pytest).
- **Run:** `uv run activity-dashboard --subject me ...` — no manual venv activation.
- **Makefile** wraps common tasks: `make install`, `make install-dev`, `make test`, `make test-quick`, `make run`, `make clean`, `make help`. `make run` accepts `SUBJECT=`, `OUT=`, `CONFIG=` overrides.

## Time budget
~17–18h estimated for B' scope. ~5.5h slack inside the 24h window.

## Current status
- ✅ Brainstorming complete.
- ✅ Design spec written, self-reviewed, committed.
- ✅ Implementation plan written (`docs/superpowers/plans/2026-05-13-activity-dashboard.md`) — 12 TDD tasks.
- ✅ **All 12 implementation tasks complete.** Subagent-driven execution with two-stage review (spec compliance + code quality) per task.
- ✅ Final holistic review done.
- 🟢 **71/71 tests passing** (was 64 after task 12; +6 for LP-reviewer fix, +1 for scrape-isolation test).
- ✅ Spec gap #2 (Jira reporter) closed as spec correction (assignee-only is the desired behavior).
- ✅ Spec gap #1 (Launchpad reviewer MPs) closed with `+activereviews` scrape (`d68247a` + `c964ba1`).
- ⏭️ **Next:** likely demo prep / smoke-test against real APIs.

## Implementation summary

uv-managed Python package `activity-dashboard` at the repo root. Run via the `activity-dashboard` CLI entrypoint defined in `pyproject.toml`.

### File layout (built)
```
activity-dashboard/
├── README.md                 (quick-start)
├── Makefile                  (install / test / run / clean targets)
├── config.example.yaml       (annotated YAML template)
├── pyproject.toml
├── uv.lock                   (reproducible install)
├── activity_dashboard/
│   ├── item.py               (Item dataclass + Bucket enum)
│   ├── config.py             (YAML loader, typed dataclasses)
│   ├── rules.py              (per-source bucket assignment)
│   ├── cli.py                (argparse + ThreadPoolExecutor orchestrator)
│   ├── render.py             (Jinja2 + Vanilla Framework HTML)
│   ├── templates/report.html.j2
│   └── adapters/
│       ├── github.py         live
│       ├── launchpad.py      live (launchpadlib + +activereviews scrape)
│       ├── jira.py           live
│       ├── gdocs.py          live (parses "For next week" + "Carried over")
│       └── gmail.py          scaffold only (raises NotImplementedError)
└── tests/                    (71 tests across all modules)
```

### Bugs caught and fixed during reviews
1. **`config.py`:** `_expand` silently accepted `None` for non-optional `Path` fields → added `_require_expand` (Task 3 fix, `4e5488d`).
2. **`render.py`:** autoescape was silently disabled because `select_autoescape(["html"])` doesn't match `.j2` extension — real XSS hole on item titles → fixed to `select_autoescape(["html", "j2"])` (`c04dd10`).
3. **`render.py`:** `SOURCE_LABELS[name]` would `KeyError` on unknown source → defensive `.get(name, name)` (`c04dd10`).
4. **`render.py`:** `Path.write_text(html)` used locale-default encoding → explicit `encoding="utf-8"` (`80959da`).

## Known gaps (final review findings)

These are spec items the plan **didn't propagate to code**. The dashboard works without them, but for a complete demo:

| # | Severity | Gap | Spec ref | Cost |
|---|---|---|---|---|
| ~~1~~ | resolved | ~~Launchpad reviewer MPs~~ — closed in `d68247a` + `c964ba1` by scraping `https://code.launchpad.net/~<id>/+activereviews` (works around LP API gap for Git MPs, [bug 1979817](https://bugs.launchpad.net/launchpad/+bug/1979817)). Adopted from Canonical's existing scraping pattern. Rules engine routes reviewer-role MPs → NEEDS_ATTENTION. Scrape failures isolated so they don't drop launchpadlib data. | §7.2, §8 | done |
| ~~2~~ | resolved | ~~Jira `reporter` query~~ — spec corrected: assignee-only is the desired behavior (we want the subject's *current work*, not historical filings). No code change needed. | §7.3 (spec updated) | done |
| 3 | Minor (latent) | **Source badge label** in top-tier bucket template uses `source_labels[it.source]`, would render blank for unknown source. All 5 current sources are mapped so not observable today. | n/a (defensive only) | 1 line |
| 4 | Minor / informational | Silent fallback to anonymous GitHub when token file is configured-but-missing — no warning. | n/a | ~3 lines |

Workaround for an immediate demo: pick a subject whose work is primarily author/assignee (not reviewer-heavy).

## Demo-readiness
The final reviewer's verdict: **Ready**, with awareness of gaps #1 and #2 above.

## Suggested next steps for Sebastien
1. **Smoke test against real APIs.** Drop tokens into `~/.config/activity-dashboard/`, run `activity-dashboard --subject me`, inspect the HTML.
2. **Fix the two Important gaps** (#1 LP reviewer MPs, #2 Jira reporter) if they matter for your demo subject.
3. **Demo prep:** dry-run the report against a few different subjects to catch any visual issues.

## Resume instructions (for any future Claude session)
If this conversation died and you're picking up cold:

1. **Read in order:** `CONTEXT.md` (this file), `docs/superpowers/specs/2026-05-13-activity-dashboard-design.md`, `docs/superpowers/plans/2026-05-13-activity-dashboard.md`.
2. **Verify state:** `cd /home/ubuntu/hackhathon/activity-dashboard && make test-quick` (expect 71 passing). Or `uv run pytest -q`.
3. **Check `git log --oneline`** — should match the "Recent commits" section below.
4. **Ask Sebastien what to work on next.** Most likely: smoke-test against real APIs (drop tokens, `make run SUBJECT=me`), polish, or demo prep.

## Recent commits (most recent first)
```
167cf03 chore: add Makefile for common dev tasks
5702415 chore: switch dev workflow to uv
de86477 CONTEXT.md: mark LP reviewer-MP gap closed
c964ba1 fix(adapters): correct LP scrape regex and isolate scrape failures
d68247a feat(adapters): scrape +activereviews for LP reviewer-side MPs
95fc703 spec: clarify Jira adapter is assignee-only by design
33852d1 CONTEXT.md: mark v1 implementation complete; record known gaps
80959da fix(render): write report as UTF-8 explicitly
19d5e8b polish: example config, README quick-start, source status table
c04dd10 fix(render): enable autoescape for .j2 templates, robust source label lookup
9c8745c fix(render): correct vanilla-framework test assertion
f11420a feat(render): Jinja2 template + Vanilla Framework HTML output
87ac947 feat(cli): orchestrator with parallel fetch and failure isolation
b6bb23b feat(rules): per-source bucket assignment with thresholds
674d44d feat(adapters): Gmail scaffold raising NotImplementedError
e0883c9 feat(adapters): Google Docs adapter parsing For next week + Carried over
626dbc8 feat(adapters): Jira adapter using JQL assignee + window
67e6a58 feat(adapters): Launchpad adapter for bugs and merge proposals
322f7e4 feat(adapters): GitHub adapter with author + review-requested queries
4e5488d fix(config): tighten path types and UTF-8 read
019b702 feat(config): YAML loader with Settings/SubjectConfig dataclasses
5c4246f feat(item): add Item dataclass and Bucket enum
8673577 scaffold: package layout, pyproject.toml, smoke test
... (earlier commits: brainstorming/spec/plan)
```

## Author / operator distinction
- **Author of spec & commits:** Sebastien Bacher (designing the tool with Claude).
- **"the user" in spec body:** generic — anyone who runs the tool. Genericized so the tool can be shared with others.

## Process notes
- Brainstorming skill in use — design first, no code until spec is approved.
- CONTEXT.md is updated on explicit request.

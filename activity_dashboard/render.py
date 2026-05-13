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
    secs = max(0, int(delta.total_seconds()))
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
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.globals["relative_age"] = _relative_age

    grouped = _group_by_bucket(results)

    # Per-source feed: include sources we got results from (success or failure),
    # excluding gdocs (it's handled by the 1-1 panel).
    active_sources = [(name, SOURCE_LABELS.get(name, name))
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

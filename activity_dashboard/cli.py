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

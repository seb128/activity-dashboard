"""Render module — full implementation in Task 11."""

from pathlib import Path


def render_report(results, subject, settings, out_path) -> None:
    Path(out_path).write_text("<html><body>placeholder</body></html>")

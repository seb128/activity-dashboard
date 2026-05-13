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
                     "email_file": "/dev/null", "token_file": "/dev/null"},
            "google_credentials_file": "/dev/null", "google_token_file": "/dev/null",
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

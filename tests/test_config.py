from pathlib import Path
import pytest
import yaml
from activity_dashboard.config import load_config, SubjectConfig, Settings


def write_config(tmp_path: Path, contents: dict) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(contents))
    return p


def minimal_config() -> dict:
    return {
        "credentials": {
            "github_token_file": "~/gh.token",
            "jira": {
                "base_url": "https://example.atlassian.net",
                "email_file": "~/jira.email",
                "token_file": "~/jira.token",
            },
            "google_credentials_file": "~/google-creds.json",
            "google_token_file": "~/google-token.json",
        },
        "rules": {
            "window_days": 7,
            "needs_attention": {
                "pr_awaiting_review_days": 0,
                "jira_assigned_no_movement_days": 2,
                "stalled_pr_days": 5,
                "stalled_jira_days": 5,
                "stalled_launchpad_days": 5,
            },
        },
        "subjects": {
            "alice": {
                "display_name": "Alice Smith",
                "canonical_email": "alice@canonical.com",
                "launchpad_id": "alice-lp",
                "github_id": "alice-gh",
                "one_on_one_doc": "https://docs.google.com/document/d/AAA/edit",
            },
        },
    }


def test_load_config_returns_settings(tmp_path: Path):
    p = write_config(tmp_path, minimal_config())
    settings = load_config(p)
    assert isinstance(settings, Settings)
    assert settings.rules.window_days == 7
    assert settings.rules.needs_attention.stalled_pr_days == 5


def test_load_config_returns_subject_by_name(tmp_path: Path):
    p = write_config(tmp_path, minimal_config())
    settings = load_config(p)
    alice = settings.subject("alice")
    assert isinstance(alice, SubjectConfig)
    assert alice.display_name == "Alice Smith"
    assert alice.github_id == "alice-gh"
    assert alice.canonical_email == "alice@canonical.com"


def test_load_config_missing_subject_raises(tmp_path: Path):
    p = write_config(tmp_path, minimal_config())
    settings = load_config(p)
    with pytest.raises(KeyError):
        settings.subject("nope")


def test_load_config_optional_ubuntu_alias(tmp_path: Path):
    cfg = minimal_config()
    cfg["subjects"]["alice"]["ubuntu_alias"] = "alice@ubuntu.com"
    p = write_config(tmp_path, cfg)
    settings = load_config(p)
    assert settings.subject("alice").ubuntu_alias == "alice@ubuntu.com"


def test_load_config_resolves_home_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = write_config(tmp_path, minimal_config())
    settings = load_config(p)
    assert str(settings.credentials.github_token_file).startswith(str(tmp_path))
    assert str(settings.credentials.jira.email_file).startswith(str(tmp_path))
    assert str(settings.credentials.google_credentials_file).startswith(str(tmp_path))


def test_load_config_required_path_null_raises(tmp_path):
    cfg = minimal_config()
    cfg["credentials"]["jira"]["email_file"] = None
    p = write_config(tmp_path, cfg)
    with pytest.raises(ValueError):
        load_config(p)

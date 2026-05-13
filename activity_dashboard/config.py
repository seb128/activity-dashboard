"""YAML config loader and dataclasses."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


def _expand(p: str | None) -> Path | None:
    if p is None:
        return None
    return Path(p).expanduser()


def _require_expand(p: str) -> Path:
    if not p:
        raise ValueError("required path is missing or empty")
    return Path(p).expanduser()


@dataclass
class JiraCredentials:
    base_url: str
    email_file: Path
    token_file: Path
    pulse_jql: str | None = None     # JQL fragment scoping the "pulse"; None = feature off


@dataclass
class Credentials:
    github_token_file: Path | None
    jira: JiraCredentials
    google_credentials_file: Path
    google_token_file: Path


@dataclass
class NeedsAttentionThresholds:
    pr_awaiting_review_days: int = 0
    jira_assigned_no_movement_days: int = 2
    stalled_pr_days: int = 5
    stalled_jira_days: int = 5
    stalled_launchpad_days: int = 5
    pulse_stale_days: int = 7        # items in pulse with no movement > this → NEEDS_ATTENTION


@dataclass
class Rules:
    window_days: int = 7
    needs_attention: NeedsAttentionThresholds = field(default_factory=NeedsAttentionThresholds)


@dataclass
class SubjectConfig:
    name: str
    display_name: str
    canonical_email: str
    launchpad_id: str
    github_id: str
    one_on_one_doc: str
    ubuntu_alias: str | None = None


@dataclass
class Settings:
    credentials: Credentials
    rules: Rules
    subjects: dict[str, SubjectConfig]

    def subject(self, name: str) -> SubjectConfig:
        if name not in self.subjects:
            raise KeyError(f"subject '{name}' not in config")
        return self.subjects[name]


def load_config(path: Path) -> Settings:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))

    c = raw["credentials"]
    creds = Credentials(
        github_token_file=_expand(c.get("github_token_file")),
        jira=JiraCredentials(
            base_url=c["jira"]["base_url"],
            email_file=_require_expand(c["jira"]["email_file"]),
            token_file=_require_expand(c["jira"]["token_file"]),
            pulse_jql=c["jira"].get("pulse_jql"),
        ),
        google_credentials_file=_require_expand(c["google_credentials_file"]),
        google_token_file=_require_expand(c["google_token_file"]),
    )

    r = raw.get("rules", {})
    na = r.get("needs_attention", {})
    rules = Rules(
        window_days=r.get("window_days", 7),
        needs_attention=NeedsAttentionThresholds(
            pr_awaiting_review_days=na.get("pr_awaiting_review_days", 0),
            jira_assigned_no_movement_days=na.get("jira_assigned_no_movement_days", 2),
            stalled_pr_days=na.get("stalled_pr_days", 5),
            stalled_jira_days=na.get("stalled_jira_days", 5),
            stalled_launchpad_days=na.get("stalled_launchpad_days", 5),
            pulse_stale_days=na.get("pulse_stale_days", 7),
        ),
    )

    subjects: dict[str, SubjectConfig] = {}
    for name, s in raw["subjects"].items():
        subjects[name] = SubjectConfig(
            name=name,
            display_name=s["display_name"],
            canonical_email=s["canonical_email"],
            launchpad_id=s["launchpad_id"],
            github_id=s["github_id"],
            one_on_one_doc=s["one_on_one_doc"],
            ubuntu_alias=s.get("ubuntu_alias"),
        )

    return Settings(credentials=creds, rules=rules, subjects=subjects)

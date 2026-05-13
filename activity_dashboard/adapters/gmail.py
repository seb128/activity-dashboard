"""Gmail adapter — scaffolded for v1. The orchestrator catches NotImplementedError
and hides this adapter from the UI."""

NAME = "gmail"


def fetch(subject, settings, *, _client=None):
    raise NotImplementedError(
        "Gmail adapter is not implemented in v1. Planned approach: a Workspace "
        "automation generates a daily summary Google Doc that the gdocs adapter parses."
    )

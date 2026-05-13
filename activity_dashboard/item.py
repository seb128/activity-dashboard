"""Common item schema returned by all adapters."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Bucket(Enum):
    DONE = "done"
    ACTIVE = "active"
    NEEDS_ATTENTION = "needs_attention"
    NONE = "none"


@dataclass
class Item:
    source: str
    kind: str
    title: str
    url: str
    subject_role: str
    status: str
    last_activity_at: datetime
    bucket: Bucket | None = None
    raw: dict = field(default_factory=dict)

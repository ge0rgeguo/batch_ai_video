from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RemoteTaskStatus(str, Enum):
    pending = "pending"
    queued = "queued"
    in_progress = "in-progress"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


@dataclass
class CreateResult:
    task_id: str


@dataclass
class QueryResult:
    status: RemoteTaskStatus
    video_url: Optional[str] = None
    error: Optional[str] = None



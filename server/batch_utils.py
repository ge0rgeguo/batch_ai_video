from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Batch, Task, TaskStatus


def recompute_batch_counters(db: Session, batch_id: str) -> None:
    counts = (
        db.query(Task.status, func.count(Task.id))
        .filter(Task.batch_id == batch_id, Task.deleted_at.is_(None))
        .group_by(Task.status)
        .all()
    )
    status_to_count = {status: cnt for status, cnt in counts}

    def c(status: TaskStatus) -> int:
        return int(status_to_count.get(status, 0))

    batch = db.get(Batch, batch_id)
    if not batch:
        return
    batch.completed = c(TaskStatus.completed)
    batch.failed = c(TaskStatus.failed)
    batch.running = c(TaskStatus.running)
    batch.queued = c(TaskStatus.queued) + c(TaskStatus.pending)
    batch.total = batch.completed + batch.failed + batch.running + batch.queued
    db.add(batch)
    db.commit()

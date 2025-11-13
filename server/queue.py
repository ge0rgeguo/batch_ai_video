from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Task, TaskStatus, CreditTransaction
from .providers.yunwu import call_yunwu_generate
from .settings import settings
from .batch_utils import recompute_batch_counters
from .pricing import get_unit_cost


class AsyncTaskExecutor:
    def __init__(self) -> None:
        self._queue: Deque[str] = deque()
        self._global_running: int = 0
        self._user_running: Dict[int, int] = defaultdict(int)
        self._loop_task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._loop_task is None:
            self._loop_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._loop_task:
            self._stop.set()
            await self._loop_task
            self._loop_task = None

    def enqueue_task(self, task_id: str) -> None:
        self._queue.append(task_id)

    async def _worker_loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(0.1)
            if not self._queue:
                continue

            task_id = self._queue[0]
            with SessionLocal() as db:
                task: Optional[Task] = db.get(Task, task_id)
                if task is None:
                    self._queue.popleft()
                    continue
                user_id = task.user_id

                # 并发与配额检查（不从队列移除）
                if self._global_running >= settings.GLOBAL_CONCURRENCY:
                    continue
                if self._user_running[user_id] >= settings.PER_USER_CONCURRENCY:
                    continue

                # 原子"领取"任务：仅当当前仍为 pending/queued 才置为 running
                affected = (
                    db.query(Task)
                    .filter(Task.id == task_id, Task.status.in_([TaskStatus.pending, TaskStatus.queued]))
                    .update({Task.status: TaskStatus.running})
                )
                db.commit()

                if affected == 0:
                    # 已被其他执行器领取，弹出并跳过
                    self._queue.popleft()
                    continue

                # 领取成功后再弹出队列并启动执行
                self._queue.popleft()
                asyncio.create_task(self._execute_task(task_id, user_id))

    async def _execute_task(self, task_id: str, user_id: int) -> None:
        self._global_running += 1
        self._user_running[user_id] += 1
        try:
            # 仅执行一次；远端创建+轮询在 provider 内部完成，避免重复创建
            try:
                await self._execute_once(task_id)
            except Exception as exc:
                # 标记失败并退款
                with SessionLocal() as db:
                    task = db.get(Task, task_id)
                    if task:
                        task.status = TaskStatus.failed
                        task.error_summary = str(exc)[:500]
                        db.add(task)
                        # 失败退款（避免重复退款）
                        unit_cost = get_unit_cost(task.model, int(task.duration))
                        exists = (
                            db.query(CreditTransaction)
                            .filter(
                                CreditTransaction.user_id == task.user_id,
                                CreditTransaction.ref_task_id == task.id,
                                CreditTransaction.delta > 0,
                            )
                            .first()
                        )
                        if not exists:
                            db.add(
                                CreditTransaction(
                                    user_id=task.user_id,
                                    delta=unit_cost,
                                    reason=f"refund_task:{task.id}",
                                    ref_task_id=task.id,
                                    ref_batch_id=task.batch_id,
                                )
                            )
                        db.commit()
                        recompute_batch_counters(db, task.batch_id)
        finally:
            self._global_running -= 1
            self._user_running[user_id] -= 1

    async def _run_with_retries(self, task_id: str) -> None:
        backoffs = [2, 5]
        attempt = 0
        while True:
            try:
                await self._execute_once(task_id)
                return
            except Exception as exc:
                attempt += 1
                if attempt > len(backoffs):
                    with SessionLocal() as db:
                        task = db.get(Task, task_id)
                        if task:
                            task.status = TaskStatus.failed
                            task.error_summary = str(exc)[:500]
                            db.add(task)
                            # 失败退款（避免重复退款）
                            unit_cost = get_unit_cost(task.model, int(task.duration))
                            exists = (
                                db.query(CreditTransaction)
                                .filter(
                                    CreditTransaction.user_id == task.user_id,
                                    CreditTransaction.ref_task_id == task.id,
                                    CreditTransaction.delta > 0,
                                )
                                .first()
                            )
                            if not exists:
                                db.add(
                                    CreditTransaction(
                                        user_id=task.user_id,
                                        delta=unit_cost,
                                        reason=f"refund_task:{task.id}",
                                        ref_task_id=task.id,
                                        ref_batch_id=task.batch_id,
                                    )
                                )
                            db.commit()
                            recompute_batch_counters(db, task.batch_id)
                    return
                await asyncio.sleep(backoffs[attempt - 1])

    async def _execute_once(self, task_id: str) -> None:
        def sync_call() -> str:
            with SessionLocal() as db:
                task = db.get(Task, task_id)
                if task is None:
                    raise RuntimeError("Task not found")
                if task.status == TaskStatus.cancelled:
                    return ""
                out_path = call_yunwu_generate(
                    prompt=task.prompt,
                    image_path=task.image_path,
                    model=task.model,
                    orientation=task.orientation,
                    size=task.size,
                    duration=task.duration,
                    user_id=task.user_id,
                    task_id=task.id,
                )
                task.result_path = out_path
                task.status = TaskStatus.completed
                db.add(task)
                db.commit()
                recompute_batch_counters(db, task.batch_id)
                return out_path

        await asyncio.to_thread(sync_call)


executor = AsyncTaskExecutor()

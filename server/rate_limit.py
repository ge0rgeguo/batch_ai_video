from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from .settings import settings


class PerUserRateLimiter:
    def __init__(self) -> None:
        self._events: Dict[int, Deque[float]] = defaultdict(deque)

    def allow_new_batch(self, user_id: int) -> bool:
        now = time.time()
        window = 60.0
        dq = self._events[user_id]
        while dq and now - dq[0] > window:
            dq.popleft()
        if len(dq) >= settings.MAX_BATCHES_PER_USER_PER_MINUTE:
            return False
        dq.append(now)
        return True


rate_limiter = PerUserRateLimiter()

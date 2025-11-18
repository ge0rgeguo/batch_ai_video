from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, status

from .settings import settings


class _BurstLimiter:
    def __init__(self) -> None:
        self.storage: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int, min_interval_seconds: int) -> None:
        now = time.time()
        bucket = self.storage[key]

        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()

        if bucket and now - bucket[-1] < min_interval_seconds:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="验证码请求过于频繁，请稍后再试")

        if len(bucket) >= limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="验证码请求次数过多，请稍后再试")

        bucket.append(now)


limiter = _BurstLimiter()


def ensure_sms_rate_limit(mobile: str, client_ip: str) -> None:
    mobile_key = f"mobile:{mobile}"
    ip_key = f"ip:{client_ip}"
    limiter.check(
        mobile_key,
        limit=settings.SMS_CODE_MAX_PER_MOBILE_PER_DAY,
        window_seconds=86400,
        min_interval_seconds=settings.SMS_CODE_RESEND_INTERVAL,
    )
    limiter.check(
        ip_key,
        limit=settings.SMS_CODE_MAX_PER_MOBILE_PER_DAY * 5,
        window_seconds=86400,
        min_interval_seconds=5,
    )





from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from .settings import settings


async def cleanup_loop() -> None:
    ttl_seconds = settings.LOCAL_FILE_TTL_DAYS * 24 * 3600
    upload_dir = Path(settings.UPLOAD_DIR)
    results_dir = Path(settings.RESULTS_BASE_DIR)
    while True:
        now = time.time()
        for base in (upload_dir, results_dir):
            try:
                base.mkdir(parents=True, exist_ok=True)
                for root, _, files in os.walk(base):
                    for name in files:
                        fpath = Path(root) / name
                        try:
                            if now - fpath.stat().st_mtime > ttl_seconds:
                                fpath.unlink(missing_ok=True)
                        except Exception:
                            pass
            except Exception:
                pass
        await asyncio.sleep(3600)

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import List, Optional

import requests

from ..settings import settings
from .yunwu_client import create_sora2, query_task
from .types import RemoteTaskStatus
from ..db import SessionLocal
from ..models import UserApiKey
from ..crypto import decrypt_text


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _public_url_for_local_path(filename: str) -> Optional[str]:
    """Map a relative filename to a public URL using PUBLIC_BASE_URL.

    Args:
        filename: Relative filename like "1_1234567890.123.png"
    
    Returns:
        Public URL like "https://xxx.ngrok.app/uploads/1_1234567890.123.png"
        or None if PUBLIC_BASE_URL is not set.
    """
    if not settings.PUBLIC_BASE_URL:
        return None
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/uploads/{filename}"


def _download_to_results(url: str) -> str:
    _ensure_dir(settings.RESULTS_BASE_DIR)
    out_path = str(Path(settings.RESULTS_BASE_DIR) / f"{uuid.uuid4()}.mp4")
    with requests.get(url, stream=True, timeout=settings.REQUEST_TIMEOUT_SECONDS) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=settings.DOWNLOAD_CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
    return out_path


def call_yunwu_generate(
    prompt: str,
    image_path: Optional[str],
    model: str,
    orientation: str,
    size: str,
    duration: int,
    user_id: int,
) -> str:
    """Create remote task on Yunwu and poll until completion, then download the video.

    Docs: [创建视频 sora-2](https://yunwu.apifox.cn/api-358068907), [查询任务](https://yunwu.apifox.cn/api-358068905)
    """
    print(f"[yunwu] call_yunwu_generate: user_id={user_id} model={model} has_image={bool(image_path)}")
    
    # 优先使用用户级API Key；如无则回退至全局环境变量
    api_key: Optional[str] = None
    with SessionLocal() as db:
        rec = (
            db.query(UserApiKey)
            .filter(UserApiKey.user_id == user_id, UserApiKey.provider == "yunwu")
            .first()
        )
        if rec:
            try:
                api_key = decrypt_text(rec.encrypted_key)
                print(f"[yunwu] using user-level API key for user_id={user_id}")
            except Exception:
                api_key = None
    if not api_key:
        api_key = settings.YUNWU_API_KEY
        if api_key:
            print("[yunwu] using global YUNWU_API_KEY from environment")
    if not api_key:
        print("[yunwu] ❌ no API key found (neither user-level nor environment)")
        raise RuntimeError("缺少云雾API密钥：请在个人设置中配置，或设置环境变量 YUNWU_API_KEY")

    images: Optional[List[str]] = None
    if image_path:
        print(f"[yunwu] image_path provided: {image_path}")
        public_url = _public_url_for_local_path(image_path)
        print(f"[yunwu] mapped public_url: {public_url}")
        if public_url:
            images = [public_url]
        else:
            print(f"[yunwu] ⚠️  PUBLIC_BASE_URL not set or path mapping failed, sending without images")
    else:
        print(f"[yunwu] no image_path provided")

    # 触发创建
    print(f"[yunwu] creating sora2 task: api_base={settings.YUNWU_API_BASE} has_images={bool(images)} size={size} orientation={orientation} duration={duration}")
    # 传入幂等键，确保即便上层误触发也不会创建重复远端任务
    idempotency_key = f"batch-{int(time.time()*1000)}-{uuid.uuid4().hex[:8]}"
    created = create_sora2(
        api_key=api_key,
        prompt=prompt,
        orientation=orientation,
        size=size,
        duration=duration,
        images=images,
        idempotency_key=idempotency_key,
    )
    print(f"[yunwu] ✅ created remote task_id={created.task_id}, starting poll...")

    # 轮询状态
    deadline = time.time() + settings.MAX_POLL_SECONDS
    last_status = None
    while time.time() < deadline:
        try:
            q = query_task(api_key=api_key, task_id=created.task_id)
            print(f"[yunwu] poll: status={q.status.value} video_url={q.video_url or 'None'} error={q.error or 'None'}")
            last_status = q.status
            if q.status == RemoteTaskStatus.completed and q.video_url:
                # 按需返回远端可访问URL（由前端直接打开），避免本地下载再提供链接
                return q.video_url
            if q.status in {RemoteTaskStatus.failed, RemoteTaskStatus.cancelled}:
                raise RuntimeError(q.error or f"远端任务{q.status.value}")
        except Exception as e:
            # 捕获瞬时网络/解析错误，避免抛给上层导致重复创建远端任务
            print(f"[yunwu] poll error: {type(e).__name__}: {e}")
        time.sleep(settings.POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"远端任务超时，最后状态: {last_status}")

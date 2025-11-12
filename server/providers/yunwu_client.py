from __future__ import annotations

from typing import Dict, List, Optional
import json

import requests

from ..settings import settings
from .types import CreateResult, QueryResult, RemoteTaskStatus


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return token
    return token[:6] + "..." + token[-2:]


def _headers(api_key: str) -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _resolve_api_base() -> str:
    return settings.YUNWU_API_BASE.rstrip("/")


def create_sora2(
    *,
    api_key: str,
    model: str,
    prompt: str,
    orientation: str,
    size: str,
    duration: int,
    images: Optional[List[str]] = None,
    idempotency_key: Optional[str] = None,
) -> CreateResult:
    """Create a Sora2 video generation task on Yunwu.

    API doc reference: [云雾API 创建视频 sora-2](https://yunwu.apifox.cn/api-358068907)
    """
    api_base = _resolve_api_base()

    # Yunwu示例使用 size=large，当前项目有 small/medium 两档，映射为：
    yunwu_size = "small" if size == "small" else "large"

    payload = {
        "model": model,
        "prompt": prompt,
        "orientation": orientation,
        "size": yunwu_size,
        "duration": duration,
        # 强制关闭水印
        "watermark": False,
    }
    # sora-2-pro 需要 private 字段（根据云雾API文档）
    if model == "sora-2-pro":
        payload["private"] = False
    
    if images:
        payload["images"] = images

    # Debug log: outbound request summary
    print(
        "[yunwu_client] POST",
        f"{api_base}/video/create",
        f"model={payload['model']} orientation={orientation} size={yunwu_size} duration={duration}",
        f"images={'True' if images else 'False'} images_count={len(images) if images else 0}",
    )
    print(
        "[yunwu_client] headers.Authorization=Bearer",
        _mask_token(api_key),
    )
    print(
        "[yunwu_client] prompt_len=",
        len(prompt),
        "prompt_preview=",
        (prompt[:200] + ("..." if len(prompt) > 200 else "")),
    )
    try:
        print("[yunwu_client] payload_json=", json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass

    headers = _headers(api_key)
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    resp = requests.post(
        f"{api_base}/video/create",
        headers=headers,
        json=payload,
        timeout=settings.REQUEST_TIMEOUT_SECONDS,
    )
    print("[yunwu_client] response_status=", resp.status_code)
    resp.raise_for_status()
    data = resp.json()
    print("[yunwu_client] response_json_keys=", list(data.keys()))

    task_id = data.get("id") or data.get("task_id")
    if not task_id:
        raise RuntimeError("Yunwu API 未返回任务ID")

    return CreateResult(task_id=task_id)


def query_task(*, api_key: str, task_id: str) -> QueryResult:
    """Query task status; returns status and optional video URL when completed.

    API doc reference: [云雾API 查询任务](https://yunwu.apifox.cn/api-358068905)
    """
    api_base = _resolve_api_base()
    # 根据对方接口：GET /v1/video/query?id={task_id}
    query_url = f"{api_base}/video/query?id={task_id}"
    print("[yunwu_client] GET", query_url, "Authorization=Bearer", _mask_token(api_key))
    resp = requests.get(
        query_url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        timeout=settings.REQUEST_TIMEOUT_SECONDS,
    )
    print("[yunwu_client] query_response_status=", resp.status_code)
    resp.raise_for_status()
    data = resp.json()
    print("[yunwu_client] query_response_json_keys=", list(data.keys()))

    # 云雾状态字段：优先使用 data.status（completed），回退到外层 status（SUCCESS）
    # 外层 status 可能是 SUCCESS/FAILED，内层 data.status 是 completed/failed
    status_raw = ""
    if "data" in data and isinstance(data.get("data"), dict):
        status_raw = (data["data"].get("status") or "").lower()
    if not status_raw:
        status_raw = (data.get("status") or "").lower()
    
    # 状态映射：SUCCESS -> completed, FAILED -> failed
    status_mapping = {
        "success": "completed",
        "failed": "failed",
        "error": "failed",
        "completed": "completed",
        "in-progress": "in-progress",
        "in_progress": "in-progress",
        "processing": "in-progress",
        "pending": "pending",
        "queued": "queued",
    }
    status = status_mapping.get(status_raw.replace(" ", "-"), RemoteTaskStatus.in_progress.value)
    print(f"[yunwu_client] status_raw={status_raw}, mapped_status={status}")

    # video_url 也可能在 data 对象中
    video_url = None
    if "data" in data and isinstance(data.get("data"), dict):
        video_url = data["data"].get("video_url")
    if not video_url:
        video_url = data.get("video_url") or data.get("result_url")

    return QueryResult(
        status=RemoteTaskStatus(status),
        video_url=video_url,
        error=data.get("error") or data.get("message") or data.get("fail_reason"),
    )



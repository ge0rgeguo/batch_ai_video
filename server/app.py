from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO
import time
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from sqlalchemy.orm import Session
 

from .batch_utils import recompute_batch_counters
from .cleanup import cleanup_loop
from .db import get_db, init_db
from .models import Batch, IdempotencyKey, Task, TaskStatus, User, CreditTransaction
from .queue import executor
from .rate_limit import rate_limiter
from .schemas import (
    ApiResponse,
    BatchCreateRequest,
    BatchRead,
    CreditAdjustRequest,
    LoginRequest,
    MeResponse,
    TaskRead,
    fail,
    ok,
)
from .security import (
    clear_session_cookie,
    create_session,
    get_current_user,
    hash_password,
    set_session_cookie,
    verify_password,
)
from .settings import settings
from .crypto import encrypt_text
from .models import UserApiKey

app = FastAPI(title="Video Generation Batch API")


def _ensure_dirs() -> None:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.RESULTS_BASE_DIR, exist_ok=True)
    os.makedirs(settings.PUBLIC_DIR, exist_ok=True)


@app.on_event("startup")
async def on_startup() -> None:
    _ensure_dirs()
    init_db()
    _ensure_initial_admin()
    if not settings.DISABLE_BACKGROUND:
        print("[startup] Background executor starting...")
        executor.start()
        import asyncio
        asyncio.create_task(cleanup_loop())
        print("[startup] Cleanup loop started. Public dir:", settings.PUBLIC_DIR)
        # 进程内队列在重启后会丢失，这里自动将 DB 中未启动的任务重新入队
        try:
            from .db import SessionLocal
            from .models import Task, TaskStatus
            with SessionLocal() as db:
                rows = (
                    db.query(Task.id)
                    .filter(Task.status.in_([TaskStatus.pending, TaskStatus.queued]), Task.deleted_at.is_(None))
                    .all()
                )
                count = 0
                for (task_id,) in rows:
                    executor.enqueue_task(task_id)
                    count += 1
                if count:
                    print(f"[startup] Re-enqueued {count} pending/queued tasks")
        except Exception as e:
            print("[startup] Re-enqueue failed:", e)
    else:
        print("[startup] DISABLE_BACKGROUND=true，后台任务未启动（仅用于测试环境）")


def _ensure_initial_admin() -> None:
    from .db import SessionLocal
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            default_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "admin000")
            print("⚠️  创建默认管理员: username=admin")
            print("🔒 生产环境请设置 INITIAL_ADMIN_PASSWORD 环境变量或立即修改密码")
            admin_user = User(
                username="admin",
                password_hash=hash_password(default_password),
                is_admin=True,
            )
            db.add(admin_user)
            db.commit()
    finally:
        db.close()


@app.post("/api/login")
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user = db.query(User).filter(User.username == req.username).first()
    if user is None or not verify_password(req.password, user.password_hash):
        return fail("用户名或密码错误")
    if not user.enabled:
        return fail("账号已禁用")
    session = create_session(db, user)
    set_session_cookie(response, session.id)
    return ok({"user_id": user.id, "username": user.username, "is_admin": user.is_admin})


@app.post("/api/logout")
def logout(response: Response, user: User = Depends(get_current_user)) -> ApiResponse[None]:
    clear_session_cookie(response)
    return ok(None)


def _get_user_credits(db: Session, user_id: int) -> int:
    total = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()
    return sum(t.delta for t in total)


@app.get("/api/me")
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApiResponse[MeResponse]:
    credits = _get_user_credits(db, user.id)
    return ok(MeResponse(user_id=user.id, username=user.username, is_admin=user.is_admin, credits=credits))


@app.post("/api/images/upload")
def upload_image(file: UploadFile = File(...), user: User = Depends(get_current_user)) -> ApiResponse[dict]:
    if file.content_type not in settings.ALLOWED_IMAGE_MIME:
        return fail("仅支持 PNG/JPEG 格式")
    data = file.file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > settings.IMAGE_MAX_SIZE_MB:
        return fail(f"图片超过 {settings.IMAGE_MAX_SIZE_MB}MB")
    try:
        img = Image.open(BytesIO(data))
        w, h = img.size
        if w > settings.IMAGE_MAX_EDGE_PX or h > settings.IMAGE_MAX_EDGE_PX:
            return fail(f"图片尺寸超过 {settings.IMAGE_MAX_EDGE_PX}px")
    except Exception:
        return fail("无效图片")
    fname = f"{user.id}_{datetime.utcnow().timestamp()}.png"
    path = Path(settings.UPLOAD_DIR) / fname
    with open(path, "wb") as f:
        f.write(data)
    # 返回相对路径，便于后续映射为公网URL
    return ok({"path": fname})


@app.delete("/api/images")
def delete_image(image_path: str, user: User = Depends(get_current_user)) -> ApiResponse[None]:
    try:
        # image_path 现在是相对文件名，需要拼接完整路径
        p = Path(settings.UPLOAD_DIR) / image_path
        if p.exists() and p.parent == Path(settings.UPLOAD_DIR):
            p.unlink()
            return ok(None)
    except Exception:
        pass
    return fail("删除失败")


@app.post("/api/admin/api-key")
def admin_set_api_key(provider: str, api_key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApiResponse[None]:
    # 仅管理员可配置平台级密钥，不暴露在前端
    if not user.is_admin:
        return fail("无权限")
    if provider != "yunwu":
        return fail("不支持的provider")
    # 存为admin用户的密钥，作为全局回退
    enc = encrypt_text(api_key)
    row = db.query(UserApiKey).filter(UserApiKey.user_id == user.id, UserApiKey.provider == provider, UserApiKey.environment == "prod").first()
    if row:
        row.encrypted_key = enc
        db.add(row)
    else:
        db.add(UserApiKey(user_id=user.id, provider=provider, environment="prod", encrypted_key=enc))
    db.commit()
    return ok(None)


@app.post("/api/admin/credits/adjust")
def admin_adjust_credits(req: CreditAdjustRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApiResponse[None]:
    if not user.is_admin:
        return fail("无权限")
    if req.delta == 0:
        return fail("delta 不能为 0")
    tx = CreditTransaction(user_id=req.user_id, delta=req.delta, reason=req.reason)
    db.add(tx)
    db.commit()
    return ok(None)


@app.post("/api/batches")
def create_batch(
    req: BatchCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # prompt validations
    prompt = (req.prompt or "").strip()
    print(f"[create_batch] user_id={user.id} num_videos={req.num_videos} prompt_len={len(prompt)} image_path={req.image_path or 'None'}")
    if not prompt:
        return fail("prompt 为必填")
    if len(prompt) > 3000:
        return fail("prompt 超过 3000 字符")

    if not rate_limiter.allow_new_batch(user.id):
        return fail("批次创建速率限制，请稍后再试")

    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        existing = db.query(IdempotencyKey).filter(IdempotencyKey.key == idem_key).first()
        if existing:
            cutoff = datetime.utcnow().timestamp() - settings.IDEMPOTENCY_WINDOW_SECONDS
            if existing.created_at.timestamp() > cutoff:
                if existing.batch_id:
                    batch = db.get(Batch, existing.batch_id)
                    if batch:
                        return ok({"batch_id": batch.id})
                return fail("重复提交")

    # 校验模型与时长组合
    allowed = {
        "sora-2": {5, 10, 15},
        "sora-2-pro": {15, 25},
    }
    if req.model not in allowed or req.duration not in allowed[req.model]:
        return fail("该模型不支持所选时长")

    # 积分：定价
    # 已知：10秒=15分，5秒=8分；新增 15 秒暂按 23 分（向上取整比例）
    if req.duration == 5:
        unit_cost = 8
    elif req.duration == 10:
        unit_cost = 15
    elif req.duration == 15:
        unit_cost = 23
    elif req.duration == 25:
        unit_cost = 38
    else:
        unit_cost = 15
    total_cost = unit_cost * req.num_videos
    user_credits = _get_user_credits(db, user.id)
    if user_credits < total_cost:
        return fail(f"积分不足，需要 {total_cost} 分，当前 {user_credits} 分，请充值", code="INSUFFICIENT_CREDITS")

    batch = Batch(
        user_id=user.id,
        prompt=prompt,
        model=req.model,
        orientation=req.orientation,
        size=req.size,
        duration=req.duration,
        num_videos=req.num_videos,
        image_path=req.image_path,
        total=req.num_videos,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    if idem_key:
        idem = IdempotencyKey(key=idem_key, user_id=user.id, batch_id=batch.id)
        db.add(idem)
        db.commit()

    # 扣减积分（按批次一次性扣）
    db.add(CreditTransaction(user_id=user.id, delta=-total_cost, reason=f"deduct_for_batch:{batch.id}", ref_batch_id=batch.id))
    db.commit()

    print(f"[create_batch] creating {req.num_videos} tasks for batch_id={batch.id}")
    for i in range(req.num_videos):
        task = Task(
            batch_id=batch.id,
            user_id=user.id,
            prompt=prompt,
            model=req.model,
            orientation=req.orientation,
            size=req.size,
            duration=req.duration,
            image_path=req.image_path,
            status=TaskStatus.queued,
        )
        db.add(task)
        db.flush()
        print(f"[create_batch] task {i+1}/{req.num_videos} created: task_id={task.id}")
        executor.enqueue_task(task.id)
    db.commit()
    recompute_batch_counters(db, batch.id)

    return ok({"batch_id": batch.id})


@app.get("/api/batches")
def list_batches(page: int = 1, page_size: int = 10, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApiResponse[dict]:
    q = db.query(Batch).filter(Batch.user_id == user.id, Batch.deleted_at.is_(None)).order_by(Batch.created_at.desc())
    total = q.count()
    page = max(1, page)
    page_size = max(1, min(50, page_size))
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return ok({
        "items": [BatchRead(**b.__dict__) for b in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
    })


@app.get("/api/batches/{batch_id}/tasks")
def list_tasks(batch_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApiResponse[List[TaskRead]]:
    batch = db.get(Batch, batch_id)
    if not batch or batch.user_id != user.id:
        return fail("批次不存在")
    tasks = db.query(Task).filter(Task.batch_id == batch_id, Task.deleted_at.is_(None)).order_by(Task.created_at).all()
    # 历史清理：运行中但不会再进行的任务 → 置为失败；有结果但未完成 → 置为完成
    changed = False
    now = datetime.utcnow()
    for t in tasks:
        if t.result_path and t.status != TaskStatus.completed:
            t.status = TaskStatus.completed
            db.add(t)
            changed = True
        # 简化标准：运行态超过30分钟视为失败（不引入settings）
        if t.status == TaskStatus.running and (now - t.updated_at).total_seconds() > 1800:
            t.status = TaskStatus.failed
            t.error_summary = t.error_summary or "运行超时"
            db.add(t)
            changed = True
            # 超时失败退款（避免重复退款）
            if int(t.duration) == 5:
                unit_cost = 8
            elif int(t.duration) == 10:
                unit_cost = 15
            elif int(t.duration) == 15:
                unit_cost = 23
            elif int(t.duration) == 25:
                unit_cost = 38
            else:
                unit_cost = 15
            exists = (
                db.query(CreditTransaction)
                .filter(
                    CreditTransaction.user_id == t.user_id,
                    CreditTransaction.ref_task_id == t.id,
                    CreditTransaction.delta > 0,
                )
                .first()
            )
            if not exists:
                db.add(
                    CreditTransaction(
                        user_id=t.user_id,
                        delta=unit_cost,
                        reason=f"refund_task:{t.id}",
                        ref_task_id=t.id,
                        ref_batch_id=t.batch_id,
                    )
                )
    if changed:
        db.commit()
        recompute_batch_counters(db, batch_id)
        tasks = db.query(Task).filter(Task.batch_id == batch_id, Task.deleted_at.is_(None)).order_by(Task.created_at).all()
    return ok([TaskRead(**t.__dict__) for t in tasks])


@app.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApiResponse[None]:
    task = db.get(Task, task_id)
    if not task or task.user_id != user.id:
        return fail("任务不存在")
    if task.status == TaskStatus.failed:
        task.status = TaskStatus.queued
        task.error_summary = None
        db.add(task)
        db.commit()
        recompute_batch_counters(db, task.batch_id)
        executor.enqueue_task(task.id)
        return ok(None)
    return fail("仅失败任务可重试")


@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApiResponse[None]:
    task = db.get(Task, task_id)
    if not task or task.user_id != user.id:
        return fail("任务不存在")
    if task.status in {TaskStatus.pending, TaskStatus.queued, TaskStatus.running}:
        task.status = TaskStatus.cancelled
        db.add(task)
        db.commit()
        recompute_batch_counters(db, task.batch_id)
        return ok(None)
    return fail("任务无法取消")


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApiResponse[None]:
    task = db.get(Task, task_id)
    if not task or task.user_id != user.id:
        return fail("任务不存在")
    task.deleted_at = datetime.utcnow()
    db.add(task)
    db.commit()
    recompute_batch_counters(db, task.batch_id)
    return ok(None)


@app.delete("/api/batches/{batch_id}")
def delete_batch(batch_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApiResponse[None]:
    batch = db.get(Batch, batch_id)
    if not batch or batch.user_id != user.id:
        return fail("批次不存在")
    batch.deleted_at = datetime.utcnow()
    for task in batch.tasks:
        task.deleted_at = datetime.utcnow()
    db.add(batch)
    db.commit()
    return ok(None)


@app.get("/api/batches/{batch_id}/download")
def download_zip(batch_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batch = db.get(Batch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(status_code=404, detail="批次不存在")
    
    tasks = db.query(Task).filter(
        Task.batch_id == batch_id,
        Task.status == TaskStatus.completed,
        Task.result_path.isnot(None),
        Task.deleted_at.is_(None),
    ).all()

    # 生成临时ZIP文件（由清理循环按TTL清除）
    out_dir = Path(settings.RESULTS_BASE_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"batch_{batch_id}_{int(time.time())}.zip"
    temp_downloads = []  # 追踪临时下载的文件，打包后删除

    manifest_lines = []
    try:
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i, task in enumerate(tasks, start=1):
                if not task.result_path:
                    continue
                
                # 判断是远程 URL 还是本地路径
                if task.result_path.startswith("http://") or task.result_path.startswith("https://"):
                    # 远程 URL：下载到临时文件
                    try:
                        import requests
                        print(f"[download_zip] 下载远程视频: {task.result_path}")
                        resp = requests.get(task.result_path, timeout=60)
                        resp.raise_for_status()
                        
                        # 保存到临时文件
                        temp_file = out_dir / f"temp_{uuid.uuid4().hex}.mp4"
                        temp_file.write_bytes(resp.content)
                        temp_downloads.append(temp_file)
                        
                        fname = f"{i:03d}_task_{task.id[:8]}.mp4"
                        zf.write(str(temp_file), arcname=fname)
                        manifest_lines.append(f"{fname}: {task.prompt[:100]}")
                        print(f"[download_zip] ✅ 已添加到 ZIP: {fname}")
                    except Exception as e:
                        print(f"[download_zip] ⚠️  下载失败 {task.id}: {e}")
                        continue
                else:
                    # 本地路径：直接添加
                    if os.path.exists(task.result_path):
                        fname = f"{i:03d}_{Path(task.result_path).name}"
                        zf.write(task.result_path, arcname=fname)
                        manifest_lines.append(f"{fname}: {task.prompt[:100]}")
                        print(f"[download_zip] ✅ 已添加本地文件到 ZIP: {fname}")
            
            if manifest_lines:
                zf.writestr("manifest.txt", "\n".join(manifest_lines))
    finally:
        # 清理临时下载的文件
        for temp_file in temp_downloads:
            try:
                temp_file.unlink()
            except Exception:
                pass

    return FileResponse(
        str(zip_path),
        media_type="application/zip",
        filename=f"batch_{batch_id}.zip",
    )


app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=settings.PUBLIC_DIR, html=True), name="static")

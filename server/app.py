from __future__ import annotations

import os
import hashlib
import re
import secrets
from datetime import datetime, timedelta
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
from .models import Batch, IdempotencyKey, Task, TaskStatus, User, CreditTransaction, SmsVerifySession
from .queue import executor
from .rate_limit import rate_limiter
from .pricing import get_unit_cost
from .schemas import (
    ApiResponse,
    BatchCreateRequest,
    BatchRead,
    CreditAdjustRequest,
    LoginRequest,
    MeResponse,
    TaskRead,
    SmsSendRequest,
    SmsVerifyRequest,
    RechargeCreateRequest,
    RechargeResponse,
    PaymentStatusResponse,
    CreditTransactionRead,
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
from .models import UserApiKey, RechargeOrder
from .providers.aliyun_sms import client as sms_client, AliyunSmsError
from .sms_rate_limit import ensure_sms_rate_limit
from .providers.payment import payment_service
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth

app = FastAPI(title="Video Generation Batch API", docs_url=None, redoc_url=None)


@app.get("/api/health")
def health_check():
    """健康检查端点，用于 Docker 和负载均衡器"""
    return {"status": "ok"}

# Session middleware for OAuth state (使用随机密钥，生产环境中应该固定)
# TODO: 在生产环境中设置固定的 SESSION_SECRET 环境变量
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.environ.get("SESSION_SECRET", secrets.token_urlsafe(32))
)

# Google OAuth 客户端配置
oauth = OAuth()
if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name='google',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )
    print("✅ Google OAuth 已配置")
else:
    print("⚠️  Google OAuth 未配置（GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET 未设置）")

# Stripe 支付配置
import stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY
    print("✅ Stripe 支付已配置")
else:
    print("⚠️  Stripe 支付未配置（STRIPE_SECRET_KEY 未设置）")


MOBILE_REGEX = re.compile(r"^(?:\+?86)?1\d{10}$")


def _normalize_mobile(raw: str) -> str:
    mobile = (raw or "").strip().replace(" ", "")
    if MOBILE_REGEX.fullmatch(mobile) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请输入正确的手机号（仅支持中国大陆 11 位手机号）",
        )
    if mobile.startswith("+86"):
        mobile = mobile[3:]
    if mobile.startswith("86") and len(mobile) == 13:
        mobile = mobile[2:]
    return mobile


def _hash_sms_code(mobile: str, session_id: str, code: str) -> str:
    payload = f"{settings.SMS_CODE_HASH_SALT}:{mobile}:{session_id}:{code}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _generate_sms_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _ensure_sms_configured() -> bool:
    if not settings.ALIYUN_SMS_ACCESS_KEY_ID or not settings.ALIYUN_SMS_ACCESS_KEY_SECRET:
        print("⚠️  短信服务未配置，使用本地模拟模式（验证码将打印在控制台）")
        return False
    return True


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


# -------------------------------------------------------------------------
# Google OAuth 登录
# -------------------------------------------------------------------------

@app.get("/api/auth/google/login")
async def google_login(request: Request):
    """发起 Google OAuth 登录"""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth 未配置，请联系管理员"
        )
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/api/auth/google/callback")
async def google_callback(request: Request, response: Response, db: Session = Depends(get_db)):
    """Google OAuth 回调处理"""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth 未配置"
        )
    
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        print(f"[google_callback] OAuth error: {e}")
        # 重定向到登录页并显示错误
        return RedirectResponse(url="/?error=google_auth_failed")
    
    user_info = token.get('userinfo')
    if not user_info or not user_info.get('email'):
        return RedirectResponse(url="/?error=google_no_email")
    
    email = user_info['email']
    google_id = user_info.get('sub')  # Google 用户唯一ID
    name = user_info.get('name', email.split('@')[0])
    
    # 查找现有用户（优先按 google_id，其次按 email）
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
    
    if user is None:
        # 创建新用户
        username = email.split('@')[0]
        # 确保用户名唯一
        base_username = username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}_{counter}"
            counter += 1
        
        user = User(
            username=username,
            email=email,
            google_id=google_id,
            password_hash=hash_password(secrets.token_urlsafe(32)),  # 随机密码
            is_admin=False,
            enabled=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # 新用户赠送 100 积分
        db.add(CreditTransaction(user_id=user.id, delta=100, reason="new_user_gift"))
        db.commit()
        print(f"[google_callback] 新用户注册: {email}")
    else:
        # 更新 google_id（如果之前是通过其他方式注册的）
        if not user.google_id:
            user.google_id = google_id
            db.add(user)
            db.commit()
        
        if not user.enabled:
            return RedirectResponse(url="/?error=account_disabled")
        print(f"[google_callback] 用户登录: {email}")
    
    # 创建会话
    session = create_session(db, user)
    
    # 创建重定向响应并设置 cookie
    redirect_response = RedirectResponse(url="/", status_code=302)
    redirect_response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session.id,
        httponly=True,
        max_age=int(settings.SESSION_TTL.total_seconds()),
        samesite="lax",
        secure=False,
        path="/",
    )
    return redirect_response


def _get_user_credits(db: Session, user_id: int) -> int:
    total = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()
    return sum(t.delta for t in total)


@app.get("/api/me")
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApiResponse[MeResponse]:
    credits = _get_user_credits(db, user.id)
    return ok(
        MeResponse(
            user_id=user.id,
            username=user.username,
            is_admin=user.is_admin,
            credits=credits,
            mobile=user.mobile,
        )
    )


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


@app.post("/api/mobile/send-code")
def send_mobile_code(
    req: SmsSendRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[None]:
    is_real_sms = _ensure_sms_configured()
    mobile = _normalize_mobile(req.mobile)
    client_ip = request.client.host if request.client else "unknown"
    ensure_sms_rate_limit(mobile, client_ip)

    if is_real_sms:
        try:
            result = sms_client.send_sms_code(
                phone_number=mobile,
                scene=req.scene or "login",
                sign_name=settings.ALIYUN_SMS_SIGN_NAME,
                template_code=settings.ALIYUN_SMS_TEMPLATE_CODE,
                template_param={"code": "##code##", "min": "5"},
                expire_seconds=settings.SMS_CODE_EXPIRE_SECONDS,
            )
        except AliyunSmsError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"短信发送失败：{exc.message or exc.code}",
            ) from exc
    else:
        # Mock SMS sending
        code = "123456"  # Fixed code for local testing
        print(f"\n{'='*40}")
        print(f"📱 [MOCK SMS] Mobile: {mobile}")
        print(f"🔑 [MOCK SMS] Code:   {code}")
        print(f"{'='*40}\n")
        
        class MockResult:
            def __init__(self, code):
                self.sms_session_id = f"mock_{uuid.uuid4().hex}"
                self.sms_code = code
        
        result = MockResult(code)

    record = SmsVerifySession(
        mobile=mobile,
        scene=req.scene or "login",
        sms_session_id=result.sms_session_id,
        code_hash=_hash_sms_code(mobile, result.sms_session_id, result.sms_code),
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(seconds=settings.SMS_CODE_EXPIRE_SECONDS),
    )
    db.add(record)
    db.commit()
    return ok(None)


@app.post("/api/mobile/verify")
def verify_mobile_code(
    req: SmsVerifyRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    is_real_sms = _ensure_sms_configured()
    mobile = _normalize_mobile(req.mobile)
    now = datetime.utcnow()

    record = (
        db.query(SmsVerifySession)
        .filter(
            SmsVerifySession.mobile == mobile,
            SmsVerifySession.scene == (req.scene or "login"),
            SmsVerifySession.expires_at >= now,
        )
        .order_by(SmsVerifySession.created_at.desc())
        .first()
    )
    if record is None:
        return fail("请先获取验证码")
    if record.verified_at:
        return fail("验证码已使用，请重新获取")

    code_hash = _hash_sms_code(mobile, record.sms_session_id, req.code)
    if code_hash != record.code_hash:
        record.attempts += 1
        db.add(record)
        db.commit()
        return fail("验证码错误")

    if is_real_sms:
        try:
            sms_client.check_sms_code(mobile, req.code, record.scene)
        except AliyunSmsError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"验证码核验失败：{exc.message or exc.code}",
            ) from exc
    else:
        print(f"[verify] Mock verification passed for {mobile}")

    record.verified_at = now
    db.add(record)
    db.commit()

    user = db.query(User).filter(User.mobile == mobile).first()
    if user is None:
        # 注册功能已禁用，新用户需由管理员创建
        return fail("用户不存在，请联系管理员注册账号")
    else:
        if not user.enabled:
            return fail("账号已禁用，请联系管理员")
        if user.mobile != mobile:
            user.mobile = mobile
            db.add(user)
            db.commit()

    session = create_session(db, user)
    set_session_cookie(response, session.id)
    credits = _get_user_credits(db, user.id)
    return ok(
        MeResponse(
            user_id=user.id,
            username=user.username,
            is_admin=user.is_admin,
            credits=credits,
            mobile=user.mobile,
        ).dict()
    )


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
    if len(prompt) > 10000:
        return fail("prompt 超过 10000 字符")

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

    # 校验模型与时长/尺寸组合
    # sora-2-all: 10s/15s, 仅 small(720p)
    # sora-2-pro-all: 10s/15s/25s, 仅 large(1080p)
    # veo_3_1: 8s固定, 支持 720p/1080p/4k
    model_constraints = {
        "sora-2-all": {
            "durations": {10, 15},
            "allowed_sizes": {"small"},
        },
        "sora-2-pro-all": {
            "durations": {10, 15, 25},
            "allowed_sizes": {"large"},
        },
        "veo_3_1": {
            "durations": {8},
            "allowed_sizes": {"720p", "1080p", "4k"},
        },
    }
    if req.model not in model_constraints:
        return fail("不支持的模型")
    constraints = model_constraints[req.model]
    if req.duration not in constraints["durations"]:
        return fail(f"该模型不支持所选时长，支持: {sorted(constraints['durations'])}")
    if req.size not in constraints["allowed_sizes"]:
        return fail(f"该模型不支持所选尺寸，支持: {sorted(constraints['allowed_sizes'])}")

    # 积分：定价（按模型与时长/尺寸）
    unit_cost = get_unit_cost(req.model, req.duration, req.size)
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
            unit_cost = get_unit_cost(t.model, int(t.duration), t.size)
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
    # 如果任务还在排队或待处理，标记为取消
    if task.status in {TaskStatus.pending, TaskStatus.queued}:
        task.status = TaskStatus.cancelled
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
        # 如果任务还在排队或待处理，标记为取消
        if task.status in {TaskStatus.pending, TaskStatus.queued}:
            task.status = TaskStatus.cancelled
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


# -------------------------------------------------------------------------
# 支付与积分相关接口
# -------------------------------------------------------------------------

@app.post("/api/recharge/orders")
def create_recharge_order(
    req: RechargeCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> ApiResponse[RechargeResponse]:
    try:
        order, pay_info = payment_service.create_order(
            user_id=user.id,
            amount_cny=req.amount,
            payment_method=req.payment_method,
            db_session=db
        )
        return ok(RechargeResponse(
            order_id=order.id,
            payment_url=pay_info.get("payment_url"),
            qr_code=pay_info.get("qr_code"),
            method=pay_info.get("method", "unknown")
        ))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return fail(f"创建订单失败: {str(e)}")

@app.get("/api/recharge/orders/{order_id}/status")
def get_order_status(
    order_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> ApiResponse[PaymentStatusResponse]:
    order = db.query(RechargeOrder).filter(RechargeOrder.id == order_id).first()
    if not order or order.user_id != user.id:
        return fail("订单不存在")
    
    # 主动查询状态（如果是 pending）
    if order.status == "pending":
        status_str = payment_service.check_order_status(order, db)
    else:
        status_str = order.status
        
    return ok(PaymentStatusResponse(
        order_id=order.id,
        status=status_str,
        credits_added=order.credits if status_str == "paid" else 0
    ))

@app.get("/api/credits/history")
def get_credit_history(
    page: int = 1, 
    page_size: int = 20, 
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_user)
) -> ApiResponse[dict]:
    q = db.query(CreditTransaction).filter(CreditTransaction.user_id == user.id).order_by(CreditTransaction.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    
    return ok({
        "items": [CreditTransactionRead(**t.__dict__) for t in items],
        "total": total,
        "page": page,
        "page_size": page_size
    })


# -------------------------------------------------------------------------
# Stripe 支付接口
# -------------------------------------------------------------------------

# Stripe 套餐配置（价格单位：美分）
STRIPE_PACKAGES = [
    {"id": "pkg_100", "price_cents": 199, "credits": 100, "display": "$1.99 = 100 积分"},
    {"id": "pkg_500", "price_cents": 899, "credits": 500, "display": "$8.99 = 500 积分"},
    {"id": "pkg_1000", "price_cents": 1599, "credits": 1000, "display": "$15.99 = 1000 积分"},
]


@app.get("/api/stripe/config")
def get_stripe_config(user: User = Depends(get_current_user)) -> ApiResponse[dict]:
    """获取 Stripe 前端配置"""
    if not settings.STRIPE_PUBLISHABLE_KEY:
        return fail("Stripe 支付未配置")
    
    return ok({
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "packages": STRIPE_PACKAGES
    })


@app.post("/api/stripe/create-checkout-session")
def create_stripe_checkout(
    request: Request,
    package_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> ApiResponse[dict]:
    """创建 Stripe Checkout 会话"""
    if not settings.STRIPE_SECRET_KEY:
        return fail("Stripe 支付未配置，请联系管理员")
    
    # 查找套餐
    package = next((p for p in STRIPE_PACKAGES if p["id"] == package_id), None)
    if not package:
        return fail("无效的套餐")
    
    # 创建订单记录
    order_id = f"stripe_{uuid.uuid4().hex[:16]}"
    order = RechargeOrder(
        id=order_id,
        user_id=user.id,
        amount=package["price_cents"],  # 美分
        credits=package["credits"],
        payment_method="stripe",
        status="pending"
    )
    db.add(order)
    db.commit()
    
    try:
        # 构建回调 URL
        base_url = settings.BASE_URL
        success_url = f"{base_url}/?payment=success&order_id={order_id}"
        cancel_url = f"{base_url}/?payment=cancelled"
        
        # 创建 Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": package["price_cents"],
                    "product_data": {
                        "name": f"AI 视频积分充值 - {package['credits']} 积分",
                        "description": f"购买 {package['credits']} 积分用于 AI 视频生成",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=order_id,  # 关联我们的订单ID
            metadata={
                "order_id": order_id,
                "user_id": str(user.id),
                "credits": str(package["credits"]),
            }
        )
        
        return ok({
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id,
            "order_id": order_id
        })
        
    except stripe.error.StripeError as e:
        print(f"[Stripe Error] {e}")
        order.status = "failed"
        db.add(order)
        db.commit()
        return fail(f"创建支付会话失败: {str(e)}")


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """接收 Stripe Webhook 回调"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not settings.STRIPE_WEBHOOK_SECRET:
        print("[Stripe Webhook] Webhook secret not configured")
        return {"error": "Webhook secret not configured"}
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        print(f"[Stripe Webhook] Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        print(f"[Stripe Webhook] Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # 处理 checkout.session.completed 事件
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("client_reference_id") or session.get("metadata", {}).get("order_id")
        
        if order_id:
            order = db.query(RechargeOrder).filter(RechargeOrder.id == order_id).first()
            if order and order.status == "pending":
                # 更新订单状态
                order.status = "paid"
                order.external_order_id = session.get("id")
                order.paid_at = datetime.utcnow()
                db.add(order)
                
                # 添加积分
                credit_tx = CreditTransaction(
                    user_id=order.user_id,
                    delta=order.credits,
                    reason="stripe_recharge"
                )
                db.add(credit_tx)
                db.commit()
                
                print(f"[Stripe Webhook] Payment successful: order={order_id}, credits={order.credits}")
            else:
                print(f"[Stripe Webhook] Order not found or already processed: {order_id}")
        else:
            print(f"[Stripe Webhook] No order_id in session")
    
    return {"received": True}


@app.post("/api/stripe/create-alipay-payment")
def create_alipay_payment(
    request: Request,
    package_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> ApiResponse[dict]:
    """创建支付宝支付（通过 Stripe）"""
    if not settings.STRIPE_SECRET_KEY:
        return fail("Stripe 支付未配置，请联系管理员")
    
    # 查找套餐
    package = next((p for p in STRIPE_PACKAGES if p["id"] == package_id), None)
    if not package:
        return fail("无效的套餐")
    
    # 创建订单记录
    order_id = f"alipay_{uuid.uuid4().hex[:16]}"
    order = RechargeOrder(
        id=order_id,
        user_id=user.id,
        amount=package["price_cents"],  # 美分
        credits=package["credits"],
        payment_method="alipay",
        status="pending"
    )
    db.add(order)
    db.commit()
    
    try:
        # 构建回调 URL
        base_url = settings.BASE_URL
        return_url = f"{base_url}/?payment=success&order_id={order_id}"
        
        # 创建 Stripe PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=package["price_cents"],
            currency="usd",
            payment_method_types=["alipay"],
            metadata={
                "order_id": order_id,
                "user_id": str(user.id),
                "credits": str(package["credits"]),
            }
        )
        
        # 保存 PaymentIntent ID
        order.external_order_id = payment_intent.id
        db.add(order)
        db.commit()
        
        # 确认 PaymentIntent 以获取支付宝重定向 URL
        confirmed_intent = stripe.PaymentIntent.confirm(
            payment_intent.id,
            payment_method_data={
                "type": "alipay"
            },
            return_url=return_url
        )
        
        # 获取支付宝重定向 URL
        redirect_url = None
        if confirmed_intent.next_action and confirmed_intent.next_action.type == "alipay_handle_redirect":
            redirect_url = confirmed_intent.next_action.alipay_handle_redirect.url
        elif confirmed_intent.next_action and confirmed_intent.next_action.type == "redirect_to_url":
            redirect_url = confirmed_intent.next_action.redirect_to_url.url
        
        if not redirect_url:
            return fail("无法获取支付宝支付链接")
        
        return ok({
            "redirect_url": redirect_url,
            "payment_intent_id": payment_intent.id,
            "order_id": order_id,
            "amount_usd": package["price_cents"] / 100,
            "credits": package["credits"]
        })
        
    except stripe.error.StripeError as e:
        print(f"[Stripe Alipay Error] {e}")
        order.status = "failed"
        db.add(order)
        db.commit()
        return fail(f"创建支付宝支付失败: {str(e)}")


# 微信支付套餐配置（人民币，单位：分）
# CNY 价格约为 USD 价格的 7 倍
WECHAT_PACKAGES = [
    {"id": "pkg_100", "price_cny_cents": 1400, "credits": 100, "display": "¥14 = 100 积分"},
    {"id": "pkg_500", "price_cny_cents": 6400, "credits": 500, "display": "¥64 = 500 积分"},
    {"id": "pkg_1000", "price_cny_cents": 11500, "credits": 1000, "display": "¥115 = 1000 积分"},
]


@app.post("/api/stripe/create-wechat-payment")
def create_wechat_payment(
    request: Request,
    package_id: str,
    custom_amount: Optional[int] = None,  # 自定义金额（人民币元）
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> ApiResponse[dict]:
    """创建微信支付（通过 Stripe）"""
    if not settings.STRIPE_SECRET_KEY:
        return fail("Stripe 支付未配置，请联系管理员")
    
    # 处理自定义金额或预设套餐
    if custom_amount is not None and custom_amount > 0:
        # 自定义金额模式: 1元 = 10积分
        if custom_amount < 1:
            return fail("最低充值金额为 ¥1")
        price_cny_cents = custom_amount * 100  # 元转分
        credits = custom_amount * 10  # 1元=10积分
    else:
        # 预设套餐模式
        package = next((p for p in WECHAT_PACKAGES if p["id"] == package_id), None)
        if not package:
            return fail("无效的套餐")
        price_cny_cents = package["price_cny_cents"]
        credits = package["credits"]
    
    # 创建订单记录（存储人民币分数）
    order_id = f"wechat_{uuid.uuid4().hex[:16]}"
    order = RechargeOrder(
        id=order_id,
        user_id=user.id,
        amount=price_cny_cents,  # 人民币分
        credits=credits,
        payment_method="wechat_pay",
        status="pending"
    )
    db.add(order)
    db.commit()
    
    try:
        # 构建回调 URL
        base_url = settings.BASE_URL
        return_url = f"{base_url}/?payment=success&order_id={order_id}"
        
        # 创建 Stripe PaymentIntent (微信支付，使用 CNY)
        payment_intent = stripe.PaymentIntent.create(
            amount=price_cny_cents,
            currency="cny",  # 微信支付必须使用 CNY 或 HKD
            payment_method_types=["wechat_pay"],
            metadata={
                "order_id": order_id,
                "user_id": str(user.id),
                "credits": str(credits),
            }
        )
        
        # 保存 PaymentIntent ID
        order.external_order_id = payment_intent.id
        db.add(order)
        db.commit()
        
        # 确认 PaymentIntent 以获取微信支付二维码
        confirmed_intent = stripe.PaymentIntent.confirm(
            payment_intent.id,
            payment_method_data={
                "type": "wechat_pay"
            },
            payment_method_options={
                "wechat_pay": {
                    "client": "web"  # 指定为 web 端
                }
            },
            return_url=return_url
        )
        
        # 获取微信支付二维码 URL
        qr_code_url = None
        if confirmed_intent.next_action:
            if confirmed_intent.next_action.type == "wechat_pay_display_qr_code":
                qr_code_url = confirmed_intent.next_action.wechat_pay_display_qr_code.data
            elif confirmed_intent.next_action.type == "redirect_to_url":
                qr_code_url = confirmed_intent.next_action.redirect_to_url.url
        
        if not qr_code_url:
            return fail("无法获取微信支付二维码")
        
        return ok({
            "qr_code_url": qr_code_url,
            "payment_intent_id": payment_intent.id,
            "order_id": order_id,
            "amount_cny": price_cny_cents / 100,  # 返回人民币元
            "credits": credits
        })
        
    except stripe.error.StripeError as e:
        print(f"[Stripe WeChat Error] {e}")
        order.status = "failed"
        db.add(order)
        db.commit()
        return fail(f"创建微信支付失败: {str(e)}")


@app.get("/api/stripe/payment-status/{order_id}")
def get_stripe_payment_status(
    order_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> ApiResponse[dict]:
    """查询 Stripe 支付状态（用于前端轮询）"""
    order = db.query(RechargeOrder).filter(RechargeOrder.id == order_id).first()
    if not order or order.user_id != user.id:
        return fail("订单不存在")
    
    # 如果订单已完成，直接返回
    if order.status == "paid":
        return ok({
            "status": "paid",
            "credits": order.credits
        })
    
    # 如果订单有 PaymentIntent ID，查询 Stripe 状态
    if order.external_order_id and order.status == "pending":
        try:
            # 检查是否是 PaymentIntent (pi_) 还是 CheckoutSession (cs_)
            if order.external_order_id.startswith("pi_"):
                payment_intent = stripe.PaymentIntent.retrieve(order.external_order_id)
                
                if payment_intent.status == "succeeded":
                    # 更新订单状态
                    order.status = "paid"
                    order.paid_at = datetime.utcnow()
                    db.add(order)
                    
                    # 根据支付方式确定 reason
                    reason = f"{order.payment_method}_recharge"
                    
                    # 添加积分
                    credit_tx = CreditTransaction(
                        user_id=order.user_id,
                        delta=order.credits,
                        reason=reason
                    )
                    db.add(credit_tx)
                    db.commit()
                    
                    print(f"[Stripe] Payment successful: order={order_id}, method={order.payment_method}, credits={order.credits}")
                    return ok({
                        "status": "paid",
                        "credits": order.credits
                    })
                elif payment_intent.status in ["canceled", "requires_payment_method"]:
                    order.status = "failed"
                    db.add(order)
                    db.commit()
                    return ok({"status": "failed"})
                else:
                    return ok({"status": "pending"})
        except stripe.error.StripeError as e:
            print(f"[Stripe Status Error] {e}")
            return ok({"status": "pending"})
    
    return ok({"status": order.status})


# Mock 支付页面
@app.get("/mock-pay.html", response_class=HTMLResponse)
def mock_pay_page(order_id: str, amount: float, credits: int):
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>模拟支付收银台</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f0f2f5; margin: 0; }}
            .card {{ background: white; padding: 2.5rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); text-align: center; max-width: 400px; width: 90%; }}
            h1 {{ color: #1f1f1f; font-size: 20px; margin-bottom: 1.5rem; font-weight: 600; }}
            .amount {{ font-size: 36px; color: #1677ff; font-weight: bold; margin: 0.5rem 0; display: flex; align-items: baseline; justify-content: center; }}
            .amount small {{ font-size: 18px; margin-right: 4px; font-weight: normal; }}
            .info {{ color: #666; font-size: 14px; margin-bottom: 0.5rem; }}
            .qr-container {{ margin: 1.5rem 0; background: #f8f9fa; padding: 1rem; border-radius: 8px; display: inline-block; }}
            .qr-code {{ width: 180px; height: 180px; background-color: #fff; padding: 10px; border-radius: 4px; }}
            .btn-group {{ display: flex; flex-direction: column; gap: 10px; margin-top: 1.5rem; }}
            button {{ background: #1677ff; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; font-size: 16px; width: 100%; transition: all 0.2s; font-weight: 500; }}
            button:hover {{ background: #4096ff; transform: translateY(-1px); box-shadow: 0 2px 5px rgba(22,119,255,0.2); }}
            button:active {{ transform: translateY(0); }}
            .cancel {{ background: #f5f5f5; color: #666; }}
            .cancel:hover {{ background: #e0e0e0; color: #333; box-shadow: none; }}
            .divider {{ height: 1px; background: #eee; margin: 1.5rem 0; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>模拟支付收银台</h1>
            <div class="info">订单号: {order_id}</div>
            <div class="amount"><small>¥</small>{amount}</div>
            <div class="info">支付后将获得 <span style="color: #1677ff; font-weight: bold;">{credits}</span> 积分</div>
            
            <div class="qr-container">
                <!-- 使用 API 生成简单的二维码，或者使用静态占位图 -->
                <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=MOCK_PAYMENT_{order_id}" class="qr-code" alt="Mock QR Code" />
                <div style="font-size: 12px; color: #999; margin-top: 8px;">请使用手机扫码支付 (模拟)</div>
            </div>

            <div class="btn-group">
                <button onclick="confirmPay()">确认支付 (模拟成功)</button>
                <button class="cancel" onclick="window.close()">取消支付</button>
            </div>
        </div>
        <script>
            async function confirmPay() {{
                const btn = document.querySelector('button');
                btn.disabled = true;
                btn.textContent = '处理中...';
                try {{
                    const res = await fetch('/api/mock/pay/{order_id}', {{ method: 'POST' }});
                    const data = await res.json();
                    if (data.ok) {{
                        // 支付成功后，尝试通知父窗口刷新（如果是弹窗）
                        try {{
                            if (window.opener && !window.opener.closed) {{
                                window.opener.postMessage({{ type: 'PAYMENT_SUCCESS', orderId: '{order_id}' }}, '*');
                            }}
                        }} catch (e) {{ console.error(e); }}
                        
                        alert('支付成功！请返回原窗口查看。');
                        window.close();
                    }} else {{
                        alert('支付失败: ' + (data.error?.message || '未知错误'));
                    }}
                }} catch (e) {{
                    alert('网络错误');
                }} finally {{
                    btn.disabled = false;
                    btn.textContent = '确认支付 (模拟成功)';
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/mock/pay/{order_id}")
def mock_pay_confirm(order_id: str, db: Session = Depends(get_db)):
    if payment_service.mock_pay_success(order_id, db):
        return ok({"status": "paid"})
    return fail("订单不存在或已支付")


# -------------------------------------------------------------------------
# 静态文件缓存控制中间件
# -------------------------------------------------------------------------
@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    # 对 JS、CSS 和 HTML 文件禁用缓存（开发环境）
    path = request.url.path
    if path.endswith(('.js', '.css', '.html')) or path == '/' or path == '':
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=settings.PUBLIC_DIR, html=True), name="static")

from __future__ import annotations

from datetime import datetime
from typing import Optional

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import User, UserSession
from .settings import settings


def hash_password(raw_password: str) -> str:
    # 使用原生 bcrypt 库
    password_bytes = raw_password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')


def verify_password(raw_password: str, password_hash: str) -> bool:
    # 使用原生 bcrypt 库验证
    password_bytes = raw_password.encode('utf-8')
    hash_bytes = password_hash.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hash_bytes)


def create_session(db: Session, user: User) -> UserSession:
    expires_at = datetime.utcnow() + settings.SESSION_TTL
    session = UserSession(user_id=user.id, expires_at=expires_at)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        max_age=int(settings.SESSION_TTL.total_seconds()),
        samesite="lax",
        secure=False,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.SESSION_COOKIE_NAME, path="/")


def get_current_user(
    db: Session = Depends(get_db),
    session_id: Optional[str] = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
) -> User:
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session: Optional[UserSession] = db.get(UserSession, session_id)
    if session is None or session.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user: Optional[User] = db.get(User, session.user_id)
    if user is None or not user.enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user

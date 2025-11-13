from __future__ import annotations

import enum
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class TaskStatus(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    api_keys = relationship("UserApiKey", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, default=lambda: secrets.token_urlsafe(32))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")


class UserApiKey(Base):
    __tablename__ = "user_api_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "environment", name="uq_user_provider_env"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    environment = Column(String(16), nullable=False)
    encrypted_key = Column(Text, nullable=False)
    last_verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="api_keys")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    model = Column(String(32), nullable=False)
    orientation = Column(String(16), nullable=False)
    size = Column(String(16), nullable=False)
    duration = Column(Integer, nullable=False)
    num_videos = Column(Integer, nullable=False)
    image_path = Column(Text, nullable=True)

    total = Column(Integer, default=0, nullable=False)
    completed = Column(Integer, default=0, nullable=False)
    failed = Column(Integer, default=0, nullable=False)
    running = Column(Integer, default=0, nullable=False)
    queued = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    tasks = relationship("Task", back_populates="batch", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    prompt = Column(Text, nullable=False)
    model = Column(String(32), nullable=False)
    orientation = Column(String(16), nullable=False)
    size = Column(String(16), nullable=False)
    duration = Column(Integer, nullable=False)
    image_path = Column(Text, nullable=True)

    status = Column(Enum(TaskStatus), default=TaskStatus.pending, nullable=False)
    error_summary = Column(Text, nullable=True)
    progress = Column(String(16), nullable=True)  # 进度信息，如 "50%"
    retries = Column(Integer, default=0, nullable=False)
    rerun_of_task_id = Column(String(36), nullable=True, index=True)

    result_path = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    batch = relationship("Batch", back_populates="tasks")

    __table_args__ = (
        CheckConstraint("duration IN (5, 10, 15, 25)", name="ck_duration_values"),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=True)


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 正数为增加积分，负数为扣减积分
    delta = Column(Integer, nullable=False)
    reason = Column(String(64), nullable=False)
    # 便于避免重复退款/扣费，关联到批次或任务
    ref_batch_id = Column(String(36), nullable=True, index=True)
    ref_task_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field
try:
    from pydantic.generics import GenericModel
except Exception:
    GenericModel = BaseModel


T = TypeVar("T")


class ApiError(BaseModel):
    message: str
    code: Optional[str] = None


class ApiResponse(GenericModel, Generic[T]):
    ok: bool = Field(..., description="Indicates success")
    data: Optional[T] = None
    error: Optional[ApiError] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class MeResponse(BaseModel):
    user_id: int
    username: str
    is_admin: bool
    credits: int = 0
    mobile: Optional[str] = None


class BatchCreateRequest(BaseModel):
    prompt: str
    model: Literal["sora-2", "sora-2-pro"]
    orientation: Literal["portrait", "landscape"]
    size: Literal["small", "medium", "large"]
    duration: Literal[5, 10, 15, 25]
    num_videos: int = Field(gt=0, le=50)
    image_path: Optional[str] = None


class ApiKeySetRequest(BaseModel):
    provider: str
    api_key: str


class ApiKeyGetResponse(BaseModel):
    provider: str
    configured: bool


class CreditAdjustRequest(BaseModel):
    user_id: int
    delta: int
    reason: str = Field(min_length=1, max_length=64)


class TaskRead(BaseModel):
    id: str
    batch_id: str
    status: str
    result_path: Optional[str] = None
    error_summary: Optional[str] = None
    progress: Optional[str] = None
    remote_started_at: Optional[datetime] = None
    remote_finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class BatchRead(BaseModel):
    id: str
    prompt: str
    model: str
    orientation: str
    size: str
    duration: int
    num_videos: int
    image_path: Optional[str] = None
    total: int
    completed: int
    failed: int
    running: int
    queued: int
    created_at: datetime
    updated_at: datetime


class SmsSendRequest(BaseModel):
    mobile: str
    scene: Optional[str] = Field(default="login", max_length=32)


class SmsVerifyRequest(BaseModel):
    mobile: str
    code: str = Field(min_length=4, max_length=10)
    scene: Optional[str] = Field(default="login", max_length=32)


def ok(data: Any) -> ApiResponse[Any]:
    return ApiResponse(ok=True, data=data)


def fail(message: str, code: Optional[str] = None) -> ApiResponse[Any]:
    return ApiResponse(ok=False, error=ApiError(message=message, code=code))

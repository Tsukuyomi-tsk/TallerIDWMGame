# app/schemas/admin_user.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


# app/schemas/admin_user.py (continúa)
class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_verified: bool
    is_suspended: bool
    suspended_at: datetime | None
    suspension_reason: str | None
    created_at: datetime


class UserPage(BaseModel):
    items: list[AdminUserRead]
    page: int
    size: int
    total: int
    pages: int


class SuspendUserRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

# app/routers/admin_users.py
# app/routers/admin_users.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.core.dependencies import AdminUser
from app.schemas.admin_user import AdminUserRead, SuspendUserRequest
from app.services import admin_user_service

# app/routers/admin_users.py (continúa)
router = APIRouter(prefix="/admin/users", tags=["admin-users"])

SessionDep = Annotated[Session, Depends(get_session)]


# app/routers/admin_users.py (continúa)
@router.patch("/{user_id}/suspend", response_model=AdminUserRead)
def suspend_user(
    user_id: int, payload: SuspendUserRequest, session: SessionDep, admin: AdminUser
) -> AdminUserRead:
    user = admin_user_service.suspend_user(
        session, admin_id=admin.id, user_id=user_id, reason=payload.reason
    )
    return AdminUserRead.model_validate(user)

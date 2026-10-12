# app/services/admin_user_service.py
from __future__ import annotations

from sqlmodel import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.time import utcnow
from app.models import User
from app.repositories.user_repository import UserRepository


# app/services/admin_user_service.py
def suspend_user(session: Session, *, admin_id: int, user_id: int, reason: str) -> User:
    if admin_id == user_id:
        raise ConflictError("No puedes suspender tu propia cuenta.")

    users = UserRepository(session)
    user = users.get(user_id)
    if user is None:
        raise NotFoundError("Usuario no encontrado.")

    user.is_suspended = True
    user.suspended_at = utcnow()
    user.suspension_reason = reason
    users.add(user)
    session.commit()
    session.refresh(user)
    return user

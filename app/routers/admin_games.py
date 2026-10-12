# app/routers/admin_games.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status, File, Form, UploadFile
from sqlmodel import Session

from app.core.database import get_session
from app.core.dependencies import AdminUser
from app.schemas.admin_game import (
    GameAdminDetail,
    GameAdminListItem,
    GameAdminPage,
    GameCreate,
    GameUpdate,
)
from app.schemas.category import CategoryRead
from app.schemas.game import GameImageRead
from app.services import admin_game_service

# app/routers/admin_games.py (continúa)
router = APIRouter(prefix="/admin/games", tags=["admin-games"])

SessionDep = Annotated[Session, Depends(get_session)]


# app/routers/admin_games.py (continúa)
def _to_detail(row) -> GameAdminDetail:
    game = row.game
    return GameAdminDetail(
        id=game.id,
        title=game.title,
        slug=game.slug,
        description=game.description,
        developer=game.developer,
        publisher=game.publisher,
        platform=game.platform,
        release_date=game.release_date,
        base_price=game.base_price,
        is_active=game.is_active,
        deleted_at=game.deleted_at,
        created_at=game.created_at,
        updated_at=game.updated_at,
        categories=[CategoryRead.model_validate(c) for c in row.categories],
        images=[GameImageRead.model_validate(i) for i in row.images],
    )


# app/routers/admin_games.py (continúa)
@router.get("", response_model=GameAdminPage)
def list_games(
    session: SessionDep,
    _admin: AdminUser,
    q: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> GameAdminPage:
    items, total, pages = admin_game_service.list_games(session, q=q, page=page, size=size)
    return GameAdminPage(
        items=[
            GameAdminListItem(
                id=g.id,
                title=g.title,
                slug=g.slug,
                platform=g.platform,
                base_price=g.base_price,
                is_active=g.is_active,
                deleted_at=g.deleted_at,
                created_at=g.created_at,
            )
            for g in items
        ],
        page=page,
        size=size,
        total=total,
        pages=pages,
    )


# app/routers/admin_games.py (continúa)
@router.get("/{game_id}", response_model=GameAdminDetail)
def get_game(game_id: int, session: SessionDep, _admin: AdminUser) -> GameAdminDetail:
    row = admin_game_service.get_game(session, game_id=game_id)
    return _to_detail(row)


@router.post("", response_model=GameAdminDetail, status_code=status.HTTP_201_CREATED)
def create_game(payload: GameCreate, session: SessionDep, _admin: AdminUser) -> GameAdminDetail:
    row = admin_game_service.create_game(session, payload=payload)
    return _to_detail(row)


@router.patch("/{game_id}", response_model=GameAdminDetail)
def update_game(
    game_id: int, payload: GameUpdate, session: SessionDep, _admin: AdminUser
) -> GameAdminDetail:
    row = admin_game_service.update_game(session, game_id=game_id, payload=payload)
    return _to_detail(row)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(game_id: int, session: SessionDep, _admin: AdminUser) -> None:
    admin_game_service.soft_delete_game(session, game_id=game_id)


# app/routers/admin_games.py
@router.post("/{game_id}/images", response_model=GameImageRead, status_code=status.HTTP_201_CREATED)
async def upload_game_image(
    game_id: int,
    session: SessionDep,
    _admin: AdminUser,
    file: Annotated[UploadFile, File()],
    is_cover: Annotated[bool, Form()] = False,
) -> GameImageRead:
    content = await file.read()
    image = admin_game_service.add_game_image(
        session,
        game_id=game_id,
        filename=file.filename or "image",
        content=content,
        content_type=file.content_type,
        is_cover=is_cover,
    )
    return GameImageRead.model_validate(image)


@router.delete("/{game_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game_image(game_id: int, image_id: int, session: SessionDep, _admin: AdminUser) -> None:
    admin_game_service.delete_game_image(session, game_id=game_id, image_id=image_id)

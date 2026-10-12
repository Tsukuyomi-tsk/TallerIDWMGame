# app/services/admin_game_service.py
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.time import utcnow
from app.integrations import cloudinary_client
from app.models import Game, GameImage
from app.repositories.category_repository import CategoryRepository
from app.repositories.game_image_repository import GameImageRepository
from app.repositories.game_repository import GameAdminRow, GameRepository
from app.schemas.admin_game import GameCreate, GameUpdate


# app/services/admin_game_service.py (continúa)
def _validate_category_ids(categories: CategoryRepository, category_ids: list[int]) -> None:
    if not category_ids:
        return
    found = categories.get_many(category_ids)
    missing = set(category_ids) - {c.id for c in found}
    if missing:
        raise ValidationError(f"Categorias invalidas: {sorted(missing)}")


# app/services/admin_game_service.py (continúa)
def list_games(
    session: Session, *, q: str | None, page: int, size: int
) -> tuple[list[Game], int, int]:
    games = GameRepository(session)
    offset = (page - 1) * size
    items, total = games.list_admin(q=q, offset=offset, limit=size)
    pages = (total + size - 1) // size if total else 0
    return items, total, pages


def get_game(session: Session, *, game_id: int) -> GameAdminRow:
    games = GameRepository(session)
    game = games.get(game_id, include_deleted=True)
    if game is None:
        raise NotFoundError("Juego no encontrado.")
    return games.load_admin_row(game)


# app/services/admin_game_service.py (continúa)
def create_game(session: Session, *, payload: GameCreate) -> GameAdminRow:
    games = GameRepository(session)
    categories = CategoryRepository(session)

    if games.get_by_slug(payload.slug, include_deleted=True) is not None:
        raise ValidationError("Ya existe un juego con ese slug.")
    _validate_category_ids(categories, payload.category_ids)

    # Entre la revisión del slug y el commit otra petición pudo crear el mismo
    # slug: la restricción única de la base nos frena con un IntegrityError.
    # El try envuelve desde games.add() (que ya hace flush y puede disparar el
    # error) hasta el commit, no solo el commit.
    try:
        game = games.add(
            Game(
                title=payload.title,
                slug=payload.slug,
                description=payload.description,
                developer=payload.developer,
                publisher=payload.publisher,
                platform=payload.platform,
                release_date=payload.release_date,
                base_price=payload.base_price,
            )
        )
        games.set_categories(game.id, payload.category_ids)
        session.commit()
    except IntegrityError:
        # Se deshace la transacción fallida.
        session.rollback()
        # Si la causa es el slug, ahora la otra fila es visible: se responde el
        # mismo 422 de la revisión previa. `from None` deja solo el error limpio.
        if games.get_by_slug(payload.slug, include_deleted=True) is not None:
            raise ValidationError("Ya existe un juego con ese slug.") from None
        # Si fue por otra causa, no se esconde.
        raise
    session.refresh(game)
    return games.load_admin_row(game)


# app/services/admin_game_service.py (continúa)
def update_game(session: Session, *, game_id: int, payload: GameUpdate) -> GameAdminRow:
    games = GameRepository(session)
    categories = CategoryRepository(session)

    game = games.get(game_id, include_deleted=True)
    if game is None:
        raise NotFoundError("Juego no encontrado.")

    data = payload.model_dump(exclude_unset=True)
    category_ids = data.pop("category_ids", None)

    if "slug" in data and data["slug"] != game.slug:
        existing = games.get_by_slug(data["slug"], include_deleted=True)
        if existing is not None and existing.id != game.id:
            raise ValidationError("Ya existe un juego con ese slug.")

    for field, value in data.items():
        setattr(game, field, value)

    # Se guarda ahora: tras un rollback el objeto queda expirado.
    new_slug = data.get("slug")
    try:
        games.add(game)
        if category_ids is not None:
            _validate_category_ids(categories, category_ids)
            games.set_categories(game.id, category_ids)
        session.commit()
    except IntegrityError:
        # Otra petición nos ganó el slug entre la revisión y el commit.
        session.rollback()
        taken = games.get_by_slug(new_slug, include_deleted=True) if new_slug else None
        # Solo cuenta si el slug lo tiene OTRO juego (no este mismo).
        if taken is not None and taken.id != game_id:
            raise ValidationError("Ya existe un juego con ese slug.") from None
        raise
    session.refresh(game)
    return games.load_admin_row(game)


# app/services/admin_game_service.py (continúa)
def soft_delete_game(session: Session, *, game_id: int) -> None:
    games = GameRepository(session)
    game = games.get(game_id, include_deleted=True)
    if game is None:
        raise NotFoundError("Juego no encontrado.")
    if game.deleted_at is not None:
        return  # ya eliminado — DELETE es idempotente
    game.deleted_at = utcnow()
    games.add(game)
    session.commit()


# app/services/admin_game_service.py
def add_game_image(
    session: Session,
    *,
    game_id: int,
    filename: str,
    content: bytes,
    content_type: str | None,
    is_cover: bool,
) -> GameImage:
    games = GameRepository(session)
    images = GameImageRepository(session)

    game = games.get(game_id, include_deleted=True)
    if game is None:
        raise NotFoundError("Juego no encontrado.")
    if not content_type or not content_type.startswith("image/"):
        raise ValidationError("El archivo debe ser una imagen.")

    url, public_id = cloudinary_client.upload_image(
        game_id=game_id, filename=filename, content=content
    )

    if is_cover:
        images.clear_cover(game_id)

    existing_count = len(images.list_for_game(game_id))
    image = images.add(
        GameImage(
            game_id=game_id,
            url=url,
            public_id=public_id,
            is_cover=is_cover,
            sort_order=existing_count,
        )
    )
    session.commit()
    session.refresh(image)
    return image


def delete_game_image(session: Session, *, game_id: int, image_id: int) -> None:
    images = GameImageRepository(session)
    image = images.get(image_id)
    if image is None or image.game_id != game_id:
        raise NotFoundError("Imagen no encontrada.")

    cloudinary_client.delete_image(image.public_id)
    images.delete(image)
    session.commit()

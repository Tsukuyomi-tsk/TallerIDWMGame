from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.time import utcnow
from app.models import Category
from app.repositories.category_repository import CategoryRepository
from app.schemas.admin_category import CategoryCreate, CategoryUpdate


def soft_delete_category(session: Session, *, category_id: int) -> None:
    categories = CategoryRepository(session)
    category = categories.get(category_id, include_deleted=True)
    if category is None:
        raise NotFoundError("Categoria no encontrada.")
    if category.deleted_at is not None:
        return  # idempotente
    category.deleted_at = utcnow()
    categories.add(category)
    session.commit()


def _check_unique(
    categories: CategoryRepository, *, slug: str, name: str, exclude_id: int | None = None
) -> None:
    # Revisa que ni el slug ni el nombre estén ocupados por OTRA categoría.
    # include_deleted=True: una categoría eliminada sigue ocupando su slug y su nombre.
    # exclude_id evita que una categoría choque contra sí misma al modificarla.
    existing = categories.get_by_slug(slug, include_deleted=True)
    if existing is not None and existing.id != exclude_id:
        raise ValidationError("Ya existe una categoria con ese slug.")
    existing = categories.get_by_name(name, include_deleted=True)
    if existing is not None and existing.id != exclude_id:
        raise ValidationError("Ya existe una categoria con ese nombre.")


def create_category(session: Session, *, payload: CategoryCreate) -> Category:
    categories = CategoryRepository(session)
    # La revisión de siempre: responde 422 cuando el choque es visible desde ya.
    _check_unique(categories, slug=payload.slug, name=payload.name)

    # Entre la revisión y el commit otra petición pudo insertar el mismo slug o
    # nombre: la restricción única de la base nos frena con un IntegrityError.
    # El try envuelve desde add() (que ya hace flush) hasta el commit.
    try:
        category = categories.add(
            Category(name=payload.name, slug=payload.slug, description=payload.description)
        )
        session.commit()
    except IntegrityError:
        # Se deshace la transacción fallida.
        session.rollback()
        # Ahora la fila de la otra petición es visible: la misma revisión de antes
        # encuentra el choque y lanza el 422 correcto en vez de un 500.
        _check_unique(categories, slug=payload.slug, name=payload.name)
        # Si el error fue por otra causa, no se esconde.
        raise
    session.refresh(category)
    return category


def update_category(session: Session, *, category_id: int, payload: CategoryUpdate) -> Category:
    categories = CategoryRepository(session)
    category = categories.get(category_id, include_deleted=True)
    if category is None:
        raise NotFoundError("Categoria no encontrada.")

    data = payload.model_dump(exclude_unset=True)
    # Slug y nombre finales: el nuevo si vino en el PATCH, si no el que ya tenía.
    new_slug = data.get("slug", category.slug)
    new_name = data.get("name", category.name)
    # Se guarda el id ahora: tras un rollback el objeto queda expirado.
    category_id = category.id
    _check_unique(categories, slug=new_slug, name=new_name, exclude_id=category_id)

    for field, value in data.items():
        setattr(category, field, value)

    try:
        categories.add(category)
        session.commit()
    except IntegrityError:
        # Misma defensa que al crear: otra petición nos ganó el slug o el nombre.
        session.rollback()
        _check_unique(categories, slug=new_slug, name=new_name, exclude_id=category_id)
        raise
    session.refresh(category)
    return category


def restore_category(session: Session, *, category_id: int) -> Category:
    categories = CategoryRepository(session)
    category = categories.get(category_id, include_deleted=True)
    if category is None:
        raise NotFoundError("Categoria no encontrada.")
    if category.deleted_at is not None:
        category.deleted_at = None
        categories.add(category)
        session.commit()
        session.refresh(category)
    return category


def list_categories(session: Session) -> list[Category]:
    return CategoryRepository(session).list_all_admin()

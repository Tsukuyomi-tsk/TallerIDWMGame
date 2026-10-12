# app/services/admin_offer_service.py
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import Offer
from app.repositories.game_repository import GameRepository
from app.repositories.offer_repository import OfferRepository
from app.schemas.offer import OfferCreate, OfferUpdate


# app/services/admin_offer_service.py
def _check_no_overlap(
    offers: OfferRepository,
    *,
    game_id: int,
    starts_at: datetime,
    ends_at: datetime,
    is_active: bool,
    exclude_offer_id: int | None = None,
) -> None:
    if not is_active:
        return
    overlapping = offers.list_overlapping_active(
        game_id=game_id, starts_at=starts_at, ends_at=ends_at, exclude_offer_id=exclude_offer_id
    )
    if overlapping:
        raise ConflictError(
            "Ya existe una oferta activa que se superpone con este rango de fechas para este juego."
        )


def list_offers(session: Session, *, game_id: int | None) -> list[Offer]:
    return OfferRepository(session).list_all(game_id=game_id)


# app/services/admin_offer_service.py
def create_offer(session: Session, *, payload: OfferCreate) -> Offer:
    games = GameRepository(session)
    offers = OfferRepository(session)

    if games.get(payload.game_id) is None:
        raise NotFoundError("Juego no encontrado.")

    # Candado sobre el juego: si otra petición está creando una oferta para él,
    # esperamos a que haga commit y recién entonces revisamos el solapamiento.
    offers.lock_game_offers(payload.game_id)
    _check_no_overlap(
        offers,
        game_id=payload.game_id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=payload.is_active,
    )

    offer = offers.add(
        Offer(
            game_id=payload.game_id,
            discount_percent=payload.discount_percent,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            is_active=payload.is_active,
        )
    )
    session.commit()
    session.refresh(offer)
    return offer


# app/services/admin_offer_service.py (continúa)
def update_offer(session: Session, *, offer_id: int, payload: OfferUpdate) -> Offer:
    offers = OfferRepository(session)
    offer = offers.get(offer_id)
    if offer is None:
        raise NotFoundError("Oferta no encontrada.")

    # Mismo candado que al crear: serializa las escrituras sobre las ofertas del juego.
    offers.lock_game_offers(offer.game_id)
    # Mientras esperábamos el candado, otra petición pudo modificar o borrar esta
    # oferta: se descarta lo que la sesión tenía en memoria y se vuelve a leer.
    session.expire(offer)
    offer = offers.get(offer_id)
    if offer is None:
        raise NotFoundError("Oferta no encontrada.")

    data = payload.model_dump(exclude_unset=True)
    resolved_starts_at = data.get("starts_at", offer.starts_at)
    resolved_ends_at = data.get("ends_at", offer.ends_at)
    resolved_is_active = data.get("is_active", offer.is_active)

    if resolved_ends_at <= resolved_starts_at:
        raise ValidationError("ends_at debe ser posterior a starts_at.")

    _check_no_overlap(
        offers,
        game_id=offer.game_id,
        starts_at=resolved_starts_at,
        ends_at=resolved_ends_at,
        is_active=resolved_is_active,
        exclude_offer_id=offer.id,
    )

    for field, value in data.items():
        setattr(offer, field, value)

    offers.add(offer)
    session.commit()
    session.refresh(offer)
    return offer

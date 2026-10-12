# app/schemas/offer.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


# app/schemas/offer.py (continúa)
class OfferCreate(BaseModel):
    game_id: int
    discount_percent: int = Field(ge=1, le=90)
    starts_at: datetime
    ends_at: datetime
    is_active: bool = True

    @model_validator(mode="after")
    def _window_is_ordered(self) -> OfferCreate:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at debe ser posterior a starts_at.")
        return self


# app/schemas/offer.py (continúa)
class OfferUpdate(BaseModel):
    discount_percent: int | None = Field(default=None, ge=1, le=90)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None


class OfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    game_id: int
    discount_percent: int
    starts_at: datetime
    ends_at: datetime
    is_active: bool

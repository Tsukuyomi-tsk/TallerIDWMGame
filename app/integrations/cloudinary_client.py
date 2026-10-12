# app/integrations/cloudinary_client.py
from __future__ import annotations

import logging
import uuid
from pathlib import Path

import cloudinary
import cloudinary.uploader

from app.core.config import settings


# app/integrations/cloudinary_client.py
logger = logging.getLogger(__name__)

_MEDIA_DIR = Path("media")

_DEV_PREFIX = "dev:"

_UPLOAD_TRANSFORMATION = [{"width": 1280, "height": 1280, "crop": "limit"}, {"quality": "auto"}]

# app/integrations/cloudinary_client.py
if settings.media_mode == "cloudinary":
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
else:
    logger.warning(
        "[MODO DEV] Credenciales de Cloudinary ausentes -> las imagenes se "
        "guardan en ./media/, NO se suben de verdad."
    )


# app/integrations/cloudinary_client.py
def _save_to_disk(*, game_id: int, filename: str, content: bytes) -> tuple[str, str]:
    _MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    extension = Path(filename).suffix or ".bin"
    local_name = f"{game_id}_{uuid.uuid4().hex}{extension}"
    (_MEDIA_DIR / local_name).write_bytes(content)
    logger.warning(
        "[MODO DEV] Imagen simulada para el juego %s guardada en media/%s", game_id, local_name
    )
    return f"/media/{local_name}", f"{_DEV_PREFIX}{local_name}"


# app/integrations/cloudinary_client.py
def upload_image(*, game_id: int, filename: str, content: bytes) -> tuple[str, str]:
    if settings.media_mode != "cloudinary":
        return _save_to_disk(game_id=game_id, filename=filename, content=content)

    result = cloudinary.uploader.upload(
        content,
        folder="gamevault/games",
        public_id=f"game_{game_id}_{uuid.uuid4().hex}",
        transformation=_UPLOAD_TRANSFORMATION,
    )
    return result["secure_url"], result["public_id"]


def delete_image(public_id: str) -> None:
    if public_id.startswith(_DEV_PREFIX):
        local_name = public_id.removeprefix(_DEV_PREFIX)
        (_MEDIA_DIR / local_name).unlink(missing_ok=True)
        return

    cloudinary.uploader.destroy(public_id)

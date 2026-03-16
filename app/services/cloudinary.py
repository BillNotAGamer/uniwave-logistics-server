from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path

import cloudinary
import cloudinary.uploader

from app.core.config import Settings, get_settings
from app.core.exceptions import AppException
from app.utils.slug import slugify


class CloudinaryService:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        if self.is_configured:
            cloudinary.config(
                cloud_name=self._settings.cloudinary_cloud_name,
                api_key=self._settings.cloudinary_api_key,
                api_secret=self._settings.cloudinary_api_secret,
                secure=True,
            )

    @property
    def is_configured(self) -> bool:
        return bool(
            self._settings.cloudinary_cloud_name
            and self._settings.cloudinary_api_key
            and self._settings.cloudinary_api_secret
        )

    async def upload_image(self, *, file_bytes: bytes, filename: str | None = None) -> str:
        if not self.is_configured:
            raise AppException(
                code="cloudinary_not_configured",
                message="Cloudinary credentials are not configured.",
                status_code=500,
            )

        upload_options: dict[str, str | bool] = {
            "resource_type": "image",
            "secure": True,
            "overwrite": True,
        }

        folder = self._settings.cloudinary_folder.strip()
        if folder:
            upload_options["folder"] = folder

        public_id = self._build_public_id(filename)
        if public_id:
            upload_options["public_id"] = public_id

        try:
            result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                file_bytes,
                **upload_options,
            )
        except Exception as exc:
            raise AppException(
                code="image_upload_failed",
                message="Image upload failed.",
                status_code=502,
                details={"reason": str(exc)},
            ) from None

        secure_url = result.get("secure_url") if isinstance(result, dict) else None
        if not secure_url:
            raise AppException(
                code="image_upload_failed",
                message="Image upload failed.",
                status_code=502,
            )

        return str(secure_url)

    @staticmethod
    def _build_public_id(filename: str | None) -> str | None:
        if not filename:
            return None

        file_stem = Path(filename).stem.strip()
        if not file_stem:
            return None

        return slugify(file_stem)


@lru_cache
def get_cloudinary_service() -> CloudinaryService:
    return CloudinaryService(settings=get_settings())

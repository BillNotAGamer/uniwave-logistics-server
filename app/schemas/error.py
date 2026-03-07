from __future__ import annotations

from typing import Any

from app.schemas.base import APIModel


class ErrorBody(APIModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(APIModel):
    error: ErrorBody

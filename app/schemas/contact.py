from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.base import APIModel


class ContactRequest(APIModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=20)
    email: str = Field(min_length=5, max_length=256)
    message: str = Field(min_length=1, max_length=2000)
    source: str | None = Field(default=None, max_length=200)

    @field_validator("name", "phone", "message")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be empty.")
        return normalized

    @field_validator("source")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.split("@")[-1]:
            raise ValueError("Email must be a valid email address.")
        return normalized


class ContactResponse(APIModel):
    message: str

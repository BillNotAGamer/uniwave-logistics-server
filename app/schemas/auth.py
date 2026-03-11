from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, Field, field_validator, model_validator

from app.schemas.base import APIModel


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class RegisterRequest(APIModel):
    email: str = Field(min_length=5, max_length=256)
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)
    phone_number: str | None = Field(default=None, max_length=20)
    nationality: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("full_name", "phone_number", "nationality", "display_name")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_full_name(self) -> "RegisterRequest":
        if not self.full_name and not self.display_name:
            raise ValueError("fullName is required.")
        return self

    @property
    def resolved_full_name(self) -> str:
        return (self.full_name or self.display_name or "").strip()


class LoginRequest(APIModel):
    email: str = Field(min_length=5, max_length=256)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class ForgotPasswordRequest(APIModel):
    email: str = Field(min_length=5, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class ResetPasswordRequest(APIModel):
    email: str = Field(min_length=5, max_length=256)
    reset_token: str = Field(
        min_length=1,
        max_length=1024,
        validation_alias=AliasChoices("resetToken", "reset_token", "token"),
    )
    new_password: str = Field(min_length=8, max_length=100)
    confirm_password: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("reset_token")
    @classmethod
    def normalize_reset_token(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_password_confirmation(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("confirmPassword must match newPassword.")
        return self


class VerifyEmailRequest(APIModel):
    token: str = Field(min_length=20, max_length=1024)


class ResendVerificationRequest(APIModel):
    email: str = Field(min_length=5, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class UserProfileResponse(APIModel):
    email: str
    full_name: str | None = None
    phone_number: str | None = None
    address: str | None = None
    nationality: str | None = None
    tier: str
    is_profile_complete: bool
    requires_profile_completion: bool
    missing_fields: list[str] = Field(default_factory=list)


class RegisterResponse(APIModel):
    message: str


class LoginResponse(APIModel):
    access_token: str
    refresh_token: str
    email: str
    full_name: str = ""
    roles: list[str] = Field(default_factory=list)
    token_type: str = "bearer"


class UpdateProfileRequest(APIModel):
    full_name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=1, max_length=20)
    address: str = Field(min_length=1, max_length=500)
    nationality: str | None = Field(default=None, max_length=120)
    current_password: str | None = None
    new_password: str | None = None

    @field_validator("full_name", "phone_number", "address")
    @classmethod
    def normalize_required_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be empty.")
        return normalized

    @field_validator("nationality")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)


class ResetPasswordValidateResponse(APIModel):
    is_valid: bool
    expires_at: datetime | None = None


class AuthMessageResponse(APIModel):
    message: str

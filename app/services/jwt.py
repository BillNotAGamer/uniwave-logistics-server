from __future__ import annotations

import base64
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from jose import JWTError, jwt

from app.core.config import get_settings


class JWTService:
    def __init__(
        self,
        *,
        secret_key: str,
        algorithm: str,
        access_token_expire_minutes: int,
        issuer: str | None = None,
        audience: str | None = None,
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.issuer = issuer
        self.audience = audience

    @property
    def access_token_expires_in_seconds(self) -> int:
        return self.access_token_expire_minutes * 60

    def create_access_token(
        self,
        *,
        user_id: int,
        email: str,
        roles: list[str],
    ) -> str:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.access_token_expire_minutes)

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "nameid": str(user_id),
            "email": email,
            "roles": roles,
            "role": roles,
            "iat": now,
            "nbf": now,
            "exp": expires_at,
        }
        if self.issuer:
            payload["iss"] = self.issuer
        if self.audience:
            payload["aud"] = self.audience

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_access_token(self, token: str) -> dict[str, Any]:
        decode_kwargs: dict[str, Any] = {
            "algorithms": [self.algorithm],
            "options": {"require": ["sub", "exp"]},
        }
        if self.issuer:
            decode_kwargs["issuer"] = self.issuer
        if self.audience:
            decode_kwargs["audience"] = self.audience

        payload = jwt.decode(token, self.secret_key, **decode_kwargs)
        if not isinstance(payload, dict):
            raise JWTError("Invalid token payload")
        return payload

    def create_refresh_token(self) -> str:
        return base64.b64encode(secrets.token_bytes(64)).decode("ascii")


@lru_cache
def get_jwt_service() -> JWTService:
    settings = get_settings()
    return JWTService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )

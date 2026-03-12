from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.models.mixins import utc_now
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.jwt import JWTService


@dataclass(slots=True)
class RefreshAccessTokenResult:
    access_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        jwt_service: JWTService,
    ) -> None:
        self._session = session
        self._jwt_service = jwt_service

    async def refresh_access_token(self, *, refresh_token: str) -> RefreshAccessTokenResult:
        token_value = (refresh_token or "").strip()
        if not token_value:
            raise AppException(
                code="invalid_refresh_token",
                message="Refresh token is invalid or expired.",
                status_code=401,
            )

        statement = (
            select(RefreshToken)
            .options(selectinload(RefreshToken.user).selectinload(User.roles))
            .where(RefreshToken.token == token_value)
            .order_by(RefreshToken.id.desc())
        )
        token_record = await self._session.scalar(statement)
        if token_record is None:
            raise AppException(
                code="invalid_refresh_token",
                message="Refresh token is invalid or expired.",
                status_code=401,
            )

        now = utc_now()
        if token_record.revoked_at is not None:
            raise AppException(
                code="invalid_refresh_token",
                message="Refresh token is invalid or expired.",
                status_code=401,
            )

        if token_record.expires_at < now:
            token_record.revoked_at = now
            await self._session.commit()
            raise AppException(
                code="refresh_token_expired",
                message="Refresh token is expired.",
                status_code=401,
            )

        user = token_record.user
        if user is None:
            raise AppException(
                code="user_not_found",
                message="User for this refresh token was not found.",
                status_code=401,
            )

        if not user.is_active:
            raise AppException(
                code="user_inactive",
                message="User account is inactive.",
                status_code=403,
            )

        role_names = sorted({role.name for role in user.roles})
        access_token = self._jwt_service.create_access_token(
            user_id=user.id,
            email=user.email,
            roles=role_names,
        )
        return RefreshAccessTokenResult(
            access_token=access_token,
            expires_in=self._jwt_service.access_token_expires_in_seconds,
        )

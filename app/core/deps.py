from __future__ import annotations

from collections.abc import Callable

from jose import JWTError
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.db.session import get_db_session
from app.models.user import User
from app.services.jwt import JWTService, get_jwt_service

ROLE_ADMIN = "Admin"
ROLE_CONTENT_EDITOR = "ContentEditor"
ROLE_USER = "User"

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> User:
    if credentials is None:
        raise AppException(
            code="not_authenticated",
            message="Authentication credentials were not provided.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = credentials.credentials
    try:
        payload = jwt_service.decode_access_token(token)
    except JWTError:
        raise AppException(
            code="invalid_token",
            message="Invalid or expired access token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from None

    sub = payload.get("sub")
    if sub is None:
        raise AppException(
            code="invalid_token",
            message="Token subject claim is missing.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise AppException(
            code="invalid_token",
            message="Token subject claim is invalid.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from None

    statement = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id)
    )
    user = await session.scalar(statement)
    if user is None:
        raise AppException(
            code="user_not_found",
            message="User for this token was not found.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    if not user.is_active:
        raise AppException(
            code="user_inactive",
            message="User account is inactive.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return user


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> User | None:
    if credentials is None:
        return None

    token = credentials.credentials
    try:
        payload = jwt_service.decode_access_token(token)
    except JWTError:
        return None

    sub = payload.get("sub")
    if sub is None:
        return None

    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None

    statement = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id)
    )
    user = await session.scalar(statement)
    if user is None or not user.is_active:
        return None

    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    normalized_allowed = {role.lower() for role in allowed_roles}

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_roles = {role.name.lower() for role in current_user.roles}
        if user_roles.isdisjoint(normalized_allowed):
            raise AppException(
                code="forbidden",
                message="User does not have the required role.",
                status_code=status.HTTP_403_FORBIDDEN,
                details={
                    "required_roles": sorted(allowed_roles),
                    "user_roles": sorted(role.name for role in current_user.roles),
                },
            )
        return current_user

    dependency.__name__ = f"require_roles_{'_'.join(sorted(normalized_allowed))}"
    return dependency


require_admin = require_roles(ROLE_ADMIN)
require_content_editor = require_roles(ROLE_CONTENT_EDITOR, ROLE_ADMIN)
require_user_role = require_roles(ROLE_USER, ROLE_CONTENT_EDITOR, ROLE_ADMIN)

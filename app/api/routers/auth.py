from __future__ import annotations

import base64
import logging
import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.deps import ROLE_USER, get_current_user
from app.core.exceptions import AppException
from app.core.security import generate_secure_token, get_password_hash, hash_token, verify_password
from app.db.session import get_db_session
from app.models.email_verification_token import EmailVerificationToken
from app.models.mixins import utc_now
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    AuthMessageResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    ResetPasswordValidateResponse,
    UpdateProfileRequest,
    UserProfileResponse,
    VerifyEmailRequest,
)
from app.services.email import EmailService, get_email_service
from app.services.jwt import JWTService, get_jwt_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])

GENERIC_RESET_MESSAGE = "If the email exists, a reset link has been sent."
PASSWORD_LETTER_PATTERN = re.compile(r"[A-Za-z]")
PASSWORD_NUMBER_PATTERN = re.compile(r"[0-9]")
PASSWORD_SYMBOL_PATTERN = re.compile(r"[^A-Za-z0-9]")


def _message_response(status_code_value: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code_value, content={"message": message})


def _build_user_profile(user: User) -> UserProfileResponse:
    full_name = (user.full_name or user.display_name or "").strip() or None
    is_profile_complete = user.is_profile_complete()
    return UserProfileResponse(
        email=user.email,
        full_name=full_name,
        phone_number=user.phone_number,
        address=user.address,
        tier=(user.tier or "Bronze"),
        is_profile_complete=is_profile_complete,
        requires_profile_completion=not is_profile_complete,
        missing_fields=user.get_missing_profile_fields(),
    )


def _generate_reset_token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def _validate_password_policy(password: str) -> str | None:
    if not password or len(password) < 8:
        return "Password must be at least 8 characters long."
    if not PASSWORD_LETTER_PATTERN.search(password):
        return "Password must include at least one letter."
    if not PASSWORD_NUMBER_PATTERN.search(password):
        return "Password must include at least one number."
    if not PASSWORD_SYMBOL_PATTERN.search(password):
        return "Password must include at least one symbol."
    return None


async def _get_user_by_email(
    session: AsyncSession,
    email: str,
    *,
    include_roles: bool,
) -> User | None:
    statement = select(User).where(func.lower(User.email) == email.lower())
    if include_roles:
        statement = statement.options(selectinload(User.roles))

    return await session.scalar(statement)


async def _ensure_user_role(session: AsyncSession) -> Role:
    statement = select(Role).where(Role.name == ROLE_USER)
    role = await session.scalar(statement)
    if role is not None:
        return role

    role = Role(
        name=ROLE_USER,
        description="Default application role.",
    )
    session.add(role)
    await session.flush()
    return role


async def _is_password_reset_rate_limited(
    session: AsyncSession,
    *,
    user_id: int,
    settings: Settings,
) -> bool:
    now = utc_now()
    window_start = now - timedelta(minutes=settings.password_reset_rate_limit_window_minutes)
    count_statement = select(func.count(PasswordResetToken.id)).where(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.created_at >= window_start,
    )
    recent_count = int(await session.scalar(count_statement) or 0)
    if recent_count >= settings.password_reset_rate_limit_max_requests:
        return True

    last_statement = (
        select(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id)
        .order_by(PasswordResetToken.created_at.desc())
    )
    last_request = await session.scalar(last_statement)
    if (
        last_request is not None
        and now - last_request.created_at < timedelta(seconds=settings.password_reset_cooldown_seconds)
    ):
        return True

    return False


async def _invalidate_active_reset_tokens(
    session: AsyncSession,
    *,
    user_id: int,
    now,
) -> None:
    active_statement = select(PasswordResetToken).where(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > now,
    )
    active_tokens = (await session.scalars(active_statement)).all()
    for token in active_tokens:
        token.used_at = now


async def _enforce_verification_rate_limit(
    session: AsyncSession,
    *,
    user_id: int,
    settings: Settings,
) -> None:
    window_start = utc_now() - timedelta(minutes=settings.email_verification_rate_limit_window_minutes)
    count_statement = select(func.count(EmailVerificationToken.id)).where(
        EmailVerificationToken.user_id == user_id,
        EmailVerificationToken.created_at >= window_start,
    )
    recent_count = int(await session.scalar(count_statement) or 0)
    if recent_count >= settings.email_verification_rate_limit_max_requests:
        raise AppException(
            code="email_verification_rate_limited",
            message="Too many verification requests. Please try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


async def _create_email_verification_token(
    session: AsyncSession,
    *,
    user_id: int,
    settings: Settings,
) -> str:
    raw_token = generate_secure_token()
    token = EmailVerificationToken(
        user_id=user_id,
        token_hash=hash_token(raw_token),
        expires_at=utc_now() + timedelta(minutes=settings.email_verification_token_expire_minutes),
    )
    session.add(token)
    await session.flush()
    return raw_token


async def _verify_email_token(session: AsyncSession, token_value: str) -> str:
    token_hash = hash_token(token_value)
    statement = (
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == token_hash)
        .order_by(EmailVerificationToken.created_at.desc())
    )
    token_record = await session.scalar(statement)
    if token_record is None:
        raise AppException(
            code="invalid_verification_token",
            message="Verification token is invalid.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    now = utc_now()
    if token_record.expires_at < now:
        raise AppException(
            code="verification_token_expired",
            message="Verification token has expired.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = await session.get(User, token_record.user_id)
    if user is None:
        raise AppException(
            code="user_not_found",
            message="User associated with token was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if token_record.verified_at is not None or user.email_verified_at is not None:
        return "Email is already verified."

    token_record.verified_at = now
    user.email_verified_at = now
    await session.commit()
    return "Email verified successfully."


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_200_OK,
)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RegisterResponse | JSONResponse:
    existing_user = await _get_user_by_email(session, request.email, include_roles=False)
    if existing_user is not None:
        return _message_response(status.HTTP_409_CONFLICT, "Email has already been used.")

    default_role = await _ensure_user_role(session)
    resolved_full_name = request.resolved_full_name
    user = User(
        email=request.email,
        password_hash=get_password_hash(request.password),
        full_name=resolved_full_name,
        display_name=resolved_full_name,
        phone_number=request.phone_number,
        tier="Bronze",
        email_verified_at=utc_now(),
    )
    user.roles.append(default_role)
    session.add(user)
    await session.commit()

    return RegisterResponse(message="Registration successful.")


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
    jwt_service: JWTService = Depends(get_jwt_service),
    settings: Settings = Depends(get_settings),
) -> LoginResponse | JSONResponse:
    user = await _get_user_by_email(session, request.email, include_roles=True)
    if user is None or not verify_password(request.password, user.password_hash):
        return _message_response(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")

    if not user.is_active:
        return _message_response(status.HTTP_403_FORBIDDEN, "Account has been locked.")

    role_names = sorted({role.name for role in user.roles})
    access_token = jwt_service.create_access_token(
        user_id=user.id,
        email=user.email,
        roles=role_names,
    )
    refresh_token = jwt_service.create_refresh_token()

    now = utc_now()
    user.last_login_at = now
    session.add(
        RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await session.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        email=user.email,
        full_name=(user.full_name or user.display_name or ""),
        roles=role_names,
    )


@router.post(
    "/forgot-password",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
)
async def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    email_service: EmailService = Depends(get_email_service),
) -> AuthMessageResponse:
    generic_response = AuthMessageResponse(message=GENERIC_RESET_MESSAGE)

    user = await _get_user_by_email(session, request.email, include_roles=False)
    if user is None:
        return generic_response

    if await _is_password_reset_rate_limited(session, user_id=user.id, settings=settings):
        return generic_response

    now = utc_now()
    await _invalidate_active_reset_tokens(session, user_id=user.id, now=now)

    raw_token = _generate_reset_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=now + timedelta(minutes=settings.password_reset_token_expire_minutes),
        request_ip=(http_request.client.host if http_request.client else None),
        user_agent=http_request.headers.get("user-agent"),
    )
    session.add(reset_token)
    await session.commit()

    try:
        await email_service.send_password_reset_email(
            to_email=user.email,
            token=raw_token,
            user_id=user.id,
            background_tasks=background_tasks,
        )
    except Exception:
        logger.exception("Failed to queue password reset email for %s", user.email)

    return generic_response


@router.get(
    "/reset-password/validate",
    response_model=ResetPasswordValidateResponse,
    status_code=status.HTTP_200_OK,
)
async def validate_reset_password_token(
    token: str | None = Query(default=None),
    email: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> ResetPasswordValidateResponse:
    now = utc_now()
    normalized_token = (token or "").strip()
    if not normalized_token:
        return ResetPasswordValidateResponse(is_valid=False)

    normalized_email = (email or "").strip()
    user_id: int | None = None
    if normalized_email:
        user = await _get_user_by_email(session, normalized_email, include_roles=False)
        if user is None:
            return ResetPasswordValidateResponse(is_valid=False)
        user_id = user.id

    statement = select(PasswordResetToken).where(
        PasswordResetToken.token_hash == hash_token(normalized_token)
    )
    if user_id is not None:
        statement = statement.where(PasswordResetToken.user_id == user_id)

    statement = statement.order_by(PasswordResetToken.created_at.desc())
    token_record = await session.scalar(statement)
    if (
        token_record is None
        or token_record.used_at is not None
        or token_record.expires_at < now
    ):
        return ResetPasswordValidateResponse(is_valid=False)

    return ResetPasswordValidateResponse(is_valid=True, expires_at=token_record.expires_at)


@router.post(
    "/reset-password",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
)
async def reset_password(
    request: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    email_service: EmailService = Depends(get_email_service),
) -> AuthMessageResponse | JSONResponse:
    normalized_email = request.email.strip()
    user = await _get_user_by_email(session, normalized_email, include_roles=False)
    if user is None:
        return _message_response(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token.")

    password_error = _validate_password_policy(request.new_password)
    if password_error:
        return _message_response(status.HTTP_400_BAD_REQUEST, password_error)

    if verify_password(request.new_password, user.password_hash):
        return _message_response(
            status.HTTP_400_BAD_REQUEST,
            "New password cannot be the same as your current password. Please choose a different one for better security.",
        )

    now = utc_now()
    token_hash_value = hash_token(request.reset_token.strip())
    token_statement = (
        select(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.token_hash == token_hash_value,
        )
        .order_by(PasswordResetToken.created_at.desc())
    )
    token_record = await session.scalar(token_statement)
    if (
        token_record is None
        or token_record.used_at is not None
        or token_record.expires_at < now
    ):
        return _message_response(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token.")

    user.password_hash = get_password_hash(request.new_password)
    user.updated_at = now
    token_record.used_at = now

    sibling_tokens_statement = select(PasswordResetToken).where(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != token_record.id,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > now,
    )
    sibling_tokens = (await session.scalars(sibling_tokens_statement)).all()
    for sibling_token in sibling_tokens:
        sibling_token.used_at = now

    refresh_tokens_statement = select(RefreshToken).where(RefreshToken.user_id == user.id)
    refresh_tokens = (await session.scalars(refresh_tokens_statement)).all()
    for refresh_token in refresh_tokens:
        await session.delete(refresh_token)

    await session.commit()

    try:
        await email_service.send_password_changed_email(
            to_email=user.email,
            user_id=user.id,
            raise_on_failure=True,
        )
    except Exception:
        logger.exception("Failed to send password changed email to %s", user.email)
        return _message_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Email service failed. Check SMTP config/logs.",
        )

    return AuthMessageResponse(message="Password has been reset successfully.")


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserProfileResponse | JSONResponse:
    user = await session.get(User, current_user.id)
    if user is None:
        return _message_response(status.HTTP_404_NOT_FOUND, "User not found.")
    return _build_user_profile(user)


@router.put(
    "/profile",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserProfileResponse | JSONResponse:
    user = await session.get(User, current_user.id)
    if user is None:
        return _message_response(status.HTTP_404_NOT_FOUND, "User not found.")

    wants_password_change = bool(
        (request.current_password or "").strip() or (request.new_password or "").strip()
    )
    if wants_password_change:
        if not (request.current_password or "").strip():
            return _message_response(status.HTTP_400_BAD_REQUEST, "Current password is required.")
        if not (request.new_password or "").strip():
            return _message_response(status.HTTP_400_BAD_REQUEST, "New password is required.")
        if not verify_password(request.current_password or "", user.password_hash):
            return _message_response(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")

        password_error = _validate_password_policy(request.new_password or "")
        if password_error:
            return _message_response(status.HTTP_400_BAD_REQUEST, password_error)

        if verify_password(request.new_password or "", user.password_hash):
            return _message_response(
                status.HTTP_400_BAD_REQUEST,
                "New password cannot be the same as your current password.",
            )

        user.password_hash = get_password_hash(request.new_password or "")

    user.full_name = request.full_name
    user.display_name = request.full_name
    user.phone_number = request.phone_number
    user.address = request.address
    user.updated_at = utc_now()

    await session.commit()
    await session.refresh(user)
    return _build_user_profile(user)


@router.get(
    "/profile",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def get_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    return _build_user_profile(current_user)


@router.post(
    "/verify-email",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_email_post(
    request: VerifyEmailRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuthMessageResponse:
    message = await _verify_email_token(session, request.token)
    return AuthMessageResponse(message=message)


@router.get(
    "/verify-email",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_email_get(
    token: str = Query(..., min_length=20),
    session: AsyncSession = Depends(get_db_session),
) -> AuthMessageResponse:
    message = await _verify_email_token(session, token)
    return AuthMessageResponse(message=message)


@router.post(
    "/resend-verification",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_verification(
    request: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    email_service: EmailService = Depends(get_email_service),
) -> AuthMessageResponse:
    generic_response = AuthMessageResponse(
        message="If an unverified account exists for that email, a verification email has been sent.",
    )

    user = await _get_user_by_email(session, request.email, include_roles=False)
    if user is None:
        return generic_response
    if user.email_verified_at is not None:
        return generic_response

    await _enforce_verification_rate_limit(session, user_id=user.id, settings=settings)

    verification_token = await _create_email_verification_token(
        session,
        user_id=user.id,
        settings=settings,
    )
    await session.commit()

    await email_service.send_verification_email(
        to_email=user.email,
        token=verification_token,
        user_id=user.id,
        background_tasks=background_tasks,
    )

    return generic_response

from __future__ import annotations

import asyncio
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.mixins import utc_now
from app.models.refresh_token import RefreshToken
from app.models.user import User


def _login(client: TestClient, *, email: str, password: str) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _find_refresh_token_record(client: TestClient, token_value: str) -> RefreshToken:
    async def _load() -> RefreshToken | None:
        session_factory = client.app.state.test_session_factory
        async with session_factory() as session:
            statement = (
                select(RefreshToken)
                .where(RefreshToken.token == token_value)
                .order_by(RefreshToken.id.desc())
            )
            return await session.scalar(statement)

    token_record = asyncio.run(_load())
    assert token_record is not None
    return token_record


def _expire_refresh_token(client: TestClient, token_value: str) -> None:
    async def _expire() -> None:
        session_factory = client.app.state.test_session_factory
        async with session_factory() as session:
            statement = (
                select(RefreshToken)
                .where(RefreshToken.token == token_value)
                .order_by(RefreshToken.id.desc())
            )
            token_record = await session.scalar(statement)
            assert token_record is not None
            token_record.expires_at = utc_now() - timedelta(minutes=1)
            await session.commit()

    asyncio.run(_expire())


def _revoke_refresh_token(client: TestClient, token_value: str) -> None:
    async def _revoke() -> None:
        session_factory = client.app.state.test_session_factory
        async with session_factory() as session:
            statement = (
                select(RefreshToken)
                .where(RefreshToken.token == token_value)
                .order_by(RefreshToken.id.desc())
            )
            token_record = await session.scalar(statement)
            assert token_record is not None
            token_record.revoked_at = utc_now()
            await session.commit()

    asyncio.run(_revoke())


def _set_user_active_for_refresh_token(
    client: TestClient,
    token_value: str,
    *,
    is_active: bool,
) -> None:
    async def _set_active() -> None:
        session_factory = client.app.state.test_session_factory
        async with session_factory() as session:
            statement = (
                select(RefreshToken)
                .where(RefreshToken.token == token_value)
                .order_by(RefreshToken.id.desc())
            )
            token_record = await session.scalar(statement)
            assert token_record is not None

            user = await session.get(User, token_record.user_id)
            assert user is not None
            user.is_active = is_active
            await session.commit()

    asyncio.run(_set_active())


def test_refresh_token_returns_new_access_token(client: TestClient) -> None:
    seed = client.app.state.seed_data
    login_payload = _login(
        client,
        email=seed["customer_email"],
        password=seed["password"],
    )

    response = client.post(
        "/api/auth/refresh",
        json={"refreshToken": login_payload["refreshToken"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["accessToken"]
    assert payload["expiresIn"] == 3600

    me_response = client.get(
        "/api/auth/me",
        headers=_auth_header(payload["accessToken"]),
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == seed["customer_email"]


def test_refresh_token_rejects_unknown_token(client: TestClient) -> None:
    response = client.post(
        "/api/auth/refresh",
        json={"refreshToken": "invalid-refresh-token-value-123456789"},
    )
    assert response.status_code == 401


def test_refresh_token_rejects_expired_token(client: TestClient) -> None:
    seed = client.app.state.seed_data
    login_payload = _login(
        client,
        email=seed["customer_email"],
        password=seed["password"],
    )
    refresh_token = login_payload["refreshToken"]
    _expire_refresh_token(client, refresh_token)

    response = client.post(
        "/api/auth/refresh",
        json={"refreshToken": refresh_token},
    )
    assert response.status_code == 401

    token_record = _find_refresh_token_record(client, refresh_token)
    assert token_record.revoked_at is not None


def test_refresh_token_rejects_revoked_token(client: TestClient) -> None:
    seed = client.app.state.seed_data
    login_payload = _login(
        client,
        email=seed["customer_email"],
        password=seed["password"],
    )
    refresh_token = login_payload["refreshToken"]
    _revoke_refresh_token(client, refresh_token)

    response = client.post(
        "/api/auth/refresh",
        json={"refreshToken": refresh_token},
    )
    assert response.status_code == 401


def test_refresh_token_rejects_inactive_user(client: TestClient) -> None:
    seed = client.app.state.seed_data
    login_payload = _login(
        client,
        email=seed["customer_email"],
        password=seed["password"],
    )
    refresh_token = login_payload["refreshToken"]
    _set_user_active_for_refresh_token(client, refresh_token, is_active=False)

    try:
        response = client.post(
            "/api/auth/refresh",
            json={"refreshToken": refresh_token},
        )
        assert response.status_code == 403
    finally:
        _set_user_active_for_refresh_token(client, refresh_token, is_active=True)

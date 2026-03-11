from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, *, email: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    return payload["accessToken"]


def test_register_with_nationality_persists_in_profile(client: TestClient) -> None:
    email = "nationality.with@example.com"
    password = "Password123!"
    register_response = client.post(
        "/api/auth/register",
        json={
            "fullName": "Nationality User",
            "email": email,
            "password": password,
            "nationality": "  Vietnamese  ",
        },
    )
    assert register_response.status_code == 200

    token = _login(client, email=email, password=password)
    profile_response = client.get("/api/auth/me", headers=_auth_header(token))

    assert profile_response.status_code == 200
    payload = profile_response.json()
    assert "nationality" in payload
    assert payload["nationality"] == "Vietnamese"


def test_register_without_nationality_is_allowed(client: TestClient) -> None:
    email = "nationality.none@example.com"
    password = "Password123!"
    register_response = client.post(
        "/api/auth/register",
        json={
            "fullName": "No Nationality User",
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 200

    token = _login(client, email=email, password=password)
    profile_response = client.get("/api/auth/me", headers=_auth_header(token))

    assert profile_response.status_code == 200
    payload = profile_response.json()
    assert "nationality" in payload
    assert payload["nationality"] is None


def test_existing_user_without_nationality_still_has_valid_profile_response(client: TestClient) -> None:
    seed = client.app.state.seed_data
    token = _login(
        client,
        email=seed["smoke_email"],
        password=seed["password"],
    )

    profile_response = client.get("/api/auth/me", headers=_auth_header(token))
    assert profile_response.status_code == 200
    payload = profile_response.json()
    assert "nationality" in payload
    assert payload["nationality"] is None


def test_profile_update_can_change_nationality(client: TestClient) -> None:
    seed = client.app.state.seed_data
    token = _login(
        client,
        email=seed["customer_email"],
        password=seed["password"],
    )

    update_response = client.put(
        "/api/auth/profile",
        headers=_auth_header(token),
        json={
            "fullName": "Customer User",
            "phoneNumber": "0900000001",
            "address": "123 Legacy Street",
            "nationality": "Japan",
        },
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["nationality"] == "Japan"

    profile_response = client.get("/api/auth/me", headers=_auth_header(token))
    assert profile_response.status_code == 200
    profile_payload = profile_response.json()
    assert profile_payload["nationality"] == "Japan"


def test_profile_update_without_nationality_field_remains_compatible(client: TestClient) -> None:
    seed = client.app.state.seed_data
    token = _login(
        client,
        email=seed["customer_email"],
        password=seed["password"],
    )

    set_nationality_response = client.put(
        "/api/auth/profile",
        headers=_auth_header(token),
        json={
            "fullName": "Customer User",
            "phoneNumber": "0900000001",
            "address": "123 Legacy Street",
            "nationality": "Korea",
        },
    )
    assert set_nationality_response.status_code == 200
    assert set_nationality_response.json()["nationality"] == "Korea"

    update_response = client.put(
        "/api/auth/profile",
        headers=_auth_header(token),
        json={
            "fullName": "Customer User",
            "phoneNumber": "0900000001",
            "address": "123 Legacy Street",
        },
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert "nationality" in update_payload
    assert update_payload["nationality"] == "Korea"

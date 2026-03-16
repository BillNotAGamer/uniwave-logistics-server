from __future__ import annotations

from fastapi.testclient import TestClient


def test_auth_login_smoke(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "email": "smoke@example.com",
            "password": "Password123!",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accessToken"]
    assert payload["refreshToken"]
    assert payload["tokenType"] == "bearer"
    assert payload["email"] == "smoke@example.com"


def test_auth_login_legacy_case_route_smoke(client: TestClient) -> None:
    response = client.post(
        "/api/Auth/login",
        json={
            "email": "smoke@example.com",
            "password": "Password123!",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accessToken"]
    assert payload["refreshToken"]


def test_quote_estimate_legacy_case_route_smoke(client: TestClient) -> None:
    response = client.post(
        "/api/Quote/estimate",
        json={
            "pickupAddress": "A street",
            "dropoffAddress": "B street",
            "distanceKm": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["vehicles"]


def test_weather_forecast_legacy_alias_smoke(client: TestClient) -> None:
    response = client.get("/WeatherForecast")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload
    assert "temperatureC" in payload[0]


def test_public_blog_endpoint_smoke(client: TestClient) -> None:
    response = client.get("/api/blogs/public")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload
    assert any(item["slug"] == "smoke-post" for item in payload)

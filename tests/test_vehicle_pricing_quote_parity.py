from __future__ import annotations

import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.quote_lead import QuoteLead
from app.services.jwt import get_jwt_service


def _issue_access_token(
    *,
    user_id: int,
    email: str,
    roles: list[str],
) -> str:
    jwt_service = get_jwt_service()
    return jwt_service.create_access_token(
        user_id=user_id,
        email=email,
        roles=roles,
    )


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_public_vehicles_list_parity(client: TestClient) -> None:
    response = client.get("/api/vehicles")
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)
    assert payload
    assert all(item["isActive"] is True for item in payload)

    capacities = [item["capacityKg"] for item in payload]
    assert capacities == sorted(capacities)

    first = payload[0]
    assert "code" in first
    assert "name" in first
    assert "capacityKg" in first
    assert "lengthM" in first
    assert "widthM" in first
    assert "heightM" in first
    assert "imageUrl" in first


def test_admin_vehicle_crud_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    token = _issue_access_token(
        user_id=int(seed["admin_id"]),
        email=seed["admin_email"],
        roles=["Admin"],
    )
    auth = _auth_header(token)

    admin_list = client.get("/api/vehicles/admin", headers=auth)
    assert admin_list.status_code == 200
    list_payload = admin_list.json()
    assert any(item["code"] == "INACTIVE_OLD" and item["isActive"] is False for item in list_payload)

    create_response = client.post(
        "/api/vehicles/admin",
        headers=auth,
        json={
            "name": "Parity Truck",
            "code": "PARITY_TRUCK",
            "capacityKg": 700,
            "lengthM": 2.5,
            "widthM": 1.6,
            "heightM": 1.7,
            "imageUrl": None,
            "isActive": True,
        },
    )
    assert create_response.status_code == 201
    vehicle_id = create_response.json()["id"]

    detail_response = client.get(f"/api/vehicles/admin/{vehicle_id}", headers=auth)
    assert detail_response.status_code == 200
    assert detail_response.json()["code"] == "PARITY_TRUCK"

    update_response = client.put(
        f"/api/vehicles/admin/{vehicle_id}",
        headers=auth,
        json={
            "name": "Parity Truck Updated",
            "code": "PARITY_TRUCK_2",
            "capacityKg": 750,
            "lengthM": 2.6,
            "widthM": 1.7,
            "heightM": 1.8,
            "imageUrl": "/img/parity.svg",
            "isActive": True,
        },
    )
    assert update_response.status_code == 204

    delete_response = client.delete(f"/api/vehicles/admin/{vehicle_id}", headers=auth)
    assert delete_response.status_code == 204

    deactivated_detail = client.get(f"/api/vehicles/admin/{vehicle_id}", headers=auth)
    assert deactivated_detail.status_code == 200
    assert deactivated_detail.json()["isActive"] is False


def test_vehicle_pricing_crud_and_admin_boundary_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    unauthorized = client.get("/api/vehiclepricing")
    assert unauthorized.status_code == 401

    token = _issue_access_token(
        user_id=int(seed["admin_id"]),
        email=seed["admin_email"],
        roles=["Admin"],
    )
    auth = _auth_header(token)

    list_response = client.get("/api/vehiclepricing", headers=auth)
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert isinstance(list_payload, list)
    assert list_payload
    assert "rate_2to10" in list_payload[0]
    assert "rate_10to15" in list_payload[0]
    assert "rate_15to40" in list_payload[0]
    assert "rate_Over40" in list_payload[0]

    create_response = client.post(
        "/api/vehiclepricing",
        headers=auth,
        json={
            "vehicleTypeId": int(seed["vehicle_type_id"]),
            "basePrice": 123000,
            "rate_2to10": 11000,
            "rate_10to15": 12000,
            "rate_15to40": 13000,
            "rate_Over40": 14000,
            "currency": "VND",
            "isActive": True,
        },
    )
    assert create_response.status_code == 201
    rule_id = create_response.json()["id"]

    detail_response = client.get(f"/api/vehiclepricing/{rule_id}", headers=auth)
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert Decimal(str(detail_payload["basePrice"])) == Decimal("123000")
    assert Decimal(str(detail_payload["rate_2to10"])) == Decimal("11000")

    update_response = client.put(
        f"/api/vehiclepricing/{rule_id}",
        headers=auth,
        json={
            "vehicleTypeId": int(seed["vehicle_type_id"]),
            "basePrice": 130000,
            "rate_2to10": 15000,
            "rate_10to15": 16000,
            "rate_15to40": 17000,
            "rate_Over40": 18000,
            "currency": "VND",
            "isActive": False,
        },
    )
    assert update_response.status_code == 204

    updated_detail = client.get(f"/api/vehiclepricing/{rule_id}", headers=auth)
    assert updated_detail.status_code == 200
    assert Decimal(str(updated_detail.json()["rate_2to10"])) == Decimal("15000")
    assert updated_detail.json()["isActive"] is False

    delete_response = client.delete(f"/api/vehiclepricing/{rule_id}", headers=auth)
    assert delete_response.status_code == 204
    assert client.get(f"/api/vehiclepricing/{rule_id}", headers=auth).status_code == 404


def test_quote_estimate_parity(client: TestClient) -> None:
    response = client.post(
        "/api/quote/estimate",
        json={
            "pickupAddress": "A street",
            "dropoffAddress": "B street",
            "distanceKm": 12,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert Decimal(str(payload["distanceKm"])) == Decimal("12")
    vehicles = payload["vehicles"]
    assert vehicles

    prices = [Decimal(str(item["estimatedPrice"])) for item in vehicles]
    assert prices == sorted(prices)
    assert vehicles[0]["vehicleCode"] == "MOTORCYCLE"
    assert Decimal(str(vehicles[0]["estimatedPrice"])) == Decimal("154000")
    assert vehicles[0]["imageUrl"] == "/image/price-check/image/motorcycle.svg"


def test_quote_lead_auth_and_user_linkage_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data

    unauthenticated = client.post(
        "/api/quote/lead",
        json={
            "customerName": "Customer User",
            "customerEmail": "customer@example.com",
            "pickupAddress": "A street",
            "dropoffAddress": "B street",
            "distanceKm": 12,
            "selectedVehicleTypeId": int(seed["quote_vehicle_type_id"]),
        },
    )
    assert unauthenticated.status_code == 401

    user_token = _issue_access_token(
        user_id=int(seed["customer_id"]),
        email=seed["customer_email"],
        roles=["User"],
    )
    authenticated = client.post(
        "/api/quote/lead",
        headers=_auth_header(user_token),
        json={
            "customerName": "Customer User",
            "customerEmail": "customer@example.com",
            "pickupAddress": "A street",
            "dropoffAddress": "B street",
            "distanceKm": 12,
            "selectedVehicleTypeId": int(seed["quote_vehicle_type_id"]),
        },
    )
    assert authenticated.status_code == 200
    assert "Uniwave" in authenticated.json()["message"]

    async def _load_latest_lead():
        session_factory = client.app.state.test_session_factory
        async with session_factory() as session:
            statement = (
                select(QuoteLead)
                .options(selectinload(QuoteLead.prices))
                .order_by(QuoteLead.id.desc())
            )
            return await session.scalar(statement)

    latest_lead = asyncio.run(_load_latest_lead())
    assert latest_lead is not None
    assert latest_lead.user_id == int(seed["customer_id"])
    assert latest_lead.email == seed["customer_email"]
    assert latest_lead.prices
    assert latest_lead.prices[0].vehicle_type_id == int(seed["quote_vehicle_type_id"])

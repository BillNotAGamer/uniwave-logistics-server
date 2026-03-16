from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.services.jwt import get_jwt_service
from app.utils.customer_id import customer_id_to_external


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


def test_orders_my_requires_complete_profile(client: TestClient) -> None:
    seed = client.app.state.seed_data
    token = _issue_access_token(
        user_id=int(seed["incomplete_id"]),
        email=seed["incomplete_email"],
        roles=["User"],
    )

    response = client.get("/api/orders/my", headers=_auth_header(token))

    assert response.status_code == 428
    assert response.json()["message"] == "Please complete your profile before viewing orders."


def test_orders_my_and_get_by_order_code_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    token = _issue_access_token(
        user_id=int(seed["customer_id"]),
        email=seed["customer_email"],
        roles=["User"],
    )

    list_response = client.get("/api/orders/my", headers=_auth_header(token))
    assert list_response.status_code == 200
    payload = list_response.json()
    assert isinstance(payload, list)
    assert payload
    assert payload[0]["orderCode"]
    UUID(payload[0]["id"])
    assert isinstance(payload[0]["currentStatus"], int)

    order_code = payload[0]["orderCode"]
    detail_response = client.get(f"/api/orders/{order_code}", headers=_auth_header(token))
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["orderCode"] == order_code
    assert isinstance(detail_payload["currentStatus"], int)
    assert "receiverName" in detail_payload
    assert "receiverPhone" in detail_payload
    assert "distanceKm" in detail_payload


def test_orders_admin_routes_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    admin_token = _issue_access_token(
        user_id=int(seed["admin_id"]),
        email=seed["admin_email"],
        roles=["Admin"],
    )
    auth = _auth_header(admin_token)

    list_response = client.get("/api/orders/admin", headers=auth)
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert isinstance(list_payload, list)

    customer_external_id = customer_id_to_external(int(seed["customer_id"]))
    filtered_list_response = client.get(
        f"/api/orders/admin?userId={customer_external_id}",
        headers=auth,
    )
    assert filtered_list_response.status_code == 200

    create_response = client.post(
        "/api/orders/admin",
        headers=auth,
        json={
            "userId": customer_external_id,
            "pickupAddress": "From A",
            "dropoffAddress": "To B",
            "receiverName": "Receiver A",
            "receiverPhone": "0900222333",
            "distanceKm": 10,
            "vehicleTypeId": int(seed["vehicle_type_id"]),
            "estimatedPrice": 200000,
            "finalPrice": 210000,
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    UUID(create_payload["id"])
    assert create_payload["orderCode"].startswith("VN-LOCAL-")

    created_id = create_payload["id"]
    created_code = create_payload["orderCode"]

    status_response = client.post(
        f"/api/orders/admin/{created_id}/status",
        headers=auth,
        json={
            "status": 2,
            "title": "In transit",
            "description": "Package departed",
            "location": "Warehouse A",
        },
    )
    assert status_response.status_code == 204

    detail_response = client.get(f"/api/orders/{created_code}", headers=auth)
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["orderCode"] == created_code
    assert detail_payload["currentStatus"] == 2


def test_admin_orders_crud_and_soft_delete_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    admin_token = _issue_access_token(
        user_id=int(seed["admin_id"]),
        email=seed["admin_email"],
        roles=["Admin"],
    )
    auth = _auth_header(admin_token)

    list_response = client.get("/api/admin/orders", headers=auth)
    assert list_response.status_code == 200
    assert "X-Total-Count" in list_response.headers
    assert isinstance(list_response.json(), list)

    create_response = client.post(
        "/api/admin/orders",
        headers=auth,
        json={
            "customerId": customer_id_to_external(int(seed["customer_id"])),
            "pickupAddress": "Start 1",
            "dropoffAddress": "End 1",
            "receiverName": "Receiver B",
            "receiverPhone": "0900333444",
            "distanceKm": 20,
            "vehicleTypeId": int(seed["vehicle_type_id"]),
            "estimatedPrice": 300000,
            "finalPrice": 350000,
            "status": 0,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    order_id = created["id"]
    UUID(order_id)
    assert created["customerId"] == customer_id_to_external(int(seed["customer_id"]))
    assert created["deliveryStatus"] == 0

    update_response = client.put(
        f"/api/admin/orders/{order_id}",
        headers=auth,
        json={
            "pickupAddress": "Start 2",
            "dropoffAddress": "End 2",
            "receiverName": "Receiver C",
            "receiverPhone": "0900444555",
            "distanceKm": 30,
            "vehicleTypeId": int(seed["vehicle_type_id"]),
            "estimatedPrice": 400000,
            "finalPrice": 450000,
            "status": 2,
            "title": "In transit",
            "description": "Updated route",
            "location": "Hub B",
        },
    )
    assert update_response.status_code == 204

    detail_response = client.get(f"/api/admin/orders/{order_id}", headers=auth)
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["deliveryStatus"] == 2

    delete_response = client.delete(f"/api/admin/orders/{order_id}", headers=auth)
    assert delete_response.status_code == 204

    deleted_detail = client.get(f"/api/admin/orders/{order_id}", headers=auth)
    assert deleted_detail.status_code == 404

    final_list = client.get("/api/admin/orders", headers=auth)
    assert final_list.status_code == 200
    assert all(item["id"] != order_id for item in final_list.json())


def test_tracking_by_order_code_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    order_code = seed["seed_order_code"]

    public_response = client.get(f"/api/tracking/{order_code}")
    assert public_response.status_code == 200
    payload = public_response.json()
    assert payload["orderCode"] == order_code
    assert "statusDisplay" in payload
    assert len(payload["steps"]) == 4
    assert isinstance(payload["history"], list)

    other_user_token = _issue_access_token(
        user_id=int(seed["smoke_id"]),
        email=seed["smoke_email"],
        roles=["User"],
    )
    forbidden_response = client.get(
        f"/api/tracking/{order_code}",
        headers=_auth_header(other_user_token),
    )
    assert forbidden_response.status_code == 403

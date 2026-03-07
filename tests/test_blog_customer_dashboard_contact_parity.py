from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models.email_log import EmailLog
from app.services.cloudinary import get_cloudinary_service
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


def test_admin_blog_crud_status_and_soft_delete_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    admin_token = _issue_access_token(
        user_id=int(seed["admin_id"]),
        email=seed["admin_email"],
        roles=["Admin"],
    )
    auth = _auth_header(admin_token)

    list_response = client.get("/api/admin/blogs", headers=auth)
    assert list_response.status_code == 200
    assert "X-Total-Count" in list_response.headers
    assert isinstance(list_response.json(), list)

    create_response = client.post(
        "/api/admin/blogs",
        headers=auth,
        json={
            "title": "Parity blog draft",
            "summary": "draft summary",
            "contentHtml": "<p>draft content</p>",
            "thumbnailUrl": "https://example.com/draft.png",
            "status": 0,
        },
    )
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]

    detail_response = client.get(f"/api/admin/blogs/{created_id}", headers=auth)
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["id"] == created_id
    assert detail_payload["status"] == 0
    assert detail_payload["summary"] == "draft summary"

    update_response = client.put(
        f"/api/admin/blogs/{created_id}",
        headers=auth,
        json={
            "title": "Parity blog published",
            "slug": "parity-blog-published",
            "summary": "published summary",
            "contentHtml": "<p>published content</p>",
            "thumbnailUrl": "https://example.com/published.png",
            "status": 1,
        },
    )
    assert update_response.status_code == 204

    updated_detail = client.get(f"/api/admin/blogs/{created_id}", headers=auth)
    assert updated_detail.status_code == 200
    updated_payload = updated_detail.json()
    assert updated_payload["status"] == 1
    assert updated_payload["slug"] == "parity-blog-published"
    assert updated_payload["publishedAt"] is not None

    delete_response = client.delete(f"/api/admin/blogs/{created_id}", headers=auth)
    assert delete_response.status_code == 204

    deleted_detail = client.get(f"/api/admin/blogs/{created_id}", headers=auth)
    assert deleted_detail.status_code == 404
    assert deleted_detail.json()["message"] == "Blog not found."


def test_admin_blog_upload_compatibility_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    admin_token = _issue_access_token(
        user_id=int(seed["admin_id"]),
        email=seed["admin_email"],
        roles=["Admin"],
    )
    auth = _auth_header(admin_token)

    class _FakeCloudinaryService:
        async def upload_image(self, *, file_bytes: bytes, filename: str | None = None) -> str:
            assert file_bytes
            return "https://cdn.example.com/blogs/uploaded-image.png"

    client.app.dependency_overrides[get_cloudinary_service] = lambda: _FakeCloudinaryService()
    try:
        upload_response = client.post(
            "/api/admin/blogs/upload",
            headers=auth,
            files={"file": ("thumb.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        )
    finally:
        client.app.dependency_overrides.pop(get_cloudinary_service, None)

    assert upload_response.status_code == 200
    payload = upload_response.json()
    assert payload["url"] == "https://cdn.example.com/blogs/uploaded-image.png"
    assert payload["path"] == "https://cdn.example.com/blogs/uploaded-image.png"


def test_public_blog_filtering_and_detail_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    admin_token = _issue_access_token(
        user_id=int(seed["admin_id"]),
        email=seed["admin_email"],
        roles=["Admin"],
    )
    auth = _auth_header(admin_token)

    published_create = client.post(
        "/api/admin/blogs",
        headers=auth,
        json={
            "title": "Public parity post",
            "slug": "public-parity-post",
            "summary": "public summary",
            "contentHtml": "<p>public content</p>",
            "status": 1,
        },
    )
    assert published_create.status_code == 201

    draft_create = client.post(
        "/api/admin/blogs",
        headers=auth,
        json={
            "title": "Draft hidden post",
            "slug": "draft-hidden-post",
            "summary": "draft summary",
            "contentHtml": "<p>draft content</p>",
            "status": 0,
        },
    )
    assert draft_create.status_code == 201

    public_list = client.get("/api/blogs/public")
    assert public_list.status_code == 200
    assert "X-Total-Count" in public_list.headers
    list_payload = public_list.json()
    assert isinstance(list_payload, list)
    slugs = {item["slug"] for item in list_payload}
    assert "public-parity-post" in slugs
    assert "draft-hidden-post" not in slugs

    public_detail = client.get("/api/blogs/public/public-parity-post")
    assert public_detail.status_code == 200
    assert public_detail.json()["contentHtml"] == "<p>public content</p>"

    hidden_detail = client.get("/api/blogs/public/draft-hidden-post")
    assert hidden_detail.status_code == 404
    assert hidden_detail.json()["message"] == "Bài viết không tồn tại hoặc chưa được xuất bản."


def test_admin_customers_list_and_detail_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    admin_token = _issue_access_token(
        user_id=int(seed["admin_id"]),
        email=seed["admin_email"],
        roles=["Admin"],
    )
    auth = _auth_header(admin_token)

    list_response = client.get("/api/admin/customers", headers=auth)
    assert list_response.status_code == 200
    assert "X-Total-Count" in list_response.headers
    payload = list_response.json()
    assert isinstance(payload, list)
    assert payload

    for item in payload:
        UUID(item["id"])

    customer_row = next(item for item in payload if item["email"] == seed["customer_email"])
    customer_external_id = customer_row["id"]
    detail_response = client.get(f"/api/admin/customers/{customer_external_id}", headers=auth)
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["id"] == customer_external_id
    assert isinstance(detail_payload["tier"], int)
    assert isinstance(detail_payload["orders"], list)
    assert detail_payload["orders"]
    first_order = detail_payload["orders"][0]
    UUID(first_order["id"])
    assert "orderCode" in first_order
    assert isinstance(first_order["deliveryStatus"], int)

    # Backward compatibility for already-migrated numeric clients.
    numeric_detail = client.get(f"/api/admin/customers/{int(seed['customer_id'])}", headers=auth)
    assert numeric_detail.status_code == 200
    assert numeric_detail.json()["id"] == customer_external_id

    non_customer = client.get(
        f"/api/admin/customers/{customer_id_to_external(int(seed['admin_id']))}",
        headers=auth,
    )
    assert non_customer.status_code == 404
    assert non_customer.json()["message"] == "Customer not found."


def test_admin_dashboard_contract_parity(client: TestClient) -> None:
    seed = client.app.state.seed_data
    admin_token = _issue_access_token(
        user_id=int(seed["admin_id"]),
        email=seed["admin_email"],
        roles=["Admin"],
    )
    auth = _auth_header(admin_token)

    response = client.get("/api/admin/dashboard", headers=auth)
    assert response.status_code == 200
    payload = response.json()

    assert set(payload.keys()) == {"blogs", "totalCustomers", "orders"}
    assert set(payload["blogs"].keys()) == {"draft", "published", "deleted"}
    assert set(payload["orders"].keys()) == {
        "draft",
        "carrierReceived",
        "inTransit",
        "delivered",
        "deliveryFailed",
        "cancelled",
    }
    assert isinstance(payload["totalCustomers"], int)


def test_contact_parity_response_and_email_side_effects(client: TestClient) -> None:
    before_sent = len(client.app.state.sent_emails)

    async def _count_email_logs() -> int:
        session_factory = client.app.state.test_session_factory
        async with session_factory() as session:
            statement = select(func.count(EmailLog.id))
            return int((await session.scalar(statement)) or 0)

    before_logs = asyncio.run(_count_email_logs())

    response = client.post(
        "/api/contact",
        json={
            "name": "Nguyen Van A",
            "phone": "0900123456",
            "email": "customer@example.com",
            "message": "Tôi cần báo giá vận chuyển nội thành.",
            "source": "homepage",
        },
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Thông tin liên hệ đã được gửi thành công. Cảm ơn bạn!"

    after_sent = len(client.app.state.sent_emails)
    assert after_sent - before_sent == 3

    sent_slice = client.app.state.sent_emails[before_sent:after_sent]
    recipients = {item["to_email"] for item in sent_slice}
    assert "sales@uniwave-logistics.com" in recipients
    assert "rachel.ho@uniwave-logistics.com" in recipients
    assert "customer@example.com" in recipients

    after_logs = asyncio.run(_count_email_logs())
    assert after_logs - before_logs == 3

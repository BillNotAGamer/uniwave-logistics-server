from __future__ import annotations

import asyncio
import importlib
import os
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.models.blog_post import BlogPost
from app.models.email_log import EmailLog
from app.models.mixins import utc_now
from app.models.order import Order
from app.models.order_status_history import OrderStatusHistory
from app.models.role import Role
from app.models.user import User
from app.models.vehicle_pricing_rule import VehiclePricingRule
from app.models.vehicle_type import VehicleType
from app.services.email import get_email_service


@pytest.fixture(scope="session")
def client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    db_dir: Path = tmp_path_factory.mktemp("db")
    db_path = db_dir / "smoke.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    os.environ["ENVIRONMENT"] = "test"
    os.environ["ENABLE_DEV_STARTUP_DB_CHECK"] = "false"
    os.environ["SEED_ADMIN_EMAIL"] = ""
    os.environ["SEED_ADMIN_PASSWORD"] = ""
    get_settings.cache_clear()

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False, future=True)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    seed_data: dict[str, str] = {
        "smoke_email": "smoke@example.com",
        "customer_email": "customer@example.com",
        "incomplete_email": "incomplete@example.com",
        "admin_email": "admin@example.com",
        "password": "Password123!",
    }

    async def _prepare_seed_data() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            role_user = Role(name="User", description="Default role.")
            role_admin = Role(name="Admin", description="Admin role.")
            session.add_all([role_user, role_admin])
            await session.flush()

            smoke_user = User(
                id=1,
                email=seed_data["smoke_email"],
                password_hash=get_password_hash(seed_data["password"]),
                display_name="Smoke User",
                is_active=True,
                email_verified_at=utc_now(),
            )
            smoke_user.roles.append(role_user)
            session.add(smoke_user)

            customer_user = User(
                id=2,
                email=seed_data["customer_email"],
                password_hash=get_password_hash(seed_data["password"]),
                display_name="Customer User",
                full_name="Customer User",
                phone_number="0900000001",
                address="123 Legacy Street",
                tier="Bronze",
                is_active=True,
                email_verified_at=utc_now(),
            )
            customer_user.roles.append(role_user)
            session.add(customer_user)

            incomplete_user = User(
                id=3,
                email=seed_data["incomplete_email"],
                password_hash=get_password_hash(seed_data["password"]),
                display_name="Incomplete User",
                full_name="Incomplete User",
                is_active=True,
                email_verified_at=utc_now(),
            )
            incomplete_user.roles.append(role_user)
            session.add(incomplete_user)

            admin_user = User(
                id=4,
                email=seed_data["admin_email"],
                password_hash=get_password_hash(seed_data["password"]),
                display_name="Admin User",
                full_name="Admin User",
                phone_number="0900000009",
                address="9 Admin Road",
                tier="Gold",
                is_active=True,
                email_verified_at=utc_now(),
            )
            admin_user.roles.append(role_admin)
            session.add(admin_user)
            await session.flush()

            blog_post = BlogPost(
                id=1,
                author_id=smoke_user.id,
                slug="smoke-post",
                title="Smoke Post",
                excerpt="Smoke test excerpt",
                content="Smoke test content",
                status=1,
                is_published=True,
                published_at=utc_now(),
            )
            session.add(blog_post)

            vehicle_motorcycle = VehicleType(
                id=1,
                code="MOTORCYCLE",
                name="Xe máy",
                capacity_kg=30,
                length_m=Decimal("0.5"),
                width_m=Decimal("0.4"),
                height_m=Decimal("0.5"),
                image_url=None,
                description="Seed motorcycle",
                is_active=True,
            )
            vehicle_van = VehicleType(
                id=2,
                code="VAN_500KG",
                name="Xe Van 500KG",
                capacity_kg=500,
                length_m=Decimal("1.7"),
                width_m=Decimal("1.2"),
                height_m=Decimal("1.2"),
                image_url=None,
                description="Seed van",
                is_active=True,
            )
            vehicle_inactive = VehicleType(
                id=3,
                code="INACTIVE_OLD",
                name="Inactive vehicle",
                capacity_kg=900,
                length_m=Decimal("2"),
                width_m=Decimal("1.5"),
                height_m=Decimal("1.5"),
                image_url=None,
                description="Seed inactive",
                is_active=False,
            )
            session.add_all([vehicle_motorcycle, vehicle_van, vehicle_inactive])
            await session.flush()

            pricing_motorcycle = VehiclePricingRule(
                id=1,
                vehicle_type_id=vehicle_motorcycle.id,
                rule_name="Pricing MOTORCYCLE",
                base_price=Decimal("30000"),
                rate_2to10=Decimal("12000"),
                rate_10to15=Decimal("14000"),
                rate_15to40=Decimal("16000"),
                rate_over40=Decimal("15000"),
                price_per_km=Decimal("12000"),
                minimum_price=None,
                currency_code="VND",
                currency="VND",
                effective_from=utc_now().replace(year=2025, month=1, day=1),
                effective_to=None,
                is_active=True,
                notes=None,
            )
            pricing_van = VehiclePricingRule(
                id=2,
                vehicle_type_id=vehicle_van.id,
                rule_name="Pricing VAN_500KG",
                base_price=Decimal("240000"),
                rate_2to10=Decimal("24000"),
                rate_10to15=Decimal("21000"),
                rate_15to40=Decimal("20000"),
                rate_over40=Decimal("18000"),
                price_per_km=Decimal("24000"),
                minimum_price=None,
                currency_code="VND",
                currency="VND",
                effective_from=utc_now().replace(year=2025, month=1, day=1),
                effective_to=None,
                is_active=True,
                notes=None,
            )
            session.add_all([pricing_motorcycle, pricing_van])

            order = Order(
                id=1,
                order_code="VN-LOCAL-20260306-1111",
                user_id=customer_user.id,
                vehicle_type_id=vehicle_van.id,
                status="created",
                pickup_address="A street",
                dropoff_address="B street",
                receiver_name="Receiver Name",
                receiver_phone="0900111222",
                distance_km=Decimal("12.5"),
                estimated_price=Decimal("150000"),
                final_price=None,
                subtotal_amount=Decimal("150000"),
                tax_amount=Decimal("0"),
                total_amount=Decimal("150000"),
                currency_code="VND",
            )
            session.add(order)
            await session.flush()

            history = OrderStatusHistory(
                id=1,
                order_id=order.id,
                previous_status=None,
                new_status="created",
                status="created",
                title="Đặt hàng thành công",
                description="Đơn hàng của quý khách đã được tạo và đang trong quá trình xử lý.",
                location=None,
                changed_by_user_id=None,
                changed_at=utc_now(),
                notes=None,
            )
            session.add(history)
            await session.commit()

            seed_data["customer_id"] = str(customer_user.id)
            seed_data["smoke_id"] = str(smoke_user.id)
            seed_data["incomplete_id"] = str(incomplete_user.id)
            seed_data["admin_id"] = str(admin_user.id)
            seed_data["vehicle_type_id"] = str(vehicle_van.id)
            seed_data["quote_vehicle_type_id"] = str(vehicle_motorcycle.id)
            seed_data["seed_order_code"] = order.order_code

    asyncio.run(_prepare_seed_data())

    main_module = importlib.import_module("main")
    app = main_module.create_app()
    app.state.seed_data = seed_data
    app.state.test_session_factory = session_factory
    app.state.sent_emails = []

    from app.db.session import get_db_session

    class _FakeEmailService:
        def __init__(self, session_factory, sent_emails: list[dict]) -> None:
            self._session_factory = session_factory
            self._sent_emails = sent_emails

        async def send_email(self, email, *args, **kwargs) -> None:
            self._sent_emails.append(
                {
                    "to_email": email.to_email,
                    "subject": email.subject,
                    "template_key": email.template_key,
                    "text_body": email.text_body,
                }
            )
            async with self._session_factory() as session:
                log = EmailLog(
                    user_id=email.user_id,
                    to_email=email.to_email,
                    subject=email.subject,
                    template_key=email.template_key,
                    provider_name="fake",
                    status="sent",
                    payload=email.payload,
                    sent_at=utc_now(),
                )
                session.add(log)
                await session.commit()

        async def send_password_reset_email(self, *args, **kwargs) -> None:
            return None

        async def send_password_changed_email(self, *args, **kwargs) -> None:
            return None

        async def send_verification_email(self, *args, **kwargs) -> None:
            return None

        async def send_order_created_detailed_email(self, *args, **kwargs) -> None:
            return None

        async def send_order_confirmation_to_customer(self, *args, **kwargs) -> None:
            return None

    fake_email_service = _FakeEmailService(session_factory, app.state.sent_emails)

    async def _override_get_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_email_service] = lambda: fake_email_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
    get_settings.cache_clear()

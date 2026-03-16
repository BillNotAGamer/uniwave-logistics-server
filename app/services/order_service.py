from __future__ import annotations

import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.models.mixins import utc_now
from app.models.user import User
from app.models.vehicle_type import VehicleType
from app.repositories.order_repository import OrderRepository
from app.schemas.orders_legacy import (
    LegacyAdminOrderCreateRequest,
    LegacyAdminOrderUpdateRequest,
    LegacyOrderCreateRequest,
    LegacyOrderStatusUpdateRequest,
    map_delivery_to_order_status,
    normalize_delivery_status,
)
from app.services.email import EmailService


@dataclass(slots=True)
class PaginationResult:
    offset: int | None
    limit: int | None
    page: int | None
    page_size: int | None
    is_unbounded: bool


class OrderService:
    def __init__(self, *, session: AsyncSession, repository: OrderRepository) -> None:
        self._session = session
        self._repository = repository

    @staticmethod
    def is_admin(user: User) -> bool:
        return any(role.name.lower() == "admin" for role in user.roles)

    @staticmethod
    def resolve_pagination(
        *,
        page: int | None,
        page_size: int | None,
        default_page_size: int,
        max_page_size: int,
        legacy_unbounded: bool,
    ) -> PaginationResult:
        if legacy_unbounded and page is None and page_size is None:
            return PaginationResult(
                offset=None,
                limit=None,
                page=None,
                page_size=None,
                is_unbounded=True,
            )

        resolved_page = page or 1
        resolved_page_size = page_size or default_page_size
        if resolved_page_size > max_page_size:
            raise AppException(
                code="invalid_page_size",
                message="Requested page_size exceeds the configured maximum.",
                status_code=400,
            )

        return PaginationResult(
            offset=(resolved_page - 1) * resolved_page_size,
            limit=resolved_page_size,
            page=resolved_page,
            page_size=resolved_page_size,
            is_unbounded=False,
        )

    async def list_my_orders(self, *, user_id: int):
        return await self._repository.list_my_orders(user_id=user_id)

    async def get_order_by_code_for_user(
        self,
        *,
        order_code: str,
        requester: User,
    ):
        order = await self._repository.get_order_by_code(order_code=order_code)
        if order is None:
            raise AppException(
                code="order_not_found",
                message="Order not found.",
                status_code=404,
            )

        if not self.is_admin(requester) and order.user_id != requester.id:
            raise AppException(
                code="forbidden",
                message="You cannot access this order.",
                status_code=403,
            )

        return order

    async def list_orders_for_orders_controller_admin(self, *, user_id: int | None = None):
        return await self._repository.list_orders_for_admin(user_id=user_id)

    async def create_order_for_orders_controller_admin(
        self,
        *,
        request: LegacyOrderCreateRequest,
        email_service: EmailService,
    ):
        user = await self._session.get(User, request.user_id)
        if user is None:
            raise AppException(
                code="user_not_found",
                message="UserId does not exist.",
                status_code=400,
            )

        vehicle = await self._session.get(VehicleType, request.vehicle_type_id)
        if vehicle is None:
            raise AppException(
                code="vehicle_type_not_found",
                message="VehicleTypeId does not exist.",
                status_code=400,
            )

        order_code = await self._generate_order_code()
        order = await self._repository.create_order(
            order_code=order_code,
            user_id=user.id,
            pickup_address=request.pickup_address,
            dropoff_address=request.dropoff_address,
            receiver_name=request.receiver_name,
            receiver_phone=request.receiver_phone,
            distance_km=request.distance_km,
            vehicle_type_id=request.vehicle_type_id,
            estimated_price=request.estimated_price,
            final_price=request.final_price,
            status="created",
        )
        await self._repository.append_status_history(
            order_id=order.id,
            status="created",
            title="Order created successfully",
            description="Your order has been created and is being processed.",
            location=None,
            changed_by_user_id=None,
            previous_status=None,
            new_status="created",
        )
        await self._session.commit()

        await email_service.send_order_created_detailed_email(
            to_email=user.email,
            customer_name=user.full_name or user.display_name or user.email,
            order_code=order_code,
            receiver_name=request.receiver_name,
            receiver_phone=request.receiver_phone,
            pickup_address=request.pickup_address,
            dropoff_address=request.dropoff_address,
            distance_km=request.distance_km,
            estimated_price=request.estimated_price,
            raise_on_failure=True,
        )

        return await self._repository.get_order_by_code(order_code=order_code)

    async def add_status_for_orders_controller_admin(
        self,
        *,
        order_id: int,
        request: LegacyOrderStatusUpdateRequest,
        admin_user_id: int,
    ) -> None:
        order = await self._repository.get_order_by_id(order_id=order_id, for_update=True)
        if order is None:
            raise AppException(
                code="order_not_found",
                message="Order not found.",
                status_code=404,
            )

        previous_status = order.status
        order.status = request.status
        order.updated_at = utc_now()

        await self._repository.append_status_history(
            order_id=order.id,
            status=request.status,
            title=request.title,
            description=request.description,
            location=request.location,
            changed_by_user_id=admin_user_id,
            previous_status=previous_status,
            new_status=request.status,
        )
        await self._session.commit()

    async def list_admin_orders(
        self,
        *,
        status_filter: int | str | None,
        page: int,
        page_size: int,
        user_id: int | None = None,
    ):
        statuses: set[str] | None = None
        if status_filter is not None:
            try:
                delivery_status = normalize_delivery_status(status_filter)
            except ValueError as exc:
                raise AppException(
                    code="invalid_delivery_status",
                    message="Invalid delivery status.",
                    status_code=400,
                ) from exc
            if delivery_status == "draft":
                statuses = {"created"}
            elif delivery_status == "carrier_received":
                statuses = {"preparing"}
            elif delivery_status == "in_transit":
                statuses = {"in_transit", "at_local_warehouse", "out_for_delivery"}
            elif delivery_status == "delivered":
                statuses = {"delivered"}
            elif delivery_status == "delivery_failed":
                statuses = {"delivery_failed"}
            elif delivery_status == "cancelled":
                statuses = {"cancelled"}

        total = await self._repository.count_admin_orders(statuses=statuses, user_id=user_id)
        rows = await self._repository.list_admin_orders(
            statuses=statuses,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
        return rows, total

    async def get_admin_order_by_id(self, *, order_id: int):
        order = await self._repository.get_order_by_id(order_id=order_id, include_history=True)
        if order is None:
            raise AppException(
                code="order_not_found",
                message="Order not found.",
                status_code=404,
            )
        return order

    async def create_admin_order(
        self,
        *,
        request: LegacyAdminOrderCreateRequest,
        admin_user_id: int,
        email_service: EmailService,
    ):
        user_statement = (
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == request.customer_id)
        )
        customer = await self._session.scalar(user_statement)
        if customer is None:
            raise AppException(
                code="customer_not_found",
                message="Customer not found.",
                status_code=400,
            )
        if not any(role.name == "User" for role in customer.roles):
            raise AppException(
                code="invalid_customer",
                message="User is not a customer.",
                status_code=400,
            )

        vehicle = await self._session.get(VehicleType, request.vehicle_type_id)
        if vehicle is None:
            raise AppException(
                code="vehicle_type_not_found",
                message="VehicleTypeId does not exist.",
                status_code=400,
            )

        order_code = await self._generate_order_code()
        status = map_delivery_to_order_status(request.status)
        order = await self._repository.create_order(
            order_code=order_code,
            user_id=request.customer_id,
            pickup_address=request.pickup_address,
            dropoff_address=request.dropoff_address,
            receiver_name=request.receiver_name,
            receiver_phone=request.receiver_phone,
            distance_km=request.distance_km,
            vehicle_type_id=request.vehicle_type_id,
            estimated_price=request.estimated_price,
            final_price=request.final_price,
            status=status,
        )
        await self._repository.append_status_history(
            order_id=order.id,
            status=status,
            title=self._build_status_title(status),
            description=None,
            location=None,
            changed_by_user_id=admin_user_id,
            previous_status=None,
            new_status=status,
        )
        await self._session.commit()

        await email_service.send_order_confirmation_to_customer(
            to_email=customer.email,
            customer_name=customer.full_name or customer.display_name or customer.email,
            order_code=order_code,
            raise_on_failure=False,
        )

        return await self._repository.get_order_by_code(order_code=order_code, include_history=True)

    async def update_admin_order(
        self,
        *,
        order_id: int,
        request: LegacyAdminOrderUpdateRequest,
        admin_user_id: int,
    ) -> None:
        vehicle = await self._session.get(VehicleType, request.vehicle_type_id)
        if vehicle is None:
            raise AppException(
                code="vehicle_type_not_found",
                message="VehicleTypeId does not exist.",
                status_code=400,
            )

        new_status = map_delivery_to_order_status(request.status)
        order = await self._repository.get_order_by_id(order_id=order_id, for_update=True)
        if order is None:
            raise AppException(
                code="order_not_found",
                message="Order not found.",
                status_code=404,
            )

        status_changed = order.status != new_status
        previous_status = order.status

        order.pickup_address = request.pickup_address
        order.dropoff_address = request.dropoff_address
        order.receiver_name = request.receiver_name
        order.receiver_phone = request.receiver_phone
        order.distance_km = request.distance_km
        order.vehicle_type_id = request.vehicle_type_id
        order.estimated_price = request.estimated_price
        order.final_price = request.final_price
        order.status = new_status
        order.updated_at = utc_now()

        order.subtotal_amount = request.estimated_price
        order.total_amount = request.final_price if request.final_price is not None else request.estimated_price

        if status_changed:
            title = request.title.strip() if request.title and request.title.strip() else self._build_status_title(new_status)
            await self._repository.append_status_history(
                order_id=order.id,
                status=new_status,
                title=title,
                description=request.description.strip() if request.description and request.description.strip() else None,
                location=request.location.strip() if request.location and request.location.strip() else None,
                changed_by_user_id=admin_user_id,
                previous_status=previous_status,
                new_status=new_status,
            )
        await self._session.commit()

    async def delete_admin_order(self, *, order_id: int, admin_user_id: int) -> None:
        order = await self._repository.get_order_by_id(order_id=order_id, for_update=True)
        if order is None:
            raise AppException(
                code="order_not_found",
                message="Order not found.",
                status_code=404,
            )
        await self._repository.soft_delete_order(order=order, changed_by_user_id=admin_user_id)
        await self._session.commit()

    async def get_tracking_order(self, *, order_code: str, requester: User | None):
        order = await self._repository.get_order_by_code(order_code=order_code, include_history=True)
        if order is None:
            raise AppException(
                code="tracking_not_found",
                message="Tracking code not found.",
                status_code=404,
            )

        if requester is not None and not self.is_admin(requester) and order.user_id != requester.id:
            raise AppException(
                code="forbidden",
                message="You cannot access this order tracking record.",
                status_code=403,
            )

        return order

    async def _generate_order_code(self) -> str:
        date_part = utc_now().strftime("%Y%m%d")
        for _ in range(12):
            random_part = secrets.randbelow(9000) + 1000
            candidate = f"VN-LOCAL-{date_part}-{random_part}"
            if not await self._repository.order_code_exists(order_code=candidate):
                return candidate

        raise AppException(
            code="order_code_generation_failed",
            message="Unable to generate a unique order code.",
            status_code=500,
        )

    @staticmethod
    def _build_status_title(status: str) -> str:
        mapping = {
            "created": "Order created",
            "preparing": "Carrier received",
            "in_transit": "In transit",
            "at_local_warehouse": "Arrived at local warehouse",
            "out_for_delivery": "Out for delivery",
            "delivered": "Delivered",
            "delivery_failed": "Delivery failed",
            "cancelled": "Order cancelled",
            "deleted": "Order deleted",
        }
        return mapping.get(status, "Order update")

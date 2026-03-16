from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.models.order import Order
from app.models.order_status_history import OrderStatusHistory
from app.schemas.base import APIModel
from app.schemas.pagination import PaginationMeta


VALID_ORDER_STATUSES = {
    "created",
    "pending",
    "confirmed",
    "in_progress",
    "completed",
    "cancelled",
}


def _normalize_currency_code(value: str) -> str:
    return value.strip().upper()


def _normalize_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in VALID_ORDER_STATUSES:
        raise ValueError("Invalid order status.")
    return normalized


class OrderCreateRequest(APIModel):
    quote_lead_id: int | None = Field(default=None, ge=1)
    vehicle_type_id: int | None = Field(default=None, ge=1)
    pickup_address: str = Field(min_length=1)
    dropoff_address: str = Field(min_length=1)
    scheduled_at: datetime | None = None
    subtotal_amount: Decimal
    tax_amount: Decimal = Decimal("0")
    total_amount: Decimal
    currency_code: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return _normalize_currency_code(value)


class OrderUpdateRequest(APIModel):
    quote_lead_id: int | None = Field(default=None, ge=1)
    vehicle_type_id: int | None = Field(default=None, ge=1)
    pickup_address: str | None = Field(default=None, min_length=1)
    dropoff_address: str | None = Field(default=None, min_length=1)
    scheduled_at: datetime | None = None
    subtotal_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_currency_code(value)


class OrderCancelRequest(APIModel):
    reason: str | None = Field(default=None, max_length=500)


class AdminOrderCreateRequest(OrderCreateRequest):
    user_id: int = Field(ge=1)
    order_code: str | None = Field(default=None, min_length=3, max_length=64)
    status: str = Field(default="created", min_length=3, max_length=32)
    status_note: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        return _normalize_status(value)


class AdminOrderUpdateRequest(OrderUpdateRequest):
    order_code: str | None = Field(default=None, min_length=3, max_length=64)
    status: str | None = Field(default=None, min_length=3, max_length=32)
    status_note: str | None = Field(default=None, max_length=500)
    user_id: int | None = Field(default=None, ge=1)

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_status(value)


class OrderStatusHistoryRead(APIModel):
    id: int
    previous_status: str | None = None
    new_status: str
    changed_at: datetime
    changed_by_user_id: int | None = None
    changed_by_email: str | None = None
    notes: str | None = None

    @classmethod
    def from_model(cls, history: OrderStatusHistory) -> "OrderStatusHistoryRead":
        changed_by_email = None
        if history.changed_by_user is not None:
            changed_by_email = history.changed_by_user.email

        return cls(
            id=history.id,
            previous_status=history.previous_status,
            new_status=history.new_status,
            changed_at=history.changed_at,
            changed_by_user_id=history.changed_by_user_id,
            changed_by_email=changed_by_email,
            notes=history.notes,
        )


class OrderRead(APIModel):
    id: int
    order_code: str
    user_id: int
    user_email: str | None = None
    quote_lead_id: int | None = None
    vehicle_type_id: int | None = None
    vehicle_type_code: str | None = None
    vehicle_type_name: str | None = None
    status: str
    pickup_address: str
    dropoff_address: str
    scheduled_at: datetime | None = None
    subtotal_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency_code: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, order: Order) -> "OrderRead":
        vehicle_type_code = order.vehicle_type.code if order.vehicle_type is not None else None
        vehicle_type_name = order.vehicle_type.name if order.vehicle_type is not None else None
        user_email = order.user.email if order.user is not None else None

        return cls(
            id=order.id,
            order_code=order.order_code,
            user_id=order.user_id,
            user_email=user_email,
            quote_lead_id=order.quote_lead_id,
            vehicle_type_id=order.vehicle_type_id,
            vehicle_type_code=vehicle_type_code,
            vehicle_type_name=vehicle_type_name,
            status=order.status,
            pickup_address=order.pickup_address,
            dropoff_address=order.dropoff_address,
            scheduled_at=order.scheduled_at,
            subtotal_amount=order.subtotal_amount,
            tax_amount=order.tax_amount,
            total_amount=order.total_amount,
            currency_code=order.currency_code,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )


class OrderDetailResponse(APIModel):
    order: OrderRead
    status_history: list[OrderStatusHistoryRead]


class OrderListResponse(APIModel):
    items: list[OrderRead]
    pagination: PaginationMeta


class OrderTrackingResponse(APIModel):
    order_id: int
    order_code: str
    current_status: str
    timeline: list[OrderStatusHistoryRead]
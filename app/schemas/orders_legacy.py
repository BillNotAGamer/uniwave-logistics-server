from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator

from app.models.order import Order
from app.models.order_status_history import OrderStatusHistory
from app.schemas.base import APIModel
from app.utils.customer_id import customer_id_to_external, resolve_customer_identifier
from app.utils.order_id import order_id_to_external

ORDER_STATUS_CODE_TO_NAME: dict[int, str] = {
    0: "created",
    1: "preparing",
    2: "in_transit",
    3: "at_local_warehouse",
    4: "out_for_delivery",
    5: "delivered",
    6: "delivery_failed",
    7: "cancelled",
    8: "deleted",
}
ORDER_STATUS_NAME_TO_CODE: dict[str, int] = {value: key for key, value in ORDER_STATUS_CODE_TO_NAME.items()}

DELIVERY_STATUS_CODE_TO_NAME: dict[int, str] = {
    0: "draft",
    1: "carrier_received",
    2: "in_transit",
    3: "delivered",
    4: "delivery_failed",
    5: "cancelled",
}
DELIVERY_STATUS_NAME_TO_CODE: dict[str, int] = {
    value: key for key, value in DELIVERY_STATUS_CODE_TO_NAME.items()
}

DELIVERY_TO_ORDER_STATUS: dict[str, str] = {
    "draft": "created",
    "carrier_received": "preparing",
    "in_transit": "in_transit",
    "delivered": "delivered",
    "delivery_failed": "delivery_failed",
    "cancelled": "cancelled",
}


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def normalize_order_status(value: int | str) -> str:
    if isinstance(value, int):
        if value not in ORDER_STATUS_CODE_TO_NAME:
            raise ValueError("Invalid order status.")
        return ORDER_STATUS_CODE_TO_NAME[value]

    normalized = _normalize_key(value)
    aliases = {
        "intransit": "in_transit",
        "atlocalwarehouse": "at_local_warehouse",
        "outfordelivery": "out_for_delivery",
        "deliveryfailed": "delivery_failed",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in ORDER_STATUS_NAME_TO_CODE:
        raise ValueError("Invalid order status.")
    return normalized


def normalize_delivery_status(value: int | str) -> str:
    if isinstance(value, int):
        if value not in DELIVERY_STATUS_CODE_TO_NAME:
            raise ValueError("Invalid delivery status.")
        return DELIVERY_STATUS_CODE_TO_NAME[value]

    normalized = _normalize_key(value)
    aliases = {
        "carrierreceived": "carrier_received",
        "intransit": "in_transit",
        "deliveryfailed": "delivery_failed",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in DELIVERY_STATUS_NAME_TO_CODE:
        raise ValueError("Invalid delivery status.")
    return normalized


def order_status_code(status: str) -> int:
    return ORDER_STATUS_NAME_TO_CODE.get(status, ORDER_STATUS_NAME_TO_CODE["created"])


def delivery_status_code(status: str) -> int:
    return DELIVERY_STATUS_NAME_TO_CODE.get(status, DELIVERY_STATUS_NAME_TO_CODE["draft"])


def map_delivery_to_order_status(delivery_status: str) -> str:
    return DELIVERY_TO_ORDER_STATUS.get(delivery_status, "created")


def map_order_to_delivery_status(order_status: str) -> str:
    if order_status == "created":
        return "draft"
    if order_status == "preparing":
        return "carrier_received"
    if order_status in {"in_transit", "at_local_warehouse", "out_for_delivery"}:
        return "in_transit"
    if order_status == "delivered":
        return "delivered"
    if order_status == "delivery_failed":
        return "delivery_failed"
    if order_status == "cancelled":
        return "cancelled"
    return "draft"


def build_order_status_label(status: str) -> str:
    return {
        "created": "Ordered",
        "preparing": "Carrier received",
        "in_transit": "In transit",
        "at_local_warehouse": "At local warehouse",
        "out_for_delivery": "Out for delivery",
        "delivered": "Delivered",
        "delivery_failed": "Delivery failed",
        "cancelled": "Cancelled",
        "deleted": "Deleted",
    }.get(status, "Unknown")


class LegacyOrderCreateRequest(APIModel):
    user_id: int = Field(ge=1)
    pickup_address: str = Field(min_length=1, max_length=500)
    dropoff_address: str = Field(min_length=1, max_length=500)
    receiver_name: str = Field(min_length=1, max_length=200)
    receiver_phone: str = Field(min_length=1, max_length=20)
    distance_km: Decimal = Field(ge=0, le=10000)
    vehicle_type_id: int = Field(ge=1)
    estimated_price: Decimal = Field(ge=0, le=1_000_000_000)
    final_price: Decimal | None = Field(default=None, ge=0, le=1_000_000_000)

    @field_validator("user_id", mode="before")
    @classmethod
    def parse_user_id(cls, value: Any) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return resolve_customer_identifier(value)
            except ValueError as exc:
                raise ValueError("Invalid user identifier.") from exc
        raise ValueError("Invalid user identifier.")


class LegacyOrderStatusUpdateRequest(APIModel):
    status: str
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=200)

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> str:
        if isinstance(value, (int, str)):
            return normalize_order_status(value)
        raise ValueError("Invalid order status.")


class LegacyAdminOrderCreateRequest(APIModel):
    customer_id: int = Field(ge=1)
    pickup_address: str = Field(min_length=1, max_length=500)
    dropoff_address: str = Field(min_length=1, max_length=500)
    receiver_name: str = Field(min_length=1, max_length=200)
    receiver_phone: str = Field(min_length=1, max_length=20)
    distance_km: Decimal = Field(ge=0, le=10000)
    vehicle_type_id: int = Field(ge=1)
    estimated_price: Decimal = Field(ge=0, le=1_000_000_000)
    final_price: Decimal | None = Field(default=None, ge=0, le=1_000_000_000)
    status: str = "draft"

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> str:
        if isinstance(value, (int, str)):
            return normalize_delivery_status(value)
        raise ValueError("Invalid delivery status.")

    @field_validator("customer_id", mode="before")
    @classmethod
    def parse_customer_id(cls, value: Any) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return resolve_customer_identifier(value)
            except ValueError as exc:
                raise ValueError("Invalid customer identifier.") from exc
        raise ValueError("Invalid customer identifier.")


class LegacyAdminOrderUpdateRequest(APIModel):
    pickup_address: str = Field(min_length=1, max_length=500)
    dropoff_address: str = Field(min_length=1, max_length=500)
    receiver_name: str = Field(min_length=1, max_length=200)
    receiver_phone: str = Field(min_length=1, max_length=20)
    distance_km: Decimal = Field(ge=0, le=10000)
    vehicle_type_id: int = Field(ge=1)
    estimated_price: Decimal = Field(ge=0, le=1_000_000_000)
    final_price: Decimal | None = Field(default=None, ge=0, le=1_000_000_000)
    status: str
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=200)

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> str:
        if isinstance(value, (int, str)):
            return normalize_delivery_status(value)
        raise ValueError("Invalid delivery status.")


class LegacyOrderSummaryRead(APIModel):
    id: str
    order_code: str
    created_at: datetime
    current_status: int
    pickup_address: str
    dropoff_address: str
    estimated_price: Decimal
    final_price: Decimal | None = None

    @classmethod
    def from_model(cls, order: Order) -> "LegacyOrderSummaryRead":
        return cls(
            id=order_id_to_external(order.id),
            order_code=order.order_code,
            created_at=order.created_at,
            current_status=order_status_code(order.status),
            pickup_address=order.pickup_address,
            dropoff_address=order.dropoff_address,
            estimated_price=Decimal(str(order.estimated_price or order.total_amount)),
            final_price=(
                Decimal(str(order.final_price))
                if order.final_price is not None
                else None
            ),
        )


class LegacyOrderDetailRead(APIModel):
    id: str
    order_code: str
    created_at: datetime
    current_status: int
    pickup_address: str
    dropoff_address: str
    receiver_name: str
    receiver_phone: str
    distance_km: Decimal
    vehicle_type_id: int | None = None
    vehicle_name: str
    estimated_price: Decimal
    final_price: Decimal | None = None

    @classmethod
    def from_model(cls, order: Order) -> "LegacyOrderDetailRead":
        vehicle_name = order.vehicle_type.name if order.vehicle_type is not None else "Unknown"
        return cls(
            id=order_id_to_external(order.id),
            order_code=order.order_code,
            created_at=order.created_at,
            current_status=order_status_code(order.status),
            pickup_address=order.pickup_address,
            dropoff_address=order.dropoff_address,
            receiver_name=order.receiver_name or "",
            receiver_phone=order.receiver_phone or "",
            distance_km=Decimal(str(order.distance_km or 0)),
            vehicle_type_id=order.vehicle_type_id,
            vehicle_name=vehicle_name,
            estimated_price=Decimal(str(order.estimated_price or order.total_amount)),
            final_price=(
                Decimal(str(order.final_price))
                if order.final_price is not None
                else None
            ),
        )


class LegacyAdminOrderListItemRead(APIModel):
    id: str
    order_code: str
    customer_id: str
    customer_name: str | None = None
    customer_email: str | None = None
    delivery_status: int
    created_at: datetime
    updated_at: datetime | None = None
    pickup_address: str
    dropoff_address: str
    estimated_price: Decimal
    final_price: Decimal | None = None

    @classmethod
    def from_model(cls, order: Order) -> "LegacyAdminOrderListItemRead":
        customer_name = None
        customer_email = None
        if order.user is not None:
            customer_name = order.user.full_name or order.user.display_name or order.user.email
            customer_email = order.user.email

        return cls(
            id=order_id_to_external(order.id),
            order_code=order.order_code,
            customer_id=customer_id_to_external(order.user_id),
            customer_name=customer_name,
            customer_email=customer_email,
            delivery_status=delivery_status_code(map_order_to_delivery_status(order.status)),
            created_at=order.created_at,
            updated_at=order.updated_at,
            pickup_address=order.pickup_address,
            dropoff_address=order.dropoff_address,
            estimated_price=Decimal(str(order.estimated_price or order.total_amount)),
            final_price=Decimal(str(order.final_price)) if order.final_price is not None else None,
        )


class LegacyAdminOrderDetailRead(APIModel):
    id: str
    order_code: str
    customer_id: str
    customer_name: str | None = None
    customer_email: str | None = None
    delivery_status: int
    created_at: datetime
    updated_at: datetime | None = None
    pickup_address: str
    dropoff_address: str
    receiver_name: str
    receiver_phone: str
    distance_km: Decimal
    vehicle_type_id: int | None = None
    vehicle_name: str | None = None
    estimated_price: Decimal
    final_price: Decimal | None = None

    @classmethod
    def from_model(cls, order: Order) -> "LegacyAdminOrderDetailRead":
        customer_name = None
        customer_email = None
        if order.user is not None:
            customer_name = order.user.full_name or order.user.display_name or order.user.email
            customer_email = order.user.email

        return cls(
            id=order_id_to_external(order.id),
            order_code=order.order_code,
            customer_id=customer_id_to_external(order.user_id),
            customer_name=customer_name,
            customer_email=customer_email,
            delivery_status=delivery_status_code(map_order_to_delivery_status(order.status)),
            created_at=order.created_at,
            updated_at=order.updated_at,
            pickup_address=order.pickup_address,
            dropoff_address=order.dropoff_address,
            receiver_name=order.receiver_name or "",
            receiver_phone=order.receiver_phone or "",
            distance_km=Decimal(str(order.distance_km or 0)),
            vehicle_type_id=order.vehicle_type_id,
            vehicle_name=(order.vehicle_type.name if order.vehicle_type is not None else None),
            estimated_price=Decimal(str(order.estimated_price or order.total_amount)),
            final_price=Decimal(str(order.final_price)) if order.final_price is not None else None,
        )


class LegacyTrackingStatusDisplayRead(APIModel):
    text: str
    color: str
    icon: str


class LegacyTrackingStepRead(APIModel):
    key: str
    label: str
    completed: bool
    completed_at: datetime | None = None
    icon: str


class LegacyTrackingEntryRead(APIModel):
    created_at: datetime
    status: str
    title: str | None = None
    description: str | None = None
    location: str | None = None

    @classmethod
    def from_model(cls, history: OrderStatusHistory) -> "LegacyTrackingEntryRead":
        status_key = history.status or history.new_status
        return cls(
            created_at=history.created_at,
            status=build_order_status_label(status_key),
            title=history.title,
            description=history.description,
            location=history.location,
        )


def build_tracking_status_display(status: str) -> LegacyTrackingStatusDisplayRead:
    mapping: dict[str, tuple[str, str, str]] = {
        "delivered": ("ĐƠN HÀNG ĐÃ HOÀN THÀNH", "#27ae60", "check-circle"),
        "delivery_failed": ("GIAO HÀNG THẤT BẠI", "#ef4444", "alert"),
        "cancelled": ("ĐƠN HÀNG ĐÃ HỦY", "#94a3b8", "alert"),
        "preparing": ("ĐƠN HÀNG ĐÃ ĐƯỢC TIẾP NHẬN", "#f59e0b", "wallet"),
        "in_transit": ("ĐƠN HÀNG ĐANG VẬN CHUYỂN", "#f59e0b", "truck"),
        "at_local_warehouse": ("ĐƠN HÀNG ĐÃ ĐẾN KHO", "#f59e0b", "truck"),
        "out_for_delivery": ("ĐƠN HÀNG ĐANG GIAO", "#f59e0b", "truck"),
        "created": ("ĐƠN HÀNG ĐÃ ĐƯỢC TẠO", "#2563eb", "document"),
    }
    text, color, icon = mapping.get(status, ("CẬP NHẬT ĐƠN HÀNG", "#2563eb", "document"))
    return LegacyTrackingStatusDisplayRead(text=text, color=color, icon=icon)


def _status_rank(status: str) -> int:
    if status == "created":
        return 0
    if status == "preparing":
        return 1
    if status in {"in_transit", "at_local_warehouse", "out_for_delivery", "delivery_failed"}:
        return 2
    if status == "delivered":
        return 3
    return 0


def build_tracking_steps(order: Order) -> list[LegacyTrackingStepRead]:
    definitions: list[tuple[str, str, str, set[str]]] = [
        ("ORDERED", "Đặt hàng", "document", {"created"}),
        ("CONFIRMED", "Tiếp nhận", "wallet", {"preparing"}),
        (
            "IN_TRANSIT",
            "Đang vận chuyển",
            "truck",
            {"in_transit", "at_local_warehouse", "out_for_delivery"},
        ),
        ("DELIVERED", "Nhận hàng", "box", {"delivered"}),
    ]

    history = list(order.status_history or [])
    current_rank = _status_rank(order.status)
    for entry in history:
        status_key = entry.status or entry.new_status
        rank = _status_rank(status_key)
        if rank > current_rank:
            current_rank = rank

    steps: list[LegacyTrackingStepRead] = []
    for index, (key, label, icon, statuses) in enumerate(definitions):
        completed_at = next(
            (
                h.created_at
                for h in sorted(history, key=lambda item: item.created_at)
                if (h.status or h.new_status) in statuses
            ),
            None,
        )

        completed = completed_at is not None or index <= current_rank
        if completed_at is None and "created" in statuses:
            completed_at = order.created_at

        steps.append(
            LegacyTrackingStepRead(
                key=key,
                label=label,
                icon=icon,
                completed=completed,
                completed_at=completed_at,
            )
        )
    return steps


class LegacyTrackingResponseRead(APIModel):
    order_code: str
    current_status: str
    status_display: LegacyTrackingStatusDisplayRead
    steps: list[LegacyTrackingStepRead]
    receiver_name: str
    receiver_phone: str
    pickup_address: str
    dropoff_address: str
    distance_km: Decimal
    vehicle_name: str
    history: list[LegacyTrackingEntryRead]

    @classmethod
    def from_model(cls, order: Order) -> "LegacyTrackingResponseRead":
        history = sorted(order.status_history or [], key=lambda item: item.created_at, reverse=True)
        return cls(
            order_code=order.order_code,
            current_status=build_order_status_label(order.status),
            status_display=build_tracking_status_display(order.status),
            steps=build_tracking_steps(order),
            receiver_name=order.receiver_name or "",
            receiver_phone=order.receiver_phone or "",
            pickup_address=order.pickup_address,
            dropoff_address=order.dropoff_address,
            distance_km=Decimal(str(order.distance_km or 0)),
            vehicle_name=(order.vehicle_type.name if order.vehicle_type is not None else "Unknown"),
            history=[LegacyTrackingEntryRead.from_model(item) for item in history],
        )

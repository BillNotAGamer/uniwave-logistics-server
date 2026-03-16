from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.schemas.base import APIModel

USER_TIER_CODE_TO_NAME: dict[int, str] = {
    0: "Bronze",
    1: "Silver",
    2: "Gold",
}
USER_TIER_NAME_TO_CODE: dict[str, int] = {
    value.lower(): key for key, value in USER_TIER_CODE_TO_NAME.items()
}


def normalize_tier_code(tier: str | None) -> int:
    if not tier:
        return 0
    return USER_TIER_NAME_TO_CODE.get(tier.strip().lower(), 0)


class CustomerAdminListItemRead(APIModel):
    id: str
    email: str
    full_name: str | None = None
    phone_number: str | None = None
    tier: int
    is_active: bool
    created_at: datetime


class CustomerOrderSummaryRead(APIModel):
    id: str
    order_code: str
    delivery_status: int
    created_at: datetime
    estimated_price: Decimal
    final_price: Decimal | None = None


class CustomerAdminDetailRead(APIModel):
    id: str
    email: str
    full_name: str | None = None
    phone_number: str | None = None
    address: str | None = None
    tier: int
    is_active: bool
    created_at: datetime
    orders: list[CustomerOrderSummaryRead]

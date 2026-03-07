from __future__ import annotations

from decimal import Decimal

from app.repositories.customer_repository import CustomerRepository
from app.schemas.customers import (
    CustomerAdminDetailRead,
    CustomerAdminListItemRead,
    CustomerOrderSummaryRead,
    normalize_tier_code,
)
from app.schemas.orders_legacy import delivery_status_code, map_order_to_delivery_status
from app.utils.customer_id import customer_id_to_external, resolve_customer_identifier
from app.utils.order_id import order_id_to_external


class CustomerAdminService:
    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository

    @staticmethod
    def normalize_legacy_paging(*, page: int, page_size: int) -> tuple[int, int]:
        normalized_page = page if page > 0 else 1
        normalized_page_size = page_size if 0 < page_size <= 50 else 10
        return normalized_page, normalized_page_size

    async def list_customers(
        self,
        *,
        search: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[CustomerAdminListItemRead], int]:
        normalized_page, normalized_page_size = self.normalize_legacy_paging(
            page=page,
            page_size=page_size,
        )
        offset = (normalized_page - 1) * normalized_page_size

        rows = await self._repository.list_customers(
            search=search,
            offset=offset,
            limit=normalized_page_size,
        )
        total = await self._repository.count_customers(search=search)

        items = [
            CustomerAdminListItemRead(
                id=customer_id_to_external(user.id),
                email=user.email,
                full_name=user.full_name,
                phone_number=user.phone_number,
                tier=normalize_tier_code(user.tier),
                is_active=user.is_active,
                created_at=user.created_at,
            )
            for user in rows
        ]
        return items, total

    async def get_customer_detail(self, *, customer_identifier: str) -> CustomerAdminDetailRead | None:
        try:
            customer_id = resolve_customer_identifier(customer_identifier)
        except ValueError:
            return None

        user = await self._repository.get_customer_by_id(customer_id)
        if user is None:
            return None

        orders = await self._repository.list_customer_orders(user_id=customer_id)
        order_items = [
            CustomerOrderSummaryRead(
                id=order_id_to_external(order.id),
                order_code=order.order_code,
                delivery_status=delivery_status_code(map_order_to_delivery_status(order.status)),
                created_at=order.created_at,
                estimated_price=Decimal(str(order.estimated_price or order.total_amount or 0)),
                final_price=Decimal(str(order.final_price)) if order.final_price is not None else None,
            )
            for order in orders
        ]

        return CustomerAdminDetailRead(
            id=customer_id_to_external(user.id),
            email=user.email,
            full_name=user.full_name,
            phone_number=user.phone_number,
            address=user.address,
            tier=normalize_tier_code(user.tier),
            is_active=user.is_active,
            created_at=user.created_at,
            orders=order_items,
        )

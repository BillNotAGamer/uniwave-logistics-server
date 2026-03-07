from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mixins import utc_now
from app.models.order import Order
from app.models.order_status_history import OrderStatusHistory


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _is_sqlite(self) -> bool:
        bind = self._session.get_bind()
        return bool(bind is not None and bind.dialect.name == "sqlite")

    async def _next_id(self, model_cls) -> int:
        statement = select(func.coalesce(func.max(model_cls.id), 0) + 1)
        value = await self._session.scalar(statement)
        return int(value or 1)

    def _base_statement(self, *, include_history: bool = False):
        statement = select(Order).options(
            selectinload(Order.user),
            selectinload(Order.vehicle_type),
        )
        if include_history:
            statement = statement.options(
                selectinload(Order.status_history).selectinload(OrderStatusHistory.changed_by_user)
            )
        return statement

    async def list_my_orders(self, *, user_id: int) -> list[Order]:
        statement = (
            self._base_statement()
            .where(Order.user_id == user_id, Order.status != "deleted")
            .order_by(Order.created_at.desc())
        )
        rows = await self._session.scalars(statement)
        return list(rows)

    async def list_orders_for_admin(self, *, user_id: int | None = None) -> list[Order]:
        statement = self._base_statement().where(Order.status != "deleted")
        if user_id is not None:
            statement = statement.where(Order.user_id == user_id)
        statement = statement.order_by(Order.created_at.desc())
        rows = await self._session.scalars(statement)
        return list(rows)

    async def count_admin_orders(
        self,
        *,
        statuses: set[str] | None = None,
        user_id: int | None = None,
    ) -> int:
        statement = select(func.count(Order.id)).where(Order.status != "deleted")
        if user_id is not None:
            statement = statement.where(Order.user_id == user_id)
        if statuses:
            statement = statement.where(Order.status.in_(statuses))
        total = await self._session.scalar(statement)
        return int(total or 0)

    async def list_admin_orders(
        self,
        *,
        statuses: set[str] | None = None,
        user_id: int | None = None,
        page: int,
        page_size: int,
    ) -> list[Order]:
        statement = self._base_statement().where(Order.status != "deleted")
        if user_id is not None:
            statement = statement.where(Order.user_id == user_id)
        if statuses:
            statement = statement.where(Order.status.in_(statuses))

        statement = statement.order_by(Order.created_at.desc())
        statement = statement.offset((page - 1) * page_size).limit(page_size)
        rows = await self._session.scalars(statement)
        return list(rows)

    async def get_order_by_code(
        self,
        *,
        order_code: str,
        include_history: bool = False,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> Order | None:
        statement = self._base_statement(include_history=include_history).where(
            func.lower(Order.order_code) == order_code.lower()
        )
        if not include_deleted:
            statement = statement.where(Order.status != "deleted")
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_order_by_id(
        self,
        *,
        order_id: int,
        include_history: bool = False,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> Order | None:
        statement = self._base_statement(include_history=include_history).where(Order.id == order_id)
        if not include_deleted:
            statement = statement.where(Order.status != "deleted")
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def order_code_exists(
        self,
        *,
        order_code: str,
        exclude_order_id: int | None = None,
    ) -> bool:
        statement = select(Order.id).where(func.lower(Order.order_code) == order_code.lower())
        if exclude_order_id is not None:
            statement = statement.where(Order.id != exclude_order_id)
        existing = await self._session.scalar(statement)
        return existing is not None

    async def create_order(
        self,
        *,
        order_code: str,
        user_id: int,
        pickup_address: str,
        dropoff_address: str,
        receiver_name: str,
        receiver_phone: str,
        distance_km: Decimal,
        vehicle_type_id: int,
        estimated_price: Decimal,
        final_price: Decimal | None,
        status: str,
        quote_lead_id: int | None = None,
        scheduled_at: datetime | None = None,
        subtotal_amount: Decimal | None = None,
        tax_amount: Decimal | None = None,
        total_amount: Decimal | None = None,
        currency_code: str = "VND",
    ) -> Order:
        resolved_subtotal = subtotal_amount if subtotal_amount is not None else estimated_price
        resolved_tax = tax_amount if tax_amount is not None else Decimal("0")
        resolved_total = total_amount
        if resolved_total is None:
            resolved_total = final_price if final_price is not None else estimated_price

        order_id: int | None = None
        if self._is_sqlite():
            order_id = await self._next_id(Order)

        entity = Order(
            id=order_id,
            order_code=order_code,
            user_id=user_id,
            quote_lead_id=quote_lead_id,
            vehicle_type_id=vehicle_type_id,
            status=status,
            pickup_address=pickup_address,
            dropoff_address=dropoff_address,
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
            distance_km=distance_km,
            estimated_price=estimated_price,
            final_price=final_price,
            scheduled_at=scheduled_at,
            subtotal_amount=resolved_subtotal,
            tax_amount=resolved_tax,
            total_amount=resolved_total,
            currency_code=currency_code,
        )
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def append_status_history(
        self,
        *,
        order_id: int,
        status: str,
        title: str | None,
        description: str | None,
        location: str | None,
        changed_by_user_id: int | None,
        previous_status: str | None = None,
        new_status: str | None = None,
    ) -> OrderStatusHistory:
        now = utc_now()
        history_id: int | None = None
        if self._is_sqlite():
            history_id = await self._next_id(OrderStatusHistory)

        history = OrderStatusHistory(
            id=history_id,
            order_id=order_id,
            status=status,
            title=title,
            description=description,
            location=location,
            previous_status=previous_status,
            new_status=new_status or status,
            changed_by_user_id=changed_by_user_id,
            changed_at=now,
            created_at=now,
            notes=description,
        )
        self._session.add(history)
        await self._session.flush()
        return history

    async def soft_delete_order(self, *, order: Order, changed_by_user_id: int | None) -> None:
        previous_status = order.status
        order.status = "deleted"
        order.updated_at = utc_now()
        await self.append_status_history(
            order_id=order.id,
            status="deleted",
            title="Order deleted",
            description=None,
            location=None,
            changed_by_user_id=changed_by_user_id,
            previous_status=previous_status,
            new_status="deleted",
        )

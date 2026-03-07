from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order
from app.models.role import Role
from app.models.user import User


class CustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _apply_search(statement, *, search: str | None):
        if not search:
            return statement

        normalized = search.strip()
        if not normalized:
            return statement

        like_pattern = f"%{normalized}%"
        return statement.where(
            User.email.ilike(like_pattern)
            | func.coalesce(User.full_name, "").ilike(like_pattern)
        )

    async def count_customers(self, *, search: str | None = None) -> int:
        statement = (
            select(func.count(func.distinct(User.id)))
            .join(User.roles)
            .where(Role.name == "User")
        )
        statement = self._apply_search(statement, search=search)
        total = await self._session.scalar(statement)
        return int(total or 0)

    async def list_customers(
        self,
        *,
        search: str | None = None,
        offset: int,
        limit: int,
    ) -> list[User]:
        statement = (
            select(User)
            .join(User.roles)
            .where(Role.name == "User")
            .options(selectinload(User.roles))
            .order_by(User.created_at.desc())
            .distinct()
            .offset(offset)
            .limit(limit)
        )
        statement = self._apply_search(statement, search=search)

        rows = await self._session.scalars(statement)
        return list(rows)

    async def get_customer_by_id(self, user_id: int) -> User | None:
        statement = (
            select(User)
            .options(selectinload(User.roles))
            .where(
                User.id == user_id,
                User.roles.any(Role.name == "User"),
            )
        )
        return await self._session.scalar(statement)

    async def list_customer_orders(self, *, user_id: int) -> list[Order]:
        statement = (
            select(Order)
            .where(
                Order.user_id == user_id,
                Order.status != "deleted",
            )
            .order_by(Order.created_at.desc())
        )
        rows = await self._session.scalars(statement)
        return list(rows)

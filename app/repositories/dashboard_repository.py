from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blog_post import BlogPost
from app.models.order import Order
from app.models.role import Role
from app.models.user import User


class DashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_blog_status_counts(self) -> list[tuple[int, int]]:
        statement = (
            select(BlogPost.status, func.count(BlogPost.id).label("count"))
            .group_by(BlogPost.status)
        )
        result = await self._session.execute(statement)
        return [(int(status), int(count or 0)) for status, count in result.all()]

    async def get_total_customers(self) -> int:
        statement = (
            select(func.count(func.distinct(User.id)))
            .join(User.roles)
            .where(Role.name == "User")
        )
        total = await self._session.scalar(statement)
        return int(total or 0)

    async def get_order_status_counts(self) -> list[tuple[str, int]]:
        statement = (
            select(Order.status, func.count(Order.id).label("count"))
            .where(Order.status != "deleted")
            .group_by(Order.status)
        )
        result = await self._session.execute(statement)
        return [(str(status), int(count or 0)) for status, count in result.all()]

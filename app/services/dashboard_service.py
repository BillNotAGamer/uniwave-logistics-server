from __future__ import annotations

from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.blog import BLOG_STATUS_DELETED, BLOG_STATUS_DRAFT, BLOG_STATUS_PUBLISHED
from app.schemas.dashboard import BlogStatusStatsRead, DashboardStatsRead, OrderStatusStatsRead


class DashboardService:
    def __init__(self, repository: DashboardRepository) -> None:
        self._repository = repository

    async def get_dashboard(self) -> DashboardStatsRead:
        blog_counts = await self._repository.get_blog_status_counts()
        order_counts = await self._repository.get_order_status_counts()
        total_customers = await self._repository.get_total_customers()

        blogs = BlogStatusStatsRead()
        for status, count in blog_counts:
            if status == BLOG_STATUS_DRAFT:
                blogs.draft = count
            elif status == BLOG_STATUS_PUBLISHED:
                blogs.published = count
            elif status == BLOG_STATUS_DELETED:
                blogs.deleted = count

        orders = OrderStatusStatsRead()
        for status, count in order_counts:
            if status == "created":
                orders.draft += count
            elif status == "preparing":
                orders.carrier_received += count
            elif status in {"in_transit", "at_local_warehouse", "out_for_delivery"}:
                orders.in_transit += count
            elif status == "delivered":
                orders.delivered += count
            elif status == "delivery_failed":
                orders.delivery_failed += count
            elif status == "cancelled":
                orders.cancelled += count

        return DashboardStatsRead(
            blogs=blogs,
            total_customers=total_customers,
            orders=orders,
        )

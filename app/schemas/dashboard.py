from __future__ import annotations

from app.schemas.base import APIModel


class BlogStatusStatsRead(APIModel):
    draft: int = 0
    published: int = 0
    deleted: int = 0


class OrderStatusStatsRead(APIModel):
    draft: int = 0
    carrier_received: int = 0
    in_transit: int = 0
    delivered: int = 0
    delivery_failed: int = 0
    cancelled: int = 0


class DashboardStatsRead(APIModel):
    blogs: BlogStatusStatsRead
    total_customers: int
    orders: OrderStatusStatsRead

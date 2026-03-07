from app.api.routers.admin_customers import router as admin_customers_router
from app.api.routers.admin_dashboard import router as admin_dashboard_router
from app.api.routers.admin_blogs import router as admin_blogs_router
from app.api.routers.admin_orders import router as admin_orders_router
from app.api.routers.auth import router as auth_router
from app.api.routers.blog_public import router as blog_public_router
from app.api.routers.contact import router as contact_router
from app.api.routers.orders import router as orders_router
from app.api.routers.quote import router as quote_router
from app.api.routers.tracking import router as tracking_router
from app.api.routers.vehicle_pricing import router as vehicle_pricing_router
from app.api.routers.vehicles import router as vehicles_router

__all__ = [
    "auth_router",
    "vehicles_router",
    "vehicle_pricing_router",
    "orders_router",
    "tracking_router",
    "quote_router",
    "contact_router",
    "blog_public_router",
    "admin_orders_router",
    "admin_customers_router",
    "admin_dashboard_router",
    "admin_blogs_router",
]

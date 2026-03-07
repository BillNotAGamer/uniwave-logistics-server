from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.admin_blogs import router as admin_blogs_router
from app.api.routers.admin_customers import router as admin_customers_router
from app.api.routers.admin_dashboard import router as admin_dashboard_router
from app.api.routers.admin_orders import router as admin_orders_router
from app.api.routers.auth import router as auth_router
from app.api.routers.blog_public import router as blog_public_router
from app.api.routers.contact import router as contact_router
from app.api.routers.orders import router as orders_router
from app.api.routers.quote import router as quote_router
from app.api.routers.tracking import router as tracking_router
from app.api.routers.vehicle_pricing import router as vehicle_pricing_router
from app.api.routers.vehicles import router as vehicles_router
from app.core.config import get_settings
from app.core.error_handlers import ErrorHandlingMiddleware, register_exception_handlers
from app.core.legacy_path_case import LegacyPathCaseCompatibilityMiddleware
from app.core.logging import configure_logging
from app.db.session import run_dev_startup_db_check
from app.routers import api_router
from app.routers.weather_forecast_legacy import router as weather_forecast_legacy_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if not settings.is_production and settings.enable_dev_startup_db_check:
            await run_dev_startup_db_check(
                require_alembic_version=settings.dev_startup_require_alembic_version,
            )
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LegacyPathCaseCompatibilityMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(auth_router)
    app.include_router(vehicles_router)
    app.include_router(vehicle_pricing_router)
    app.include_router(quote_router)
    app.include_router(contact_router)
    app.include_router(blog_public_router)
    app.include_router(orders_router)
    app.include_router(tracking_router)
    app.include_router(admin_orders_router)
    app.include_router(admin_customers_router)
    app.include_router(admin_dashboard_router)
    app.include_router(admin_blogs_router)
    app.include_router(weather_forecast_legacy_router)

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

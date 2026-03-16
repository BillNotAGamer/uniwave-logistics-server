from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import DashboardStatsRead
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/admin/dashboard", tags=["AdminDashboard"])


def get_dashboard_service(
    session: AsyncSession = Depends(get_db_session),
) -> DashboardService:
    return DashboardService(DashboardRepository(session))


@router.get(
    "",
    response_model=DashboardStatsRead,
    status_code=status.HTTP_200_OK,
)
async def get_dashboard(
    current_admin: User = Depends(require_admin),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardStatsRead:
    return await service.get_dashboard()

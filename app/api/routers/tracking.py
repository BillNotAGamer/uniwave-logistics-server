from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_optional_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.schemas.orders_legacy import LegacyTrackingResponseRead
from app.services.order_service import OrderService

router = APIRouter(prefix="/api/tracking", tags=["Tracking"])


def get_order_service(
    session: AsyncSession = Depends(get_db_session),
) -> OrderService:
    return OrderService(session=session, repository=OrderRepository(session))


@router.get(
    "/{orderCode}",
    response_model=LegacyTrackingResponseRead,
    status_code=status.HTTP_200_OK,
)
async def get_order_tracking(
    orderCode: str,
    current_user: User | None = Depends(get_optional_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> LegacyTrackingResponseRead:
    order = await order_service.get_tracking_order(order_code=orderCode, requester=current_user)
    return LegacyTrackingResponseRead.from_model(order)

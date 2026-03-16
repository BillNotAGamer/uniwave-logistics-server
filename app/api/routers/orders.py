from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.deps import require_admin, require_user_role
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.schemas.orders_legacy import (
    LegacyOrderCreateRequest,
    LegacyOrderDetailRead,
    LegacyOrderStatusUpdateRequest,
    LegacyOrderSummaryRead,
)
from app.services.email import EmailService, get_email_service
from app.services.order_service import OrderService
from app.utils.customer_id import resolve_customer_identifier
from app.utils.order_id import order_id_to_external, resolve_order_identifier

router = APIRouter(prefix="/api/orders", tags=["Orders"])


def get_order_service(
    session: AsyncSession = Depends(get_db_session),
) -> OrderService:
    return OrderService(session=session, repository=OrderRepository(session))


@router.get(
    "/my",
    response_model=list[LegacyOrderSummaryRead],
    status_code=status.HTTP_200_OK,
)
async def get_my_orders(
    current_user: User = Depends(require_user_role),
    order_service: OrderService = Depends(get_order_service),
) -> list[LegacyOrderSummaryRead] | JSONResponse:
    if not current_user.is_profile_complete():
        return JSONResponse(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            content={"message": "Please complete your profile before viewing orders."},
        )

    rows = await order_service.list_my_orders(user_id=current_user.id)
    return [LegacyOrderSummaryRead.from_model(order) for order in rows]


@router.get(
    "/admin",
    response_model=list[LegacyOrderSummaryRead],
    status_code=status.HTTP_200_OK,
)
async def get_orders_for_admin(
    userId: str | None = Query(default=None),
    _: User = Depends(require_admin),
    order_service: OrderService = Depends(get_order_service),
) -> list[LegacyOrderSummaryRead]:
    resolved_user_id: int | None = None
    if userId is not None:
        try:
            resolved_user_id = resolve_customer_identifier(userId)
        except ValueError as exc:
            raise AppException(
                code="invalid_user_id",
                message="Invalid user id.",
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc

    rows = await order_service.list_orders_for_orders_controller_admin(user_id=resolved_user_id)
    return [LegacyOrderSummaryRead.from_model(order) for order in rows]


@router.post(
    "/admin",
    status_code=status.HTTP_201_CREATED,
)
async def create_order_for_admin(
    request: LegacyOrderCreateRequest,
    _: User = Depends(require_admin),
    order_service: OrderService = Depends(get_order_service),
    email_service: EmailService = Depends(get_email_service),
) -> JSONResponse:
    created_order = await order_service.create_order_for_orders_controller_admin(
        request=request,
        email_service=email_service,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "id": order_id_to_external(created_order.id),
            "orderCode": created_order.order_code,
        },
    )


@router.post(
    "/admin/{orderId}/status",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_status_for_admin(
    orderId: str,
    request: LegacyOrderStatusUpdateRequest,
    current_admin: User = Depends(require_admin),
    order_service: OrderService = Depends(get_order_service),
) -> Response:
    try:
        resolved_order_id = resolve_order_identifier(orderId)
    except ValueError as exc:
        raise AppException(
            code="invalid_order_id",
            message="Invalid order id.",
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc

    await order_service.add_status_for_orders_controller_admin(
        order_id=resolved_order_id,
        request=request,
        admin_user_id=current_admin.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{orderCode}",
    response_model=LegacyOrderDetailRead,
    status_code=status.HTTP_200_OK,
)
async def get_order_by_code(
    orderCode: str,
    current_user: User = Depends(require_user_role),
    order_service: OrderService = Depends(get_order_service),
) -> LegacyOrderDetailRead:
    order = await order_service.get_order_by_code_for_user(
        order_code=orderCode,
        requester=current_user,
    )
    return LegacyOrderDetailRead.from_model(order)

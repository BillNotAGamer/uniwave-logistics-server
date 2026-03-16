from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.deps import require_admin
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.schemas.orders_legacy import (
    LegacyAdminOrderCreateRequest,
    LegacyAdminOrderDetailRead,
    LegacyAdminOrderListItemRead,
    LegacyAdminOrderUpdateRequest,
)
from app.services.email import EmailService, get_email_service
from app.services.order_service import OrderService
from app.utils.order_id import resolve_order_identifier

router = APIRouter(prefix="/api/admin/orders", tags=["OrdersAdmin"])


def get_order_service(
    session: AsyncSession = Depends(get_db_session),
) -> OrderService:
    return OrderService(session=session, repository=OrderRepository(session))


@router.get(
    "",
    response_model=list[LegacyAdminOrderListItemRead],
    status_code=status.HTTP_200_OK,
)
async def list_orders_admin(
    response: Response,
    status_filter: int | str | None = Query(default=None, alias="status"),
    page: int = Query(default=1),
    pageSize: int = Query(default=10),
    _: User = Depends(require_admin),
    order_service: OrderService = Depends(get_order_service),
) -> list[LegacyAdminOrderListItemRead]:
    normalized_page = page if page > 0 else 1
    normalized_page_size = pageSize if 0 < pageSize <= 50 else 10

    rows, total = await order_service.list_admin_orders(
        status_filter=status_filter,
        page=normalized_page,
        page_size=normalized_page_size,
    )

    response.headers["X-Total-Count"] = str(total)
    return [LegacyAdminOrderListItemRead.from_model(order) for order in rows]


@router.get(
    "/{id}",
    response_model=LegacyAdminOrderDetailRead,
    status_code=status.HTTP_200_OK,
)
async def get_order_by_id(
    id: str,
    _: User = Depends(require_admin),
    order_service: OrderService = Depends(get_order_service),
) -> LegacyAdminOrderDetailRead:
    try:
        resolved_order_id = resolve_order_identifier(id)
    except ValueError:
        raise AppException(
            code="invalid_order_id",
            message="Invalid order id.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    order = await order_service.get_admin_order_by_id(order_id=resolved_order_id)
    return LegacyAdminOrderDetailRead.from_model(order)


@router.post(
    "",
    response_model=LegacyAdminOrderDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    request: LegacyAdminOrderCreateRequest,
    current_admin: User = Depends(require_admin),
    order_service: OrderService = Depends(get_order_service),
    email_service: EmailService = Depends(get_email_service),
) -> LegacyAdminOrderDetailRead:
    created_order = await order_service.create_admin_order(
        request=request,
        admin_user_id=current_admin.id,
        email_service=email_service,
    )
    return LegacyAdminOrderDetailRead.from_model(created_order)


@router.put(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_order(
    id: str,
    request: LegacyAdminOrderUpdateRequest,
    current_admin: User = Depends(require_admin),
    order_service: OrderService = Depends(get_order_service),
) -> Response:
    try:
        resolved_order_id = resolve_order_identifier(id)
    except ValueError:
        raise AppException(
            code="invalid_order_id",
            message="Invalid order id.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    await order_service.update_admin_order(
        order_id=resolved_order_id,
        request=request,
        admin_user_id=current_admin.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_order(
    id: str,
    current_admin: User = Depends(require_admin),
    order_service: OrderService = Depends(get_order_service),
) -> Response:
    try:
        resolved_order_id = resolve_order_identifier(id)
    except ValueError:
        raise AppException(
            code="invalid_order_id",
            message="Invalid order id.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    await order_service.delete_admin_order(
        order_id=resolved_order_id,
        admin_user_id=current_admin.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

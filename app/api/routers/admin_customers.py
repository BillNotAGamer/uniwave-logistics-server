from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customers import CustomerAdminDetailRead, CustomerAdminListItemRead
from app.services.customer_admin_service import CustomerAdminService

router = APIRouter(prefix="/api/admin/customers", tags=["CustomersAdmin"])


def get_customer_admin_service(
    session: AsyncSession = Depends(get_db_session),
) -> CustomerAdminService:
    return CustomerAdminService(CustomerRepository(session))


@router.get(
    "",
    response_model=list[CustomerAdminListItemRead],
    status_code=status.HTTP_200_OK,
)
async def list_customers_admin(
    response: Response,
    search: str | None = Query(default=None),
    page: int = Query(default=1),
    pageSize: int = Query(default=10),
    _: User = Depends(require_admin),
    service: CustomerAdminService = Depends(get_customer_admin_service),
) -> list[CustomerAdminListItemRead]:
    items, total = await service.list_customers(
        search=search,
        page=page,
        page_size=pageSize,
    )
    response.headers["X-Total-Count"] = str(total)
    return items


@router.get(
    "/{id}",
    response_model=CustomerAdminDetailRead,
    status_code=status.HTTP_200_OK,
)
async def get_customer_admin(
    id: str,
    _: User = Depends(require_admin),
    service: CustomerAdminService = Depends(get_customer_admin_service),
) -> CustomerAdminDetailRead | JSONResponse:
    detail = await service.get_customer_detail(customer_identifier=id)
    if detail is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Customer not found."})
    return detail

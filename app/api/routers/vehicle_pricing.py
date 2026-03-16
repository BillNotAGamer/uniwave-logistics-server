from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.vehicle_pricing_repository import VehiclePricingRepository
from app.repositories.vehicle_type_repository import VehicleTypeRepository
from app.schemas.vehicle_pricing import VehiclePricingCreateUpdateRequest, VehiclePricingDto

router = APIRouter(prefix="/api/vehiclepricing", tags=["VehiclePricing"])


def get_vehicle_pricing_repository(
    session: AsyncSession = Depends(get_db_session),
) -> VehiclePricingRepository:
    return VehiclePricingRepository(session)


@router.get(
    "",
    response_model=list[VehiclePricingDto],
    status_code=status.HTTP_200_OK,
)
async def get_all(
    _: User = Depends(require_admin),
    repository: VehiclePricingRepository = Depends(get_vehicle_pricing_repository),
) -> list[VehiclePricingDto]:
    data = await repository.list_all()
    return [VehiclePricingDto.from_model(item) for item in data]


@router.get(
    "/{id}",
    response_model=VehiclePricingDto,
    status_code=status.HTTP_200_OK,
)
async def get_by_id(
    id: int,
    _: User = Depends(require_admin),
    repository: VehiclePricingRepository = Depends(get_vehicle_pricing_repository),
) -> VehiclePricingDto | Response:
    rule = await repository.get_by_id(id)
    if rule is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return VehiclePricingDto.from_model(rule)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def create(
    request: VehiclePricingCreateUpdateRequest,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    vehicle_repo = VehicleTypeRepository(session)
    pricing_repo = VehiclePricingRepository(session)

    vehicle = await vehicle_repo.get_by_id(request.vehicle_type_id)
    if vehicle is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "VehicleTypeId không tồn tại."},
        )

    entity = await pricing_repo.create(
        vehicle_type_id=request.vehicle_type_id,
        base_price=request.base_price,
        rate_2to10=request.rate_2to10,
        rate_10to15=request.rate_10to15,
        rate_15to40=request.rate_15to40,
        rate_over40=request.rate_over40,
        currency=request.currency,
        is_active=request.is_active,
    )
    await pricing_repo.save()
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"id": entity.id})


@router.put(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update(
    id: int,
    request: VehiclePricingCreateUpdateRequest,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    vehicle_repo = VehicleTypeRepository(session)
    pricing_repo = VehiclePricingRepository(session)

    entity = await pricing_repo.get_by_id(id)
    if entity is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    vehicle = await vehicle_repo.get_by_id(request.vehicle_type_id)
    if vehicle is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "VehicleTypeId không tồn tại."},
        )

    entity.vehicle_type_id = request.vehicle_type_id
    entity.base_price = request.base_price
    entity.rate_2to10 = request.rate_2to10
    entity.rate_10to15 = request.rate_10to15
    entity.rate_15to40 = request.rate_15to40
    entity.rate_over40 = request.rate_over40
    entity.currency = request.currency
    entity.is_active = request.is_active

    entity.price_per_km = request.rate_2to10
    entity.currency_code = request.currency[:3].upper()

    await pricing_repo.save()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete(
    id: int,
    _: User = Depends(require_admin),
    repository: VehiclePricingRepository = Depends(get_vehicle_pricing_repository),
) -> Response:
    entity = await repository.get_by_id(id)
    if entity is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    await repository.delete(entity)
    await repository.save()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

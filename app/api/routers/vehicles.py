from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.vehicle_type_repository import VehicleTypeRepository
from app.schemas.vehicle_type import VehicleCreateUpdateRequest, VehicleDto

router = APIRouter(prefix="/api/vehicles", tags=["Vehicles"])


def get_vehicle_type_repository(
    session: AsyncSession = Depends(get_db_session),
) -> VehicleTypeRepository:
    return VehicleTypeRepository(session)


@router.get(
    "",
    response_model=list[VehicleDto],
    status_code=status.HTTP_200_OK,
)
async def get_active_vehicles(
    repository: VehicleTypeRepository = Depends(get_vehicle_type_repository),
) -> list[VehicleDto]:
    vehicles = await repository.list_active_for_public()
    return [VehicleDto.from_model(vehicle) for vehicle in vehicles]


@router.get(
    "/admin",
    response_model=list[VehicleDto],
    status_code=status.HTTP_200_OK,
)
async def get_all_vehicles_for_admin(
    _: User = Depends(require_admin),
    repository: VehicleTypeRepository = Depends(get_vehicle_type_repository),
) -> list[VehicleDto]:
    vehicles = await repository.list_all_for_admin()
    return [VehicleDto.from_model(vehicle) for vehicle in vehicles]


@router.get(
    "/admin/{id}",
    response_model=VehicleDto,
    status_code=status.HTTP_200_OK,
)
async def get_vehicle_by_id(
    id: int,
    _: User = Depends(require_admin),
    repository: VehicleTypeRepository = Depends(get_vehicle_type_repository),
) -> VehicleDto | Response:
    vehicle = await repository.get_by_id(id)
    if vehicle is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return VehicleDto.from_model(vehicle)


@router.post(
    "/admin",
    status_code=status.HTTP_201_CREATED,
)
async def create_vehicle(
    request: VehicleCreateUpdateRequest,
    _: User = Depends(require_admin),
    repository: VehicleTypeRepository = Depends(get_vehicle_type_repository),
) -> JSONResponse:
    if await repository.is_code_taken(request.code):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"message": "Mã xe (Code) đã tồn tại."},
        )

    entity = await repository.create(**request.model_dump())
    await repository.save()
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"id": entity.id})


@router.put(
    "/admin/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_vehicle(
    id: int,
    request: VehicleCreateUpdateRequest,
    _: User = Depends(require_admin),
    repository: VehicleTypeRepository = Depends(get_vehicle_type_repository),
) -> Response:
    entity = await repository.get_by_id(id)
    if entity is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    if await repository.is_code_taken(request.code, exclude_id=id):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"message": "Mã xe (Code) đã tồn tại ở bản ghi khác."},
        )

    for field_name, field_value in request.model_dump().items():
        setattr(entity, field_name, field_value)

    await repository.save()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/admin/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_vehicle(
    id: int,
    _: User = Depends(require_admin),
    repository: VehicleTypeRepository = Depends(get_vehicle_type_repository),
) -> Response:
    entity = await repository.get_by_id(id)
    if entity is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    entity.is_active = False
    await repository.save()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

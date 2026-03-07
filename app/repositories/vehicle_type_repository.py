from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vehicle_type import VehicleType


class VehicleTypeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_for_public(self) -> list[VehicleType]:
        statement = (
            select(VehicleType)
            .where(VehicleType.is_active.is_(True))
            .order_by(VehicleType.capacity_kg.asc())
        )
        rows = await self._session.scalars(statement)
        return list(rows)

    async def list_all_for_admin(self) -> list[VehicleType]:
        statement = select(VehicleType).order_by(VehicleType.id.asc())
        rows = await self._session.scalars(statement)
        return list(rows)

    async def get_by_id(self, vehicle_type_id: int) -> VehicleType | None:
        statement = select(VehicleType).where(VehicleType.id == vehicle_type_id)
        return await self._session.scalar(statement)

    async def is_code_taken(self, code: str, *, exclude_id: int | None = None) -> bool:
        statement = select(VehicleType.id).where(func.lower(VehicleType.code) == code.lower())
        if exclude_id is not None:
            statement = statement.where(VehicleType.id != exclude_id)

        existing_id = await self._session.scalar(statement)
        return existing_id is not None

    async def create(
        self,
        *,
        name: str,
        code: str,
        capacity_kg: int,
        length_m: Decimal,
        width_m: Decimal,
        height_m: Decimal,
        image_url: str | None,
        is_active: bool,
    ) -> VehicleType:
        entity = VehicleType(
            name=name,
            code=code,
            capacity_kg=capacity_kg,
            length_m=length_m,
            width_m=width_m,
            height_m=height_m,
            image_url=image_url,
            is_active=is_active,
        )
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def save(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

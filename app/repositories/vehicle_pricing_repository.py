from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mixins import utc_now
from app.models.vehicle_pricing_rule import VehiclePricingRule


class VehiclePricingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[VehiclePricingRule]:
        statement = (
            select(VehiclePricingRule)
            .options(selectinload(VehiclePricingRule.vehicle_type))
            .order_by(VehiclePricingRule.vehicle_type_id.asc(), VehiclePricingRule.id.asc())
        )
        rows = await self._session.scalars(statement)
        return list(rows)

    async def get_by_id(self, rule_id: int) -> VehiclePricingRule | None:
        statement = (
            select(VehiclePricingRule)
            .options(selectinload(VehiclePricingRule.vehicle_type))
            .where(VehiclePricingRule.id == rule_id)
        )
        return await self._session.scalar(statement)

    async def create(
        self,
        *,
        vehicle_type_id: int,
        base_price: Decimal,
        rate_2to10: Decimal,
        rate_10to15: Decimal,
        rate_15to40: Decimal,
        rate_over40: Decimal,
        currency: str,
        is_active: bool,
    ) -> VehiclePricingRule:
        entity = VehiclePricingRule(
            vehicle_type_id=vehicle_type_id,
            base_price=base_price,
            rate_2to10=rate_2to10,
            rate_10to15=rate_10to15,
            rate_15to40=rate_15to40,
            rate_over40=rate_over40,
            currency=currency,
            is_active=is_active,
            effective_from=utc_now(),
            rule_name=f"Pricing {vehicle_type_id}",
            price_per_km=rate_2to10,
            minimum_price=None,
            currency_code=currency[:3].upper(),
            notes=None,
        )
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def save(self) -> None:
        await self._session.commit()

    async def delete(self, entity: VehiclePricingRule) -> None:
        await self._session.delete(entity)

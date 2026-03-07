from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quote_lead import QuoteLead
from app.models.quote_lead_price import QuoteLeadPrice
from app.models.vehicle_pricing_rule import VehiclePricingRule
from app.models.vehicle_type import VehicleType


class QuoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _is_sqlite(self) -> bool:
        bind = self._session.get_bind()
        return bool(bind is not None and bind.dialect.name == "sqlite")

    async def _next_id(self, model_cls) -> int:
        statement = select(func.coalesce(func.max(model_cls.id), 0) + 1)
        value = await self._session.scalar(statement)
        return int(value or 1)

    async def list_effective_pricing_rules(
        self,
        *,
        as_of: datetime,
    ) -> list[VehiclePricingRule]:
        statement = (
            select(VehiclePricingRule)
            .options(selectinload(VehiclePricingRule.vehicle_type))
            .join(VehicleType, VehicleType.id == VehiclePricingRule.vehicle_type_id)
            .where(
                VehiclePricingRule.is_active.is_(True),
                VehicleType.is_active.is_(True),
                VehiclePricingRule.effective_from <= as_of,
                or_(
                    VehiclePricingRule.effective_to.is_(None),
                    VehiclePricingRule.effective_to >= as_of,
                ),
            )
        )
        rows = await self._session.scalars(statement)
        return list(rows)

    async def get_effective_rule_for_vehicle(
        self,
        *,
        vehicle_type_id: int,
        as_of: datetime,
    ) -> VehiclePricingRule | None:
        statement = (
            select(VehiclePricingRule)
            .options(selectinload(VehiclePricingRule.vehicle_type))
            .join(VehicleType, VehicleType.id == VehiclePricingRule.vehicle_type_id)
            .where(
                VehiclePricingRule.vehicle_type_id == vehicle_type_id,
                VehiclePricingRule.is_active.is_(True),
                VehicleType.is_active.is_(True),
                VehiclePricingRule.effective_from <= as_of,
                or_(
                    VehiclePricingRule.effective_to.is_(None),
                    VehiclePricingRule.effective_to >= as_of,
                ),
            )
            .order_by(VehiclePricingRule.effective_from.desc(), VehiclePricingRule.id.desc())
        )
        return await self._session.scalar(statement)

    async def create_quote_lead(
        self,
        *,
        email: str,
        pickup_address: str,
        dropoff_address: str,
        distance_km: Decimal,
        user_id: int | None,
    ) -> QuoteLead:
        lead_id: int | None = None
        if self._is_sqlite():
            lead_id = await self._next_id(QuoteLead)

        entity = QuoteLead(
            id=lead_id,
            email=email,
            pickup_address=pickup_address,
            dropoff_address=dropoff_address,
            distance_km=distance_km,
            user_id=user_id,
            lead_status=0,
            status="new",
        )
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def create_quote_lead_price(
        self,
        *,
        quote_lead_id: int,
        vehicle_type_id: int,
        estimated_price: Decimal,
    ) -> QuoteLeadPrice:
        price_id: int | None = None
        if self._is_sqlite():
            price_id = await self._next_id(QuoteLeadPrice)

        entity = QuoteLeadPrice(
            id=price_id,
            quote_lead_id=quote_lead_id,
            vehicle_type_id=vehicle_type_id,
            estimated_price=estimated_price,
            amount=estimated_price,
            currency_code="VND",
            pricing_breakdown=None,
        )
        self._session.add(entity)
        await self._session.flush()
        return entity

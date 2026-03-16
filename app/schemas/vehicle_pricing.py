from __future__ import annotations

from decimal import Decimal

from pydantic import AliasChoices, Field

from app.models.vehicle_pricing_rule import VehiclePricingRule
from app.schemas.base import APIModel


class VehiclePricingCreateUpdateRequest(APIModel):
    vehicle_type_id: int = Field(ge=1)
    base_price: Decimal = Field(ge=0, le=100000000)
    rate_2to10: Decimal = Field(
        ge=0,
        le=10000000,
        validation_alias=AliasChoices("rate_2to10", "rate2to10"),
        serialization_alias="rate_2to10",
    )
    rate_10to15: Decimal = Field(
        ge=0,
        le=10000000,
        validation_alias=AliasChoices("rate_10to15", "rate10to15"),
        serialization_alias="rate_10to15",
    )
    rate_15to40: Decimal = Field(
        ge=0,
        le=10000000,
        validation_alias=AliasChoices("rate_15to40", "rate15to40"),
        serialization_alias="rate_15to40",
    )
    rate_over40: Decimal = Field(
        ge=0,
        le=10000000,
        validation_alias=AliasChoices("rate_Over40", "rate_over40", "rateOver40"),
        serialization_alias="rate_Over40",
    )
    currency: str = Field(default="VND", max_length=10)
    is_active: bool = True


class VehiclePricingDto(APIModel):
    id: int
    vehicle_type_id: int
    vehicle_name: str
    vehicle_code: str
    base_price: Decimal
    rate_2to10: Decimal = Field(serialization_alias="rate_2to10")
    rate_10to15: Decimal = Field(serialization_alias="rate_10to15")
    rate_15to40: Decimal = Field(serialization_alias="rate_15to40")
    rate_over40: Decimal = Field(serialization_alias="rate_Over40")
    currency: str = "VND"
    is_active: bool

    @classmethod
    def from_model(cls, rule: VehiclePricingRule) -> "VehiclePricingDto":
        return cls(
            id=rule.id,
            vehicle_type_id=rule.vehicle_type_id,
            vehicle_name=(rule.vehicle_type.name if rule.vehicle_type is not None else ""),
            vehicle_code=(rule.vehicle_type.code if rule.vehicle_type is not None else ""),
            base_price=rule.base_price,
            rate_2to10=rule.rate_2to10,
            rate_10to15=rule.rate_10to15,
            rate_15to40=rule.rate_15to40,
            rate_over40=rule.rate_over40,
            currency=rule.currency or rule.currency_code,
            is_active=rule.is_active,
        )

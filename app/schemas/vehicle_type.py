from __future__ import annotations

from decimal import Decimal

from pydantic import Field, field_validator

from app.models.vehicle_type import VehicleType
from app.schemas.base import APIModel


def _normalize_code(value: str) -> str:
    return value.strip().upper()


class VehicleCreateUpdateRequest(APIModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50)
    capacity_kg: int = Field(ge=1, le=100000)
    length_m: Decimal = Field(gt=Decimal("0"), le=Decimal("100"))
    width_m: Decimal = Field(gt=Decimal("0"), le=Decimal("100"))
    height_m: Decimal = Field(gt=Decimal("0"), le=Decimal("100"))
    image_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return _normalize_code(value)


class VehicleDto(APIModel):
    id: int
    name: str
    code: str
    capacity_kg: int
    length_m: Decimal
    width_m: Decimal
    height_m: Decimal
    image_url: str | None = None
    is_active: bool

    @classmethod
    def from_model(cls, vehicle_type: VehicleType) -> "VehicleDto":
        return cls(
            id=vehicle_type.id,
            name=vehicle_type.name,
            code=vehicle_type.code,
            capacity_kg=vehicle_type.capacity_kg,
            length_m=vehicle_type.length_m,
            width_m=vehicle_type.width_m,
            height_m=vehicle_type.height_m,
            image_url=vehicle_type.image_url,
            is_active=vehicle_type.is_active,
        )

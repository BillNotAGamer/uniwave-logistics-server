from __future__ import annotations

from decimal import Decimal

from pydantic import EmailStr, field_validator, Field

from app.schemas.base import APIModel


class EstimateRequest(APIModel):
    pickup_address: str = Field(min_length=1, max_length=500)
    dropoff_address: str = Field(min_length=1, max_length=500)
    distance_km: Decimal = Field(ge=0, le=10000)


class VehicleEstimateDto(APIModel):
    vehicle_type_id: int
    vehicle_name: str
    vehicle_code: str
    capacity_kg: int
    length_m: Decimal
    width_m: Decimal
    height_m: Decimal
    image_url: str | None = None
    estimated_price: Decimal


class EstimateResponse(APIModel):
    distance_km: Decimal
    vehicles: list[VehicleEstimateDto]


class LeadRequest(APIModel):
    customer_name: str
    customer_email: EmailStr | None = None
    customer_phone: str | None = None
    pickup_address: str
    dropoff_address: str
    distance_km: Decimal
    selected_vehicle_type_id: int

    @field_validator("customer_phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class LeadResponse(APIModel):
    message: str

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

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
    customer_name: str = Field(min_length=1, max_length=200)
    customer_email: str = Field(min_length=3, max_length=256)
    pickup_address: str = Field(min_length=1, max_length=500)
    dropoff_address: str = Field(min_length=1, max_length=500)
    distance_km: Decimal = Field(ge=0, le=10000)
    selected_vehicle_type_id: int = Field(ge=1)


class LeadResponse(APIModel):
    message: str

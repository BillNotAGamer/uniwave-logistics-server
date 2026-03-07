from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppException
from app.models.mixins import utc_now
from app.models.user import User
from app.models.vehicle_pricing_rule import VehiclePricingRule
from app.repositories.quote_repository import QuoteRepository
from app.schemas.quote import (
    EstimateRequest,
    EstimateResponse,
    LeadRequest,
    LeadResponse,
    VehicleEstimateDto,
)
from app.services.email import EmailService, OutboundEmail

logger = logging.getLogger(__name__)


class QuoteService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: QuoteRepository,
        settings: Settings,
    ) -> None:
        self._session = session
        self._repository = repository
        self._settings = settings

    async def estimate(self, request: EstimateRequest) -> EstimateResponse:
        if request.distance_km <= 0:
            raise AppException(
                code="invalid_distance",
                message="DistanceKm phải > 0.",
                status_code=400,
            )
        if request.distance_km > 5000:
            raise AppException(
                code="invalid_distance",
                message="DistanceKm quá lớn, vui lòng kiểm tra lại tuyến đường.",
                status_code=400,
            )

        now = utc_now()
        pricing_rules = await self._repository.list_effective_pricing_rules(as_of=now)
        if not pricing_rules:
            raise AppException(
                code="pricing_not_configured",
                message="Chưa cấu hình bảng giá cho các loại xe.",
                status_code=500,
            )

        vehicles: list[VehicleEstimateDto] = []
        for rule in pricing_rules:
            vehicle = rule.vehicle_type
            if vehicle is None:
                continue

            price = self._calculate_price(request.distance_km, rule)
            price = Decimal(str(round(price, 0)))

            image_url = vehicle.image_url or self._get_default_image_url(vehicle.code)
            vehicles.append(
                VehicleEstimateDto(
                    vehicle_type_id=vehicle.id,
                    vehicle_name=vehicle.name,
                    vehicle_code=vehicle.code,
                    capacity_kg=vehicle.capacity_kg,
                    length_m=vehicle.length_m,
                    width_m=vehicle.width_m,
                    height_m=vehicle.height_m,
                    image_url=image_url,
                    estimated_price=price,
                )
            )

        vehicles = sorted(vehicles, key=lambda item: item.estimated_price)
        return EstimateResponse(distance_km=request.distance_km, vehicles=vehicles)

    async def create_lead(
        self,
        *,
        request: LeadRequest,
        current_user: User,
        email_service: EmailService,
    ) -> LeadResponse:
        if request.distance_km <= 0:
            raise AppException(
                code="invalid_distance",
                message="DistanceKm phải > 0.",
                status_code=400,
            )

        now = utc_now()
        pricing_rule = await self._repository.get_effective_rule_for_vehicle(
            vehicle_type_id=request.selected_vehicle_type_id,
            as_of=now,
        )
        if pricing_rule is None or pricing_rule.vehicle_type is None:
            raise AppException(
                code="invalid_selected_vehicle",
                message="Selected vehicle type is not available.",
                status_code=400,
            )

        effective_email = (current_user.email or request.customer_email).strip()
        customer_name = request.customer_name.strip() if request.customer_name.strip() else effective_email

        lead = await self._repository.create_quote_lead(
            email=effective_email,
            pickup_address=request.pickup_address,
            dropoff_address=request.dropoff_address,
            distance_km=request.distance_km,
            user_id=current_user.id,
        )

        price = self._calculate_price(request.distance_km, pricing_rule)
        price = Decimal(str(round(price, 0)))
        await self._repository.create_quote_lead_price(
            quote_lead_id=lead.id,
            vehicle_type_id=pricing_rule.vehicle_type_id,
            estimated_price=price,
        )
        await self._session.commit()

        await self._send_quote_lead_to_sales(
            email_service=email_service,
            customer_name=customer_name,
            customer_email=effective_email,
            pickup_address=request.pickup_address,
            dropoff_address=request.dropoff_address,
            distance_km=request.distance_km,
            selected_vehicle_type_name=pricing_rule.vehicle_type.name,
        )

        return LeadResponse(
            message="Uniwave đã nhận được thông tin của quý khách! Chúng tôi sẽ sớm liên hệ tư vấn chi tiết.",
        )

    @staticmethod
    def _calculate_price(distance_km: Decimal, rule: VehiclePricingRule) -> Decimal:
        if distance_km <= 0:
            return Decimal("0")

        base_covered_km = Decimal("2")
        if distance_km <= base_covered_km:
            return Decimal(str(rule.base_price))

        total = Decimal(str(rule.base_price))
        remaining = distance_km - base_covered_km

        seg_2to10 = min(remaining, Decimal("8"))
        total += seg_2to10 * Decimal(str(rule.rate_2to10))
        remaining -= seg_2to10
        if remaining <= 0:
            return total

        seg_10to15 = min(remaining, Decimal("5"))
        total += seg_10to15 * Decimal(str(rule.rate_10to15))
        remaining -= seg_10to15
        if remaining <= 0:
            return total

        seg_15to40 = min(remaining, Decimal("25"))
        total += seg_15to40 * Decimal(str(rule.rate_15to40))
        remaining -= seg_15to40
        if remaining <= 0:
            return total

        total += remaining * Decimal(str(rule.rate_over40))
        return total

    async def _send_quote_lead_to_sales(
        self,
        *,
        email_service: EmailService,
        customer_name: str,
        customer_email: str,
        pickup_address: str,
        dropoff_address: str,
        distance_km: Decimal,
        selected_vehicle_type_name: str,
    ) -> None:
        sales_email = self._settings.quote_lead_notification_email or "sales@uniwave-logistics.com"
        if not sales_email.strip():
            return

        subject = "Quote lead request"
        body = (
            f"Customer name: {customer_name}\n"
            f"Customer email: {customer_email}\n"
            f"Pickup address: {pickup_address}\n"
            f"Dropoff address: {dropoff_address}\n"
            f"Distance (km): {distance_km}\n"
            f"Selected vehicle type: {selected_vehicle_type_name}"
        )

        try:
            await email_service.send_email(
                OutboundEmail(
                    to_email=sales_email,
                    subject=subject,
                    text_body=body,
                    template_key="quote_lead_notification",
                    payload={"customer_email": customer_email},
                ),
                raise_on_failure=False,
            )
        except Exception:  # pragma: no cover - defensive parity with legacy behavior
            logger.exception("Failed to send quote lead email to sales.")

    @staticmethod
    def _get_default_image_url(vehicle_code: str | None) -> str:
        mapping = {
            "MOTORCYCLE": "/image/price-check/image/motorcycle.svg",
            "TRICYCLE": "/image/price-check/image/tricycle.svg",
            "VAN_500KG": "/image/price-check/image/van500.svg",
            "VAN_1T": "/image/price-check/image/van1000.svg",
            "TRUCK_500KG": "/image/price-check/image/truck500.svg",
            "TRUCK_1T": "/image/price-check/image/truck1000.svg",
            "TRUCK_1_5T": "/image/price-check/image/truck1500.svg",
            "TRUCK_2T": "/image/price-check/image/truck2000.svg",
        }
        return mapping.get((vehicle_code or "").strip().upper(), "/image/price-check/image/truck1000.svg")

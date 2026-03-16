from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.vehicle_type import VehicleType


class VehiclePricingRule(TimestampMixin, Base):
    __tablename__ = "vehicle_pricing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vehicle_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    rate_2to10: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))
    rate_10to15: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))
    rate_15to40: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))
    rate_over40: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))
    price_per_km: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    minimum_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="VND", server_default=text("'VND'"))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    vehicle_type: Mapped["VehicleType"] = relationship("VehicleType", back_populates="pricing_rules")

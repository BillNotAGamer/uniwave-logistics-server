from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.quote_lead_price import QuoteLeadPrice
    from app.models.vehicle_pricing_rule import VehiclePricingRule


class VehicleType(TimestampMixin, Base):
    __tablename__ = "vehicle_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    capacity_kg: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    length_m: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default=text("0"))
    width_m: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default=text("0"))
    height_m: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default=text("0"))
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    pricing_rules: Mapped[list["VehiclePricingRule"]] = relationship(
        "VehiclePricingRule",
        back_populates="vehicle_type",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    quote_lead_prices: Mapped[list["QuoteLeadPrice"]] = relationship(
        "QuoteLeadPrice",
        back_populates="vehicle_type",
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="vehicle_type")

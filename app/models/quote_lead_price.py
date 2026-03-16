from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.quote_lead import QuoteLead
    from app.models.vehicle_type import VehicleType


class QuoteLeadPrice(TimestampMixin, Base):
    __tablename__ = "quote_lead_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    quote_lead_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("quote_leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vehicle_type_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("vehicle_types.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    estimated_price: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    pricing_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    quote_lead: Mapped["QuoteLead"] = relationship("QuoteLead", back_populates="prices")
    vehicle_type: Mapped["VehicleType | None"] = relationship("VehicleType", back_populates="quote_lead_prices")

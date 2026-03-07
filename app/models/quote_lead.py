from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.quote_lead_price import QuoteLeadPrice
    from app.models.user import User


class QuoteLead(TimestampMixin, Base):
    __tablename__ = "quote_leads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pickup_address: Mapped[str] = mapped_column(Text, nullable=False)
    dropoff_address: Mapped[str] = mapped_column(Text, nullable=False)
    distance_km: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    lead_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    prices: Mapped[list["QuoteLeadPrice"]] = relationship(
        "QuoteLeadPrice",
        back_populates="quote_lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    user: Mapped["User | None"] = relationship("User")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="quote_lead")

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order_status_history import OrderStatusHistory
    from app.models.quote_lead import QuoteLead
    from app.models.user import User
    from app.models.vehicle_type import VehicleType


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quote_lead_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("quote_leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    vehicle_type_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("vehicle_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="created",
        server_default=text("'created'"),
    )
    pickup_address: Mapped[str] = mapped_column(Text, nullable=False)
    dropoff_address: Mapped[str] = mapped_column(Text, nullable=False)
    receiver_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    receiver_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    distance_km: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    estimated_price: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    final_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subtotal_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    user: Mapped["User"] = relationship("User", back_populates="orders")
    quote_lead: Mapped["QuoteLead | None"] = relationship("QuoteLead", back_populates="orders")
    vehicle_type: Mapped["VehicleType | None"] = relationship("VehicleType", back_populates="orders")
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

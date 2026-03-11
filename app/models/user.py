from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.blog_post import BlogPost
    from app.models.email_log import EmailLog
    from app.models.email_verification_token import EmailVerificationToken
    from app.models.order import Order
    from app.models.password_reset_token import PasswordResetToken
    from app.models.refresh_token import RefreshToken
    from app.models.role import Role
    from app.models.user_role import UserRole

SQLITE_SAFE_BIGINT = BigInteger().with_variant(Integer(), "sqlite")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(SQLITE_SAFE_BIGINT, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Bronze",
        server_default=text("'Bronze'"),
    )
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="roles,users",
    )
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        overlaps="role,user_roles,user",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    email_verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        "EmailVerificationToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")
    blog_posts: Mapped[list["BlogPost"]] = relationship("BlogPost", back_populates="author")
    email_logs: Mapped[list["EmailLog"]] = relationship("EmailLog", back_populates="user")

    def is_profile_complete(self) -> bool:
        return bool(
            (self.full_name or "").strip()
            and (self.phone_number or "").strip()
            and (self.address or "").strip()
        )

    def get_missing_profile_fields(self) -> list[str]:
        missing: list[str] = []
        if not (self.full_name or "").strip():
            missing.append("fullName")
        if not (self.phone_number or "").strip():
            missing.append("phoneNumber")
        if not (self.address or "").strip():
            missing.append("address")
        return missing

"""auth user parity

Revision ID: 4c6f9f2a1b4e
Revises: e553b2ada37f
Create Date: 2026-03-06 17:10:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4c6f9f2a1b4e"
down_revision = "e553b2ada37f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("phone_number", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("address", sa.String(length=500), nullable=True))
    op.add_column(
        "users",
        sa.Column("tier", sa.String(length=20), server_default=sa.text("'Bronze'"), nullable=False),
    )

    op.alter_column(
        "password_reset_tokens",
        "token_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.add_column("password_reset_tokens", sa.Column("request_ip", sa.String(length=64), nullable=True))
    op.add_column("password_reset_tokens", sa.Column("user_agent", sa.String(length=512), nullable=True))

    op.add_column("refresh_tokens", sa.Column("token", sa.String(length=512), nullable=True))
    op.execute("UPDATE refresh_tokens SET token = token_hash WHERE token IS NULL")
    op.alter_column("refresh_tokens", "token", existing_type=sa.String(length=512), nullable=False)
    op.drop_index(op.f("ix_refresh_tokens_token_hash"), table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "token_hash")
    op.drop_column("refresh_tokens", "is_revoked")


def downgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("is_revoked", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("refresh_tokens", sa.Column("token_hash", sa.String(length=128), nullable=True))
    op.execute("UPDATE refresh_tokens SET token_hash = token WHERE token_hash IS NULL")
    op.alter_column("refresh_tokens", "token_hash", existing_type=sa.String(length=128), nullable=False)
    op.create_index(op.f("ix_refresh_tokens_token_hash"), "refresh_tokens", ["token_hash"], unique=True)
    op.drop_column("refresh_tokens", "token")

    op.drop_column("password_reset_tokens", "user_agent")
    op.drop_column("password_reset_tokens", "request_ip")
    op.alter_column(
        "password_reset_tokens",
        "token_hash",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=False,
    )

    op.drop_column("users", "tier")
    op.drop_column("users", "address")
    op.drop_column("users", "phone_number")
    op.drop_column("users", "full_name")

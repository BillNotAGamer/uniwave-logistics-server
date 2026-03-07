"""orders tracking parity

Revision ID: b1f02e7d94a3
Revises: 4c6f9f2a1b4e
Create Date: 2026-03-06 20:10:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b1f02e7d94a3"
down_revision = "4c6f9f2a1b4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("receiver_name", sa.String(length=200), nullable=True))
    op.add_column("orders", sa.Column("receiver_phone", sa.String(length=20), nullable=True))
    op.add_column(
        "orders",
        sa.Column(
            "distance_km",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "estimated_price",
            sa.Numeric(precision=12, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column("orders", sa.Column("final_price", sa.Numeric(precision=12, scale=2), nullable=True))

    op.add_column("order_status_history", sa.Column("status", sa.String(length=32), nullable=True))
    op.add_column("order_status_history", sa.Column("title", sa.String(length=200), nullable=True))
    op.add_column("order_status_history", sa.Column("description", sa.String(length=1000), nullable=True))
    op.add_column("order_status_history", sa.Column("location", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("order_status_history", "location")
    op.drop_column("order_status_history", "description")
    op.drop_column("order_status_history", "title")
    op.drop_column("order_status_history", "status")

    op.drop_column("orders", "final_price")
    op.drop_column("orders", "estimated_price")
    op.drop_column("orders", "distance_km")
    op.drop_column("orders", "receiver_phone")
    op.drop_column("orders", "receiver_name")

"""add user nationality

Revision ID: a3d1e7b9c2f4
Revises: f2b8c4b7d0a1
Create Date: 2026-03-11 16:30:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a3d1e7b9c2f4"
down_revision = "f2b8c4b7d0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("nationality", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "nationality")

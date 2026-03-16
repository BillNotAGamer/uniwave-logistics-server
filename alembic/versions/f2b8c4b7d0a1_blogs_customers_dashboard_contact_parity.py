"""blogs customers dashboard contact parity

Revision ID: f2b8c4b7d0a1
Revises: d9e41a0c7f15
Create Date: 2026-03-06 23:55:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2b8c4b7d0a1"
down_revision = "d9e41a0c7f15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "blog_posts",
        sa.Column("status", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.execute(
        """
        UPDATE blog_posts
        SET status = CASE
            WHEN is_published = TRUE THEN 1
            ELSE 0
        END
        """
    )


def downgrade() -> None:
    op.drop_column("blog_posts", "status")

"""vehicle pricing quote parity

Revision ID: d9e41a0c7f15
Revises: b1f02e7d94a3
Create Date: 2026-03-06 21:20:00.000000

"""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d9e41a0c7f15"
down_revision = "b1f02e7d94a3"
branch_labels = None
depends_on = None


LEGACY_VEHICLES = [
    {"name": "Xe Van 500KG", "code": "VAN_500KG", "capacity_kg": 500, "length_m": 1.7, "width_m": 1.2, "height_m": 1.2},
    {"name": "Xe Van 1 Tấn", "code": "VAN_1T", "capacity_kg": 1000, "length_m": 2.0, "width_m": 1.2, "height_m": 1.2},
    {"name": "Xe Tải 500KG", "code": "TRUCK_500KG", "capacity_kg": 500, "length_m": 2.0, "width_m": 1.5, "height_m": 1.5},
    {"name": "Xe Tải 1 Tấn", "code": "TRUCK_1T", "capacity_kg": 1000, "length_m": 3.0, "width_m": 1.6, "height_m": 1.7},
    {"name": "Xe Tải 1.5 Tấn", "code": "TRUCK_1_5T", "capacity_kg": 1500, "length_m": 3.0, "width_m": 1.7, "height_m": 1.7},
    {"name": "Xe Tải 2 Tấn", "code": "TRUCK_2T", "capacity_kg": 2000, "length_m": 4.0, "width_m": 1.8, "height_m": 1.8},
    {"name": "Xe máy", "code": "MOTORCYCLE", "capacity_kg": 30, "length_m": 0.5, "width_m": 0.4, "height_m": 0.5},
    {"name": "Xe ba gác", "code": "TRICYCLE", "capacity_kg": 300, "length_m": 1.5, "width_m": 1.0, "height_m": 1.2},
]

LEGACY_PRICING = [
    {"code": "VAN_500KG", "base_price": 240000, "rate_2to10": 24000, "rate_10to15": 21000, "rate_15to40": 20000, "rate_over40": 18000},
    {"code": "VAN_1T", "base_price": 330000, "rate_2to10": 30000, "rate_10to15": 26000, "rate_15to40": 22000, "rate_over40": 20000},
    {"code": "TRUCK_500KG", "base_price": 300000, "rate_2to10": 26000, "rate_10to15": 24000, "rate_15to40": 21000, "rate_over40": 19000},
    {"code": "TRUCK_1T", "base_price": 400000, "rate_2to10": 32000, "rate_10to15": 26000, "rate_15to40": 24000, "rate_over40": 22000},
    {"code": "TRUCK_1_5T", "base_price": 410000, "rate_2to10": 34000, "rate_10to15": 28000, "rate_15to40": 25000, "rate_over40": 23000},
    {"code": "TRUCK_2T", "base_price": 500000, "rate_2to10": 39000, "rate_10to15": 32000, "rate_15to40": 29000, "rate_over40": 26000},
    {"code": "MOTORCYCLE", "base_price": 30000, "rate_2to10": 12000, "rate_10to15": 14000, "rate_15to40": 16000, "rate_over40": 15000},
    {"code": "TRICYCLE", "base_price": 75000, "rate_2to10": 18000, "rate_10to15": 22000, "rate_15to40": 24000, "rate_over40": 21000},
]


def _seed_legacy_reference_data() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    effective_from = datetime(2025, 1, 1, tzinfo=timezone.utc)

    vehicle_stmt = sa.text(
        """
        INSERT INTO vehicle_types
            (code, name, capacity_kg, length_m, width_m, height_m, image_url, is_active, description, created_at, updated_at)
        VALUES
            (:code, :name, :capacity_kg, :length_m, :width_m, :height_m, :image_url, :is_active, NULL, :created_at, :updated_at)
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            capacity_kg = EXCLUDED.capacity_kg,
            length_m = EXCLUDED.length_m,
            width_m = EXCLUDED.width_m,
            height_m = EXCLUDED.height_m,
            image_url = EXCLUDED.image_url,
            is_active = EXCLUDED.is_active,
            updated_at = EXCLUDED.updated_at
        """
    )

    for item in LEGACY_VEHICLES:
        bind.execute(
            vehicle_stmt,
            {
                "code": item["code"],
                "name": item["name"],
                "capacity_kg": item["capacity_kg"],
                "length_m": item["length_m"],
                "width_m": item["width_m"],
                "height_m": item["height_m"],
                "image_url": None,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        )

    pricing_stmt = sa.text(
        """
        INSERT INTO vehicle_pricing_rules
            (
                vehicle_type_id,
                rule_name,
                base_price,
                rate_2to10,
                rate_10to15,
                rate_15to40,
                rate_over40,
                price_per_km,
                minimum_price,
                currency_code,
                currency,
                effective_from,
                effective_to,
                is_active,
                notes,
                created_at,
                updated_at
            )
        SELECT
            vt.id,
            :rule_name,
            :base_price,
            :rate_2to10,
            :rate_10to15,
            :rate_15to40,
            :rate_over40,
            :price_per_km,
            NULL,
            'VND',
            'VND',
            :effective_from,
            NULL,
            TRUE,
            NULL,
            :created_at,
            :updated_at
        FROM vehicle_types vt
        WHERE vt.code = :code
          AND NOT EXISTS (
              SELECT 1
              FROM vehicle_pricing_rules r
              WHERE r.vehicle_type_id = vt.id
                AND r.effective_from = :effective_from
          )
        """
    )

    for item in LEGACY_PRICING:
        bind.execute(
            pricing_stmt,
            {
                "code": item["code"],
                "rule_name": f"Pricing {item['code']}",
                "base_price": item["base_price"],
                "rate_2to10": item["rate_2to10"],
                "rate_10to15": item["rate_10to15"],
                "rate_15to40": item["rate_15to40"],
                "rate_over40": item["rate_over40"],
                "price_per_km": item["rate_2to10"],
                "effective_from": effective_from,
                "created_at": now,
                "updated_at": now,
            },
        )


def upgrade() -> None:
    op.alter_column(
        "vehicle_types",
        "name",
        existing_type=sa.String(length=100),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.add_column(
        "vehicle_types",
        sa.Column("capacity_kg", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "vehicle_types",
        sa.Column("length_m", sa.Numeric(precision=10, scale=2), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "vehicle_types",
        sa.Column("width_m", sa.Numeric(precision=10, scale=2), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "vehicle_types",
        sa.Column("height_m", sa.Numeric(precision=10, scale=2), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("vehicle_types", sa.Column("image_url", sa.String(length=500), nullable=True))

    op.add_column(
        "vehicle_pricing_rules",
        sa.Column("rate_2to10", sa.Numeric(precision=12, scale=2), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "vehicle_pricing_rules",
        sa.Column("rate_10to15", sa.Numeric(precision=12, scale=2), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "vehicle_pricing_rules",
        sa.Column("rate_15to40", sa.Numeric(precision=12, scale=2), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "vehicle_pricing_rules",
        sa.Column("rate_over40", sa.Numeric(precision=12, scale=2), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "vehicle_pricing_rules",
        sa.Column("currency", sa.String(length=10), server_default=sa.text("'VND'"), nullable=False),
    )
    op.add_column(
        "vehicle_pricing_rules",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )

    op.add_column(
        "quote_leads",
        sa.Column("lead_status", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("quote_leads", sa.Column("user_id", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_quote_leads_user_id"), "quote_leads", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_quote_leads_user_id_users",
        "quote_leads",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "quote_lead_prices",
        sa.Column("estimated_price", sa.Numeric(precision=12, scale=2), server_default=sa.text("0"), nullable=False),
    )

    _seed_legacy_reference_data()


def downgrade() -> None:
    op.drop_column("quote_lead_prices", "estimated_price")

    op.drop_constraint("fk_quote_leads_user_id_users", "quote_leads", type_="foreignkey")
    op.drop_index(op.f("ix_quote_leads_user_id"), table_name="quote_leads")
    op.drop_column("quote_leads", "user_id")
    op.drop_column("quote_leads", "lead_status")

    op.drop_column("vehicle_pricing_rules", "is_active")
    op.drop_column("vehicle_pricing_rules", "currency")
    op.drop_column("vehicle_pricing_rules", "rate_over40")
    op.drop_column("vehicle_pricing_rules", "rate_15to40")
    op.drop_column("vehicle_pricing_rules", "rate_10to15")
    op.drop_column("vehicle_pricing_rules", "rate_2to10")

    op.drop_column("vehicle_types", "image_url")
    op.drop_column("vehicle_types", "height_m")
    op.drop_column("vehicle_types", "width_m")
    op.drop_column("vehicle_types", "length_m")
    op.drop_column("vehicle_types", "capacity_kg")
    op.alter_column(
        "vehicle_types",
        "name",
        existing_type=sa.String(length=200),
        type_=sa.String(length=100),
        existing_nullable=False,
    )

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionFactory
from app.models.mixins import utc_now
from app.models.role import Role
from app.models.user import User
from app.models.vehicle_pricing_rule import VehiclePricingRule
from app.models.vehicle_type import VehicleType

DEFAULT_ROLES: dict[str, str] = {
    "Admin": "System administrator with full access.",
    "ContentEditor": "Can manage editable content.",
    "User": "Default application user role.",
}

LEGACY_EFFECTIVE_FROM = datetime(2025, 1, 1, tzinfo=timezone.utc)

LEGACY_VEHICLE_TYPES: list[dict[str, object]] = [
    {"name": "Xe Van 500KG", "code": "VAN_500KG", "capacity_kg": 500, "length_m": 1.7, "width_m": 1.2, "height_m": 1.2, "image_url": None, "is_active": True},
    {"name": "Xe Van 1 Tấn", "code": "VAN_1T", "capacity_kg": 1000, "length_m": 2.0, "width_m": 1.2, "height_m": 1.2, "image_url": None, "is_active": True},
    {"name": "Xe Tải 500KG", "code": "TRUCK_500KG", "capacity_kg": 500, "length_m": 2.0, "width_m": 1.5, "height_m": 1.5, "image_url": None, "is_active": True},
    {"name": "Xe Tải 1 Tấn", "code": "TRUCK_1T", "capacity_kg": 1000, "length_m": 3.0, "width_m": 1.6, "height_m": 1.7, "image_url": None, "is_active": True},
    {"name": "Xe Tải 1.5 Tấn", "code": "TRUCK_1_5T", "capacity_kg": 1500, "length_m": 3.0, "width_m": 1.7, "height_m": 1.7, "image_url": None, "is_active": True},
    {"name": "Xe Tải 2 Tấn", "code": "TRUCK_2T", "capacity_kg": 2000, "length_m": 4.0, "width_m": 1.8, "height_m": 1.8, "image_url": None, "is_active": True},
    {"name": "Xe máy", "code": "MOTORCYCLE", "capacity_kg": 30, "length_m": 0.5, "width_m": 0.4, "height_m": 0.5, "image_url": None, "is_active": True},
    {"name": "Xe ba gác", "code": "TRICYCLE", "capacity_kg": 300, "length_m": 1.5, "width_m": 1.0, "height_m": 1.2, "image_url": None, "is_active": True},
]

LEGACY_PRICING_RULES: list[dict[str, object]] = [
    {"vehicle_code": "VAN_500KG", "base_price": 240000, "rate_2to10": 24000, "rate_10to15": 21000, "rate_15to40": 20000, "rate_over40": 18000},
    {"vehicle_code": "VAN_1T", "base_price": 330000, "rate_2to10": 30000, "rate_10to15": 26000, "rate_15to40": 22000, "rate_over40": 20000},
    {"vehicle_code": "TRUCK_500KG", "base_price": 300000, "rate_2to10": 26000, "rate_10to15": 24000, "rate_15to40": 21000, "rate_over40": 19000},
    {"vehicle_code": "TRUCK_1T", "base_price": 400000, "rate_2to10": 32000, "rate_10to15": 26000, "rate_15to40": 24000, "rate_over40": 22000},
    {"vehicle_code": "TRUCK_1_5T", "base_price": 410000, "rate_2to10": 34000, "rate_10to15": 28000, "rate_15to40": 25000, "rate_over40": 23000},
    {"vehicle_code": "TRUCK_2T", "base_price": 500000, "rate_2to10": 39000, "rate_10to15": 32000, "rate_15to40": 29000, "rate_over40": 26000},
    {"vehicle_code": "MOTORCYCLE", "base_price": 30000, "rate_2to10": 12000, "rate_10to15": 14000, "rate_15to40": 16000, "rate_over40": 15000},
    {"vehicle_code": "TRICYCLE", "base_price": 75000, "rate_2to10": 18000, "rate_10to15": 22000, "rate_15to40": 24000, "rate_over40": 21000},
]


@dataclass(slots=True)
class SeedSummary:
    created_roles: list[str] = field(default_factory=list)
    admin_created: bool = False
    admin_email: str | None = None
    admin_roles_added: list[str] = field(default_factory=list)
    admin_skipped: bool = False
    vehicle_types_seeded: int = 0
    pricing_rules_seeded: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "created_roles": self.created_roles,
            "admin_created": self.admin_created,
            "admin_email": self.admin_email,
            "admin_roles_added": self.admin_roles_added,
            "admin_skipped": self.admin_skipped,
            "vehicle_types_seeded": self.vehicle_types_seeded,
            "pricing_rules_seeded": self.pricing_rules_seeded,
        }


async def _ensure_roles(session: AsyncSession) -> tuple[dict[str, Role], list[str]]:
    role_names = list(DEFAULT_ROLES.keys())
    statement = select(Role).where(Role.name.in_(role_names))
    rows = await session.scalars(statement)
    role_map = {role.name: role for role in rows}

    created: list[str] = []
    for role_name, description in DEFAULT_ROLES.items():
        if role_name in role_map:
            continue
        role = Role(name=role_name, description=description)
        session.add(role)
        role_map[role_name] = role
        created.append(role_name)

    if created:
        await session.flush()

    return role_map, created


async def _ensure_admin_user(
    session: AsyncSession,
    *,
    settings: Settings,
    role_map: dict[str, Role],
) -> tuple[bool, str | None, list[str], bool]:
    admin_email = (settings.seed_admin_email or "").strip().lower()
    admin_password = settings.seed_admin_password or ""

    if not admin_email:
        return False, None, [], True

    if not admin_password:
        raise ValueError("SEED_ADMIN_PASSWORD is required when SEED_ADMIN_EMAIL is set.")

    statement = (
        select(User)
        .options(selectinload(User.roles))
        .where(func.lower(User.email) == admin_email.lower())
    )
    result = await session.execute(statement)
    user = result.scalars().first()

    created = False
    if user is None:
        user = User(
            email=admin_email,
            password_hash=get_password_hash(admin_password),
            full_name=settings.seed_admin_display_name,
            display_name=settings.seed_admin_display_name,
            tier="Gold",
            is_active=True,
            email_verified_at=utc_now() if settings.seed_admin_mark_email_verified else None,
        )
        user.roles = []
        session.add(user)
        await session.flush()
        created = True
    else:
        await session.refresh(user, attribute_names=["roles"])

    roles_added: list[str] = []
    existing_role_names = {role.name for role in user.roles}
    for role_name in ("Admin", "User"):
        role = role_map.get(role_name)
        if role is None or role_name in existing_role_names:
            continue
        user.roles.append(role)
        roles_added.append(role_name)

    return created, admin_email, roles_added, False

async def _ensure_legacy_vehicle_types(
    session: AsyncSession,
) -> tuple[dict[str, VehicleType], int]:
    statement = select(VehicleType)
    existing_rows = await session.scalars(statement)
    existing_by_code = {row.code.upper(): row for row in existing_rows}

    seeded_count = 0
    for item in LEGACY_VEHICLE_TYPES:
        code = str(item["code"]).upper()
        row = existing_by_code.get(code)
        if row is None:
            row = VehicleType(code=code, name=str(item["name"]))
            session.add(row)
            existing_by_code[code] = row

        row.name = str(item["name"])
        row.capacity_kg = int(item["capacity_kg"])
        row.length_m = item["length_m"]
        row.width_m = item["width_m"]
        row.height_m = item["height_m"]
        row.image_url = item["image_url"]
        row.is_active = bool(item["is_active"])
        seeded_count += 1

    await session.flush()
    return existing_by_code, seeded_count


async def _ensure_legacy_pricing_rules(
    session: AsyncSession,
    *,
    vehicles_by_code: dict[str, VehicleType],
) -> int:
    statement = select(VehiclePricingRule).where(VehiclePricingRule.effective_from == LEGACY_EFFECTIVE_FROM)
    existing_rows = await session.scalars(statement)
    existing_by_vehicle_id = {row.vehicle_type_id: row for row in existing_rows}

    seeded_count = 0
    for item in LEGACY_PRICING_RULES:
        vehicle_code = str(item["vehicle_code"]).upper()
        vehicle = vehicles_by_code.get(vehicle_code)
        if vehicle is None:
            continue

        row = existing_by_vehicle_id.get(vehicle.id)
        if row is None:
            row = VehiclePricingRule(
                vehicle_type_id=vehicle.id,
                effective_from=LEGACY_EFFECTIVE_FROM,
                effective_to=None,
                rule_name=f"Pricing {vehicle.code}",
                price_per_km=0,
                minimum_price=None,
                currency_code="VND",
                notes=None,
            )
            session.add(row)
            existing_by_vehicle_id[vehicle.id] = row

        row.base_price = item["base_price"]
        row.rate_2to10 = item["rate_2to10"]
        row.rate_10to15 = item["rate_10to15"]
        row.rate_15to40 = item["rate_15to40"]
        row.rate_over40 = item["rate_over40"]
        row.currency = "VND"
        row.currency_code = "VND"
        row.is_active = True
        row.price_per_km = item["rate_2to10"]
        seeded_count += 1

    await session.flush()
    return seeded_count


async def seed_data(*, settings: Settings | None = None, skip_admin: bool = False) -> SeedSummary:
    resolved_settings = settings or get_settings()
    summary = SeedSummary()

    async with AsyncSessionFactory() as session:
        async with session.begin():
            role_map, created_roles = await _ensure_roles(session)
            summary.created_roles.extend(created_roles)

            if skip_admin:
                summary.admin_skipped = True
            else:
                created, admin_email, roles_added, skipped = await _ensure_admin_user(
                    session,
                    settings=resolved_settings,
                    role_map=role_map,
                )
                summary.admin_created = created
                summary.admin_email = admin_email
                summary.admin_roles_added.extend(roles_added)
                summary.admin_skipped = skipped

            vehicles_by_code, vehicles_seeded = await _ensure_legacy_vehicle_types(session)
            summary.vehicle_types_seeded = vehicles_seeded
            summary.pricing_rules_seeded = await _ensure_legacy_pricing_rules(
                session,
                vehicles_by_code=vehicles_by_code,
            )

    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed default roles and optional admin user.")
    parser.add_argument(
        "--skip-admin",
        action="store_true",
        help="Seed only roles and skip admin user creation.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print result as JSON.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    summary = asyncio.run(seed_data(skip_admin=args.skip_admin))
    if args.json:
        print(json.dumps(summary.to_dict(), indent=2))
        return

    print("Seed completed.")
    print(f"Created roles: {summary.created_roles or 'none'}")
    if summary.admin_skipped:
        print("Admin user: skipped")
    elif summary.admin_email is None:
        print("Admin user: not configured (set SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD)")
    else:
        status = "created" if summary.admin_created else "already existed"
        print(f"Admin user: {summary.admin_email} ({status})")
        print(f"Admin roles added: {summary.admin_roles_added or 'none'}")
    print(f"Vehicle types seeded: {summary.vehicle_types_seeded}")
    print(f"Pricing rules seeded: {summary.pricing_rules_seeded}")


if __name__ == "__main__":
    main()

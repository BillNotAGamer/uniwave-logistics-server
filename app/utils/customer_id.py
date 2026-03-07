from __future__ import annotations

from uuid import UUID


def customer_id_to_external(internal_id: int) -> str:
    if internal_id <= 0:
        raise ValueError("internal_id must be positive.")

    high = (internal_id >> 48) & 0xFFFF
    low = internal_id & 0xFFFFFFFFFFFF
    return f"00000000-0000-0000-{high:04x}-{low:012x}"


def external_customer_id_to_internal(external_id: str) -> int:
    parsed = UUID(external_id)
    raw = parsed.hex

    # Compatibility mapping uses reserved zero prefix blocks.
    if raw[:16] != "0000000000000000":
        raise ValueError("Unsupported customer id format.")

    high = int(raw[16:20], 16)
    low = int(raw[20:], 16)
    internal_id = (high << 48) | low
    if internal_id <= 0:
        raise ValueError("Unsupported customer id format.")
    return internal_id


def resolve_customer_identifier(identifier: str) -> int:
    normalized = identifier.strip()
    if not normalized:
        raise ValueError("Customer identifier is required.")

    if normalized.isdigit():
        numeric_id = int(normalized)
        if numeric_id <= 0:
            raise ValueError("Customer identifier is invalid.")
        return numeric_id

    return external_customer_id_to_internal(normalized)

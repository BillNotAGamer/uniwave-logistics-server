from __future__ import annotations

from uuid import UUID

ORDER_GUID_PREFIX_HEX = "1000000000000000"


def order_id_to_external(internal_id: int) -> str:
    if internal_id <= 0:
        raise ValueError("internal_id must be positive.")

    high = (internal_id >> 48) & 0xFFFF
    low = internal_id & 0xFFFFFFFFFFFF
    return f"10000000-0000-0000-{high:04x}-{low:012x}"


def external_order_id_to_internal(external_id: str) -> int:
    parsed = UUID(external_id)
    raw = parsed.hex

    if raw[:16] != ORDER_GUID_PREFIX_HEX:
        raise ValueError("Unsupported order id format.")

    high = int(raw[16:20], 16)
    low = int(raw[20:], 16)
    internal_id = (high << 48) | low
    if internal_id <= 0:
        raise ValueError("Unsupported order id format.")
    return internal_id


def resolve_order_identifier(identifier: str) -> int:
    normalized = identifier.strip()
    if not normalized:
        raise ValueError("Order identifier is required.")

    if normalized.isdigit():
        numeric_id = int(normalized)
        if numeric_id <= 0:
            raise ValueError("Order identifier is invalid.")
        return numeric_id

    return external_order_id_to_internal(normalized)

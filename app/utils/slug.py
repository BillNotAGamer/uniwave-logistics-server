from __future__ import annotations

import re
import unicodedata

_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LENGTH = 255


def slugify(value: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = _NON_ALNUM_PATTERN.sub("-", normalized).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)

    if not slug:
        return "post"

    trimmed = slug[:_MAX_SLUG_LENGTH].strip("-")
    return trimmed or "post"


def build_slug_candidate(base_slug: str, sequence: int) -> str:
    if sequence <= 1:
        return base_slug[:_MAX_SLUG_LENGTH]

    suffix = f"-{sequence}"
    max_base_length = _MAX_SLUG_LENGTH - len(suffix)
    trimmed_base = base_slug[:max_base_length].rstrip("-")
    if not trimmed_base:
        trimmed_base = "post"
    return f"{trimmed_base}{suffix}"

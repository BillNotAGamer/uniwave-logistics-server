from __future__ import annotations

import math

from app.schemas.base import APIModel


class PaginationMeta(APIModel):
    page: int | None = None
    page_size: int | None = None
    total_items: int
    total_pages: int | None = None
    is_unbounded: bool = False


def build_pagination_meta(
    *,
    total_items: int,
    page: int | None,
    page_size: int | None,
    is_unbounded: bool,
) -> PaginationMeta:
    normalized_total = max(total_items, 0)

    total_pages: int | None = None
    if not is_unbounded and page_size is not None and page_size > 0:
        total_pages = math.ceil(normalized_total / page_size)

    return PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=normalized_total,
        total_pages=total_pages,
        is_unbounded=is_unbounded,
    )
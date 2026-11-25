from __future__ import annotations

from app.schemas.pagination import PageMeta, PaginatedResponse, PaginationParams


def build_paginated_response(items: list, total: int, params: PaginationParams) -> PaginatedResponse:
    pages = max(1, (total + params.limit - 1) // params.limit)
    return PaginatedResponse(
        items=items,
        meta=PageMeta(
            page=params.page,
            limit=params.limit,
            total=total,
            pages=pages,
            search=params.search,
            sort_by=params.sort_by,
            sort_order=params.sort_order,
        ),
    )

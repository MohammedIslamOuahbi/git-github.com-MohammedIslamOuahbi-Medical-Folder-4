from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    sort_by: str | None = None
    sort_order: str = "desc"

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class PageMeta(BaseModel):
    page: int
    limit: int
    total: int
    pages: int
    search: str | None = None
    sort_by: str | None = None
    sort_order: str = "desc"


class PaginatedResponse(BaseModel):
    items: list[Any]
    meta: PageMeta

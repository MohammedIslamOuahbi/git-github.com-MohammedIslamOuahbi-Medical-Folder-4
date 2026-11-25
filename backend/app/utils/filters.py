from __future__ import annotations

from sqlalchemy import String, cast, or_


def build_search_filter(model, search: str, fields: list[str]):
    clauses = [cast(getattr(model, field), String).ilike(f"%{search}%") for field in fields]
    return or_(*clauses)

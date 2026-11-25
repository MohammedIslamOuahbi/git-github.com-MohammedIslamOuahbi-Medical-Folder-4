from __future__ import annotations

from app.exceptions import BadRequestException


def ensure_required_fields(data: dict, required_fields: list[str]) -> None:
    missing = [field for field in required_fields if not data.get(field)]
    if missing:
        raise BadRequestException("Validation error", {"missing_fields": missing})

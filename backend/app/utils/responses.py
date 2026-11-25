from __future__ import annotations

from fastapi.encoders import jsonable_encoder


def success_response(message: str, data=None) -> dict:
    return {"success": True, "message": message, "data": jsonable_encoder(data)}


def error_response(message: str, details=None) -> dict:
    return {"success": False, "message": message, "details": jsonable_encoder(details or {})}

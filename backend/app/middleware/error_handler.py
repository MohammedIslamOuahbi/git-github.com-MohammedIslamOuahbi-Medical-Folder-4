from __future__ import annotations

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi import Request
from fastapi.responses import JSONResponse

from app.utils.responses import error_response


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    del request
    if isinstance(exc, RequestValidationError):
        return JSONResponse(status_code=422, content=error_response("Validation error", {"errors": exc.errors()}))
    if isinstance(exc, HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail), "details": {}}
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(detail.get("message", "Request failed"), detail.get("details", {})),
        )
    return JSONResponse(status_code=500, content=error_response("Internal server error"))

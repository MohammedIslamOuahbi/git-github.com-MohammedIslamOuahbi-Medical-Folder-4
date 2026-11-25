from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.maintenance_mode import maintenance_mode_state
from app.utils.responses import error_response

ALLOWED_PATH_PREFIXES = (
    "/health",
    "/",
    "/api/v1/system-backups/status",
    "/api/v1/system-backups/restore",
)


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        snapshot = maintenance_mode_state.snapshot()
        if snapshot["enabled"]:
            path = request.url.path
            if not any(path == allowed or path.startswith(f"{allowed}/") for allowed in ALLOWED_PATH_PREFIXES):
                return JSONResponse(
                    status_code=503,
                    content=error_response(
                        "La base PostgreSQL est temporairement indisponible pendant la restauration.",
                        {"code": "POSTGRES_MAINTENANCE_MODE"},
                    ),
                )
        return await call_next(request)

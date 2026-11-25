from __future__ import annotations

import socket
import time

from fastapi import FastAPI
from fastapi import Depends
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.core.logging import configure_logging
from app.database import engine
from app.dependencies.database import get_db
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.error_handler import http_exception_handler
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.maintenance_mode import MaintenanceModeMiddleware
from app.routers import legacy_recovery, audit_logs, auth, backup, bootstrap, branches, campaigns, central, client_sync, companies, dashboard, drilling_sites, imports, installation, local_connection, medical_tests, medical_visits, medicines, medicine_imports, mission, network, permissions, prescriptions, reports, roles, sync, sync_v2, users, worker_tests, workers, workspaces, orientation_certificate, aptitude_certificate, system_backups
from app.services.build_info_service import get_build_info
from app.services.client_sync_journal import register_client_sync_journal
from app.services.sync_journal import register_sync_journal
from app.services.server_identity import get_public_server_identity
from app.services.application_seed_service import ApplicationSeedService
from app.utils.responses import success_response
from app.routers import campaign_tests

configure_logging()
register_client_sync_journal()
register_sync_journal()

STARTED_AT = time.monotonic()
app = FastAPI(title=settings.app_name)
bootstrap_service = ApplicationSeedService()


def _base_database_health_payload() -> dict[str, object | None]:
    return {
        "api_status": "online",
        "database_engine": "PostgreSQL",
        "database_type": "PostgreSQL",
        "database_status": "connected",
        "database_name": settings.database_name,
        "database_host": settings.database_host,
        "database_port": settings.database_port,
        "postgresql_version": None,
        "database_size_bytes": None,
        "active_connections": None,
        "pool_checked_out": None,
        "pool_size": None,
        "server_time": None,
        "uptime_seconds": int(time.monotonic() - STARTED_AT),
        "production_ready": False,
    }


def _attach_pool_metrics(details: dict[str, object | None]) -> None:
    pool = engine.pool
    for key, accessor in {
        "pool_checked_out": "checkedout",
        "pool_size": "size",
    }.items():
        value = getattr(pool, accessor, None)
        if callable(value):
            try:
                details[key] = int(value())
            except Exception:  # noqa: BLE001
                details[key] = None


def _collect_database_health(*, include_diagnostics: bool) -> dict[str, object | None]:
    details = _base_database_health_payload()
    database_state = "connected"

    try:
        with engine.connect() as connection:
            connection.execute(text("SET LOCAL statement_timeout = '3000ms'"))
            connection.execute(text("SELECT 1"))

            details["production_ready"] = True
            if include_diagnostics:
                row = connection.execute(
                    text(
                        """
                        SELECT
                            version() AS postgresql_version,
                            pg_database_size(current_database()) AS database_size_bytes,
                            (
                                SELECT COUNT(*)
                                FROM pg_stat_activity
                                WHERE datname = current_database()
                            ) AS active_connections,
                            now() AS server_time
                        """
                    )
                ).mappings().one()
                details.update(
                    {
                        "postgresql_version": row["postgresql_version"],
                        "database_size_bytes": int(row["database_size_bytes"] or 0),
                        "active_connections": int(row["active_connections"] or 0),
                        "server_time": row["server_time"].isoformat() if row["server_time"] else None,
                    }
                )
    except Exception:  # noqa: BLE001
        database_state = "disconnected"
        details["database_status"] = database_state
        details["production_ready"] = False

    if include_diagnostics:
        _attach_pool_metrics(details)

    return {"status": "ok" if database_state == "connected" else "error", **details}

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_origin_regex=settings.backend_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(MaintenanceModeMiddleware)

api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(users.router, prefix=api_prefix)
app.include_router(permissions.router, prefix=api_prefix)
app.include_router(roles.router, prefix=api_prefix)
app.include_router(companies.router, prefix=api_prefix)
app.include_router(branches.router, prefix=api_prefix)
app.include_router(drilling_sites.router, prefix=api_prefix)
app.include_router(workers.router, prefix=api_prefix)
app.include_router(campaigns.router, prefix=api_prefix)
app.include_router(medical_tests.router, prefix=api_prefix)
app.include_router(medical_visits.router, prefix=api_prefix)
app.include_router(prescriptions.router, prefix=api_prefix)
app.include_router(medicines.router, prefix=api_prefix)
app.include_router(medicine_imports.router, prefix=api_prefix)
app.include_router(worker_tests.router, prefix=api_prefix)
app.include_router(imports.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(sync.router, prefix=api_prefix)
app.include_router(sync_v2.router, prefix=api_prefix)
app.include_router(central.router, prefix=api_prefix)
app.include_router(central.central_sync_router, prefix=api_prefix)
app.include_router(central.system_router, prefix=api_prefix)
app.include_router(network.router, prefix=api_prefix)
app.include_router(local_connection.router, prefix=api_prefix)
app.include_router(backup.router, prefix=api_prefix)
app.include_router(system_backups.router, prefix=api_prefix)
app.include_router(audit_logs.router, prefix=api_prefix)
app.include_router(workspaces.router, prefix=api_prefix)
app.include_router(client_sync.router, prefix=api_prefix)
app.include_router(legacy_recovery.router, prefix=api_prefix)
app.include_router(mission.router, prefix=api_prefix)
app.include_router(mission.mission_sync_router, prefix=api_prefix)
app.include_router(mission.runtime_router, prefix=api_prefix)
app.include_router(mission.device_router, prefix=api_prefix)
app.include_router(bootstrap.router, prefix=api_prefix)
app.include_router(installation.router, prefix=api_prefix)

app.include_router(orientation_certificate.router, prefix=api_prefix)
app.include_router(aptitude_certificate.router, prefix=api_prefix)
app.include_router(campaign_tests.router, prefix=api_prefix)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, http_exception_handler)
app.add_exception_handler(Exception, http_exception_handler)


@app.get("/")
def root():
    return success_response("Medical Clinic Management System API", {"version": get_build_info()["version"]})


@app.get("/health")
def healthcheck():
    return success_response("Service healthy", {"status": "ok"})


@app.get("/health/build")
def health_build():
    return success_response("Build health", {"status": "ok", **get_build_info()})


@app.get("/health/identity")
def health_identity():
    return success_response(
        "Server identity",
        get_public_server_identity(),
    )


@app.get("/health/database")
def health_database():
    return success_response("Database health", _collect_database_health(include_diagnostics=False))


@app.get("/health/database/details")
def health_database_details():
    return success_response("Database health details", _collect_database_health(include_diagnostics=True))


@app.get("/health/network-info")
def health_network_info():
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except OSError:
        local_ip = "127.0.0.1"

    return success_response(
        "Network info",
        {
            "status": "ok",
            "hostname": socket.gethostname(),
            "local_ip_address": local_ip,
            "api_base_url": settings.api_base_url,
        },
    )


@app.get("/api/v1/bootstrap/status")
def bootstrap_status_alias(db=Depends(get_db)):
    return success_response("Bootstrap status", bootstrap_service.status(db))

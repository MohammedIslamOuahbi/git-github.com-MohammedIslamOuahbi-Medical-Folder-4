from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import json
import os
import sys
import traceback
from pathlib import Path

import uvicorn
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from app.core.logging import get_logger
from app.services.build_info_service import get_build_info


IGNORED_PRE_ALEMBIC_TABLES = {
    "spatial_ref_sys",
}

logger = get_logger("app.tauri_sidecar")
MIGRATION_ADVISORY_LOCK_KEY = 8_632_541_109_447


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", runtime_dir()))
    return Path(__file__).resolve().parent


def ensure_backend_on_path() -> None:
    backend_root = runtime_dir()
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)


def load_runtime_environment() -> None:
    base_dir = runtime_dir()
    env_candidates = [
        base_dir / "backend.env",
        Path.cwd() / "backend.env",
        bundle_dir() / "backend.env",
        base_dir / ".env",
        Path(__file__).resolve().parent / ".env",
    ]

    for candidate in env_candidates:
        if candidate.exists():
            load_dotenv(candidate, override=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FastAPI backend as a Tauri sidecar.")
    parser.add_argument("--host", default=os.environ.get("BACKEND_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("BACKEND_PORT", "8000")))
    parser.add_argument("--alembic-upgrade", action="store_true")
    parser.add_argument("--client-sync-import", default=None)
    parser.add_argument("--client-sync-inspect", default=None)
    parser.add_argument("--client-sync-history", action="store_true")
    parser.add_argument("--client-sync-status", action="store_true")
    parser.add_argument("--application-bootstrap", action="store_true")
    parser.add_argument("--ensure-reference-data", action="store_true")
    parser.add_argument("--inspect-alembic", action="store_true")
    parser.add_argument("--version", action="store_true")
    return parser.parse_args()


def configure_environment(args: argparse.Namespace) -> None:
    app_env = os.environ.get("APP_ENV")
    if not app_env:
        os.environ["APP_ENV"] = "production"

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        raise RuntimeError("DATABASE_URL must be configured with a PostgreSQL URL before starting the backend sidecar.")

    os.environ.setdefault("API_BASE_URL", f"http://127.0.0.1:{args.port}/api/v1")
    os.environ.setdefault("BACKEND_HOST", args.host)
    os.environ.setdefault("BACKEND_PORT", str(args.port))
    os.environ.setdefault(
        "BACKEND_CORS_ORIGINS",
        ",".join(
            [
                "tauri://localhost",
                "http://tauri.localhost",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:8000",
            ]
        ),
    )
    os.environ.setdefault("APP_NAME", "Ibn Sina Medical Clinic")


def log_runtime_diagnostics() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("[sidecar] DATABASE_URL is not configured. PostgreSQL is required.")
        return

    parsed = make_url(database_url)
    print(
        "[sidecar] PostgreSQL DATABASE_URL is configured. "
        f"host={parsed.host or 'unknown'} "
        f"port={parsed.port or 5432} "
        f"database={parsed.database or 'unknown'} "
        f"user={parsed.username or 'unknown'}"
    )


def build_alembic_config() -> AlembicConfig:
    alembic_root = bundle_dir()
    alembic_ini = alembic_root / "alembic.ini"
    script_location = alembic_root / "alembic"
    validate_alembic_assets(alembic_ini, script_location)
    config = AlembicConfig(str(alembic_ini))
    config.set_main_option("script_location", str(script_location))
    return config


def inspect_schema_state(database_url: str) -> dict[str, object]:
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            public_tables = sorted(
                table_name
                for table_name in inspector.get_table_names(schema="public")
                if table_name not in IGNORED_PRE_ALEMBIC_TABLES
            )
            return {
                "has_alembic_version": "alembic_version" in public_tables,
                "public_tables": public_tables,
                "unexpected_public_tables": [table for table in public_tables if table != "alembic_version"],
            }
    finally:
        engine.dispose()


def assert_schema_is_owned_by_alembic(database_url: str) -> None:
    schema_state = inspect_schema_state(database_url)
    has_alembic_version = bool(schema_state["has_alembic_version"])
    unexpected_public_tables = list(schema_state["unexpected_public_tables"])
    if has_alembic_version:
        return
    if unexpected_public_tables:
        tables = ", ".join(unexpected_public_tables)
        raise RuntimeError(
            "SCHEMA_CREATED_OUTSIDE_ALEMBIC: La base contient deja des tables applicatives "
            "sans revision Alembic. Supprimez les tables creees hors migrations ou relancez "
            f"la configuration sur une base vide. Tables detectees: {tables}"
        )


def verify_alembic_head(config: AlembicConfig) -> None:
    script = ScriptDirectory.from_config(config)
    expected_heads = set(script.get_heads())
    if not expected_heads:
        raise RuntimeError("ALEMBIC_REVISION_NOT_BUNDLED: Aucune revision Alembic n'est disponible.")

    database_url = os.environ.get("DATABASE_URL", "")
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_heads = set(context.get_current_heads())

        if current_heads != expected_heads:
            raise RuntimeError(
                "ALEMBIC_REVISION_SCHEMA_MISMATCH: La base n'est pas a la derniere revision Alembic. "
                f"Current: {sorted(current_heads)} Expected: {sorted(expected_heads)}"
            )
    finally:
        engine.dispose()


def collect_migration_table_owners(config: AlembicConfig) -> dict[str, list[str]]:
    script_location = Path(config.get_main_option("script_location"))
    owners: dict[str, list[str]] = defaultdict(list)
    for path in sorted((script_location / "versions").glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            raise RuntimeError(
                f"DUPLICATE_TABLE_MIGRATION_DEFINITION: Migration invalide {path.name}: {exc}"
            ) from exc
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "create_table" or not node.args:
                continue
            table_name_node = node.args[0]
            if isinstance(table_name_node, ast.Constant) and isinstance(table_name_node.value, str):
                owners[table_name_node.value].append(path.name)
    duplicates = {
        table_name: files
        for table_name, files in owners.items()
        if len(files) > 1
    }
    if duplicates:
        raise RuntimeError(
            "DUPLICATE_TABLE_MIGRATION_DEFINITION: Plusieurs migrations creent les memes tables. "
            f"Conflicts: {duplicates}"
        )
    return dict(owners)


def assert_single_head(config: AlembicConfig) -> list[str]:
    script = ScriptDirectory.from_config(config)
    heads = sorted(script.get_heads())
    if len(heads) != 1:
        raise RuntimeError(
            "ALEMBIC_MULTIPLE_HEADS: Plusieurs heads Alembic ont ete detectes. "
            f"Heads actuels: {heads}"
        )
    return heads


def acquire_migration_lock(database_url: str):
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    connection = engine.connect()
    acquired = bool(
        connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": MIGRATION_ADVISORY_LOCK_KEY},
        ).scalar()
    )
    if not acquired:
        connection.close()
        engine.dispose()
        raise RuntimeError(
            "ALEMBIC_MIGRATION_ALREADY_RUNNING: Une autre migration Alembic est deja en cours."
        )
    return engine, connection


def validate_alembic_assets(alembic_ini: Path, script_location: Path) -> None:
    versions_dir = script_location / "versions"
    revision_files = sorted(versions_dir.glob("*.py")) if versions_dir.exists() else []
    missing = []
    if not alembic_ini.exists():
        missing.append("alembic.ini")
    if not (script_location / "env.py").exists():
        missing.append("alembic/env.py")
    if not (script_location / "script.py.mako").exists():
        missing.append("alembic/script.py.mako")
    if not versions_dir.exists():
        missing.append("alembic/versions")
    if not revision_files:
        missing.append("alembic/versions/*.py")
    if missing:
        raise RuntimeError(
            "ALEMBIC_REVISION_NOT_BUNDLED: Les migrations Alembic integrees a cette version de "
            "l'application sont incompletes. Reinstallez une version contenant toutes les revisions. "
            f"Missing: {', '.join(missing)}"
        )


def inspect_alembic_bundle() -> int:
    config = build_alembic_config()
    script = ScriptDirectory.from_config(config)
    revisions = sorted(revision.revision for revision in script.walk_revisions())
    heads = sorted(script.get_heads())
    payload = {
        "success": bool(revisions and heads),
        "revision_count": len(revisions),
        "revisions": revisions,
        "heads": heads,
        "script_location": config.get_main_option("script_location"),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["success"] else 2


def print_build_info() -> int:
    print(json.dumps(get_build_info(), sort_keys=True, default=str))
    return 0


def run_alembic_upgrade() -> int:
    database_url = os.environ.get("DATABASE_URL", "")
    config = build_alembic_config()
    collect_migration_table_owners(config)
    assert_single_head(config)
    logger.info("database.preflight_started")
    schema_state = inspect_schema_state(database_url)
    logger.info(
        "database.preflight_completed has_alembic_version=%s public_tables=%s unexpected_public_tables=%s",
        schema_state["has_alembic_version"],
        schema_state["public_tables"],
        schema_state["unexpected_public_tables"],
    )
    assert_schema_is_owned_by_alembic(database_url)
    lock_engine, lock_connection = acquire_migration_lock(database_url)
    try:
        logger.info("alembic.upgrade_started")
        alembic_command.upgrade(config, "head")
        logger.info("alembic.upgrade_completed")
        verify_alembic_head(config)
        logger.info("alembic.head_verified")
    finally:
        try:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": MIGRATION_ADVISORY_LOCK_KEY},
            )
        finally:
            lock_connection.close()
            lock_engine.dispose()
    print("[sidecar] Alembic upgrade head completed successfully.")
    return 0


def run_client_sync_import(package_path: str) -> int:
    # Guard before importing database services or running Alembic.
    from app.services.sync_safety import SAFETY_CODE, SAFETY_MESSAGE
    print(json.dumps({"success": False, "code": SAFETY_CODE,
                      "retryable": False, "message": SAFETY_MESSAGE}))
    return 1


def run_client_sync_inspect(package_path: str) -> int:
    from app.database import SessionLocal
    from app.services.client_sync_import_service import ClientSyncImportService

    run_alembic_upgrade()
    with SessionLocal() as db:
        result = ClientSyncImportService().inspect_package(db, package_path)
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


def run_client_sync_history() -> int:
    from app.database import SessionLocal
    from app.services.client_sync_import_service import ClientSyncImportService

    run_alembic_upgrade()
    with SessionLocal() as db:
        result = ClientSyncImportService().history(db)
    print(json.dumps({"history": result}, sort_keys=True, default=str))
    return 0


def run_client_sync_status() -> int:
    from app.database import SessionLocal
    from app.services.client_sync_import_service import ClientSyncImportService

    run_alembic_upgrade()
    with SessionLocal() as db:
        result = ClientSyncImportService().local_status(db)
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


def run_application_bootstrap() -> int:
    from app.database import SessionLocal
    from app.services.application_seed_service import (
        ApplicationBootstrapError,
        ApplicationSeedService,
        InitialUserPayload,
    )

    run_alembic_upgrade()
    with SessionLocal() as db:
        service = ApplicationSeedService()
        logger.info("seed.started mode=application_bootstrap")
        payload = InitialUserPayload(
            first_name=os.environ.get("INITIAL_ADMIN_FIRST_NAME", ""),
            last_name=os.environ.get("INITIAL_ADMIN_LAST_NAME", ""),
            email=os.environ.get("INITIAL_ADMIN_EMAIL", ""),
            password=os.environ.get("INITIAL_ADMIN_PASSWORD", ""),
            phone=os.environ.get("INITIAL_ADMIN_PHONE") or None,
            qualification=os.environ.get("INITIAL_ADMIN_QUALIFICATION") or None,
        )
        try:
            result = service.initialize_application(db, initial_user=payload)
            logger.info("seed.completed mode=application_bootstrap")
            print(json.dumps(result, sort_keys=True, default=str))
            return 0
        except ApplicationBootstrapError as error:
            logger.exception(
                "seed.failed mode=application_bootstrap stage=%s code=%s",
                error.stage,
                error.code,
            )
            print(json.dumps(error.to_dict(), sort_keys=True, default=str))
            traceback.print_exc(file=sys.stderr)
            return 1


def run_ensure_reference_data() -> int:
    from app.database import SessionLocal
    from app.services.application_seed_service import ApplicationBootstrapError, ApplicationSeedService

    run_alembic_upgrade()
    with SessionLocal() as db:
        logger.info("seed.started mode=ensure_reference_data")
        try:
            result = ApplicationSeedService().ensure_reference_data(db)
            logger.info("seed.completed mode=ensure_reference_data")
            print(json.dumps(result, sort_keys=True, default=str))
            return 0
        except ApplicationBootstrapError as error:
            logger.exception(
                "seed.failed mode=ensure_reference_data stage=%s code=%s",
                error.stage,
                error.code,
            )
            print(json.dumps(error.to_dict(), sort_keys=True, default=str))
            traceback.print_exc(file=sys.stderr)
            return 1


def main() -> int:
    ensure_backend_on_path()
    load_runtime_environment()
    arguments = parse_args()

    if arguments.version:
        return print_build_info()
    if arguments.inspect_alembic:
        return inspect_alembic_bundle()

    if arguments.client_sync_import:
        return run_client_sync_import(arguments.client_sync_import)

    configure_environment(arguments)
    log_runtime_diagnostics()

    if arguments.alembic_upgrade:
        return run_alembic_upgrade()

    if arguments.client_sync_inspect:
        return run_client_sync_inspect(arguments.client_sync_inspect)
    if arguments.client_sync_history:
        return run_client_sync_history()
    if arguments.client_sync_status:
        return run_client_sync_status()
    if arguments.application_bootstrap:
        return run_application_bootstrap()
    if arguments.ensure_reference_data:
        return run_ensure_reference_data()

    from app.main import app

    logger.info("backend.starting host=%s port=%s", arguments.host, arguments.port)
    uvicorn.run(app, host=arguments.host, port=arguments.port, reload=False)
    logger.info("backend.ready host=%s port=%s", arguments.host, arguments.port)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CommandError as error:
        message = str(error)
        if "Can't locate revision" in message or "Can't locate" in message:
            print(
                "ALEMBIC_REVISION_NOT_BUNDLED: Les migrations Alembic integrees a cette version de "
                "l'application sont incompletes. Reinstallez une version contenant la revision attendue.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        raise
    except RuntimeError as error:
        if str(error).startswith("ALEMBIC_REVISION_NOT_BUNDLED"):
            print(str(error), file=sys.stderr)
            raise SystemExit(2)
        raise

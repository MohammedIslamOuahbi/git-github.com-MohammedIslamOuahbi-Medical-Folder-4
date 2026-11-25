"""Database-free tests: execute the actual guarded method bodies without app startup.

Run explicitly with unittest, never through backend/tests/conftest.py.
"""
from __future__ import annotations

import ast
import contextlib
import inspect
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.middleware.error_handler import http_exception_handler
from app.services.sync_safety import SAFETY_CODE, suspend_for_data_safety


TARGETS = {
    "app/repositories/sync_repository.py": ["push_changes", "resolve_conflict"],
    "app/services/sync_service.py": ["push", "resolve_conflict"],
    "app/services/sync_connection_service.py": ["run"],
    "app/services/central_sync_service.py": ["apply_central_pull", "resolve_conflict"],
    "app/services/client_sync_import_service.py": ["import_package"],
    "app/services/client_sync_service.py": ["export"],
    "app/services/mission_copy_service.py": ["apply_batch"],
}


class Untouchable:
    def __getattribute__(self, name):
        raise AssertionError(f"Unexpected access before safety barrier: {name}")


def extract(relative, name, **namespace):
    """Compile real source, avoiding database/model imports and their side effects."""
    path = ROOT / "backend" / relative
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    fn.decorator_list = []
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), fn], type_ignores=[])
    ast.fix_missing_locations(module)
    scope = {"suspend_for_data_safety": suspend_for_data_safety, **namespace}
    exec(compile(module, str(path), "exec"), scope)
    return scope[name]


def call_guarded(fn):
    return fn(**{name: Untouchable() for name, p in inspect.signature(fn).parameters.items()
                 if p.default is inspect.Parameter.empty})


class SafetyTests(unittest.TestCase):
    def test_all_service_and_repository_entries_fail_before_any_access(self):
        for path, names in TARGETS.items():
            for name in names:
                with self.subTest(path=path, method=name):
                    with self.assertRaises(HTTPException) as caught:
                        call_guarded(extract(path, name))
                    self.assertEqual(caught.exception.status_code, 423)
                    self.assertEqual(caught.exception.detail["details"]["code"], SAFETY_CODE)
                    self.assertFalse(caught.exception.detail["details"]["retryable"])

    def test_http_error_contract_for_every_guarded_body(self):
        app = FastAPI()
        app.add_exception_handler(HTTPException, http_exception_handler)
        def endpoint_for(fn):
            def endpoint():
                return call_guarded(fn)
            return endpoint
        for i, (path, names) in enumerate(TARGETS.items()):
            for name in names:
                app.add_api_route(f"/test/{i}/{name}", endpoint_for(extract(path, name)), methods=["POST"])
        with TestClient(app) as client:
            for route in app.routes:
                if not route.path.startswith("/test/"):
                    continue
                result = client.post(route.path)
                self.assertEqual(result.status_code, 423)
                self.assertFalse(result.json()["success"])
                self.assertEqual(result.json()["details"]["code"], SAFETY_CODE)
                self.assertFalse(result.json()["details"]["retryable"])

    def test_sidecar_import_does_not_load_db_or_run_migrations(self):
        def forbidden(*args, **kwargs):
            self.fail("Database or migration invoked")
        fn = extract("run_tauri_sidecar.py", "run_client_sync_import", json=json,
                     run_alembic_upgrade=forbidden, SessionLocal=forbidden)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(fn("nonexistent.sync"), 1)
        payload = json.loads(output.getvalue())
        self.assertFalse(payload["success"])
        self.assertEqual(payload["code"], SAFETY_CODE)
        self.assertFalse(payload["retryable"])
        self.assertNotIn("app.database", sys.modules)

    def test_sidecar_dispatch_precedes_configuration_and_upgrade(self):
        class Args:
            version = False
            inspect_alembic = False
            client_sync_import = "nonexistent.sync"
            alembic_upgrade = True
        def forbidden(*args):
            self.fail("Configuration/upgrade must not run for a blocked import")
        fn = extract("run_tauri_sidecar.py", "main", ensure_backend_on_path=lambda: None,
                     load_runtime_environment=lambda: None, parse_args=Args,
                     run_client_sync_import=lambda path: 1,
                     configure_environment=forbidden, run_alembic_upgrade=forbidden)
        self.assertEqual(fn(), 1)

    def test_read_operations_are_not_guarded(self):
        for path, names in {
            "app/services/sync_service.py": ["pull", "status"],
            "app/services/central_sync_service.py": ["pull", "list_conflicts", "get_conflict"],
            "app/services/client_sync_import_service.py": ["inspect_package", "history", "local_status"],
            "app/services/client_sync_service.py": ["status"],
            "app/services/backup_service.py": ["create_backup", "restore_backup"],
        }.items():
            tree = ast.parse((ROOT / "backend" / path).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in names:
                    self.assertFalse(any(isinstance(n, ast.Name) and n.id == "suspend_for_data_safety"
                                         for n in ast.walk(node)), (path, node.name))


if __name__ == "__main__":
    unittest.main()

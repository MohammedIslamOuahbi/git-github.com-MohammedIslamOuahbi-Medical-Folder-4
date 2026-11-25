"""Isolated recovery tests. No application database fixture or SQLite."""
from __future__ import annotations

import ast
import json
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.exceptions import BadRequestException, ForbiddenException
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.middleware.error_handler import http_exception_handler
from app.models.legacy_recovery import RecoveryIdentityCandidate, RecoveryItem, RecoverySource
from app.routers.legacy_recovery import router as recovery_router
from app.services.legacy_recovery_service import LegacyRecoveryService, require_access
from app.services.recovery_format import CaptureValidationError, digest, interpret, validate_envelope


class FakeSession:
    """Models commit boundaries; it does not claim to validate PostgreSQL persistence."""

    def __init__(self):
        self.sources = []
        self.items = []
        self.candidates = []
        self.staged = []
        self.commits = 0

    def scalar(self, query):
        parameters = query.compile().params
        matching = list(self.sources)
        for key, value in parameters.items():
            if key.startswith("source_scope_"):
                matching = [row for row in matching if row.source_scope == value]
            elif key.startswith("source_kind_"):
                matching = [row for row in matching if row.source_kind == value]
            elif key.startswith("logical_key_"):
                matching = [row for row in matching if row.logical_key == value]
            elif key.startswith("sha256_"):
                matching = [row for row in matching if row.sha256 == value]
        return matching[-1] if matching else None

    def get(self, model, key):
        return next((source for source in self.sources if source.uuid == key), None)

    def add(self, model):
        if model not in self.staged and model not in self.sources and model not in self.items and model not in self.candidates:
            self.staged.append(model)

    def flush(self):
        for item in self.staged:
            if isinstance(item, RecoveryItem) and item.id is None:
                item.id = len(self.items) + sum(isinstance(row, RecoveryItem) for row in self.staged[:self.staged.index(item)]) + 1

    def commit(self):
        for item in self.staged:
            if isinstance(item, RecoverySource):
                self.sources.append(item)
            elif isinstance(item, RecoveryItem):
                self.items.append(item)
            elif isinstance(item, RecoveryIdentityCandidate):
                self.candidates.append(item)
        self.staged.clear()
        self.commits += 1

    def rollback(self):
        self.staged.clear()


def queue_raw(rows):
    return json.dumps({"entries": {"clinic_sync_queue": json.dumps({"workers": rows})}}, ensure_ascii=False)


def capture(service, session, user, raw, *, profile="profile-one", identity="device-one", kind="browser_local_storage"):
    return service.capture(session, user, kind=kind, logical_key="working-data", profile_id=profile,
                           source_identity=identity, format_version=1, raw_payload=raw, sha256=digest(raw))


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(uuid=uuid.uuid4(), role="doctor", is_active=True)
        self.other = SimpleNamespace(uuid=uuid.uuid4(), role="doctor", is_active=True)
        self.session = FakeSession()
        self.service = LegacyRecoveryService()

    def test_same_snapshot_twice_no_duplicate_but_same_content_operations_distinct(self):
        row = {"uuid": str(uuid.uuid4()), "name": "synthetic"}
        raw = queue_raw([row, row])
        first = capture(self.service, self.session, self.user, raw)
        second = capture(self.service, self.session, self.user, raw)
        self.assertIs(first, second)
        self.assertEqual(len(self.session.sources), 1)
        self.assertEqual([item.ordinal for item in self.session.items], [0, 1])
        self.assertEqual(len(self.session.items), 2)
        self.assertEqual(first.state, "recorded")
        self.assertTrue(all(item.state == "waiting_engine" for item in self.session.items))

    def test_changed_snapshot_new_version_linked_to_original(self):
        first = capture(self.service, self.session, self.user, queue_raw([{"uuid": str(uuid.uuid4())}]))
        second = capture(self.service, self.session, self.user, queue_raw([{"uuid": str(uuid.uuid4())}]))
        self.assertNotEqual(first.uuid, second.uuid)
        self.assertEqual(second.parent_source_uuid, first.uuid)
        self.assertEqual(len(self.session.sources), 2)

    def test_capture_commit_survives_interrupted_interpretation_and_resume(self):
        class Interrupted(LegacyRecoveryService):
            def materialize(self, db, source):
                raise RuntimeError("synthetic interruption after raw capture commit")
        raw = queue_raw([{"uuid": str(uuid.uuid4())}])
        with self.assertRaises(RuntimeError):
            capture(Interrupted(), self.session, self.user, raw)
        self.assertEqual(len(self.session.sources), 1)
        self.assertEqual(len(self.session.items), 0)
        self.assertEqual(self.session.commits, 1)
        resumed = capture(self.service, self.session, self.user, raw)
        self.assertEqual(resumed.materialized_count, 1)
        self.assertEqual(len(self.session.sources), 1)
        self.assertEqual(len(self.session.items), 1)

    def test_batch_resume_without_repeating_first_page(self):
        rows = [{"uuid": str(uuid.uuid4())} for _ in range(105)]
        raw = queue_raw(rows)
        first = capture(self.service, self.session, self.user, raw)
        self.assertEqual(first.materialized_count, 100)
        self.assertEqual(first.state, "captured")
        next_source = capture(self.service, self.session, self.user, raw)
        self.assertEqual(next_source.materialized_count, 105)
        self.assertEqual(len(self.session.items), 105)
        self.assertEqual(len({(item.source_uuid, item.ordinal) for item in self.session.items}), 105)

    def test_bad_checksum_unsupported_format_and_corrupt_source(self):
        raw = queue_raw([])
        with self.assertRaises(CaptureValidationError):
            validate_envelope("browser_local_storage", 1, raw, "0" * 64)
        with self.assertRaises(CaptureValidationError):
            validate_envelope("browser_local_storage", 9, raw, digest(raw))
        with self.assertRaises(BadRequestException):
            self.service.capture(
                self.session, self.user, kind="browser_local_storage", logical_key="working-data",
                profile_id="profile-one", source_identity="device-one", format_version=1,
                raw_payload=raw, sha256="0" * 64)
        broken = "{"  # Preserve as source evidence, but never pretend it was interpreted.
        source = capture(self.service, self.session, self.user, broken)
        self.assertEqual(source.state, "needs_review")
        self.assertEqual(source.reason_code, "SOURCE_JSON_MALFORMED")
        self.assertEqual(source.raw_payload, broken)
        self.assertEqual(len(self.session.items), 0)

    def test_numeric_collision_is_scoped_and_relationships_are_not_guessed(self):
        row_a = {"id": 7, "company_id": 9, "uuid": str(uuid.uuid4())}
        row_b = {"id": 7, "company_id": 9, "uuid": str(uuid.uuid4())}
        first = capture(self.service, self.session, self.user, queue_raw([row_a]), profile="profile-one")
        second = capture(self.service, self.session, self.user, queue_raw([row_b]), profile="profile-two")
        self.assertNotEqual(first.source_scope, second.source_scope)
        self.assertEqual(len(self.session.candidates), 2)
        self.assertNotEqual(self.session.candidates[0].entity_uuid, self.session.candidates[1].entity_uuid)
        self.assertTrue(all(item.reason_code == "LEGACY_NUMERIC_RELATION" for item in self.session.items))
        self.assertTrue(all(candidate.status == "candidate_needs_review" for candidate in self.session.candidates))

    def test_missing_identity_draft_and_malformed_item_stay_for_review(self):
        draft = json.dumps({"entries": {"medical-folder.worker-medical-file.1.create.draft": json.dumps({"form_data": {"note": "synthetic"}})}})
        source = capture(self.service, self.session, self.user, draft, identity="")
        self.assertEqual(source.state, "needs_review")
        self.assertEqual(self.session.items[0].reason_code, "DRAFT_NOT_COMMITTED")
        malformed = json.dumps({"entries": {"clinic_sync_queue": "broken"}})
        source2 = capture(self.service, self.session, self.user, malformed)
        self.assertEqual(source2.state, "needs_review")
        self.assertEqual(self.session.items[-1].reason_code, "ITEM_JSON_MALFORMED")
        missing_relation = queue_raw([{"id": 1, "branch_id": 99}])
        parsed = interpret("browser_local_storage", missing_relation, "device")
        self.assertEqual(parsed.items[0].reason_code, "LEGACY_NUMERIC_RELATION")

    def test_sensitive_fields_rejected_without_leaking_values(self):
        raw = queue_raw([{"access_token": "synthetic-secret"}])
        with self.assertRaises(CaptureValidationError) as caught:
            interpret("browser_local_storage", raw, "device")
        self.assertNotIn("synthetic-secret", str(caught.exception))
        self.assertEqual(len(self.session.sources), 0)

    def test_package_checksum_and_claimed_origin_remain_reviewable(self):
        admin = SimpleNamespace(uuid=uuid.uuid4(), role="admin", is_active=True)
        payload = {"data": {"workers": [{"id": 1, "uuid": str(uuid.uuid4())}]}}
        corrupt = {**payload, "checksum_sha256": "0" * 64}
        with self.assertRaises(BadRequestException):
            capture(self.service, self.session, admin, json.dumps(corrupt), kind="legacy_package")
        raw = json.dumps(payload)
        one = self.service.capture(self.session, admin, kind="legacy_package", logical_key="same.sync",
                                   profile_id="browser", source_identity="claimed-package-server:one",
                                   format_version=1, raw_payload=raw, sha256=digest(raw))
        two = self.service.capture(self.session, admin, kind="legacy_package", logical_key="same.sync",
                                   profile_id="browser", source_identity="claimed-package-server:two",
                                   format_version=1, raw_payload=raw, sha256=digest(raw))
        self.assertNotEqual(one.uuid, two.uuid)
        self.assertNotEqual(one.source_scope, two.source_scope)
        self.assertTrue(all(candidate.status == "candidate_needs_review" for candidate in self.session.candidates))

    def test_authorization_blocks_other_user_and_nonadmin_package(self):
        source = capture(self.service, self.session, self.user, queue_raw([]))
        with self.assertRaises(ForbiddenException):
            require_access(self.other, source)
        with self.assertRaises(ForbiddenException):
            capture(self.service, self.session, self.user, json.dumps({"data": {}}), kind="legacy_package")
        self.assertEqual(len(self.session.sources), 1)

    def test_routes_require_login_and_expose_no_raw_content(self):
        router = ast.parse((ROOT / "backend/app/routers/legacy_recovery.py").read_text(encoding="utf-8"))
        for node in router.body:
            if isinstance(node, ast.FunctionDef):
                self.assertIn("get_current_user", ast.unparse(node))
        service_ast = ast.parse((ROOT / "backend/app/services/legacy_recovery_service.py").read_text(encoding="utf-8"))
        summary = next(node for node in service_ast.body if isinstance(node, ast.FunctionDef) and node.name == "source_summary")
        self.assertNotIn("raw_payload", ast.unparse(summary))

    def test_http_capture_and_browse_reject_unauthorized_users(self):
        app = FastAPI()
        app.include_router(recovery_router)
        app.add_exception_handler(HTTPException, http_exception_handler)
        app.dependency_overrides[get_db] = lambda: self.session
        with TestClient(app) as client:
            self.assertEqual(client.get("/recovery/sources").status_code, 401)
            self.assertEqual(client.post("/recovery/sources", json={}).status_code, 401)

        source = capture(self.service, self.session, self.user, queue_raw([]))
        app.dependency_overrides[get_current_user] = lambda: self.other
        with TestClient(app) as client:
            result = client.get(f"/recovery/sources/{source.uuid}/items")
            self.assertEqual(result.status_code, 403)
            self.assertEqual(result.json()["message"], "RECOVERY_ACCESS_DENIED")
            package = json.dumps({"data": {}})
            result = client.post("/recovery/sources", json={
                "source_kind": "legacy_package", "logical_key": "synthetic.sync",
                "profile_id": "profile", "source_identity": None, "format_version": 1,
                "sha256": digest(package), "raw_payload": package,
            })
            self.assertEqual(result.status_code, 403)
        self.assertEqual(len(self.session.sources), 1)


if __name__ == "__main__":
    unittest.main()

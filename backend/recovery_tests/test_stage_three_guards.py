"""Small no-database checks for new stage-three guards."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.exceptions import ConflictException
from app.services.aptitude_certificate_service import AptitudeCertificateService
from app.services.import_service import ImportService


class StageThreeGuardTests(unittest.TestCase):
    def test_signed_aptitude_read_does_not_resync_or_mutate(self):
        service = object.__new__(AptitudeCertificateService)
        certificate = SimpleNamespace(status="validated", validated_at=None)
        with self.assertRaises(ConflictException):
            service._ensure_unsigned(certificate)
        self.assertIs(service._sync_certificate_from_visit(certificate, object()), certificate)

    def test_legacy_import_confirmation_stops_before_any_database_access(self):
        class ForbiddenDatabase:
            def __getattr__(self, name):
                raise AssertionError(f"database access before guard: {name}")
        service = object.__new__(ImportService)
        with self.assertRaises(HTTPException) as caught:
            service.confirm(ForbiddenDatabase(), 123)
        self.assertEqual(caught.exception.status_code, 423)
        self.assertEqual(caught.exception.detail["details"]["code"], "OPERATION_SUSPENDED_FOR_DATA_SAFETY")
        with self.assertRaises(HTTPException) as direct:
            service._upsert_visit(ForbiddenDatabase(), None, None, {}, None)
        self.assertEqual(direct.exception.status_code, 423)


if __name__ == "__main__":
    unittest.main()

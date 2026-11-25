"""Run: python -m unittest discover -s tests -p test_medical_test_read_permissions.py"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.permission import Permission
from app.models.user import User
from app.models.user_permission import UserPermission
from app.routers.medical_tests import router, service


class MedicalTestReadPermissionsTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.user = User(role="admin", is_active=True)
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_admin_and_super_admin_can_load_active_tests(self):
        payload = {"items": [{"id": 1, "name": "ECG"}], "meta": {"total": 1}}
        for role in ("admin", "super_admin"):
            with self.subTest(role=role):
                self.user = User(role=role, is_active=True)
                with patch.object(service, "list", return_value=SimpleNamespace(model_dump=lambda: payload)) as listing:
                    response = self.client.get("/medical-tests?active=true&limit=100")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["data"]["items"][0]["name"], "ECG")
                self.assertTrue(listing.call_args.kwargs["active"])

    def test_explicit_view_denial_blocks_list_and_detail(self):
        self.user.user_permissions = [UserPermission(
            permission=Permission(code="medical_tests.view"), effect="deny",
        )]
        with patch.object(service, "list") as listing, patch.object(service, "get") as detail:
            self.assertEqual(self.client.get("/medical-tests").status_code, 403)
            self.assertEqual(self.client.get("/medical-tests/1").status_code, 403)
            listing.assert_not_called()
            detail.assert_not_called()

    def test_user_without_view_permission_is_denied(self):
        self.user = User(role="unknown", is_active=True)
        self.assertEqual(self.client.get("/medical-tests").status_code, 403)

    def test_unauthenticated_request_is_denied(self):
        del self.app.dependency_overrides[get_current_user]
        self.assertEqual(self.client.get("/medical-tests").status_code, 401)


if __name__ == "__main__":
    unittest.main()

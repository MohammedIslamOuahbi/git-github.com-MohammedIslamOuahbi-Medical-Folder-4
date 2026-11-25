from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.enums import ConnectionMode
from app.core.permission_registry import PERMISSION_CODES
from app.exceptions import ForbiddenException
from app.models.runtime_config import RuntimeConfig
from app.models.user import User
from app.models.user_permission import UserPermission
from app.services import permission_service as permission_service_module
from app.services.connection_mode_policy import (
    CLIENT_ALLOWED_PERMISSION_CODES,
    CLIENT_DENIED_PERMISSION_CODES,
    client_policy_has_explicit_decision,
    connection_mode_policy,
)
from app.services.permission_service import permission_service
from app.services.connection_mode_service import ConnectionModeResolution, connection_mode_service
from app.services.installation_service import installation_service


def _runtime(**overrides) -> RuntimeConfig:
    values = {
        "id": 1,
        "runtime_mode": "standalone",
        "active_api_url": "http://127.0.0.1:8000/api/v1",
        "local_api_url": "http://127.0.0.1:8000/api/v1",
        "local_database_write_enabled": True,
    }
    values.update(overrides)
    return RuntimeConfig(**values)


def test_legacy_runtime_requires_explicit_v2_setup():
    result = connection_mode_service.resolve(_runtime())

    assert result.mode is None
    assert result.requires_setup is True
    assert result.source == "legacy_requires_setup"


def test_list_permissions_ignores_unregistered_legacy_rows_and_repairs_metadata():
    now = datetime.now(timezone.utc)
    permissions = [
        SimpleNamespace(
            id=1,
            code="users.view",
            module=None,
            action=None,
            name="View users",
            description=None,
            category=None,
            is_sensitive=False,
            is_system=True,
            sort_order=0,
            created_at=now,
            updated_at=now,
        ),
        SimpleNamespace(
            id=2,
            code="legacy_permission",
            module=None,
            action=None,
            name="Legacy permission",
            description=None,
            category=None,
            is_sensitive=False,
            is_system=False,
            sort_order=1,
            created_at=now,
            updated_at=now,
        ),
    ]

    class Database:
        def scalars(self, _statement):
            return SimpleNamespace(all=lambda: permissions)

    result = permission_service.list_permissions(Database())

    assert [permission.code for permission in result] == ["users.view"]
    assert result[0].module == "users"
    assert result[0].action == "view"


def test_user_permission_matrix_requires_read_permission_without_edit_permission(monkeypatch):
    actor = SimpleNamespace(id=1)
    user = SimpleNamespace(
        id=1,
        first_name="Admin",
        last_name="User",
        email="admin@example.test",
        role="super_admin",
        is_active=True,
        permissions_version=1,
        user_permissions=[],
    )
    required_codes: list[str] = []

    monkeypatch.setattr(
        permission_service,
        "require_permission",
        lambda _actor, code: required_codes.append(code),
    )
    monkeypatch.setattr(permission_service, "get_user_with_permissions", lambda _db, _user_id: user)
    monkeypatch.setattr(permission_service, "get_permission_map", lambda _db: {})
    monkeypatch.setattr(permission_service, "build_effective_permissions", lambda *_args: [])
    monkeypatch.setattr(permission_service, "is_last_active_super_admin", lambda _user: False)

    result = permission_service.get_user_permission_matrix(object(), user.id, actor)

    assert result.user["id"] == user.id
    assert required_codes == ["users.view_permissions"]


def test_installation_metadata_sync_skips_commit_when_values_are_unchanged():
    state = SimpleNamespace(
        device_uuid="device-1",
        device_code="PC-01",
        device_name="Local PC",
        central_server_uuid="server-1",
        central_generation_uuid="generation-1",
    )
    device = SimpleNamespace(uuid="device-1", device_code="PC-01", device_name="Local PC")
    central_state = SimpleNamespace(server_uuid="server-1", server_generation_uuid="generation-1")

    class Database:
        def is_modified(self, _state):
            return False

        def commit(self):
            raise AssertionError("unchanged status reads must not commit")

    result = installation_service._sync_state_metadata(Database(), state, device=device, central_state=central_state)

    assert result is state


def test_legacy_mission_client_is_only_a_setup_candidate():
    result = connection_mode_service.resolve(
        _runtime(runtime_mode="mission_client", mission_server_url="http://10.0.0.8:8000")
    )

    assert result.mode == ConnectionMode.CLIENT
    assert result.requires_setup is True
    assert result.verified is False


def test_explicit_verified_v2_server_pc_is_ready():
    result = connection_mode_service.resolve(
        _runtime(
            connection_mode="SERVER_PC",
            connection_configured=True,
            connection_verified=True,
            connection_requires_setup=False,
        )
    )

    assert result.mode == ConnectionMode.SERVER_PC
    assert result.requires_setup is False
    assert result.source == "v2"


def test_server_pc_policy_blocks_global_settings(monkeypatch):
    resolution = ConnectionModeResolution(
        mode=ConnectionMode.SERVER_PC,
        configured=True,
        verified=True,
        requires_setup=False,
        server_url=None,
        source="v2",
    )
    monkeypatch.setattr(connection_mode_service, "resolve", lambda _: resolution)

    class Database:
        def get(self, *_):
            return _runtime(connection_mode="SERVER_PC")

    with pytest.raises(ForbiddenException):
        connection_mode_policy.ensure_allowed(Database(), object(), "settings.update")

    connection_mode_policy.ensure_allowed(Database(), object(), "medical_visits.create")


def test_client_policy_explicitly_classifies_the_entire_registry():
    assert CLIENT_ALLOWED_PERMISSION_CODES.isdisjoint(CLIENT_DENIED_PERMISSION_CODES)
    assert CLIENT_ALLOWED_PERMISSION_CODES | CLIENT_DENIED_PERMISSION_CODES == PERMISSION_CODES
    assert all(client_policy_has_explicit_decision(code) for code in PERMISSION_CODES)


@pytest.mark.parametrize(
    "permission_code",
    [
        "workers.view",
        "workers.update",
        "worker_tests.validate",
        "medical_visits.create",
        "aptitude_certificates.sign",
        "orientation_certificates.sign",
        "work_stop_certificates.extend",
        "prescriptions.sign",
        "reports.export_pdf",
        "backups.create",
        "files.upload",
        "companies.view",
        "medical_campaigns.view",
        "local_network.view_status",
        "users.view_permissions",
        "roles.view",
    ],
)
def test_client_policy_allows_explicit_medical_permissions(monkeypatch, permission_code):
    resolution = ConnectionModeResolution(
        mode=ConnectionMode.CLIENT,
        configured=True,
        verified=True,
        requires_setup=False,
        server_url="https://medical.example/api/v1",
        source="v2",
    )
    monkeypatch.setattr(connection_mode_service, "resolve", lambda _: resolution)

    class Database:
        def get(self, *_):
            return _runtime(connection_mode="CLIENT")

    connection_mode_policy.ensure_allowed(Database(), object(), permission_code)


@pytest.mark.parametrize(
    "permission_code",
    [
        "users.create",
        "roles.manage_permissions",
        "companies.create",
        "medical_campaigns.assign_workers",
        "medical_tests.configure",
        "backups.restore",
        "settings.database",
        "audit_logs.view_sensitive",
        "local_network.start_server",
        "licenses.manage_devices",
        "sync.manage_devices",
    ],
)
def test_client_policy_denies_administrative_permissions_even_for_super_admin(monkeypatch, permission_code):
    resolution = ConnectionModeResolution(
        mode=ConnectionMode.CLIENT,
        configured=True,
        verified=True,
        requires_setup=False,
        server_url="https://medical.example/api/v1",
        source="v2",
    )
    monkeypatch.setattr(connection_mode_service, "resolve", lambda _: resolution)

    class Database:
        def get(self, *_):
            return _runtime(connection_mode="CLIENT")

    with pytest.raises(ForbiddenException):
        connection_mode_policy.ensure_allowed(Database(), object(), permission_code)


def test_server_policy_has_no_client_ceiling(monkeypatch):
    resolution = ConnectionModeResolution(
        mode=ConnectionMode.SERVER,
        configured=True,
        verified=True,
        requires_setup=False,
        server_url="https://medical.example/api/v1",
        source="v2",
    )
    monkeypatch.setattr(connection_mode_service, "resolve", lambda _: resolution)

    class Database:
        def get(self, *_):
            return _runtime(connection_mode="SERVER")

    connection_mode_policy.ensure_allowed(Database(), object(), "users.create")


def test_client_permission_ceiling_intersects_with_normal_rbac(monkeypatch):
    resolution = ConnectionModeResolution(
        mode=ConnectionMode.CLIENT,
        configured=True,
        verified=True,
        requires_setup=False,
        server_url="https://medical.example/api/v1",
        source="v2",
    )
    monkeypatch.setattr(connection_mode_service, "resolve", lambda _: resolution)

    class Database:
        def get(self, *_):
            return _runtime(connection_mode="CLIENT")

    monkeypatch.setattr(permission_service_module, "object_session", lambda _: Database())
    user = object()
    monkeypatch.setattr(permission_service, "get_effective_permission_codes", lambda _: [])
    with pytest.raises(ForbiddenException):
        permission_service.require_permission(user, "workers.update")

    monkeypatch.setattr(permission_service, "get_effective_permission_codes", lambda _: ["reports.view", "users.create"])
    permission_service.require_permission(user, "reports.view")
    with pytest.raises(ForbiddenException):
        permission_service.require_permission(user, "users.create")


def test_bulk_effective_permission_explanations_use_mode_role_and_user_override(db_session):
    permission_service.ensure_seed_data(db_session, sync_role_defaults=True)
    db_session.commit()
    super_admin_role = permission_service.get_role_by_code(db_session, "super_admin")
    doctor_role = permission_service.get_role_by_code(db_session, "doctor")
    assert super_admin_role is not None
    assert doctor_role is not None

    user = User(
        first_name="Permission",
        last_name="Doctor",
        email="permission-doctor@example.test",
        password_hash="not-used-by-this-test",
        role="doctor",
        role_id=doctor_role.id,
    )
    db_session.add(user)
    db_session.flush()
    workers_view = permission_service.get_permission_map(db_session)["workers.view"]
    db_session.add(UserPermission(user_id=user.id, permission_id=workers_view.id, effect="deny"))
    db_session.commit()

    client_super_admin = permission_service.explain_effective_permissions(
        db_session,
        actor=user,
        connection_mode=ConnectionMode.CLIENT,
        role_id=super_admin_role.id,
    )
    by_code = {item.code: item for item in client_super_admin.permissions}
    assert len(by_code) == len(PERMISSION_CODES)
    assert by_code["users.create"].mode_allowed is False
    assert by_code["users.create"].role_allowed is True
    assert by_code["users.create"].effective_allowed is False
    assert by_code["users.create"].reason == "mode_denied"

    client_doctor = permission_service.explain_effective_permissions(
        db_session,
        actor=user,
        connection_mode=ConnectionMode.CLIENT,
        role_id=doctor_role.id,
        user_id=user.id,
    )
    doctor_by_code = {item.code: item for item in client_doctor.permissions}
    assert doctor_by_code["workers.update"].mode_allowed is True
    assert doctor_by_code["workers.update"].role_allowed is False
    assert doctor_by_code["workers.update"].effective_allowed is False
    assert doctor_by_code["workers.update"].reason == "role_denied"
    assert doctor_by_code["workers.view"].user_override == "deny"
    assert doctor_by_code["workers.view"].reason == "user_denied"

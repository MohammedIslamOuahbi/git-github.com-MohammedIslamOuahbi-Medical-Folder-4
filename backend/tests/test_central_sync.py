from __future__ import annotations

import uuid as py_uuid
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.models.branch import Branch
from app.models.central_server_state import CentralServerState
from app.models.company import Company
from app.models.drilling_site import DrillingSite
from app.models.medical_campaign import MedicalCampaign
from app.models.mission_session import MissionSession
from app.models.prescription import Prescription
from app.models.sync_change import SyncChange
from app.models.sync_conflict import SyncConflict
from app.models.sync_device import SyncDevice
from app.models.user import User
from app.models.worker import Worker
from app.services.auth_service import AuthService
from app.services.central_sync_service import central_sync_service
from app.services.device_identity_service import device_identity_service
from app.services.installation_service import installation_service
from app.services.mission_copy_service import mission_copy_service
from app.services.sync_context import set_sync_context
from app.core.enums import InstallationProfile


def _login(client, db_session):
    AuthService().create_admin_user(
        db_session,
        first_name="Central",
        last_name="Admin",
        email="central-admin@ibnsina-clinic.com",
        password="admin12345",
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "central-admin@ibnsina-clinic.com", "password": "admin12345"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _switch_local_device(tmp_path: Path, name: str):
    device_identity_service._storage_path = tmp_path / f"{name}.installation_uuid.txt"  # noqa: SLF001


def _register_local_device(db_session, tmp_path: Path, name: str, code: str, *, is_central_server: bool = False) -> SyncDevice:
    _switch_local_device(tmp_path, name)
    device = device_identity_service.register_or_resolve_local_device(
        db_session,
        device_code=code,
        device_name=name,
        is_central_server=is_central_server,
        app_version="1.0.2",
    )
    installation_service.provision_current_installation(
        db_session,
        InstallationProfile.CENTRAL_SERVER if is_central_server else InstallationProfile.MOBILE_DEVICE,
        audit_source="test_setup",
    )
    return device


def _create_reference_hierarchy(db_session, *, source_device_uuid: py_uuid.UUID, source_user_uuid: py_uuid.UUID, mission_uuid: py_uuid.UUID | None = None):
    set_sync_context(
        db_session,
        source_device_uuid=source_device_uuid,
        source_user_uuid=source_user_uuid,
        mission_session_uuid=mission_uuid,
        mission_server_uuid=source_device_uuid if mission_uuid else None,
    )
    company = Company(name="Hassi Energy")
    db_session.add(company)
    db_session.flush()
    branch = Branch(company_id=company.id, company=company, name="South Branch")
    db_session.add(branch)
    db_session.flush()
    site = DrillingSite(company_id=company.id, branch_id=branch.id, company=company, branch=branch, name="Rig-A", status="active")
    db_session.add(site)
    db_session.commit()
    return company, branch, site


def _collect_mission_changes(db_session, mission_uuid: py_uuid.UUID) -> list[dict]:
    rows = db_session.scalars(
        select(SyncChange)
        .where(SyncChange.mission_session_uuid == mission_uuid, SyncChange.mission_sequence.is_not(None))
        .order_by(SyncChange.mission_sequence.asc())
    ).all()
    return [
        {
            "change_uuid": str(item.change_uuid),
            "mission_sequence": item.mission_sequence,
            "entity_type": item.entity_type,
            "entity_uuid": str(item.entity_uuid),
            "operation": item.operation,
            "base_version": item.base_version,
            "entity_version": item.entity_version,
            "changed_fields": item.changed_fields or [],
            "source_device_uuid": str(item.source_device_uuid) if item.source_device_uuid else None,
            "source_user_uuid": str(item.source_user_uuid) if item.source_user_uuid else None,
            "payload": item.payload,
        }
        for item in rows
    ]


def _admin_user(db_session) -> User:
    return db_session.scalar(select(User).where(User.email == "central-admin@ibnsina-clinic.com"))


def test_central_push_is_idempotent_and_monotonic(client, db_session, tmp_path):
    token = _login(client, db_session)
    _register_local_device(db_session, tmp_path, "Central Server", "CENTRAL-SERVER", is_central_server=True)
    state = central_sync_service.get_or_create_server_state(db_session, activate=True)
    state.current_central_sequence = 1000
    db_session.add(state)
    db_session.commit()

    pc01 = _register_local_device(db_session, tmp_path, "Mission PC-01", "PC-01")
    central_sync_service.register_device_secret(db_session, device_uuid=pc01.uuid, secret="pc01-secret")

    admin_user = _admin_user(db_session)

    company, branch, site = _create_reference_hierarchy(
        db_session,
        source_device_uuid=pc01.uuid,
        source_user_uuid=admin_user.uuid,
    )
    set_sync_context(db_session, source_device_uuid=pc01.uuid, source_user_uuid=admin_user.uuid)
    worker = Worker(
        company_id=company.id,
        branch_id=branch.id,
        drilling_site_id=site.id,
        company=company,
        branch=branch,
        drilling_site=site,
        employee_number="EMP-001",
        national_id="NAT-001",
        first_name="Amina",
        last_name="Bensaid",
        phone="0550000001",
        etat_actual="present",
        is_active=True,
    )
    db_session.add(worker)
    db_session.commit()

    change = db_session.scalar(select(SyncChange).where(SyncChange.entity_type == "workers").order_by(SyncChange.id.desc()))
    payload = {
        "batch_uuid": str(py_uuid.uuid4()),
        "device_uuid": str(pc01.uuid),
        "mission_uuid": str(py_uuid.uuid4()),
        "mission_manifest_checksum": "checksum-1",
        "base_central_sequence": 1000,
        "changes": [
            {
                "change_uuid": str(change.change_uuid),
                "mission_sequence": 1,
                "entity_type": "workers",
                "entity_uuid": str(worker.uuid),
                "operation": "update",
                "base_version": 0,
                "entity_version": worker.sync_version,
                "changed_fields": ["phone"],
                "source_device_uuid": str(pc01.uuid),
                "source_user_uuid": str(admin_user.uuid),
                "payload": change.payload,
            }
        ],
    }

    _switch_local_device(tmp_path, "Central Server")
    first = client.post(
        "/api/v1/central-sync/push",
        headers={"Authorization": f"Bearer {token}", "X-Central-Device-Secret": "pc01-secret"},
        json=payload,
    )
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    assert first_data["accepted"]
    first_sequence = first_data["central_sequence"]

    second = client.post(
        "/api/v1/central-sync/push",
        headers={"Authorization": f"Bearer {token}", "X-Central-Device-Secret": "pc01-secret"},
        json=payload,
    )
    assert second.status_code == 200, second.text
    second_data = second.json()["data"]
    assert second_data["duplicates"] == [payload["changes"][0]["change_uuid"]]
    assert second_data["central_sequence"] == first_sequence

    refreshed_state = db_session.scalar(select(CentralServerState).limit(1))
    assert refreshed_state.current_central_sequence >= first_sequence >= 1001


def test_logical_duplicate_worker_creates_conflict_and_can_be_resolved(client, db_session, tmp_path):
    token = _login(client, db_session)
    central = _register_local_device(db_session, tmp_path, "Central Node", "CENTRAL-SERVER", is_central_server=True)
    central_sync_service.get_or_create_server_state(db_session, activate=True)
    pc01 = _register_local_device(db_session, tmp_path, "Mission Node", "PC-01")
    central_sync_service.register_device_secret(db_session, device_uuid=pc01.uuid, secret="pc01-secret")
    admin_user = _admin_user(db_session)

    company, branch, site = _create_reference_hierarchy(
        db_session,
        source_device_uuid=central.uuid,
        source_user_uuid=admin_user.uuid,
    )
    set_sync_context(db_session, source_device_uuid=central.uuid, source_user_uuid=admin_user.uuid)
    existing_worker = Worker(
        company_id=company.id,
        branch_id=branch.id,
        drilling_site_id=site.id,
        company=company,
        branch=branch,
        drilling_site=site,
        employee_number="EMP-C-01",
        national_id="DUP-001",
        first_name="Karim",
        last_name="Salah",
        etat_actual="present",
        is_active=True,
    )
    db_session.add(existing_worker)
    db_session.commit()

    _switch_local_device(tmp_path, "Central Node")
    response = client.post(
        "/api/v1/central-sync/push",
        headers={"Authorization": f"Bearer {token}", "X-Central-Device-Secret": "pc01-secret"},
        json=(
            lambda incoming_worker_uuid: {
                "batch_uuid": str(py_uuid.uuid4()),
                "device_uuid": str(pc01.uuid),
                "mission_uuid": str(py_uuid.uuid4()),
                "mission_manifest_checksum": "checksum-dup",
                "base_central_sequence": 0,
            "changes": [
                {
                        "change_uuid": str(py_uuid.uuid4()),
                        "mission_sequence": 1,
                        "entity_type": "workers",
                        "entity_uuid": str(incoming_worker_uuid),
                        "operation": "insert",
                        "base_version": 0,
                        "entity_version": 1,
                        "changed_fields": ["national_id", "first_name", "last_name"],
                        "source_device_uuid": str(pc01.uuid),
                        "source_user_uuid": str(admin_user.uuid),
                        "payload": {
                            "uuid": str(incoming_worker_uuid),
                            "employee_number": "EMP-M-02",
                            "national_id": "DUP-001",
                            "first_name": "Karim",
                            "last_name": "Salah",
                            "etat_actual": "present",
                        "is_active": True,
                        "company_uuid": str(company.uuid),
                        "branch_uuid": str(branch.uuid),
                        "drilling_site_uuid": str(site.uuid),
                        },
                    }
                ],
            }
        )(py_uuid.uuid4()),
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["data"]["conflicts"]) == 1

    conflict = db_session.scalar(select(SyncConflict).order_by(SyncConflict.id.desc()))
    assert conflict is not None
    resolved = client.post(
        f"/api/v1/central-sync/conflicts/{conflict.uuid}/resolve",
        headers={"Authorization": f"Bearer {token}"},
        json={"resolution_type": "keep_central", "resolved_payload": None},
    )
    assert resolved.status_code == 200, resolved.text
    db_session.refresh(conflict)
    assert conflict.status == "resolved"
    latest_change = db_session.scalar(select(SyncChange).where(SyncChange.central_sequence.is_not(None)).order_by(SyncChange.central_sequence.desc()))
    assert latest_change is not None
    assert latest_change.central_sequence is not None


def test_signed_prescription_is_not_overwritten(client, db_session, tmp_path):
    token = _login(client, db_session)
    central = _register_local_device(db_session, tmp_path, "Central Signed", "CENTRAL-SERVER", is_central_server=True)
    central_sync_service.get_or_create_server_state(db_session, activate=True)
    pc01 = _register_local_device(db_session, tmp_path, "Mission Signed", "PC-01")
    central_sync_service.register_device_secret(db_session, device_uuid=pc01.uuid, secret="pc01-secret")
    admin_user = _admin_user(db_session)

    company, branch, site = _create_reference_hierarchy(
        db_session,
        source_device_uuid=central.uuid,
        source_user_uuid=admin_user.uuid,
    )
    set_sync_context(db_session, source_device_uuid=central.uuid, source_user_uuid=admin_user.uuid)
    worker = Worker(
        company_id=company.id,
        branch_id=branch.id,
        drilling_site_id=site.id,
        company=company,
        branch=branch,
        drilling_site=site,
        employee_number="EMP-P-01",
        national_id="PRESC-001",
        first_name="Nadia",
        last_name="Toumi",
        etat_actual="present",
        is_active=True,
    )
    db_session.add(worker)
    db_session.flush()
    campaign = MedicalCampaign(
        company_id=company.id,
        branch_id=branch.id,
        drilling_site_id=site.id,
        company=company,
        branch=branch,
        drilling_site=site,
        title="Mission Campaign",
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 21),
        status="active",
        created_by=admin_user.id,
    )
    db_session.add(campaign)
    db_session.flush()
    prescription = Prescription(
        worker_id=worker.id,
        campaign_id=campaign.id,
        worker=worker,
        campaign=campaign,
        doctor_id=admin_user.id,
        prescription_number="PR-001",
        prescription_date=date(2026, 7, 20),
        diagnosis="Checkup",
        validator_name="Dr Signed",
        validated_at=datetime.now(timezone.utc),
        status="validated",
    )
    db_session.add(prescription)
    db_session.commit()

    _switch_local_device(tmp_path, "Central Signed")
    response = client.post(
        "/api/v1/central-sync/push",
        headers={"Authorization": f"Bearer {token}", "X-Central-Device-Secret": "pc01-secret"},
        json={
            "batch_uuid": str(py_uuid.uuid4()),
            "device_uuid": str(pc01.uuid),
            "mission_uuid": str(py_uuid.uuid4()),
            "mission_manifest_checksum": "checksum-prescription",
            "base_central_sequence": 0,
            "changes": [
                {
                    "change_uuid": str(py_uuid.uuid4()),
                    "mission_sequence": 10,
                    "entity_type": "prescriptions",
                    "entity_uuid": str(prescription.uuid),
                    "operation": "update",
                    "base_version": max(0, prescription.sync_version - 1),
                    "entity_version": prescription.sync_version + 1,
                    "changed_fields": ["notes"],
                    "source_device_uuid": str(pc01.uuid),
                    "source_user_uuid": str(admin_user.uuid),
                    "payload": {
                        "uuid": str(prescription.uuid),
                        "prescription_number": prescription.prescription_number,
                        "prescription_date": prescription.prescription_date.isoformat(),
                        "diagnosis": prescription.diagnosis,
                        "notes": "Attempt overwrite",
                        "status": "validated",
                        "worker_uuid": str(worker.uuid),
                        "campaign_uuid": str(campaign.uuid),
                    },
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["data"]["conflicts"]) == 1


def test_end_to_end_mission_to_central_flow(client, db_session, tmp_path):
    token = _login(client, db_session)
    admin_user = _admin_user(db_session)

    central = _register_local_device(db_session, tmp_path, "Central Server", "CENTRAL-SERVER", is_central_server=True)
    central_state = central_sync_service.get_or_create_server_state(db_session, activate=True)
    central_state.current_central_sequence = 1000
    db_session.add(central_state)
    db_session.commit()

    pc01 = _register_local_device(db_session, tmp_path, "PC-01", "PC-01")
    pc02 = _register_local_device(db_session, tmp_path, "PC-02", "PC-02")
    central_sync_service.register_device_secret(db_session, device_uuid=pc01.uuid, secret="pc01-secret")
    central_sync_service.register_device_secret(db_session, device_uuid=pc02.uuid, secret="pc02-secret")

    _switch_local_device(tmp_path, "PC-01")
    created = client.post(
        "/api/v1/mission/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "mission_code": "MISSION-HMD-2026-07-20",
            "mission_name": "End To End Mission",
            "description": "Remote occupational health mission",
            "expected_devices": [],
        },
    )
    assert created.status_code == 200, created.text
    mission_uuid = created.json()["data"]["uuid"]
    activated = client.post(
        f"/api/v1/mission/sessions/{mission_uuid}/activate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert activated.status_code == 200, activated.text

    join = client.post(
        f"/api/v1/mission/sessions/{mission_uuid}/join",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "device_uuid": str(pc02.uuid),
            "device_code": "PC-02",
            "device_name": "PC-02",
            "installation_uuid": str(pc02.installation_uuid),
            "app_version": "1.0.2",
            "schema_revision": pc02.schema_revision,
            "last_central_sequence": 1000,
            "protocol_version": "1",
        },
    )
    assert join.status_code == 200, join.text

    mission = db_session.scalar(select(MissionSession).where(MissionSession.uuid == py_uuid.UUID(mission_uuid)))
    company, branch, site = _create_reference_hierarchy(
        db_session,
        source_device_uuid=pc01.uuid,
        source_user_uuid=admin_user.uuid,
        mission_uuid=mission.uuid,
    )
    set_sync_context(
        db_session,
        source_device_uuid=pc01.uuid,
        source_user_uuid=admin_user.uuid,
        mission_session_uuid=mission.uuid,
        mission_server_uuid=pc01.uuid,
    )
    worker = Worker(
        company_id=company.id,
        branch_id=branch.id,
        drilling_site_id=site.id,
        company=company,
        branch=branch,
        drilling_site=site,
        employee_number="EMP-E2E-01",
        national_id="E2E-001",
        first_name="Yacine",
        last_name="Mebarki",
        phone="0661000000",
        etat_actual="present",
        is_active=True,
    )
    db_session.add(worker)
    db_session.commit()

    finalized = client.post(
        f"/api/v1/mission/sessions/{mission_uuid}/finalize",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert finalized.status_code == 200, finalized.text
    manifest_checksum = finalized.json()["data"]["checksum"]

    pull = client.get(
        "/api/v1/mission-sync/pull",
        headers={"Authorization": f"Bearer {token}"},
        params={"mission_uuid": mission_uuid, "after_sequence": 0, "limit": 500},
    )
    assert pull.status_code == 200, pull.text
    mission_changes = pull.json()["data"]

    _switch_local_device(tmp_path, "PC-02")
    copy_state = mission_copy_service.apply_batch(
        db_session,
        mission_uuid=py_uuid.UUID(mission_uuid),
        mission_server_uuid=pc01.uuid,
        mission_server_url="http://pc01.local/api/v1",
        changes=mission_changes["changes"],
        next_sequence=mission_changes["next_sequence"],
        final_sequence=mission_changes["final_sequence"],
        current_run_uuid=py_uuid.uuid4(),
    )
    assert copy_state.last_pulled_sequence == mission_changes["final_sequence"]

    payload = {
        "batch_uuid": str(py_uuid.uuid4()),
        "device_uuid": str(pc01.uuid),
        "mission_uuid": mission_uuid,
        "mission_manifest_checksum": manifest_checksum,
        "base_central_sequence": 1000,
        "changes": _collect_mission_changes(db_session, py_uuid.UUID(mission_uuid)),
    }
    _switch_local_device(tmp_path, "Central Server")
    pushed = client.post(
        "/api/v1/central-sync/push",
        headers={"Authorization": f"Bearer {token}", "X-Central-Device-Secret": "pc01-secret"},
        json=payload,
    )
    assert pushed.status_code == 200, pushed.text
    push_data = pushed.json()["data"]
    assert push_data["accepted"]
    assert push_data["central_sequence"] > 1000

    central_pull = client.get(
        "/api/v1/central-sync/pull",
        headers={"Authorization": f"Bearer {token}"},
        params={"after_central_sequence": 1000, "limit": 1000},
    )
    assert central_pull.status_code == 200, central_pull.text
    pull_data = central_pull.json()["data"]
    assert pull_data["changes"]

    _switch_local_device(tmp_path, "PC-01")
    pc01_apply = client.post(
        "/api/v1/central-sync/apply",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "central_server_uuid": pull_data["central_server_uuid"],
            "central_generation_uuid": pull_data["central_generation_uuid"],
            "changes": pull_data["changes"],
            "next_central_sequence": pull_data["next_central_sequence"],
            "final_central_sequence": pull_data["next_central_sequence"],
            "current_run_uuid": str(py_uuid.uuid4()),
        },
    )
    assert pc01_apply.status_code == 200, pc01_apply.text

    _switch_local_device(tmp_path, "PC-02")
    pc02_apply = client.post(
        "/api/v1/central-sync/apply",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "central_server_uuid": pull_data["central_server_uuid"],
            "central_generation_uuid": pull_data["central_generation_uuid"],
            "changes": pull_data["changes"],
            "next_central_sequence": pull_data["next_central_sequence"],
            "final_central_sequence": pull_data["next_central_sequence"],
            "current_run_uuid": str(py_uuid.uuid4()),
        },
    )
    assert pc02_apply.status_code == 200, pc02_apply.text

    db_session.expire_all()
    db_worker = db_session.scalar(select(Worker).where(Worker.national_id == "E2E-001"))
    db_mission = db_session.scalar(select(MissionSession).where(MissionSession.uuid == py_uuid.UUID(mission_uuid)))
    assert db_worker is not None
    assert db_worker.central_sync_status == "central_finalized"
    assert db_worker.central_sequence is not None and db_worker.central_sequence > 1000
    assert db_mission is not None
    assert db_mission.status in {"centralized", "centralized_with_conflicts"}
    assert copy_state.last_pulled_sequence == mission_changes["final_sequence"]

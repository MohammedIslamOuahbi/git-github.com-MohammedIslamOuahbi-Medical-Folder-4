from datetime import date

from app.core.security import hash_password
from app.models.branch import Branch
from app.models.company import Company
from app.models.doctor_campaign import DoctorCampaign
from app.models.drilling_site import DrillingSite
from app.models.medical_campaign import MedicalCampaign
from app.models.user import User
from app.models.workspace import Workspace


def _auth_headers(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_me_returns_effective_permissions(client, db_session):
    user = User(
        first_name="Samir",
        last_name="Admin",
        email="samir.admin@ibnsina-clinic.com",
        password_hash=hash_password("securepass"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.get("/api/v1/auth/me", headers=_auth_headers(client, user.email, "securepass"))

    assert response.status_code == 200
    permissions = response.json()["data"]["permissions"]
    assert "workspaces:manage" in permissions
    assert "settings:manage" not in permissions


def test_workspace_access_requires_assignment_and_valid_code(client, db_session):
    company = Company(name="Sonatrach")
    db_session.add(company)
    db_session.flush()

    branch = Branch(company_id=company.id, name="Hassi Messaoud")
    db_session.add(branch)
    db_session.flush()

    site = DrillingSite(company_id=company.id, branch_id=branch.id, name="Rig 24", status="active")
    db_session.add(site)
    db_session.flush()

    doctor = User(
        first_name="Leila",
        last_name="Doctor",
        email="leila.doctor@ibnsina-clinic.com",
        password_hash=hash_password("doctorpass"),
        role="doctor",
        is_active=True,
    )
    db_session.add(doctor)
    db_session.flush()

    campaign = MedicalCampaign(
        company_id=company.id,
        branch_id=branch.id,
        drilling_site_id=site.id,
        title="June Desert Campaign",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 10),
        status="active",
    )
    db_session.add(campaign)
    db_session.flush()

    db_session.add(DoctorCampaign(doctor_id=doctor.id, campaign_id=campaign.id))
    db_session.add(
        Workspace(
            name="Rig 24 Workspace",
            campaign_id=campaign.id,
            company_id=company.id,
            branch_id=branch.id,
            drilling_site_id=site.id,
            workspace_code="RIG24-JUNE",
            workspace_password_hash=hash_password("2468"),
            start_date=campaign.start_date,
            end_date=campaign.end_date,
            status="active",
            is_locked=False,
        )
    )
    db_session.commit()

    headers = _auth_headers(client, doctor.email, "doctorpass")

    forbidden_response = client.post(
        f"/api/v1/workspaces/by-campaign/{campaign.id}/access",
        headers=headers,
        json={"access_code": "bad-code"},
    )
    assert forbidden_response.status_code == 403

    success_response = client.post(
        f"/api/v1/workspaces/by-campaign/{campaign.id}/access",
        headers=headers,
        json={"access_code": "2468"},
    )
    assert success_response.status_code == 200
    workspace = success_response.json()["data"]["workspace"]
    assert workspace["campaign_id"] == campaign.id
    assert workspace["company_name"] == "Sonatrach"


def test_workspace_lookup_auto_provisions_missing_workspace(client, db_session):
    company = Company(name="NAFTAL")
    db_session.add(company)
    db_session.flush()

    branch = Branch(company_id=company.id, name="Ghardaia Operations")
    db_session.add(branch)
    db_session.flush()

    site = DrillingSite(company_id=company.id, branch_id=branch.id, name="Field Base 7", status="active")
    db_session.add(site)
    db_session.flush()

    admin = User(
        first_name="Mostafa",
        last_name="Admin",
        email="mostafa.admin@ibnsina-clinic.com",
        password_hash=hash_password("adminpass"),
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()

    campaign = MedicalCampaign(
        company_id=company.id,
        branch_id=branch.id,
        drilling_site_id=site.id,
        title="Auto Workspace Campaign",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
        status="active",
        created_by=admin.id,
    )
    db_session.add(campaign)
    db_session.commit()

    response = client.get(
        f"/api/v1/workspaces/by-campaign/{campaign.id}",
        headers=_auth_headers(client, admin.email, "adminpass"),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["campaign_id"] == campaign.id
    assert payload["workspace_code"] == f"WS-{campaign.id:05d}"

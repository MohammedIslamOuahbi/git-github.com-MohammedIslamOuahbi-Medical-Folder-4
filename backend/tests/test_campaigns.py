from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core.security import hash_password
from app.exceptions import BadRequestException
from app.models.branch import Branch
from app.models.campaign_test import CampaignTest
from app.models.company import Company
from app.models.drilling_site import DrillingSite
from app.models.medical_campaign import MedicalCampaign
from app.models.medical_test import MedicalTest
from app.models.user import User
from app.routers.campaigns import serialize_campaign_test
from app.schemas.medical_campaign import MedicalCampaignCreate
from app.services.campaign_service import CampaignService


def test_campaigns_requires_auth(client):
    response = client.get("/api/v1/campaigns")
    assert response.status_code in {401, 403}


def test_campaign_service_rejects_campaign_when_company_contract_is_expired(db_session):
    admin_user = User(
        first_name="Admin",
        last_name="User",
        email="campaign-admin@ibnsina-clinic.com",
        password_hash=hash_password("admin12345"),
        role="admin",
        is_active=True,
    )
    db_session.add(admin_user)
    db_session.flush()

    company = Company(
        name="Expired Contract Co",
        contract_start_date=date.today() - timedelta(days=20),
        contract_end_date=date.today() - timedelta(days=1),
    )
    db_session.add(company)
    db_session.flush()

    branch = Branch(company_id=company.id, name="Main Branch")
    db_session.add(branch)
    db_session.flush()

    site = DrillingSite(
        company_id=company.id,
        branch_id=branch.id,
        name="Main Site",
        status="active",
    )
    db_session.add(site)
    db_session.commit()

    service = CampaignService()

    with pytest.raises(BadRequestException) as exc_info:
        service.create(
            db_session,
            MedicalCampaignCreate(
                company_id=company.id,
                branch_id=branch.id,
                drilling_site_id=site.id,
                title="Blocked Campaign",
                start_date=date.today(),
                end_date=date.today() + timedelta(days=1),
                status="draft",
            ),
            current_user=admin_user,
            created_by=admin_user.id,
    )

    assert exc_info.value.status_code == 400
    assert "invalide" in exc_info.value.detail["message"].lower()


def test_campaign_service_replaces_campaign_tests_with_required_flags(db_session):
    admin_user = User(
        first_name="Admin",
        last_name="User",
        email="campaign-tests-admin@ibnsina-clinic.com",
        password_hash=hash_password("admin12345"),
        role="admin",
        is_active=True,
    )
    db_session.add(admin_user)
    db_session.flush()

    company = Company(
        name="Valid Contract Co",
        contract_start_date=date.today() - timedelta(days=5),
        contract_end_date=date.today() + timedelta(days=30),
    )
    db_session.add(company)
    db_session.flush()

    branch = Branch(company_id=company.id, name="Main Branch")
    db_session.add(branch)
    db_session.flush()

    site = DrillingSite(
        company_id=company.id,
        branch_id=branch.id,
        name="Main Site",
        status="active",
    )
    db_session.add(site)
    db_session.flush()

    test_a = MedicalTest(name="Ophtalmologie", section="Clinique", category="Clinique", is_active=True)
    test_b = MedicalTest(name="Biologie", section="Complementaire", category="Complementaire", is_active=True)
    db_session.add_all([test_a, test_b])
    db_session.commit()

    service = CampaignService()
    campaign = service.create(
        db_session,
        MedicalCampaignCreate(
            company_id=company.id,
            branch_id=branch.id,
            drilling_site_id=site.id,
            title="Campaign Tests",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status="draft",
        ),
        current_user=admin_user,
        created_by=admin_user.id,
    )

    created_assignments = service.add_tests(
        db_session,
        campaign.id,
        [
            {"test_id": test_a.id, "required": True},
            {"test_id": test_b.id, "required": False},
        ],
        admin_user,
    )
    assert {(item.test_id, item.required) for item in created_assignments} == {
        (test_a.id, True),
        (test_b.id, False),
    }

    replaced_assignments = service.replace_tests(
        db_session,
        campaign.id,
        [{"test_id": test_b.id, "required": True}],
        admin_user,
    )
    assert [(item.test_id, item.required) for item in replaced_assignments] == [
        (test_b.id, True)
    ]


def test_serialize_campaign_test_includes_flat_test_fields(db_session):
    company = Company(name="Serializer Co")
    branch = Branch(company=company, name="Serializer Branch")
    site = DrillingSite(company=company, branch=branch, name="Serializer Site", status="active")
    campaign = MedicalCampaign(
        company=company,
        branch=branch,
        drilling_site=site,
        title="Serializer Campaign",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=1),
        status="draft",
    )
    medical_test = MedicalTest(
        name="ECG",
        section="Examens complementaires",
        category="Cardiologie",
        description="Electrocardiogramme",
        is_active=True,
    )
    db_session.add_all([company, branch, site, campaign, medical_test])
    db_session.flush()

    assignment = CampaignTest(
        campaign_id=campaign.id,
        test_id=medical_test.id,
        required=True,
    )
    assignment.test = medical_test
    db_session.add(assignment)
    db_session.flush()

    payload = serialize_campaign_test(assignment)

    assert payload["campaign_test_id"] == assignment.id
    assert payload["test_id"] == medical_test.id
    assert payload["name"] == "ECG"
    assert payload["description"] == "Electrocardiogramme"
    assert payload["type"] == "Cardiologie"
    assert payload["required"] is True

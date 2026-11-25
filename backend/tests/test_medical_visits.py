from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.aptitude_certificate import AptitudeCertificate
from app.models.branch import Branch
from app.models.campaign_worker import CampaignWorker
from app.models.company import Company
from app.models.drilling_site import DrillingSite
from app.models.medical_campaign import MedicalCampaign
from app.models.orientation_certificate import OrientationCertificate
from app.models.prescription import Prescription
from app.models.user import User
from app.models.worker import Worker
from app.exceptions import ForbiddenException
from app.schemas.aptitude_certificate import AptitudeCertificateCreate
from app.schemas.medical_visit import MedicalVisitCreate, MedicalVisitUpdate
from app.schemas.orientation_certificate import OrientationCertificateCreate
from app.schemas.prescription import PrescriptionCreate, PrescriptionItemCreate
from app.services.aptitude_certificate_service import AptitudeCertificateService
from app.services.medical_visit_service import MedicalVisitService
from app.services.orientation_certificate_service import OrientationCertificateService
from app.services.prescription_service import PrescriptionService


def _attach_test_signature(user: User) -> None:
    signature_path = Path("uploads/signatures/users/tests") / f"{user.email.replace('@', '_')}.png"
    signature_path.parent.mkdir(parents=True, exist_ok=True)
    signature_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    user.signature_path = signature_path.as_posix()


def _seed_visit_dependencies(db_session):
    seed_index = db_session.query(User).count() + 1
    company = Company(name="Visit Co")
    branch = Branch(company=company, name="Visit Branch")
    site = DrillingSite(company=company, branch=branch, name="Visit Site", location="South", status="active")
    user = User(
        first_name="Doctor",
        last_name="User",
        email=f"visit-doctor-{seed_index}@ibnsina-clinic.com",
        password_hash="hashed-password",
        role="doctor",
        is_active=True,
    )
    _attach_test_signature(user)
    campaign = MedicalCampaign(
        company=company,
        branch=branch,
        drilling_site=site,
        title="Visit Campaign",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status="active",
        creator=user,
    )
    worker = Worker(
        company=company,
        branch=branch,
        drilling_site=site,
        employee_number=f"W-{100 + seed_index}",
        national_id=f"{123456789012345678 + seed_index}",
        first_name="Amina",
        last_name="Bensalah",
        gender="F",
        birth_date=date(1992, 5, 14),
        birth_wilaya="Algiers",
        blood_group="A+",
        phone="0550000000",
        address="Camp address",
        job_title="Nurse",
        department="Medical",
        medical_file_data={},
        is_active=True,
    )
    campaign_worker = CampaignWorker(campaign=campaign, worker=worker, added_by_user=user, status="active")
    db_session.add_all([company, branch, site, user, campaign, worker, campaign_worker])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(worker)
    db_session.refresh(campaign)
    return user, worker, campaign, site


def _create_user(db_session, role: str, suffix: str) -> User:
    user = User(
        first_name=role.title(),
        last_name="Signer",
        email=f"{role.replace(' ', '-')}-{suffix}@ibnsina-clinic.com",
        password_hash="hashed-password",
        role=role,
        is_active=True,
    )
    _attach_test_signature(user)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_orientation_certificate_list_accepts_clinical_filters(client, db_session):
    doctor, worker, campaign, site = _seed_visit_dependencies(db_session)
    visit = MedicalVisitService().create(
        db_session,
        MedicalVisitCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            visit_date="2026-06-29",
            site_name=site.name,
            form_data=_build_form_data(orientations={}),
        ),
        doctor,
    )
    service = OrientationCertificateService(db_session)
    certificate = service.create(
        OrientationCertificateCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            medical_visit_id=visit.id,
            doctor_id=doctor.id,
            orientation_date="2026-06-29",
            orientation_type="cardiology",
        ),
        current_user=doctor,
    )
    token = create_access_token(str(doctor.id), doctor.role, doctor.permissions_version)

    response = client.get(
        "/api/v1/orientation-certificates",
        params={
            "worker_id": worker.id,
            "campaign_id": campaign.id,
            "medical_visit_id": visit.id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["total"] == 1
    assert [item["id"] for item in payload["items"]] == [certificate.id]

    worker_response = client.get(
        f"/api/v1/orientation-certificates/worker/{worker.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert worker_response.status_code == 200, worker_response.text
    assert [item["id"] for item in worker_response.json()] == [certificate.id]


def _build_form_data(*, aptitude: bool = True, orientations: object = None, include_workspace_signature: bool = False):
    return {
        "schemaVersion": 1,
        "workerSnapshot": {
            "medicalFileNumber": "MF-100",
            "employeeCode": "W-100",
            "nationalId": "123456789012345678",
            "firstName": "Amina",
            "lastName": "Bensalah",
            "sex": "F",
            "dateOfBirth": "1992-05-14",
            "birthPlace": "Algiers",
            "phone": "0550000000",
            "addresses": "Camp address",
            "companyName": "Visit Co",
            "siteName": "Visit Site",
            "position": "Nurse",
            "department": "Medical",
            "bloodGroup": "A+",
            "rhesus": "+",
            "professionalHistory": [],
            "vaccinations": [],
            "workAccidents": [],
            "occupationalDiseases": [],
            "spontaneousConsultations": [],
        },
        "visitData": {
            "internalVisit": {
                "date": "2026-06-29",
                "doctor": "Dr House",
            },
            "clinicalExam": {},
            "complementaryExams": {},
            "medicalDecision": {
                "aptitude": "apte" if aptitude else "",
                "recommendations": {
                    "doctorRecommendations": "Follow-up in six months",
                },
                "nextVisit": {
                    "nextVisitDate": "2026-12-29",
                },
            },
            "dynamicMedicalTests": {},
            "orientationCertificate": orientations if orientations is not None else {},
            "orientationCertificates": orientations if isinstance(orientations, list) else [],
            "aptitudeCertificate": {
                "certificateNumber": "",
                "aptitude": "apte" if aptitude else "",
                "aptitudeDate": "2026-06-29",
                "doctorRecommendations": "Follow-up in six months",
                "includeWorkspaceSignature": include_workspace_signature,
                "status": "draft",
            },
            "validation": {
                "status": "confirmed",
                "validatingDoctor": "Dr House",
                "validationDate": "2026-06-29",
                "includeWorkspaceSignature": include_workspace_signature,
                "isLocked": False,
            },
        },
        "auditTrail": [],
    }


def test_visit_create_creates_exactly_one_aptitude_certificate(db_session):
    user, worker, campaign, site = _seed_visit_dependencies(db_session)
    service = MedicalVisitService()

    visit = service.create(
        db_session,
        MedicalVisitCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            visit_date="2026-06-29",
            site_name=site.name,
            form_data=_build_form_data(),
        ),
        user,
    )

    aptitude_certificates = db_session.scalars(
        select(AptitudeCertificate).where(AptitudeCertificate.medical_visit_id == visit.id)
    ).all()
    assert len(aptitude_certificates) == 1
    assert aptitude_certificates[0].aptitude == "apte"


def test_visit_update_does_not_duplicate_aptitude_certificate(db_session):
    user, worker, campaign, site = _seed_visit_dependencies(db_session)
    service = MedicalVisitService()

    visit = service.create(
        db_session,
        MedicalVisitCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            visit_date="2026-06-29",
            site_name=site.name,
            form_data=_build_form_data(),
        ),
        user,
    )

    service.update(
        db_session,
        visit.id,
        MedicalVisitUpdate(
            form_data=_build_form_data(),
        ),
        user,
    )

    aptitude_certificates = db_session.scalars(
        select(AptitudeCertificate).where(AptitudeCertificate.medical_visit_id == visit.id)
    ).all()
    assert len(aptitude_certificates) == 1


def test_visit_without_orientation_snapshot_creates_no_orientation_certificate(db_session):
    user, worker, campaign, site = _seed_visit_dependencies(db_session)
    service = MedicalVisitService()

    visit = service.create(
        db_session,
        MedicalVisitCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            visit_date="2026-06-29",
            site_name=site.name,
            form_data=_build_form_data(orientations={}),
        ),
        user,
    )

    orientation_certificates = db_session.scalars(
        select(OrientationCertificate).where(OrientationCertificate.medical_visit_id == visit.id)
    ).all()
    assert orientation_certificates == []


def test_visit_with_one_orientation_entry_creates_one_orientation_certificate(db_session):
    user, worker, campaign, site = _seed_visit_dependencies(db_session)
    service = MedicalVisitService()
    orientation_entry = {
        "orientationDate": "2026-06-29",
        "orientationType": "cardiology",
        "orientationDetails": "Specialist review",
        "includeValidatorSignature": True,
    }

    visit = service.create(
        db_session,
        MedicalVisitCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            visit_date="2026-06-29",
            site_name=site.name,
                form_data=_build_form_data(orientations=[orientation_entry]),
        ),
        user,
    )

    orientation_certificates = db_session.scalars(
        select(OrientationCertificate).where(OrientationCertificate.medical_visit_id == visit.id)
    ).all()
    assert len(orientation_certificates) == 1
    assert orientation_certificates[0].orientation_type == "cardiology"


def test_visit_with_multiple_orientation_entries_creates_one_certificate_per_entry(db_session):
    user, worker, campaign, site = _seed_visit_dependencies(db_session)
    service = MedicalVisitService()
    orientation_entries = [
        {
            "orientationNumber": "ORI-2-20260629-001",
            "orientationDate": "2026-06-29",
            "orientationType": "cardiology",
            "orientationDetails": "Specialist review",
        },
        {
            "orientationNumber": "ORI-2-20260629-002",
            "orientationDate": "2026-06-29",
            "orientationType": "dermatology",
            "orientationDetails": "Skin review",
        },
    ]

    visit = service.create(
        db_session,
        MedicalVisitCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            visit_date="2026-06-29",
            site_name=site.name,
            form_data=_build_form_data(orientations=orientation_entries),
        ),
        user,
    )

    orientation_certificates = db_session.scalars(
        select(OrientationCertificate).where(OrientationCertificate.medical_visit_id == visit.id)
    ).all()
    assert len(orientation_certificates) == 2
    assert {item.orientation_type for item in orientation_certificates} == {"cardiology", "dermatology"}


def test_legacy_workspace_signature_is_normalized_for_saved_visit(db_session):
    user, worker, campaign, site = _seed_visit_dependencies(db_session)
    service = MedicalVisitService()

    visit = service.create(
        db_session,
        MedicalVisitCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            visit_date="2026-06-29",
            site_name=site.name,
            form_data=_build_form_data(include_workspace_signature=True),
        ),
        user,
    )

    stored_visit = service.get(db_session, visit.id)
    assert stored_visit.form_data["validation"]["includeValidatorSignature"] is True

    aptitude_certificate = db_session.scalar(
        select(AptitudeCertificate).where(AptitudeCertificate.medical_visit_id == visit.id)
    )
    assert aptitude_certificate is not None
    assert aptitude_certificate.include_workspace_signature is True


def test_doctor_can_sign_aptitude_certificate(db_session):
    user, worker, campaign, _ = _seed_visit_dependencies(db_session)
    service = AptitudeCertificateService(db_session)
    certificate = service.create_certificate(
        AptitudeCertificateCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            medical_visit_id=None,
            aptitude="apte",
            doctor_recommendations="RAS",
            next_visit_date="2026-12-29",
            includeValidatorSignature=False,
            issue_date="2026-06-29",
        ),
        doctor_id=user.id,
        current_user=user,
    )

    signed = service.sign_certificate(certificate.id, user.id, current_user=user)

    assert signed is not None
    assert signed.status == "confirmed"


def test_admin_can_sign_aptitude_certificate(db_session):
    doctor, worker, campaign, _ = _seed_visit_dependencies(db_session)
    admin = _create_user(db_session, "admin", "aptitude-admin")
    service = AptitudeCertificateService(db_session)
    certificate = service.create_certificate(
        AptitudeCertificateCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            medical_visit_id=None,
            aptitude="apte",
            doctor_recommendations="RAS",
            next_visit_date="2026-12-29",
            includeValidatorSignature=False,
            issue_date="2026-06-29",
        ),
        doctor_id=doctor.id,
        current_user=doctor,
    )

    signed = service.sign_certificate(certificate.id, admin.id, current_user=admin)

    assert signed is not None
    assert signed.status == "confirmed"


def test_normal_user_cannot_sign_aptitude_certificate(db_session):
    doctor, worker, campaign, _ = _seed_visit_dependencies(db_session)
    assistant = _create_user(db_session, "assistant", "aptitude-assistant")
    service = AptitudeCertificateService(db_session)
    certificate = service.create_certificate(
        AptitudeCertificateCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            medical_visit_id=None,
            aptitude="apte",
            doctor_recommendations="RAS",
            next_visit_date="2026-12-29",
            includeValidatorSignature=False,
            issue_date="2026-06-29",
        ),
        doctor_id=doctor.id,
        current_user=doctor,
    )

    try:
        service.sign_certificate(certificate.id, assistant.id, current_user=assistant)
        assert False, "Expected ForbiddenException"
    except ForbiddenException:
        assert True


def test_normal_user_cannot_sign_orientation_certificate(db_session):
    doctor, worker, campaign, _ = _seed_visit_dependencies(db_session)
    assistant = _create_user(db_session, "assistant", "orientation-assistant")
    service = OrientationCertificateService(db_session)
    certificate = service.create(
        OrientationCertificateCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            medical_visit_id=None,
            orientation_date="2026-06-29",
            orientation_type="cardiology",
            orientation_details="Specialist review",
            doctor_name="Dr Doctor",
            includeValidatorSignature=False,
            status="draft",
        ),
        current_user=doctor,
    )

    try:
        service.sign_orientation(certificate.id, assistant)
        assert False, "Expected ForbiddenException"
    except ForbiddenException:
        assert True


def test_normal_user_cannot_sign_internal_medical_visit_signature(db_session):
    assistant, worker, campaign, site = _seed_visit_dependencies(db_session)
    assistant.role = "assistant"
    db_session.add(assistant)
    db_session.commit()
    service = MedicalVisitService()

    try:
        service.create(
            db_session,
            MedicalVisitCreate(
                worker_id=worker.id,
                campaign_id=campaign.id,
                visit_date="2026-06-29",
                site_name=site.name,
                form_data=_build_form_data(include_workspace_signature=True),
            ),
            assistant,
        )
        assert False, "Expected ForbiddenException"
    except ForbiddenException:
        assert True


def test_normal_user_cannot_sign_prescription(db_session):
    doctor, worker, campaign, _ = _seed_visit_dependencies(db_session)
    assistant = _create_user(db_session, "assistant", "prescription-assistant")
    service = PrescriptionService()
    prescription = service.create_prescription(
        db_session,
        PrescriptionCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            prescription_date=date(2026, 6, 29),
            diagnosis="Fatigue",
            notes="Hydratation",
            items=[
                PrescriptionItemCreate(
                    medication_name="Paracetamol",
                    dosage="500mg",
                    frequency="2/jour",
                    duration="5 jours",
                    quantity="1 boite",
                    instructions="Apres repas",
                )
            ],
        ),
        doctor,
    )

    try:
        service.sign_prescription(db_session, prescription.id, assistant)
        assert False, "Expected ForbiddenException"
    except ForbiddenException:
        assert True


def test_doctor_can_sign_orientation_certificate_and_persist_validator_metadata(db_session):
    doctor, worker, campaign, _ = _seed_visit_dependencies(db_session)
    service = OrientationCertificateService(db_session)
    certificate = service.create(
        OrientationCertificateCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            medical_visit_id=None,
            orientation_date="2026-06-29",
            orientation_type="cardiology",
            orientation_details="Specialist review",
            doctor_name="Dr Doctor",
            includeValidatorSignature=False,
            status="draft",
        ),
        current_user=doctor,
    )

    signed = service.sign_orientation(certificate.id, doctor)
    refreshed = service.get_or_404(certificate.id)
    serialized = service.to_response(refreshed)

    assert signed.status == "signed"
    assert refreshed.status == "signed"
    assert refreshed.doctor_id == doctor.id
    assert refreshed.validator_id == doctor.id
    assert refreshed.validator_name
    assert refreshed.validator_role == doctor.role
    assert refreshed.validator_signature_image_path == doctor.signature_path
    assert refreshed.validated_at is not None
    assert refreshed.include_workspace_signature is True
    assert serialized.validatorSignatureUrl == f"/api/v1/orientation-certificates/{certificate.id}/validator-signature"


def test_prescription_validate_sets_validated_status_and_validator(db_session):
    doctor, worker, campaign, _ = _seed_visit_dependencies(db_session)
    service = PrescriptionService()
    prescription = service.create_prescription(
        db_session,
        PrescriptionCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            prescription_date=date(2026, 6, 29),
            diagnosis="Fatigue",
            notes="Hydratation",
            items=[
                PrescriptionItemCreate(
                    medication_name="Paracetamol",
                    dosage="500mg",
                    frequency="2/jour",
                    duration="5 jours",
                    quantity="1 boite",
                    instructions="Apres repas",
                )
            ],
        ),
        doctor,
    )

    validated = service.validate_prescription(db_session, prescription.id, doctor)

    assert validated.status == "validated"
    assert validated.validatorName
    assert validated.validatedAt is not None


def test_prescription_duplicate_creates_new_draft_with_new_number(db_session):
    doctor, worker, campaign, _ = _seed_visit_dependencies(db_session)
    service = PrescriptionService()
    prescription = service.create_prescription(
        db_session,
        PrescriptionCreate(
            worker_id=worker.id,
            campaign_id=campaign.id,
            prescription_date=date(2026, 6, 29),
            diagnosis="Fatigue",
            notes="Hydratation",
            items=[
                PrescriptionItemCreate(
                    medication_name="Paracetamol",
                    dosage="500mg",
                    frequency="2/jour",
                    duration="5 jours",
                    quantity="1 boite",
                    instructions="Apres repas",
                )
            ],
        ),
        doctor,
    )

    duplicated = service.duplicate_prescription(db_session, prescription.id, doctor)

    assert duplicated.id != prescription.id
    assert duplicated.status == "draft"
    assert duplicated.prescription_number != prescription.prescription_number
    assert duplicated.items[0].medication_name == prescription.items[0].medication_name
    assert duplicated.validatorName is None


def test_legacy_include_workspace_signature_cannot_bypass_authorization(db_session):
    assistant, worker, campaign, site = _seed_visit_dependencies(db_session)
    assistant.role = "assistant"
    db_session.add(assistant)
    db_session.commit()
    service = MedicalVisitService()
    payload = _build_form_data(include_workspace_signature=True)
    payload["visitData"]["orientationCertificate"] = {
        "orientationDate": "2026-06-29",
        "orientationType": "cardiology",
        "orientationDetails": "Legacy signature attempt",
        "includeWorkspaceSignature": True,
    }

    try:
        service.create(
            db_session,
            MedicalVisitCreate(
                worker_id=worker.id,
                campaign_id=campaign.id,
                visit_date="2026-06-29",
                site_name=site.name,
                form_data=payload,
            ),
            assistant,
        )
        assert False, "Expected ForbiddenException"
    except ForbiddenException:
        assert True

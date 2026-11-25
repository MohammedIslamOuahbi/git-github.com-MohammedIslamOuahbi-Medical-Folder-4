from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.exceptions import BadRequestException, ForbiddenException, NotFoundException, ConflictException
from app.models.aptitude_certificate import AptitudeCertificate
from app.models.medical_visit import MedicalVisit
from app.models.user import User
from app.models.worker import Worker
from app.repositories.aptitude_certificate import AptitudeCertificateRepository
from app.schemas.aptitude_certificate import (
    AptitudeCertificateCreate,
    AptitudeCertificateResponse,
    AptitudeCertificateUpdate,
)
from app.services.document_pdf_storage import DocumentPdfStorage
from app.services.signature_authorization import (
    build_validator_metadata,
    ensure_can_sign_medical_documents,
    get_validator_display_name,
    normalize_validator_signature_dict,
    ensure_signature_payload_authorized,
)
from app.services.user_signature_service import UserSignatureService


class AptitudeCertificateService:
    allowed_statuses = {"draft", "confirmed", "validated", "signed", "printed", "cancelled"}

    @staticmethod
    def _is_signed(certificate: AptitudeCertificate) -> bool:
        return certificate.status in {"validated", "signed", "printed"} or certificate.validated_at is not None

    def _ensure_unsigned(self, certificate: AptitudeCertificate) -> None:
        if self._is_signed(certificate):
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")

    def __init__(self, db: Session):
        self.db = db
        self.repository = AptitudeCertificateRepository(db)
        self.pdf_storage = DocumentPdfStorage()
        self.user_signature_service = UserSignatureService()

    def get_certificate_model(self, certificate_id: int) -> AptitudeCertificate | None:
        return self.repository.get_by_id(certificate_id)

    def get_certificate(self, certificate_id: int) -> AptitudeCertificateResponse | None:
        certificate = self.get_certificate_model(certificate_id)
        return self._to_response(certificate) if certificate else None

    def get_certificate_by_number(self, cert_number: str) -> AptitudeCertificateResponse | None:
        certificate = self.repository.get_by_certificate_number(cert_number)
        return self._to_response(certificate) if certificate else None

    def get_worker_certificates(self, worker_id: int, skip: int = 0, limit: int = 100) -> list[AptitudeCertificateResponse]:
        certificates = self.repository.get_by_worker(worker_id, skip, limit)
        return [self._to_response(cert) for cert in certificates]

    def get_campaign_certificates(self, campaign_id: int, skip: int = 0, limit: int = 100) -> list[AptitudeCertificateResponse]:
        certificates = self.repository.get_by_campaign(campaign_id, skip, limit)
        return [self._to_response(cert) for cert in certificates]

    def get_all_certificates(self, skip: int = 0, limit: int = 100) -> list[AptitudeCertificateResponse]:
        certificates = self.repository.get_all(skip, limit)
        return [self._to_response(cert) for cert in certificates]

    def get_or_create_for_visit(
        self,
        visit_id: int,
        *,
        current_user: User | None = None,
    ) -> AptitudeCertificateResponse:
        visit = self._get_visit(visit_id)
        canonical = self._ensure_single_visit_certificate(visit)
        if canonical is None:
            canonical = self._create_default_for_visit(visit, current_user=current_user)
        else:
            canonical = self._sync_certificate_from_visit(canonical, visit)
        return self._to_response(canonical)

    def update_for_visit(
        self,
        visit_id: int,
        payload: AptitudeCertificateUpdate,
        *,
        current_user: User,
    ) -> AptitudeCertificateResponse:
        visit = self._get_visit(visit_id)
        certificate = self._ensure_single_visit_certificate(visit)
        if certificate is None:
            certificate = self._create_default_for_visit(visit, current_user=current_user)
        self._ensure_unsigned(certificate)
        updated = self._apply_update(certificate, payload, current_user=current_user, visit=visit)
        updated.status = "draft"
        updated.updated_at = self._now()
        updated = self.repository.update(updated)
        self._invalidate_pdf(updated.id)
        return self._to_response(updated)

    def validate_for_visit(
        self,
        visit_id: int,
        payload: AptitudeCertificateUpdate,
        *,
        current_user: User,
    ) -> AptitudeCertificateResponse:
        ensure_can_sign_medical_documents(current_user)
        visit = self._get_visit(visit_id)
        certificate = self._ensure_single_visit_certificate(visit)
        if certificate is None:
            certificate = self._create_default_for_visit(visit, current_user=current_user)

        self._ensure_unsigned(certificate)
        updated = self._apply_update(certificate, payload, current_user=current_user, visit=visit)
        self._validate_certificate_ready(updated, visit)
        self._overwrite_validator_metadata(updated, current_user)
        updated = self.repository.update(updated)
        self._invalidate_pdf(updated.id)
        return self._to_response(updated)

    def delete_for_visit(self, visit_id: int, *, current_user: User) -> bool:
        ensure_can_sign_medical_documents(current_user)
        visit = self._get_visit(visit_id)
        certificate = self._ensure_single_visit_certificate(visit)
        if certificate is None:
            return False
        self._ensure_unsigned(certificate)
        deleted = self.repository.soft_delete(certificate.id)
        if deleted:
            self._invalidate_pdf(certificate.id)
        return deleted

    def ensure_worker_certificate_from_medical_file(
        self,
        worker: Worker,
        doctor_id: Optional[int] = None,
        current_user: User | None = None,
    ) -> Optional[AptitudeCertificateResponse]:
        existing = self.repository.get_by_worker(worker.id, skip=0, limit=1)
        if existing:
            return self._to_response(existing[0])

        medical_data = worker.medical_file_data or {}
        medical_decision = medical_data.get("medicalDecision") or {}
        if not isinstance(medical_decision, dict):
            return None

        aptitude = medical_decision.get("aptitude")
        if not isinstance(aptitude, str) or not aptitude.strip():
            return None

        campaign_workers = sorted(
            worker.campaign_workers,
            key=lambda item: item.created_at or datetime.min,
            reverse=True,
        )
        if not campaign_workers:
            return None

        recommendations = medical_decision.get("recommendations") or {}
        next_visit = medical_decision.get("nextVisit") or {}
        validation = medical_decision.get("validation") or {}
        interpretation = medical_decision.get("interpretation") or {}

        issue_date = (
            self._coerce_text(validation.get("validationDate"))
            or self._coerce_text(medical_data.get("internalVisitDate"))
            or datetime.now(timezone.utc).date().isoformat()
        )

        created = self.create_certificate(
            AptitudeCertificateCreate(
                worker_id=worker.id,
                campaign_id=campaign_workers[0].campaign_id,
                doctor_id=doctor_id,
                aptitude=self._normalize_aptitude_value(aptitude),
                aptitude_interpretation=self._coerce_text(interpretation.get("decisionInterpretation")) or None,
                doctor_recommendations=self._coerce_text(recommendations.get("doctorRecommendations")) or None,
                visit_date=self._coerce_text(medical_data.get("internalVisitDate")) or None,
                next_visit_date=self._coerce_text(next_visit.get("nextVisitDate")) or None,
                includeValidatorSignature=bool(
                    validation.get("includeValidatorSignature")
                    or validation.get("includeDoctorSignature")
                    or validation.get("includeWorkspaceSignature")
                ),
                issue_date=issue_date,
            ),
            doctor_id=doctor_id,
            current_user=current_user,
        )
        return created

    def create_certificate(
        self,
        data: AptitudeCertificateCreate,
        doctor_id: Optional[int] = None,
        current_user: User | None = None,
    ) -> AptitudeCertificateResponse:
        ensure_signature_payload_authorized(user=current_user, payload=data.model_dump())
        normalized_signature = normalize_validator_signature_dict(
            data.model_dump(),
            current_user=current_user,
        )
        if normalized_signature.get("includeValidatorSignature"):
            self.user_signature_service.require_uploaded_signature(current_user)
        cert_number = self._generate_certificate_number()

        certificate = AptitudeCertificate(
            worker_id=data.worker_id,
            campaign_id=data.campaign_id,
            medical_visit_id=getattr(data, "medical_visit_id", None),
            doctor_id=doctor_id,
            certificate_number=cert_number,
            issue_date=self._parse_date(data.issue_date) or date.today(),
            visit_date=self._parse_date(data.visit_date),
            next_visit_date=self._parse_date(data.next_visit_date),
            aptitude=self._normalize_aptitude_value(data.aptitude),
            aptitude_interpretation=data.aptitude_interpretation,
            doctor_recommendations=data.doctor_recommendations,
            include_workspace_signature=normalized_signature.get("includeValidatorSignature", False),
            validator_id=normalized_signature.get("validatorId"),
            validator_name=normalized_signature.get("validatorName"),
            validator_role=normalized_signature.get("validatorRole"),
            validated_at=self._parse_datetime(normalized_signature.get("validatedAt")),
            validator_signature_image_path=normalized_signature.get("validatorSignatureImagePath"),
            status="draft",
        )

        created = self.repository.create(certificate)
        self._invalidate_pdf(created.id)
        return self._to_response(created)

    def update_certificate(
        self,
        certificate_id: int,
        data: AptitudeCertificateUpdate,
        current_user: User | None = None,
    ) -> AptitudeCertificateResponse | None:
        certificate = self.repository.get_by_id(certificate_id)
        if not certificate:
            return None
        self._ensure_unsigned(certificate)
        updated = self._apply_update(certificate, data, current_user=current_user)
        if data.status:
            updated.status = self._normalize_status(data.status)
        updated.updated_at = self._now()
        updated = self.repository.update(updated)
        self._invalidate_pdf(updated.id)
        return self._to_response(updated)

    def sign_certificate(
        self,
        certificate_id: int,
        doctor_id: int,
        current_user: User | None = None,
    ) -> AptitudeCertificateResponse | None:
        certificate = self.repository.get_by_id(certificate_id)
        if not certificate:
            return None
        self._ensure_unsigned(certificate)
        ensure_can_sign_medical_documents(current_user)
        self.user_signature_service.require_uploaded_signature(current_user)
        certificate.doctor_id = doctor_id
        self._overwrite_validator_metadata(certificate, current_user)

        updated = self.repository.update(certificate)
        self._invalidate_pdf(updated.id)
        return self._to_response(updated)

    def print_certificate(self, certificate_id: int) -> AptitudeCertificateResponse | None:
        certificate = self.repository.get_by_id(certificate_id)
        if not certificate:
            return None
        if self._is_signed(certificate):
            return self._to_response(certificate)
        certificate.updated_at = self._now()
        updated = self.repository.update(certificate)
        self._invalidate_pdf(updated.id)
        return self._to_response(updated)

    def cancel_certificate(self, certificate_id: int) -> bool:
        certificate = self.repository.get_by_id(certificate_id)
        if not certificate:
            return False
        self._ensure_unsigned(certificate)
        certificate.status = "cancelled"
        certificate.updated_at = self._now()
        self.repository.update(certificate)
        self._invalidate_pdf(certificate.id)
        return True

    def delete_certificate(self, certificate_id: int) -> bool:
        certificate = self.repository.get_by_id(certificate_id)
        if certificate is not None:
            self._ensure_unsigned(certificate)
        deleted = self.repository.soft_delete(certificate_id)
        if deleted:
            self._invalidate_pdf(certificate_id)
        return deleted

    def _get_visit(self, visit_id: int) -> MedicalVisit:
        visit = self.db.get(MedicalVisit, visit_id)
        if not visit or visit.deleted_at is not None:
            raise NotFoundException("Medical visit not found")
        if visit.worker_id is None or visit.campaign_id is None:
            raise BadRequestException("Medical visit is missing worker or campaign information")
        return visit

    def _ensure_single_visit_certificate(self, visit: MedicalVisit) -> AptitudeCertificate | None:
        records = self.repository.get_by_medical_visit(visit.id)
        if not records:
            return None
        canonical = max(
            records,
            key=lambda item: (
                2 if self._is_signed(item) else
                1 if self._normalize_status(item.status) == "confirmed" else 0,
                item.updated_at or item.created_at or datetime.min,
                item.id,
            ),
        )
        for record in records:
            if record.id == canonical.id or self._is_signed(record):
                continue
            record.deleted_at = record.deleted_at or self._now()
        self.db.commit()
        self.db.refresh(canonical)
        return canonical

    def _create_default_for_visit(self, visit: MedicalVisit, *, current_user: User | None = None) -> AptitudeCertificate:
        worker = self._get_worker(visit.worker_id)
        snapshot = self._extract_visit_snapshot(visit)
        certificate = AptitudeCertificate(
            worker_id=worker.id,
            campaign_id=visit.campaign_id,
            medical_visit_id=visit.id,
            doctor_id=current_user.id if current_user else None,
            certificate_number=self._coerce_text(snapshot.get("certificateNumber")) or self._generate_certificate_number(),
            issue_date=self._parse_date(snapshot.get("issueDate") or visit.visit_date) or date.today(),
            visit_date=self._parse_date(snapshot.get("visitDate") or visit.visit_date),
            aptitude=self._normalize_aptitude_value(snapshot.get("aptitude")),
            aptitude_interpretation=self._coerce_text(snapshot.get("aptitudeInterpretation")) or None,
            doctor_recommendations=self._coerce_text(snapshot.get("doctorRecommendations")) or None,
            include_workspace_signature=bool(snapshot.get("includeValidatorSignature")),
            status="draft",
        )
        return self.repository.create(certificate)

    def _sync_certificate_from_visit(self, certificate: AptitudeCertificate, visit: MedicalVisit) -> AptitudeCertificate:
        if self._is_signed(certificate):
            return certificate
        snapshot = self._extract_visit_snapshot(visit)
        certificate.worker_id = visit.worker_id
        certificate.campaign_id = visit.campaign_id
        if not self._coerce_text(certificate.certificate_number):
            certificate.certificate_number = self._coerce_text(snapshot.get("certificateNumber")) or self._generate_certificate_number()
        if certificate.issue_date is None:
            certificate.issue_date = self._parse_date(snapshot.get("issueDate") or visit.visit_date) or date.today()
        if certificate.visit_date is None:
            certificate.visit_date = self._parse_date(snapshot.get("visitDate") or visit.visit_date)
        if not self._coerce_text(certificate.aptitude):
            certificate.aptitude = self._normalize_aptitude_value(snapshot.get("aptitude"))
        if not self._coerce_text(certificate.aptitude_interpretation):
            certificate.aptitude_interpretation = self._coerce_text(snapshot.get("aptitudeInterpretation")) or None
        if not self._coerce_text(certificate.doctor_recommendations):
            certificate.doctor_recommendations = self._coerce_text(snapshot.get("doctorRecommendations")) or None
        certificate.updated_at = self._now()
        certificate = self.repository.update(certificate)
        self._invalidate_pdf(certificate.id)
        return certificate

    def _apply_update(
        self,
        certificate: AptitudeCertificate,
        payload: AptitudeCertificateUpdate,
        *,
        current_user: User | None = None,
        visit: MedicalVisit | None = None,
    ) -> AptitudeCertificate:
        incoming = payload.model_dump(exclude_unset=True)
        ensure_signature_payload_authorized(
            user=current_user,
            payload=incoming,
            existing_payload={
                "includeValidatorSignature": certificate.include_workspace_signature,
                "validatorId": certificate.validator_id,
                "validatorName": certificate.validator_name,
                "validatorRole": certificate.validator_role,
                "validatedAt": certificate.validated_at.isoformat() if certificate.validated_at else None,
                "validatorSignatureImagePath": certificate.validator_signature_image_path,
            },
        )
        normalized_signature = normalize_validator_signature_dict(
            incoming,
            current_user=current_user if payload.includeValidatorSignature is not None else None,
            existing_payload={
                "includeValidatorSignature": certificate.include_workspace_signature,
                "validatorId": certificate.validator_id,
                "validatorName": certificate.validator_name,
                "validatorRole": certificate.validator_role,
                "validatedAt": certificate.validated_at.isoformat() if certificate.validated_at else None,
                "validatorSignatureImagePath": certificate.validator_signature_image_path,
            },
        )
        if normalized_signature.get("includeValidatorSignature"):
            self.user_signature_service.require_uploaded_signature(current_user)

        if payload.medical_visit_id is not None:
            certificate.medical_visit_id = payload.medical_visit_id
        if payload.aptitude is not None:
            certificate.aptitude = self._normalize_aptitude_value(payload.aptitude)
        if payload.aptitude_interpretation is not None:
            certificate.aptitude_interpretation = payload.aptitude_interpretation
        if payload.doctor_recommendations is not None:
            certificate.doctor_recommendations = payload.doctor_recommendations
        if payload.visit_date is not None:
            certificate.visit_date = self._parse_date(payload.visit_date)
        if payload.next_visit_date is not None:
            certificate.next_visit_date = self._parse_date(payload.next_visit_date)
        if payload.issue_date is not None:
            certificate.issue_date = self._parse_date(payload.issue_date)
        if payload.includeValidatorSignature is not None:
            certificate.include_workspace_signature = normalized_signature.get("includeValidatorSignature", False)
            if not certificate.include_workspace_signature:
                certificate.validator_signature_image_path = None
            elif normalized_signature.get("validatorSignatureImagePath"):
                certificate.validator_signature_image_path = normalized_signature.get("validatorSignatureImagePath")
        if payload.status is not None:
            certificate.status = self._normalize_status(payload.status)
        if visit is not None:
            certificate.worker_id = visit.worker_id
            certificate.campaign_id = visit.campaign_id
            if certificate.medical_visit_id is None:
                certificate.medical_visit_id = visit.id
        return certificate

    def _overwrite_validator_metadata(
        self,
        certificate: AptitudeCertificate,
        current_user: User,
    ) -> None:
        self.user_signature_service.require_uploaded_signature(current_user)
        validator_metadata = build_validator_metadata(current_user)
        latest_validator_name = (
            validator_metadata.get("validatorName")
            or getattr(current_user, "full_name", None)
            or f"{getattr(current_user, 'first_name', '') or ''} {getattr(current_user, 'last_name', '') or ''}".strip()
            or getattr(current_user, "email", None)
            or f"User {current_user.id}"
        )
        certificate.doctor_id = current_user.id
        certificate.include_workspace_signature = True
        certificate.validator_id = validator_metadata.get("validatorId")
        certificate.validator_name = latest_validator_name
        certificate.validator_role = validator_metadata.get("validatorRole")
        certificate.validated_at = self._parse_datetime(validator_metadata.get("validatedAt"))
        certificate.validator_signature_image_path = validator_metadata.get("validatorSignatureImagePath")
        certificate.status = "confirmed"
        certificate.updated_at = self._now()

    def _validate_certificate_ready(self, certificate: AptitudeCertificate, visit: MedicalVisit) -> None:
        worker = self._get_worker(visit.worker_id)
        if not self._coerce_text(certificate.certificate_number):
            raise BadRequestException("Certificate number is required")
        if not self._coerce_text(certificate.aptitude):
            raise BadRequestException("Aptitude is required")
        if certificate.issue_date is None:
            raise BadRequestException("Issue date is required")
        if certificate.visit_date is None:
            raise BadRequestException("Visit date is required")
        if worker is None:
            raise BadRequestException("Worker data is required")

    def _extract_visit_snapshot(self, visit: MedicalVisit) -> dict[str, object]:
        form_data = visit.form_data or {}
        worker_snapshot = form_data.get("workerSnapshot") if isinstance(form_data.get("workerSnapshot"), dict) else {}
        visit_data = form_data.get("visitData") if isinstance(form_data.get("visitData"), dict) else {}
        aptitude_snapshot = visit_data.get("aptitudeCertificate") if isinstance(visit_data.get("aptitudeCertificate"), dict) else {}
        medical_decision = visit_data.get("medicalDecision") if isinstance(visit_data.get("medicalDecision"), dict) else {}
        recommendations = medical_decision.get("recommendations") if isinstance(medical_decision.get("recommendations"), dict) else {}
        interpretation = medical_decision.get("interpretation") if isinstance(medical_decision.get("interpretation"), dict) else {}
        validation = visit_data.get("validation") if isinstance(visit_data.get("validation"), dict) else {}
        return {
            "certificateNumber": aptitude_snapshot.get("certificateNumber"),
            "aptitude": aptitude_snapshot.get("aptitude") or medical_decision.get("aptitude"),
            "aptitudeInterpretation": aptitude_snapshot.get("aptitudeInterpretation")
            or aptitude_snapshot.get("doctorRecommendations")
            or interpretation.get("decisionInterpretation"),
            "doctorRecommendations": aptitude_snapshot.get("doctorRecommendations") or recommendations.get("doctorRecommendations"),
            "visitDate": aptitude_snapshot.get("visitDate") or visit.visit_date,
            "issueDate": aptitude_snapshot.get("aptitudeDate") or aptitude_snapshot.get("issueDate") or validation.get("validationDate") or visit.visit_date,
            "includeValidatorSignature": aptitude_snapshot.get("includeValidatorSignature")
            or aptitude_snapshot.get("includeDoctorSignature")
            or aptitude_snapshot.get("includeWorkspaceSignature")
            or False,
            "workerSnapshot": worker_snapshot,
        }

    def _get_worker(self, worker_id: int | None) -> Worker:
        worker = self.db.get(Worker, worker_id) if worker_id else None
        if not worker:
            raise NotFoundException("Worker not found")
        return worker

    def _generate_certificate_number(self) -> str:
        year = datetime.now().year
        current_count = self.repository.increment_aptitude_counter(year)
        return f"AP-{year}-{current_count:04d}"

    def _parse_date(self, value: object) -> date | None:
        if not value:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        normalized = str(value).strip()
        if not normalized:
            return None
        return datetime.fromisoformat(normalized[:10]).date()

    def _parse_datetime(self, value: object) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        normalized = str(value).strip().replace("Z", "+00:00")
        if not normalized:
            return None
        return datetime.fromisoformat(normalized)

    def _coerce_text(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _normalize_aptitude_value(self, value: object) -> str:
        return self._coerce_text(value) or "En attente"

    def _normalize_status(self, status: str | None) -> str:
        normalized = self._coerce_text(status).lower()
        if normalized in {"signed", "printed", "validated"}:
            return "confirmed"
        if normalized in {"draft", "confirmed", "cancelled"}:
            return normalized
        return "draft"

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _invalidate_pdf(self, certificate_id: int) -> None:
        self.pdf_storage.delete("aptitude-certificate", certificate_id)

    def _build_validator_signature_url(self, certificate: AptitudeCertificate) -> str | None:
        if not certificate.validator_signature_image_path:
            return None
        return f"/api/v1/aptitude-certificates/{certificate.id}/validator-signature"

    def _to_response(self, certificate: AptitudeCertificate) -> AptitudeCertificateResponse:
        worker = self.db.get(Worker, certificate.worker_id) if certificate.worker_id else None
        medical_visit = self.db.get(MedicalVisit, certificate.medical_visit_id) if certificate.medical_visit_id else None
        visit_snapshot = self._extract_visit_snapshot(medical_visit) if medical_visit else {}
        worker_snapshot = visit_snapshot.get("workerSnapshot") if isinstance(visit_snapshot.get("workerSnapshot"), dict) else {}

        doctor_name = get_validator_display_name(
            {"validatorName": certificate.validator_name},
            fallback=(
                f"{certificate.doctor.first_name} {certificate.doctor.last_name}".strip()
                if certificate.doctor
                else ""
            ),
        ) or None

        company_name = None
        if worker and getattr(worker, "company", None):
            company_name = getattr(worker.company, "name", None)
        company_name = company_name or self._coerce_text(worker_snapshot.get("companyName")) or None

        job_title = (
            getattr(worker, "job_title", None)
            or getattr(worker, "position", None)
            or self._coerce_text(worker_snapshot.get("position"))
            or None
        )
        birth_date = (
            worker.birth_date.isoformat() if worker and getattr(worker, "birth_date", None) else self._coerce_text(worker_snapshot.get("dateOfBirth")) or None
        )
        birth_place = (
            getattr(worker, "birth_wilaya", None)
            or self._coerce_text(worker_snapshot.get("birthPlace"))
            or None
        )
        blood_group = (
            getattr(worker, "blood_group", None)
            or self._coerce_text(worker_snapshot.get("bloodGroup"))
            or None
        )

        return AptitudeCertificateResponse(
            id=certificate.id,
            worker_id=certificate.worker_id,
            campaign_id=certificate.campaign_id,
            medical_visit_id=certificate.medical_visit_id,
            doctor_id=certificate.doctor_id,
            certificate_number=certificate.certificate_number,
            issue_date=certificate.issue_date.isoformat() if certificate.issue_date else None,
            visit_date=certificate.visit_date.isoformat() if certificate.visit_date else None,
            aptitude=self._normalize_aptitude_value(certificate.aptitude),
            aptitude_interpretation=certificate.aptitude_interpretation,
            doctor_recommendations=certificate.doctor_recommendations,
            next_visit_date=certificate.next_visit_date.isoformat() if certificate.next_visit_date else None,
            includeValidatorSignature=certificate.include_workspace_signature,
            includeDoctorSignature=certificate.include_workspace_signature,
            includeWorkspaceSignature=certificate.include_workspace_signature,
            status=self._normalize_status(certificate.status),
            created_at=certificate.created_at,
            updated_at=certificate.updated_at,
            deleted_at=certificate.deleted_at,
            validatorId=certificate.validator_id,
            validatorName=certificate.validator_name,
            validator_name=certificate.validator_name,
            validatorRole=certificate.validator_role,
            validatedAt=certificate.validated_at.isoformat() if certificate.validated_at else None,
            validatorSignatureImagePath=certificate.validator_signature_image_path,
            validated_by_user_id=certificate.validator_id,
            medicalVisitId=certificate.medical_visit_id,
            certificateNumber=certificate.certificate_number,
            firstName=(worker.first_name if worker else self._coerce_text(worker_snapshot.get("firstName"))) or None,
            lastName=(worker.last_name if worker else self._coerce_text(worker_snapshot.get("lastName"))) or None,
            companyName=company_name,
            jobTitle=job_title,
            aptitudeInterpretation=certificate.aptitude_interpretation,
            birthDate=birth_date,
            birthPlace=birth_place,
            bloodGroup=blood_group,
            doctorRecommendations=certificate.doctor_recommendations,
            visitDate=certificate.visit_date.isoformat() if certificate.visit_date else None,
            validatedDoctorName=doctor_name,
            validated_doctor_name=doctor_name,
            validatorSignatureUrl=self._build_validator_signature_url(certificate),
            issueDate=certificate.issue_date.isoformat() if certificate.issue_date else None,
            worker_full_name=f"{worker.first_name} {worker.last_name}".strip() if worker else None,
            doctorName=doctor_name,
            doctor_name=doctor_name,
        )

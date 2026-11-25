from __future__ import annotations

import base64
import os
import tempfile
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import has_role, user_has_permission
from app.exceptions import BadRequestException, ForbiddenException, NotFoundException, ConflictException
from app.models.campaign_worker import CampaignWorker
from app.models.medical_campaign import MedicalCampaign
from app.models.orientation_certificate import OrientationCertificate
from app.models.user import User
from app.models.worker import Worker
from app.repositories.orientation_certificate import OrientationCertificateRepository
from app.schemas.orientation_certificate import (
    OrientationCertificateCreate,
    OrientationCertificateResponse,
    OrientationCertificateUpdate,
)
from app.services.signature_authorization import get_validator_display_name
from app.services.user_signature_service import UserSignatureService
from app.services.worker_medical_visit_pdf_service import PdfFieldPlacement, WorkerMedicalVisitPdfService


class OrientationCertificatePdfService(WorkerMedicalVisitPdfService):
    def __init__(self) -> None:
        super().__init__()
        self.config_path = self.templates_dir / "orientation_certificate.fields.json"
        self.default_filename = "Attestation d'orientation.pdf"

    def generate_pdf(
        self,
        certificate: OrientationCertificate,
        workspace_settings: dict[str, Any] | None = None,
        include_signature: bool = False,
        signature_png: str | None = None,
    ) -> bytes:
        _ = workspace_settings
        config = self._load_config()
        template_filename = config.get("template_filename") or self.default_filename
        template_path = self.templates_dir / template_filename

        if not template_path.exists():
            raise BadRequestException(
                "Le modele PDF est introuvable.",
                {
                    "expected_template_path": str(template_path),
                    "hint": "Placez votre modele PDF dans backend/app/templates/exports avec le nom configure.",
                },
            )

        field_values = self._build_field_values(certificate)
        details_text = self._build_details_text(certificate)
        signature_image = self._extract_signature_image_bytes(
            include_signature,
            signature_png,
            certificate.validator_signature_image_path,
        )
        placements = self._parse_placements(config.get("fields", {}))

        writer = PdfWriter()
        with template_path.open("rb") as template_file:
            reader = PdfReader(template_file)
            writer.clone_document_from_reader(reader)

        writer.set_need_appearances_writer()

        form_updates_by_page: dict[int, dict[str, str]] = {}
        overlays_by_page: dict[int, list[tuple[PdfFieldPlacement, str]]] = {}
        image_overlays_by_page: dict[int, list[tuple[PdfFieldPlacement, bytes]]] = {}

        def add_text_overlay(page_index: int, placement: PdfFieldPlacement, value: str) -> None:
            overlays_by_page.setdefault(page_index, []).append((placement, value))

        def add_image_overlay(page_index: int, placement: PdfFieldPlacement, value: bytes) -> None:
            image_overlays_by_page.setdefault(page_index, []).append((placement, value))

        for field_key, field_placements in placements.items():
            value = self._coerce_value(field_values.get(field_key))

            if field_key == "orientation_details":
                for placement in field_placements:
                    page_index = placement.page - 1
                    if page_index < 0 or page_index >= len(writer.pages):
                        continue

                    if details_text:
                        detail_placement = PdfFieldPlacement(
                            page=placement.page,
                            x=placement.x,
                            y=placement.y,
                            first_line_x=placement.first_line_x,
                            other_lines_x=placement.other_lines_x,
                            font_size=placement.font_size,
                            font_color=placement.font_color,
                            font_name="Helvetica-Bold",
                            font_weight=placement.font_weight,
                            max_width=placement.max_width,
                            line_height=placement.line_height or placement.font_size + 2,
                            multiline=True,
                        )
                        add_text_overlay(page_index, detail_placement, details_text)
                continue

            if not value and not (field_key == "decision_validation_signature" and signature_image):
                continue

            for placement in field_placements:
                page_index = placement.page - 1
                if page_index < 0 or page_index >= len(writer.pages):
                    continue

                if field_key == "decision_validation_signature" and signature_image:
                    # Control signature image width and height
                    sig_width = placement.image_width or 120
                    sig_height =  placement.image_height or 50
                    
                    sig_placement = PdfFieldPlacement(
                        page=placement.page,
                        x=placement.x,
                        y=placement.y,
                        image_width=sig_width,
                        image_height=sig_height,
                    )
                    add_image_overlay(page_index, sig_placement, signature_image)
                    continue

                if placement.field_name:
                    form_updates_by_page.setdefault(page_index, {})[placement.field_name] = value
                if placement.x is not None and placement.y is not None:
                    add_text_overlay(page_index, placement, value)

        for page_index, updates in form_updates_by_page.items():
            writer.update_page_form_field_values(
                writer.pages[page_index],
                updates,
                auto_regenerate=False,
            )

        all_overlay_pages = sorted(set(overlays_by_page.keys()) | set(image_overlays_by_page.keys()))
        for page_index in all_overlay_pages:
            overlay_pdf = self._create_page_overlay(
                writer.pages[page_index],
                overlays_by_page.get(page_index, []),
                image_overlays_by_page.get(page_index, []),
            )
            overlay_reader = PdfReader(BytesIO(overlay_pdf))
            writer.pages[page_index].merge_page(overlay_reader.pages[0])

        output = BytesIO()
        writer.write(output)
        output.seek(0)
        return output.read()

    def _build_field_values(self, certificate: OrientationCertificate) -> dict[str, str]:
        worker = certificate.worker
        orientation_types = self._normalize_orientation_types(certificate)
        print("[OrientationPDF] id:", certificate.id)
        print("[OrientationPDF] orientation_types:", getattr(certificate, "orientation_types", None))
        print("[OrientationPDF] orientation_type:", getattr(certificate, "orientation_type", None))
        print("[OrientationPDF] details:", getattr(certificate, "orientation_details", None))
        doctor_name = self._join_text(
            "Dr.",
            certificate.doctor.first_name if certificate.doctor else "",
            certificate.doctor.last_name if certificate.doctor else "",
        )
        doctor_name = get_validator_display_name(
            {"validatorName": certificate.validator_name, "doctorName": certificate.doctor_name},
            fallback=doctor_name,
        )
        return {
            "orientation_date": self._format_date(certificate.orientation_date),
            "orientation_number": self._coerce_value(f"N° : {certificate.orientation_number}"),
            "patient_full_name": self._join_text(
                worker.last_name if worker else "",
                worker.first_name if worker else "",
            ),
            "patient_age": self._format_age(
                worker.birth_date if worker else None,
                certificate.orientation_date,
            ),
            "doctor_name": doctor_name,
            "orientation_type_a": self._build_orientation_type_fields(orientation_types).get("orientation_type_a"),
            "orientation_type_b": self._build_orientation_type_fields(orientation_types).get("orientation_type_b"),
            "orientation_type_c": self._build_orientation_type_fields(orientation_types).get("orientation_type_c"),
            "orientation_type_other": self._build_orientation_type_other_text(
                orientation_types,
                certificate.orientation_type_other,
            ),
            "orientation_details": "",
            "decision_validation_signature": "",
        }

    def _build_details_text(self, certificate: OrientationCertificate) -> str:
        details = self._coerce_value(certificate.orientation_details)
        if not details:
            return ""
        return f"{details}"

    def _extract_signature_image_bytes(
        self,
        include_signature: bool,
        signature_png: str | None,
        signature_image_path: str | None = None,
    ) -> bytes | None:
        if not include_signature:
            return None
        if signature_image_path:
            saved_bytes = UserSignatureService().read_signature_bytes(signature_image_path)
            if saved_bytes:
                return saved_bytes
        signature_data = self._coerce_value(signature_png)
        if not signature_data:
            return None
        if "," in signature_data:
            try:
                return base64.b64decode(signature_data.split(",", 1)[1])
            except (ValueError, TypeError):
                return None
        try:
            return base64.b64decode(signature_data)
        except (ValueError, TypeError):
            return None

    def _format_age(self, birth_date: date | str | None, at_date: date | str | None = None) -> str:
        if not birth_date:
            return ""

        if isinstance(birth_date, str):
            birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()

        if isinstance(at_date, str):
            at_date = datetime.strptime(at_date, "%Y-%m-%d").date()

        reference = at_date or date.today()

        years = reference.year - birth_date.year

        if (reference.month, reference.day) < (birth_date.month, birth_date.day):
            years -= 1

        return f"{max(years, 0)} ans"

    def _normalize_orientation_types(self, certificate: OrientationCertificate) -> dict[str, bool]:
        source = certificate.orientation_types if isinstance(certificate.orientation_types, dict) else {}
        legacy = self._coerce_value(certificate.orientation_type).lower()
        return {
            "specialistAdvice": bool(
                source.get("specialistAdvice")
                if "specialistAdvice" in source
                else legacy in {"avis_specialise", "cardiologie", "ophtalmologie"}
            ),
            "diagnosticCare": bool(
                source.get("diagnosticCare")
                if "diagnosticCare" in source
                else legacy == "prise_en_charge_diagnostic"
            ),
            "other": bool(
                source.get("other")
                if "other" in source
                else legacy == "autre"
            ),
        }

    def _build_orientation_type_fields(
        self,
        orientation_types: dict[str, bool],
    ) -> dict[str, str]:
        return {
            "orientation_type_a": "X" if orientation_types.get("specialistAdvice") else "",
            "orientation_type_b": "X" if orientation_types.get("diagnosticCare") else "",
            "orientation_type_c": "X" if orientation_types.get("other") else "",
        }

    def _build_orientation_type_other_text(
        self,
        orientation_types: dict[str, bool],
        orientation_type_other: str | None,
    ) -> str:
        if not orientation_types.get("other"):
            return ""
        return self._coerce_value(orientation_type_other)


class OrientationCertificateService:
    allowed_statuses = {"draft", "signed", "printed", "cancelled"}

    def __init__(self) -> None:
        self.repository = OrientationCertificateRepository()
        self.pdf_service = OrientationCertificatePdfService()

    def list(
        self,
        db: Session,
        worker_id: int | None = None,
        campaign_id: int | None = None,
    ) -> list[OrientationCertificateResponse]:
        items = self.repository.list(db, worker_id=worker_id, campaign_id=campaign_id)
        return [self._serialize(item) for item in items]

    def get(self, db: Session, certificate_id: int) -> OrientationCertificate:
        item = self.repository.get(db, certificate_id)
        if not item:
            raise NotFoundException("Orientation certificate not found")
        return item

    def get_response(self, db: Session, certificate_id: int) -> OrientationCertificateResponse:
        return self._serialize(self.get(db, certificate_id))

    def generate_orientation_number(
        self,
        db: Session,
        campaign_id: int,
        orientation_date: date,
    ) -> str:
        daily_count = self.repository.count_for_campaign_on_date(db, campaign_id, orientation_date) + 1
        return f"ORI-{campaign_id}-{orientation_date.strftime('%Y%m%d')}-{daily_count:03d}"

    def calculate_age(self, birth_date: date | None, at_date: date | None = None) -> int | None:
        if not birth_date:
            return None
        reference = at_date or date.today()
        years = reference.year - birth_date.year
        if (reference.month, reference.day) < (birth_date.month, birth_date.day):
            years -= 1
        return max(years, 0)

    def create(
        self,
        db: Session,
        payload: OrientationCertificateCreate,
        current_user: User,
    ) -> OrientationCertificateResponse:
        self._validate_creator_permissions(current_user, payload.status)
        worker = self._get_worker(db, payload.worker_id)
        self._ensure_campaign_assignment(db, worker.id, payload.campaign_id)
        self._get_campaign(db, payload.campaign_id)

        certificate = OrientationCertificate(
            worker_id=payload.worker_id,
            campaign_id=payload.campaign_id,
            doctor_id=payload.doctor_id
            or (current_user.id if has_role(current_user, "doctor", "admin", "super_admin") else None),
            orientation_number=payload.orientation_number
            or self.generate_orientation_number(db, payload.campaign_id, payload.orientation_date),
            orientation_date=payload.orientation_date,
            orientation_type=payload.orientation_type,
            orientation_type_other=payload.orientation_type_other,
            orientation_details=payload.orientation_details,
            status=self._normalize_status(payload.status, allow_signed=False),
            includeValidatorSignature=payload.includeValidatorSignature or False,
        )
        return self._serialize(self.repository.create(db, certificate))

    def update(
        self,
        db: Session,
        certificate_id: int,
        payload: OrientationCertificateUpdate,
        current_user: User,
    ) -> OrientationCertificateResponse:
        item = self.get(db, certificate_id)
        if item.status in {"signed", "validated", "printed"}:
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
        if item.status == "cancelled":
            raise BadRequestException("Cancelled orientation certificates cannot be updated")

        next_status = payload.status or item.status
        self._validate_creator_permissions(current_user, next_status)

        data = payload.model_dump(exclude_unset=True)
        if "status" in data:
            data["status"] = self._normalize_status(str(data["status"]), allow_signed=False)
        if "orientation_number" in data and not data["orientation_number"]:
            data["orientation_number"] = self.generate_orientation_number(
                db,
                item.campaign_id,
                data.get("orientation_date") or item.orientation_date,
            )
        for key, value in data.items():
            setattr(item, key, value)
        item.updated_at = datetime.now(timezone.utc)
        return self._serialize(self.repository.update(db, item))

    def sign(
        self,
        db: Session,
        certificate_id: int,
        current_user: User,
    ) -> OrientationCertificateResponse:
        item = self.get(db, certificate_id)
        if item.status in {"signed", "validated", "printed"}:
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
        if not has_role(current_user, "doctor", "admin", "super_admin"):
            raise ForbiddenException("Only Doctor, Admin, or Super Admin can sign orientation certificates")
        item.status = "signed"
        item.doctor_id = current_user.id
        item.updated_at = datetime.now(timezone.utc)
        return self._serialize(self.repository.update(db, item))

    def print(self, db: Session, certificate_id: int) -> OrientationCertificateResponse:
        item = self.get(db, certificate_id)
        if item.status in {"signed", "validated", "printed"}:
            return self._serialize(item)
        if item.status == "cancelled":
            raise BadRequestException("Cancelled orientation certificates cannot be printed")
        item.status = "printed"
        item.updated_at = datetime.now(timezone.utc)
        return self._serialize(self.repository.update(db, item))

    def delete(self, db: Session, certificate_id: int) -> OrientationCertificateResponse:
        item = self.get(db, certificate_id)
        if item.status in {"signed", "validated", "printed"}:
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
        item.deleted_at = datetime.now(timezone.utc)
        item.status = "cancelled"
        item.updated_at = datetime.now(timezone.utc)
        return self._serialize(self.repository.update(db, item))

    def generate_pdf(
        self,
        db: Session,
        certificate_id: int,
        workspace_settings: dict[str, Any] | None = None,
        include_signature: bool = False,
        signature_png: str | None = None,
    ) -> bytes:
        item = self.get(db, certificate_id)
        return self.pdf_service.generate_pdf(
            item,
            workspace_settings=workspace_settings,
            include_signature=include_signature,
            signature_png=signature_png,
        )

    def _serialize(self, item: OrientationCertificate) -> OrientationCertificateResponse:
        return OrientationCertificateResponse.model_validate(
            {
                **item.__dict__,
                "worker_name": f"{item.worker.first_name} {item.worker.last_name}".strip() if item.worker else None,
                "doctor_name": f"{item.doctor.first_name} {item.doctor.last_name}".strip() if item.doctor else None,
            }
        )

    def _validate_creator_permissions(self, current_user: User, status: str) -> None:
        normalized_role = (current_user.role or "").strip().lower()
        if normalized_role == "assistant":
            if not (
                user_has_permission(current_user, "workers:create")
                or user_has_permission(current_user, "workers:edit_basic")
            ):
                raise ForbiddenException("Assistant is not allowed to create orientation certificate drafts")
            if status and status.strip().lower() != "draft":
                raise ForbiddenException("Assistant can only create or update draft orientation certificates")

    def _normalize_status(self, status: str, allow_signed: bool) -> str:
        normalized = (status or "draft").strip().lower()
        if normalized not in self.allowed_statuses:
            raise BadRequestException("Invalid orientation certificate status")
        if not allow_signed and normalized in {"signed", "printed"}:
            return "draft"
        return normalized

    def _get_worker(self, db: Session, worker_id: int) -> Worker:
        worker = db.scalar(select(Worker).where(Worker.id == worker_id, Worker.deleted_at.is_(None)))
        if not worker:
            raise NotFoundException("Worker not found")
        return worker

    def _get_campaign(self, db: Session, campaign_id: int) -> MedicalCampaign:
        campaign = db.scalar(
            select(MedicalCampaign).where(
                MedicalCampaign.id == campaign_id,
                MedicalCampaign.deleted_at.is_(None),
            )
        )
        if not campaign:
            raise NotFoundException("Campaign not found")
        return campaign

    def _ensure_campaign_assignment(self, db: Session, worker_id: int, campaign_id: int) -> None:
        assignment = db.scalar(
            select(CampaignWorker).where(
                CampaignWorker.worker_id == worker_id,
                CampaignWorker.campaign_id == campaign_id,
            )
        )
        if not assignment:
            raise BadRequestException("Worker is not assigned to the selected campaign")

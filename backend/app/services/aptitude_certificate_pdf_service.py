from __future__ import annotations

import base64
from datetime import date, datetime
from io import BytesIO
from typing import Any

from pypdf import PdfReader, PdfWriter

from app.exceptions import BadRequestException
from app.models.aptitude_certificate import AptitudeCertificate
from app.services.signature_authorization import get_validator_display_name
from app.services.user_signature_service import UserSignatureService
from app.services.worker_medical_visit_pdf_service import PdfFieldPlacement, WorkerMedicalVisitPdfService


class AptitudeCertificatePdfService(WorkerMedicalVisitPdfService):
    SIGNATURE_FIELD_KEYS = {"includeWorkspaceSignature", "includeValidatorSignature"}

    def __init__(self) -> None:
        super().__init__()
        self.config_path = self.templates_dir / "cm_aptitude.fields.json"
        self.default_filename = "CM d'Aptitude.pdf"

    def generate_pdf(
        self,
        certificate: AptitudeCertificate,
        workspace_settings: dict[str, Any] | None = None,
        include_signature: bool | None = None,
        signature_png: str | None = None,
    ) -> bytes:
        _ = workspace_settings
        config = self._load_config()
        template_filename = config.get("template_filename") or self.default_filename
        template_path = self.templates_dir / template_filename

        if not template_path.exists():
            raise BadRequestException(
                "Le modele PDF du certificat d'aptitude est introuvable.",
                {
                    "expected_template_path": str(template_path),
                    "hint": "Placez le modele PDF d'aptitude dans backend/app/templates/exports.",
                },
            )

        field_values = self._build_field_values(certificate)
        signature_image = self._extract_signature_image_bytes(
            include_signature if include_signature is not None else bool(
                getattr(certificate, "include_validator_signature", None)
                or getattr(certificate, "include_workspace_signature", None)
            ),
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
            is_signature_field = field_key in self.SIGNATURE_FIELD_KEYS
            if not value and not (is_signature_field and signature_image):
                continue

            for placement in field_placements:
                page_index = placement.page - 1
                if page_index < 0 or page_index >= len(writer.pages):
                    continue

                if is_signature_field and signature_image:
                    sig_placement = PdfFieldPlacement(
                        page=placement.page,
                        x=placement.x,
                        y=placement.y,
                        image_width=placement.image_width or 120,
                        image_height=placement.image_height or 40,
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

    def _build_field_values(self, certificate: AptitudeCertificate) -> dict[str, str]:
        worker = certificate.worker
        legacy_doctor_name = self._join_text(
            "Dr.",
            certificate.doctor.first_name if certificate.doctor else "",
            certificate.doctor.last_name if certificate.doctor else "",
        )
        validator_name = get_validator_display_name(
            {"validatorName": certificate.validator_name},
            fallback=self._coerce_value(certificate.validator_name) or legacy_doctor_name,
        )
        worker_first_name = self._join_text(
            worker.first_name if worker else "",
        )
        worker_last_name = self._join_text(
            worker.last_name if worker else "",
        )
        worker_blood_group = self._coerce_value(worker.blood_group if worker else None)
        worker_blood_group_rh = (
            "Positive (+)"
            if worker_blood_group.endswith("+")
            else "Negative (-)"
            if worker_blood_group.endswith("-")
            else ""
        )

        worker_birth_place = self._coerce_value(worker.birth_wilaya if worker else None)
        worker_company = self._coerce_value(worker.company.name if worker and worker.company else None)

        worker_position = ""
        if worker:
            medical_data = worker.medical_file_data or {}
            worker_position = self._coerce_value(
                getattr(worker, "job_title", None)
                or getattr(worker, "department", None)
                or (medical_data.get("position") if isinstance(medical_data, dict) else None)
                or (medical_data.get("department") if isinstance(medical_data, dict) else None)
            )

        return {
            "certificate_number": certificate.certificate_number,
            "worker_first_name": worker_first_name,
            "worker_last_name": worker_last_name,
            "worker_birth_date": self._format_date_value(worker.birth_date if worker else None),
            "worker_position": worker_position,
            "worker_company": worker_company,
            "worker_blood_group": worker_blood_group,
            "worker_blood_group_rh": worker_blood_group_rh,
            "worker_birth_place": worker_birth_place,
            "issue_date": self._format_date_value(certificate.issue_date),
            "aptitude": self._translate_aptitude(certificate.aptitude),
            "doctor_recommendations": self._coerce_value(certificate.doctor_recommendations),
            "visit_date": self._format_date_value(certificate.visit_date or certificate.created_at),
            "doctor_name": validator_name,
            "status": self._coerce_value(certificate.status),
            "includeValidatorSignature": "true" if bool(
                getattr(certificate, "include_validator_signature", None)
                or getattr(certificate, "include_workspace_signature", None)
            ) else "",
            "includeWorkspaceSignature": "true" if bool(
                getattr(certificate, "include_workspace_signature", None)
                or getattr(certificate, "include_validator_signature", None)
            ) else "",
        }

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

    def _format_date_value(self, value: date | datetime | str | None) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        return self._format_date(value)

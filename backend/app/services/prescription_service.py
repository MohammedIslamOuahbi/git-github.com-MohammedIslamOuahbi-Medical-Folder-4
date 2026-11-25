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
from app.models.medical_visit import MedicalVisit
from app.models.prescription import Prescription
from app.models.prescription_item import PrescriptionItem
from app.models.user import User
from app.models.worker import Worker
from app.repositories.prescription_repository import PrescriptionRepository
from app.schemas.prescription import PrescriptionCreate, PrescriptionResponse, PrescriptionUpdate
from app.services.worker_medical_visit_pdf_service import PdfFieldPlacement, WorkerMedicalVisitPdfService
from app.services.signature_authorization import (
    build_validator_metadata,
    ensure_can_sign_medical_documents,
    get_validator_display_name,
    normalize_validator_signature_dict,
    ensure_signature_payload_authorized,
)
from app.services.user_signature_service import UserSignatureService
from app.services.prescription_formatter import build_prescription_item_sentence, build_prescription_preview_text


class PrescriptionPdfService(WorkerMedicalVisitPdfService):
    def __init__(self) -> None:
        super().__init__()
        self.config_path = self.templates_dir / "ordonnance.fields.json"
        self.default_filename = "Ordonnance.pdf"

    def generate_pdf(
        self,
        prescription: Prescription,
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

        field_values = self._build_field_values(prescription)
        diagnosis_text = self._build_diagnosis_text(prescription)
        notes_text = self._build_notes_text(prescription)
        signature_image = self._extract_signature_image_bytes(include_signature, signature_png)
        if include_signature and not signature_image and prescription.validator_signature_image_path:
            signature_image = UserSignatureService().read_signature_bytes(
                prescription.validator_signature_image_path
            )
        placements = self._parse_placements(config.get("fields", {}))

        table_png_path = self._generate_prescription_table_png(prescription)
        table_image_bytes = Path(table_png_path).read_bytes()

        try:
            with template_path.open("rb") as template_file:
                reader = PdfReader(template_file)
                writer = PdfWriter()
                writer.clone_document_from_reader(reader)

            writer.set_need_appearances_writer()

            form_updates_by_page: dict[int, dict[str, str]] = {}
            overlays_by_page: dict[int, list[tuple[PdfFieldPlacement, str]]] = {}
            image_overlays_by_page: dict[int, list[tuple[PdfFieldPlacement, bytes]]] = {}

            def add_text_overlay(page_index: int, placement: PdfFieldPlacement, value: str) -> None:
                overlays_by_page.setdefault(page_index, []).append((placement, value))

            def add_image_overlay(page_index: int, placement: PdfFieldPlacement, value: bytes) -> None:
                image_overlays_by_page.setdefault(page_index, []).append((placement, value))

            diagnosis_and_table_placements = placements.get("prescription_body", [])
            body_bottom_limit = self._resolve_body_bottom_limit(placements)

            for field_key, field_placements in placements.items():
                value = self._coerce_value(field_values.get(field_key))

                if field_key == "prescription_body":
                    for placement in diagnosis_and_table_placements:
                        page_index = placement.page - 1
                        if page_index < 0 or page_index >= len(writer.pages):
                            continue

                        current_y = float(placement.y or 0)
                        line_height = placement.line_height or placement.font_size + 2

                        if diagnosis_text:
                            diagnosis_placement = PdfFieldPlacement(
                                page=placement.page,
                                x=placement.x,
                                y=current_y,
                                first_line_x=placement.first_line_x,
                                other_lines_x=placement.other_lines_x,
                                font_size=placement.font_size,
                                font_color=placement.font_color,
                                font_name="Helvetica-Bold",
                                font_weight=placement.font_weight,
                                max_width=placement.max_width,
                                line_height=line_height,
                                multiline=True,
                            )
                            add_text_overlay(page_index, diagnosis_placement, diagnosis_text)
                            diagnosis_lines = self._split_text(
                                diagnosis_text,
                                diagnosis_placement.font_name,
                                diagnosis_placement.font_size,
                                diagnosis_placement.max_width,
                            )
                            current_y += len(diagnosis_lines) * line_height + 8

                        image_width = placement.max_width or placement.image_width or 300
                        table_width_px, table_height_px = self._get_image_size(table_image_bytes)
                        image_height = (
                            image_width * table_height_px / table_width_px if table_width_px else placement.image_height or 80
                        )

                        if notes_text and body_bottom_limit is not None:
                            note_lines = self._split_text(
                                notes_text,
                                placement.font_name,
                                placement.font_size,
                                placement.max_width,
                            )
                            notes_height = len(note_lines) * line_height + 10
                            available_height = max(48.0, body_bottom_limit - current_y - notes_height)
                            if image_height > available_height:
                                scale = available_height / image_height
                                image_width *= scale
                                image_height *= scale

                        image_placement = PdfFieldPlacement(
                            page=placement.page,
                            x=placement.x,
                            y=current_y,
                            image_width=image_width,
                            image_height=image_height,
                        )
                        add_image_overlay(page_index, image_placement, table_image_bytes)
                        current_y += image_height + 10

                        if notes_text:
                            notes_placement = PdfFieldPlacement(
                                page=placement.page,
                                x=placement.x,
                                y=current_y,
                                first_line_x=placement.first_line_x,
                                other_lines_x=placement.other_lines_x,
                                font_size=placement.font_size,
                                font_color=placement.font_color,
                                font_name="Helvetica-Bold",
                                font_weight=placement.font_weight,
                                max_width=placement.max_width,
                                line_height=line_height,
                                multiline=True,
                            )
                            add_text_overlay(page_index, notes_placement, notes_text)
                    continue

                if not value and not (field_key == "decision_validation_signature" and signature_image):
                    continue

                for placement in field_placements:
                    page_index = placement.page - 1
                    if page_index < 0 or page_index >= len(writer.pages):
                        continue

                    if field_key == "decision_validation_signature" and signature_image:
                        add_image_overlay(
                            page_index,
                            placement,
                            signature_image,
                        )
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
        finally:
            try:
                os.unlink(table_png_path)
            except OSError:
                pass

    def _build_field_values(self, prescription: Prescription) -> dict[str, str]:
        worker = prescription.worker
        doctor_name = self._join_text(
            "Dr.",
            prescription.doctor.first_name if prescription.doctor else "",
            prescription.doctor.last_name if prescription.doctor else "",
        )
        return {
            "prescription_date": self._format_date(prescription.prescription_date),
            "prescription_number": self._coerce_value(f"N° : {prescription.prescription_number}"),
            "patient_full_name": self._join_text(
                worker.last_name if worker else "",
                worker.first_name if worker else "",
            ),
            "patient_age": self._format_age(
                worker.birth_date if worker else None,
                prescription.prescription_date,
            ),
            "doctor_name": doctor_name,
            "prescription_body": "",
            "decision_validation_signature": "",
        }

    def _build_prescription_body(self, prescription: Prescription) -> str:
        lines: list[str] = []
        diagnosis_text = self._build_diagnosis_text(prescription)
        notes_text = self._build_notes_text(prescription)
        preview_text = build_prescription_preview_text(list(prescription.items))
        if diagnosis_text:
            lines.append(diagnosis_text)
        if preview_text.strip():
            if lines:
                lines.append("")
            lines.append(preview_text)
        if notes_text:
            if lines:
                lines.append("")
            lines.append(notes_text)
        return "\n".join(lines).strip()

    def _build_diagnosis_text(self, prescription: Prescription) -> str:
        diagnosis = self._coerce_value(prescription.diagnosis)
        if not diagnosis:
            return ""
        return f"Diagnostic / Motif: {diagnosis}"

    def _build_notes_text(self, prescription: Prescription) -> str:
        notes = self._coerce_value(prescription.notes)
        if not notes:
            return ""
        return f"Notes :\n{notes}"

    def _generate_prescription_table_png(self, prescription: Prescription) -> str:
        headers = ["N°", "Prescription"]

        rows = [
            [
                self._coerce_value(index),
                self._coerce_value(build_prescription_item_sentence(item)),
            ]
            for index, item in enumerate(prescription.items, start=1)
        ]

        if not rows:
            rows = [["", "Aucun médicament renseigné"]]

        body_font, header_font = self._load_table_fonts()

        padding_x = 8
        padding_y = 4
        border_width = 1

        header_bg = "#EAF3F8"
        row_bg = "#FFFFFF"
        alt_row_bg = "#F8FBFD"
        border_color = "#9AA8B2"
        text_color = "#111827"
        header_text_color = "#0F3D56"

        column_widths = [50, 910]

        sample = Image.new("RGB", (10, 10), "white")
        draw = ImageDraw.Draw(sample)

        def text_width(text: str, font: ImageFont.ImageFont) -> int:
            bbox = draw.textbbox((0, 0), text or " ", font=font)
            return bbox[2] - bbox[0]

        def text_height(text: str, font: ImageFont.ImageFont) -> int:
            bbox = draw.textbbox((0, 0), text or " ", font=font)
            return bbox[3] - bbox[1]

        def wrap_text(value: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
            text = self._coerce_value(value)
            if not text:
                return [""]

            words = text.split()
            lines: list[str] = []
            current = ""

            for word in words:
                candidate = f"{current} {word}".strip()

                if text_width(candidate, font) <= max_width:
                    current = candidate
                    continue

                if current:
                    lines.append(current)

                if text_width(word, font) <= max_width:
                    current = word
                else:
                    chunk = ""
                    for char in word:
                        candidate_chunk = chunk + char
                        if text_width(candidate_chunk, font) <= max_width:
                            chunk = candidate_chunk
                        else:
                            if chunk:
                                lines.append(chunk)
                            chunk = char
                    current = chunk

            if current:
                lines.append(current)

            return lines or [""]

        wrapped_headers = [
            wrap_text(header, header_font, column_widths[index] - padding_x * 2)
            for index, header in enumerate(headers)
        ]

        wrapped_rows = [
            [
                wrap_text(value, body_font, column_widths[index] - padding_x * 2)
                for index, value in enumerate(row)
            ]
            for row in rows
        ]

        header_line_height = max(text_height("Ag", header_font), 14) + 3
        body_line_height = max(text_height("Ag", body_font), 13) + 3

        header_height = max(len(lines) for lines in wrapped_headers) * header_line_height + padding_y * 2

        row_heights = [
            max(len(cell_lines) for cell_lines in row) * body_line_height + padding_y * 2
            for row in wrapped_rows
        ]

        image_width = sum(column_widths) + border_width
        print(f"Calculated image width: {image_width}")
        image_height = header_height + sum(row_heights) + border_width

        image = Image.new("RGB", (image_width, image_height), "white")
        draw_canvas = ImageDraw.Draw(image)

        def draw_cell(
            x: int,
            y: int,
            width: int,
            height: int,
            lines: list[str],
            *,
            font: ImageFont.ImageFont,
            fill: str,
            text_fill: str,
            align: str = "left",
            line_height: int,
        ) -> None:
            draw_canvas.rectangle(
                [x, y, x + width, y + height],
                fill=fill,
                outline=border_color,
                width=border_width,
            )

            text_block_height = len(lines) * line_height
            text_y = y + max((height - text_block_height) // 2, padding_y)

            for line in lines:
                line_width = text_width(line, font)

                if align == "center":
                    text_x = x + (width - line_width) // 2
                else:
                    text_x = x + padding_x

                draw_canvas.text((text_x, text_y), line, fill=text_fill, font=font)
                text_y += line_height

        x = 0
        y = 0

        for index, width in enumerate(column_widths):
            align = "center" if index == 0 else "left"
            draw_cell(
                x,
                y,
                width,
                header_height,
                wrapped_headers[index],
                font=header_font,
                fill=header_bg,
                text_fill=header_text_color,
                align=align,
                line_height=header_line_height,
            )
            x += width

        y += header_height

        for row_index, row in enumerate(wrapped_rows):
            x = 0
            row_height = row_heights[row_index]
            fill = alt_row_bg if row_index % 2 else row_bg

            for col_index, width in enumerate(column_widths):
                align = "center" if col_index == 0 else "left"
                draw_cell(
                    x,
                    y,
                    width,
                    row_height,
                    row[col_index],
                    font=body_font,
                    fill=fill,
                    text_fill=text_color,
                    align=align,
                    line_height=body_line_height,
                )
                x += width

            y += row_height

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
            image.save(tmp_file.name, format="PNG", optimize=True)
            return tmp_file.name
    
    def _load_table_fonts(self) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
        regular_candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "DejaVuSans.ttf",
            "arial.ttf",
            "LiberationSans-Regular.ttf",
        ]
        bold_candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "DejaVuSans-Bold.ttf",
            "arialbd.ttf",
            "LiberationSans-Bold.ttf",
        ]

        def load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
            for candidate in candidates:
                try:
                    return ImageFont.truetype(candidate, size=size)
                except OSError:
                    continue
            return ImageFont.load_default()

        return load_font(regular_candidates, 24), load_font(bold_candidates, 24)

    def _get_image_size(self, image_bytes: bytes) -> tuple[int, int]:
        with Image.open(BytesIO(image_bytes)) as image:
            return image.size

    def _resolve_body_bottom_limit(self, placements: dict[str, list[PdfFieldPlacement]]) -> float | None:
        doctor_name_placements = placements.get("doctor_name", [])
        if doctor_name_placements:
            values = [float(item.y) for item in doctor_name_placements if item.y is not None]
            if values:
                return min(values) - 14
        signature_placements = placements.get("decision_validation_signature", [])
        values = [float(item.y) for item in signature_placements if item.y is not None]
        return min(values) - 18 if values else None

    def _extract_signature_image_bytes(
        self,
        include_signature: bool,
        signature_png: str | None,
    ) -> bytes | None:
        if not include_signature:
            return None
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

    def _format_age(self, birth_date: date | None, at_date: date | None = None) -> str:
        if not birth_date:
            return ""
        reference = at_date or date.today()
        years = reference.year - birth_date.year
        if (reference.month, reference.day) < (birth_date.month, birth_date.day):
            years -= 1
        return f"{max(years, 0)} ans"


class PrescriptionService:
    allowed_statuses = {"draft", "validated", "printed", "cancelled"}

    def __init__(self) -> None:
        self.repository = PrescriptionRepository()
        self.pdf_service = PrescriptionPdfService()
        self.user_signature_service = UserSignatureService()

    def list(
        self,
        db: Session,
        worker_id: int | None = None,
        campaign_id: int | None = None,
        medical_visit_id: int | None = None,
    ) -> list[PrescriptionResponse]:
        items = self.repository.list(
            db,
            worker_id=worker_id,
            campaign_id=campaign_id,
            medical_visit_id=medical_visit_id,
        )
        return [self._serialize(item) for item in items]

    def get(self, db: Session, prescription_id: int) -> Prescription:
        item = self.repository.get(db, prescription_id)
        if not item:
            raise NotFoundException("Prescription not found")
        return item

    def get_response(self, db: Session, prescription_id: int) -> PrescriptionResponse:
        return self._serialize(self.get(db, prescription_id))

    def generate_prescription_number(
        self,
        db: Session,
        campaign_id: int,
        prescription_date: date,
    ) -> str:
        daily_count = self.repository.count_for_campaign_on_date(db, campaign_id, prescription_date) + 1
        return f"ORD-{campaign_id}-{prescription_date.strftime('%Y%m%d')}-{daily_count:03d}"

    def calculate_age(self, birth_date: date | None, at_date: date | None = None) -> int | None:
        if not birth_date:
            return None
        reference = at_date or date.today()
        years = reference.year - birth_date.year
        if (reference.month, reference.day) < (birth_date.month, birth_date.day):
            years -= 1
        return max(years, 0)

    def create_prescription(
        self,
        db: Session,
        payload: PrescriptionCreate,
        current_user: User,
    ) -> PrescriptionResponse:
        ensure_signature_payload_authorized(user=current_user, payload=payload.model_dump())
        if payload.includeValidatorSignature:
            self.user_signature_service.require_uploaded_signature(current_user)
        normalized_signature = normalize_validator_signature_dict(
            payload.model_dump(),
            current_user=current_user,
        )
        self._validate_creator_permissions(current_user, payload.status)
        worker = self._get_worker(db, payload.worker_id)
        self._ensure_campaign_assignment(db, worker.id, payload.campaign_id)
        self._get_campaign(db, payload.campaign_id)
        self._ensure_visit_matches_context(
            db,
            medical_visit_id=payload.medical_visit_id,
            worker_id=payload.worker_id,
            campaign_id=payload.campaign_id,
        )

        prescription = Prescription(
            worker_id=payload.worker_id,
            campaign_id=payload.campaign_id,
            medical_visit_id=payload.medical_visit_id,
            doctor_id=payload.doctor_id
            or (current_user.id if has_role(current_user, "doctor", "admin", "super_admin") else None),
            prescription_number=payload.prescription_number
            or self.generate_prescription_number(db, payload.campaign_id, payload.prescription_date),
            prescription_date=payload.prescription_date,
            diagnosis=payload.diagnosis,
            notes=payload.notes,
            include_validator_signature=normalized_signature.get("includeValidatorSignature", False),
            validator_id=normalized_signature.get("validatorId"),
            validator_name=normalized_signature.get("validatorName"),
            validator_role=normalized_signature.get("validatorRole"),
            validated_at=self._parse_datetime(normalized_signature.get("validatedAt")),
            validator_signature_image_path=normalized_signature.get("validatorSignatureImagePath"),
            status=self._normalize_status(payload.status, allow_signed=False),
            items=[PrescriptionItem(**self._normalize_item_payload(item.model_dump())) for item in payload.items],
        )
        return self._serialize(self.repository.create(db, prescription))

    def update_prescription(
        self,
        db: Session,
        prescription_id: int,
        payload: PrescriptionUpdate,
        current_user: User,
    ) -> PrescriptionResponse:
        item = self.get(db, prescription_id)
        if item.status in {"validated", "signed", "printed"}:
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
        ensure_signature_payload_authorized(user=current_user, payload=payload.model_dump(exclude_unset=True))
        if payload.includeValidatorSignature:
            self.user_signature_service.require_uploaded_signature(current_user)
        normalized_signature = normalize_validator_signature_dict(
            payload.model_dump(exclude_unset=True),
            current_user=current_user if payload.includeValidatorSignature is not None else None,
            existing_payload={
                "includeValidatorSignature": item.include_validator_signature,
                "validatorId": item.validator_id,
                "validatorName": item.validator_name,
                "validatorRole": item.validator_role,
                "validatedAt": item.validated_at.isoformat() if item.validated_at else None,
            },
        )
        if item.status == "cancelled":
            raise BadRequestException("Cancelled prescriptions cannot be updated")

        next_status = payload.status or item.status
        self._validate_creator_permissions(current_user, next_status)

        data = payload.model_dump(exclude_unset=True)
        if "status" in data:
            data["status"] = self._normalize_status(str(data["status"]), allow_signed=False)
        if "prescription_number" in data and not data["prescription_number"]:
            data["prescription_number"] = self.generate_prescription_number(
                db,
                item.campaign_id,
                data.get("prescription_date") or item.prescription_date,
            )
        if "medical_visit_id" in data:
            self._ensure_visit_matches_context(
                db,
                medical_visit_id=data["medical_visit_id"],
                worker_id=item.worker_id,
                campaign_id=item.campaign_id,
            )
        if "includeValidatorSignature" in data:
            data["include_validator_signature"] = normalized_signature.get("includeValidatorSignature", False)
            data["validator_id"] = normalized_signature.get("validatorId")
            data["validator_name"] = normalized_signature.get("validatorName")
            data["validator_role"] = normalized_signature.get("validatorRole")
            data["validated_at"] = self._parse_datetime(normalized_signature.get("validatedAt"))
            data["validator_signature_image_path"] = normalized_signature.get("validatorSignatureImagePath")
            data.pop("includeValidatorSignature", None)
        items = data.pop("items", None)
        for key, value in data.items():
            setattr(item, key, value)
        if items is not None:
            item.items = [PrescriptionItem(**self._normalize_item_payload(row)) for row in items]
        item.updated_at = datetime.now(timezone.utc)
        return self._serialize(self.repository.update(db, item))

    def sign_prescription(
        self,
        db: Session,
        prescription_id: int,
        current_user: User,
    ) -> PrescriptionResponse:
        item = self.get(db, prescription_id)
        if item.status in {"validated", "signed", "printed"}:
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
        ensure_can_sign_medical_documents(current_user)
        self.user_signature_service.require_uploaded_signature(current_user)
        validator_metadata = build_validator_metadata(current_user)
        if not item.items:
            raise BadRequestException("Add at least one medication before signing the prescription")
        item.status = "validated"
        item.doctor_id = current_user.id
        item.include_validator_signature = True
        item.validator_id = validator_metadata.get("validatorId")
        item.validator_name = validator_metadata.get("validatorName")
        item.validator_role = validator_metadata.get("validatorRole")
        item.validated_at = self._parse_datetime(validator_metadata.get("validatedAt"))
        item.validator_signature_image_path = validator_metadata.get("validatorSignatureImagePath")
        item.updated_at = datetime.now(timezone.utc)
        return self._serialize(self.repository.update(db, item))

    def validate_prescription(
        self,
        db: Session,
        prescription_id: int,
        current_user: User,
    ) -> PrescriptionResponse:
        return self.sign_prescription(db, prescription_id, current_user)

    def duplicate_prescription(
        self,
        db: Session,
        prescription_id: int,
        current_user: User,
    ) -> PrescriptionResponse:
        item = self.get(db, prescription_id)
        self._validate_creator_permissions(current_user, "draft")

        duplicated = Prescription(
            worker_id=item.worker_id,
            campaign_id=item.campaign_id,
            medical_visit_id=item.medical_visit_id,
            doctor_id=current_user.id if has_role(current_user, "doctor", "admin", "super_admin") else item.doctor_id,
            prescription_number=self.generate_prescription_number(db, item.campaign_id, date.today()),
            prescription_date=date.today(),
            diagnosis=item.diagnosis,
            notes=item.notes,
            include_validator_signature=False,
            validator_id=None,
            validator_name=None,
            validator_role=None,
            validated_at=None,
            validator_signature_image_path=None,
            status="draft",
            items=[
                PrescriptionItem(
                    medicine_id=prescription_item.medicine_id,
                    medication_name=prescription_item.medication_name,
                    brand_name=prescription_item.brand_name,
                    generic_name=prescription_item.generic_name,
                    strength=prescription_item.strength,
                    pharmaceutical_form=prescription_item.pharmaceutical_form,
                    dosage=prescription_item.dosage,
                    dose_quantity=prescription_item.dose_quantity,
                    dose_unit=prescription_item.dose_unit,
                    frequency=prescription_item.frequency,
                    frequency_custom=prescription_item.frequency_custom,
                    duration=prescription_item.duration,
                    duration_value=prescription_item.duration_value,
                    duration_unit=prescription_item.duration_unit,
                    quantity=prescription_item.quantity,
                    number_of_boxes=prescription_item.number_of_boxes,
                    instructions=prescription_item.instructions,
                    sort_order=prescription_item.sort_order,
                )
                for prescription_item in item.items
            ],
        )
        return self._serialize(self.repository.create(db, duplicated))

    def cancel_prescription(self, db: Session, prescription_id: int) -> PrescriptionResponse:
        item = self.get(db, prescription_id)
        if item.status in {"validated", "signed", "printed"}:
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
        item.status = "cancelled"
        item.updated_at = datetime.now(timezone.utc)
        return self._serialize(self.repository.update(db, item))

    def print_prescription(self, db: Session, prescription_id: int) -> PrescriptionResponse:
        item = self.get(db, prescription_id)
        if item.status in {"validated", "signed", "printed"}:
            return self._serialize(item)
        if item.status == "cancelled":
            raise BadRequestException("Cancelled prescriptions cannot be printed")
        item.status = "printed"
        item.updated_at = datetime.now(timezone.utc)
        return self._serialize(self.repository.update(db, item))

    def delete_prescription(self, db: Session, prescription_id: int) -> PrescriptionResponse:
        item = self.get(db, prescription_id)
        if item.status in {"validated", "signed", "printed"}:
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
        item.deleted_at = datetime.now(timezone.utc)
        item.status = "cancelled"
        item.updated_at = datetime.now(timezone.utc)
        return self._serialize(self.repository.update(db, item))

    def generate_prescription_pdf(
        self,
        db: Session,
        prescription_id: int,
        workspace_settings: dict[str, Any] | None = None,
        include_signature: bool = False,
        signature_png: str | None = None,
    ) -> bytes:
        item = self.get(db, prescription_id)
        return self.pdf_service.generate_pdf(
            item,
            workspace_settings=workspace_settings,
            include_signature=include_signature,
            signature_png=signature_png,
        )

    def _serialize(self, item: Prescription) -> PrescriptionResponse:
        return PrescriptionResponse.model_validate(
            {
                **item.__dict__,
                "worker_name": f"{item.worker.first_name} {item.worker.last_name}".strip() if item.worker else None,
                "doctor_name": get_validator_display_name(
                    {"validatorName": item.validator_name},
                    fallback=f"{item.doctor.first_name} {item.doctor.last_name}".strip() if item.doctor else None,
                ),
                "includeValidatorSignature": item.include_validator_signature,
                "validatorId": item.validator_id,
                "validatorName": item.validator_name,
                "validatorRole": item.validator_role,
                "validatedAt": item.validated_at,
                "validatorSignatureImagePath": item.validator_signature_image_path,
                "items": item.items,
            }
        )

    def _parse_datetime(self, value: object) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        normalized = str(value).strip().replace("Z", "+00:00")
        if not normalized:
            return None
        return datetime.fromisoformat(normalized)

    def _validate_creator_permissions(self, current_user: User, status: str) -> None:
        normalized_role = (current_user.role or "").strip().lower()
        if normalized_role == "assistant":
            if not (
                user_has_permission(current_user, "workers:create")
                or user_has_permission(current_user, "workers:edit_basic")
            ):
                raise ForbiddenException("Assistant is not allowed to create prescription drafts")
            if status and status.strip().lower() != "draft":
                raise ForbiddenException("Assistant can only create or update draft prescriptions")

    def _normalize_item_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        medication_name = str(
            normalized.get("medication_name")
            or normalized.get("brand_name")
            or normalized.get("generic_name")
            or ""
        ).strip()
        brand_name = str(normalized.get("brand_name") or medication_name or "").strip() or None
        generic_name = str(normalized.get("generic_name") or "").strip() or None
        strength = str(normalized.get("strength") or "").strip() or None
        dose_quantity = str(normalized.get("dose_quantity") or "").strip() or None
        dose_unit = str(normalized.get("dose_unit") or "").strip() or None
        frequency = str(normalized.get("frequency") or "").strip() or None
        frequency_custom = str(normalized.get("frequency_custom") or "").strip() or None
        duration_value = str(normalized.get("duration_value") or "").strip() or None
        duration_unit = str(normalized.get("duration_unit") or "").strip() or None
        instructions = str(normalized.get("instructions") or "").strip() or None
        number_of_boxes = str(normalized.get("number_of_boxes") or normalized.get("quantity") or "").strip() or None

        normalized["medication_name"] = medication_name or "Médicament"
        normalized["brand_name"] = brand_name
        normalized["generic_name"] = generic_name
        normalized["strength"] = strength
        normalized["dose_quantity"] = dose_quantity
        normalized["dose_unit"] = dose_unit
        normalized["frequency"] = frequency
        normalized["frequency_custom"] = frequency_custom
        normalized["duration_value"] = duration_value
        normalized["duration_unit"] = duration_unit
        normalized["instructions"] = instructions
        normalized["number_of_boxes"] = number_of_boxes
        normalized["dosage"] = normalized.get("dosage") or " ".join(
            part for part in [dose_quantity, dose_unit] if part
        ).strip() or None
        normalized["duration"] = normalized.get("duration") or " ".join(
            part for part in [duration_value, duration_unit] if part
        ).strip() or None
        normalized["quantity"] = normalized.get("quantity") or number_of_boxes
        normalized["sort_order"] = int(normalized.get("sort_order") or 0)
        return normalized

    def _normalize_status(self, status: str, allow_signed: bool) -> str:
        normalized = (status or "draft").strip().lower()
        if normalized == "signed":
            normalized = "validated"
        if normalized not in self.allowed_statuses:
            raise BadRequestException("Invalid prescription status")
        if not allow_signed and normalized in {"validated", "printed"}:
            return "draft"
        return normalized

    def _get_worker(self, db: Session, worker_id: int) -> Worker:
        worker = db.scalar(select(Worker).where(Worker.id == worker_id, Worker.deleted_at.is_(None)))
        if not worker:
            raise NotFoundException("Worker not found")
        return worker

    def _get_campaign(self, db: Session, campaign_id: int) -> MedicalCampaign:
        campaign = db.scalar(
            select(MedicalCampaign).where(MedicalCampaign.id == campaign_id, MedicalCampaign.deleted_at.is_(None))
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

    def _ensure_visit_matches_context(
        self,
        db: Session,
        *,
        medical_visit_id: int | None,
        worker_id: int,
        campaign_id: int,
    ) -> None:
        if medical_visit_id is None:
            return
        visit = db.scalar(
            select(MedicalVisit).where(MedicalVisit.id == medical_visit_id, MedicalVisit.deleted_at.is_(None))
        )
        if not visit:
            raise NotFoundException("Medical visit not found")
        if visit.worker_id != worker_id or visit.campaign_id != campaign_id:
            raise BadRequestException("Medical visit does not belong to the selected worker and campaign")

from __future__ import annotations

import base64
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.exceptions import BadRequestException
from app.models.worker import Worker
from app.services.signature_authorization import get_validator_display_name
from app.services.user_signature_service import UserSignatureService


@dataclass(slots=True)
class PdfFieldPlacement:
    page: int
    x: float | None = None
    y: float | None = None
    first_line_x: float | None = None
    other_lines_x: float | None = None
    font_size: float = 9
    font_color: tuple[float, float, float] = (0.1, 0.12, 0.16)
    font_name: str = "Helvetica"
    font_weight: str = "normal"
    image_width: float | None = None
    image_height: float | None = None
    max_width: float | None = None
    line_height: float | None = None
    multiline: bool = False
    field_name: str | None = None


class WorkerMedicalVisitPdfService:
    def __init__(self) -> None:
        self.templates_dir = Path(__file__).resolve().parents[1] / "templates" / "exports"
        self.config_path = self.templates_dir / "fich_intern_de_visit_medicale.fields.json"
        self.default_filename = "Fich intern de visit Medicale.pdf"

    def generate_pdf(
        self,
        worker: Worker,
        workspace_settings: dict[str, Any] | None = None,
        signature_png: str | None = None,
        visit_id: int | None = None,
        form_data: dict[str, Any] | None = None,
    ) -> bytes:
        _ = workspace_settings
        _ = visit_id
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

        field_values = self._build_field_values(worker, form_data=form_data)
        signature_image = self._extract_signature_image_bytes(worker, signature_png, form_data=form_data)
        placements = self._parse_placements(config.get("fields", {}))

        with template_path.open("rb") as template_file:
            reader = PdfReader(template_file)
            writer = PdfWriter()
            writer.clone_document_from_reader(reader)

        writer.set_need_appearances_writer()

        form_updates_by_page: dict[int, dict[str, str]] = defaultdict(dict)
        overlays_by_page: dict[int, list[tuple[PdfFieldPlacement, str]]] = defaultdict(list)
        image_overlays_by_page: dict[int, list[tuple[PdfFieldPlacement, bytes]]] = defaultdict(list)

        for field_key, field_placements in placements.items():
            value = self._coerce_value(field_values.get(field_key))
            if not value and not (field_key == "decision_validation_signature" and signature_image):
                continue

            for placement in field_placements:
                page_index = placement.page - 1
                if page_index < 0 or page_index >= len(writer.pages):
                    continue

                if field_key == "decision_validation_signature" and signature_image:
                    image_overlays_by_page[page_index].append(
                        (placement, signature_image)
                    )
                    continue

                if placement.field_name:
                    form_updates_by_page[page_index][placement.field_name] = value
                if placement.x is not None and placement.y is not None:
                    overlays_by_page[page_index].append((placement, value))

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
        return output.getvalue()

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise BadRequestException(
                "Le fichier de mapping PDF est introuvable.",
                {
                    "expected_config_path": str(self.config_path),
                    "hint": "Ajoutez le fichier JSON de coordonnees export.",
                },
            )

        with self.config_path.open("r", encoding="utf-8") as config_file:
            return json.load(config_file)

    def _parse_placements(self, raw_fields: dict[str, Any]) -> dict[str, list[PdfFieldPlacement]]:
        placements: dict[str, list[PdfFieldPlacement]] = {}

        for field_key, raw_placements in raw_fields.items():
            if not isinstance(raw_placements, list):
                continue

            parsed_items: list[PdfFieldPlacement] = []
            for raw_item in raw_placements:
                if not isinstance(raw_item, dict) or "page" not in raw_item:
                    continue
                parsed_items.append(
                    PdfFieldPlacement(
                        page=int(raw_item["page"]),
                        x=float(raw_item["x"]) if raw_item.get("x") is not None else None,
                        y=float(raw_item["y"]) if raw_item.get("y") is not None else None,
                        first_line_x=float(raw_item["first_line_x"]) if raw_item.get("first_line_x") is not None else None,
                        other_lines_x=float(raw_item["other_lines_x"]) if raw_item.get("other_lines_x") is not None else None,
                        font_size=float(raw_item.get("font_size", 9)),
                        font_color=self._parse_font_color(raw_item.get("font_color")),
                        font_name=self._resolve_font_name(
                            raw_item.get("font_name"),
                            raw_item.get("font_weight"),
                        ),
                        font_weight=self._coerce_value(raw_item.get("font_weight")).lower() or "normal",
                        image_width=float(raw_item["image_width"]) if raw_item.get("image_width") is not None else None,
                        image_height=float(raw_item["image_height"]) if raw_item.get("image_height") is not None else None,
                        max_width=float(raw_item["max_width"]) if raw_item.get("max_width") is not None else None,
                        line_height=float(raw_item["line_height"]) if raw_item.get("line_height") is not None else None,
                        multiline=bool(raw_item.get("multiline", False)),
                        field_name=raw_item.get("field_name"),
                    )
                )

            placements[field_key] = parsed_items

        return placements

    def _create_page_overlay(
        self,
        page: Any,
        overlay_entries: list[tuple[PdfFieldPlacement, str]],
        image_entries: list[tuple[PdfFieldPlacement, bytes]],
    ) -> bytes:
        overlay_stream = BytesIO()
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        pdf_canvas = canvas.Canvas(overlay_stream, pagesize=(page_width, page_height))

        for placement, value in overlay_entries:
            y_position = page_height - float(placement.y or 0)
            pdf_canvas.setFillColor(Color(*placement.font_color))
            pdf_canvas.setFont(placement.font_name, placement.font_size)

            if placement.multiline:
                line_height = placement.line_height or placement.font_size + 2
                lines = self._split_text(value, placement.font_name, placement.font_size, placement.max_width)
                for index, line in enumerate(lines):
                    if index == 0:
                        line_x = placement.first_line_x if placement.first_line_x is not None else placement.x
                    else:
                        line_x = placement.other_lines_x if placement.other_lines_x is not None else placement.x
                    pdf_canvas.drawString(float(line_x or 0), y_position - index * line_height, line)
                continue

            text = value
            if placement.max_width:
                text = self._truncate_text(value, placement.font_name, placement.font_size, placement.max_width)
            pdf_canvas.drawString(float(placement.x or 0), y_position, text)

        for placement, image_bytes in image_entries:
            if placement.x is None or placement.y is None:
                continue
            image_width = placement.image_width or 90
            image_height = placement.image_height or 32
            y_position = page_height - float(placement.y) - image_height
            pdf_canvas.drawImage(
                ImageReader(BytesIO(image_bytes)),
                float(placement.x),
                y_position,
                width=image_width,
                height=image_height,
                mask="auto",
                preserveAspectRatio=True,
                anchor="sw",
            )

        pdf_canvas.save()
        overlay_stream.seek(0)
        return overlay_stream.getvalue()

    def _split_text(self, value: str, font_name: str, font_size: float, max_width: float | None) -> list[str]:
        cleaned = value.strip()
        if not cleaned:
            return []
        if not max_width:
            return cleaned.splitlines() or [cleaned]

        lines: list[str] = []
        for chunk in cleaned.splitlines() or [cleaned]:
            lines.extend(simpleSplit(chunk, font_name, font_size, max_width) or [""])
        return lines

    def _truncate_text(self, value: str, font_name: str, font_size: float, max_width: float) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            return ""
        if stringWidth(cleaned, font_name, font_size) <= max_width:
            return cleaned

        suffix = "..."
        current = cleaned
        while current and stringWidth(f"{current}{suffix}", font_name, font_size) > max_width:
            current = current[:-1]
        return f"{current.rstrip()}{suffix}" if current else suffix

    def _parse_font_color(self, value: Any) -> tuple[float, float, float]:
        if isinstance(value, list) and len(value) == 3:
            channels: list[float] = []
            for item in value:
                try:
                    channel = float(item)
                except (TypeError, ValueError):
                    return (0.1, 0.12, 0.16)
                channels.append(channel / 255 if channel > 1 else channel)
            return tuple(max(0.0, min(channel, 1.0)) for channel in channels)  # type: ignore[return-value]
        return (0.1, 0.12, 0.16)

    def _resolve_font_name(self, font_name: Any, font_weight: Any) -> str:
        normalized_name = self._coerce_value(font_name).strip().lower()
        normalized_weight = self._coerce_value(font_weight).strip().lower()
        is_bold = normalized_weight == "bold"

        if normalized_name in {"helv", "helvetica", ""}:
            return "Helvetica-Bold" if is_bold else "Helvetica"
        if normalized_name in {"times", "times-roman", "times roman"}:
            return "Times-Bold" if is_bold else "Times-Roman"
        if normalized_name in {"cour", "courier"}:
            return "Courier-Bold" if is_bold else "Courier"
        fallback_font = "Helvetica-Bold" if is_bold else "Helvetica"
        return self._coerce_value(font_name) or fallback_font

    def _build_field_values(self, worker: Worker, form_data: dict[str, Any] | None = None) -> dict[str, str]:
        raw_form_data = form_data if isinstance(form_data, dict) else {}
        visit_data = self._normalize_visit_form_data(raw_form_data)
        worker_medical_data = self._as_dict(worker.medical_file_data)
        internal_visit = self._as_dict(visit_data.get("internalVisit"))
        clinical_exam = self._as_dict(visit_data.get("clinicalExam"))
        complementary_exams = self._as_dict(visit_data.get("complementaryExams"))
        medical_decision = self._as_dict(visit_data.get("medicalDecision"))
        validation = self._as_dict(
            visit_data.get("validation")
            or self._nested_value(medical_decision, "validation")
        )

        return {
            "worker_full_name": self._join_text(
                worker.last_name or worker_medical_data.get("lastName"),
                worker.first_name or worker_medical_data.get("firstName"),
            ),
            "worker_birth_date": self._format_date(worker.birth_date or worker_medical_data.get("dateOfBirth")),
            "worker_position": self._coerce_value(worker.job_title or worker.job_title or worker_medical_data.get("position")),
            "worker_direction": self._coerce_value(worker.department or worker_medical_data.get("direction") or worker_medical_data.get("department")),
            "worker_employee_code": self._coerce_value(worker.employee_number or worker_medical_data.get("employeeCode")),
            "worker_national_id": self._coerce_value(worker.national_id or worker_medical_data.get("nationalId")),
            "visit_type_hire": self._mark_checkbox(internal_visit.get("hire")),
            "visit_type_periodic": self._mark_checkbox(internal_visit.get("periodic")),
            "visit_date": self._format_date(internal_visit.get("date")),
            "visit_doctor": self._coerce_value(internal_visit.get("doctor")),
            "visit_weight": self._coerce_value(internal_visit.get("weightKg")),
            "visit_height": self._coerce_value(internal_visit.get("heightCm")),
            "visit_ta": self._coerce_value(internal_visit.get("ta")),
            "visit_fc": self._coerce_value(internal_visit.get("fc")),
            "visit_vision_od_sc": self._coerce_value(internal_visit.get("distanceOdSc")),
            "visit_vision_od_ac": self._coerce_value(internal_visit.get("distanceOdAc")),
            "visit_vision_og_sc": self._coerce_value(internal_visit.get("distanceOgSc")),
            "visit_vision_og_ac": self._coerce_value(internal_visit.get("distanceOgAc")),
            "visit_vision_odg": self._coerce_value(internal_visit.get("distanceOdg")),
            "clinical_ophthalmology_observations": self._nested_text(clinical_exam, "ophthalmology", "observations"),
            "clinical_ent_nose": self._nested_text(clinical_exam, "ent", "nose"),
            "clinical_ent_ears": self._nested_text(clinical_exam, "ent", "ears"),
            "clinical_ent_throat": self._nested_text(clinical_exam, "ent", "throat"),
            "clinical_stomatology_teeth": self._nested_text(clinical_exam, "stomatology", "teeth"),
            "clinical_stomatology_others": self._nested_text(clinical_exam, "stomatology", "others"),
            "clinical_cardiovascular_blood_pressure": self._coerce_value(
                self._nested_value(clinical_exam, "cardiovascular", "bloodPressure") or internal_visit.get("ta")
            ),
            "clinical_cardiovascular_dyspnea": self._nested_text(clinical_exam, "cardiovascular", "dyspnea"),
            "clinical_respiratory_chronic_cough": self._nested_text(clinical_exam, "respiratory", "chronicCough"),
            "clinical_respiratory_asthma": self._nested_text(clinical_exam, "respiratory", "asthma"),
            "clinical_digestive_ulcer": self._nested_text(clinical_exam, "digestive", "ulcer"),
            "clinical_digestive_colopathy": self._nested_text(clinical_exam, "digestive", "colopathy"),
            "clinical_digestive_hemorrhoids": self._nested_text(clinical_exam, "digestive", "hemorrhoids"),
            "clinical_digestive_others": self._nested_text(clinical_exam, "digestive", "others"),
            "clinical_urogenital_dysuria": self._nested_text(clinical_exam, "urogenital", "dysuria"),
            "clinical_urogenital_impotence": self._nested_text(clinical_exam, "urogenital", "impotence"),
            "clinical_urogenital_others": self._nested_text(clinical_exam, "urogenital", "others"),
            "clinical_endocrine_diabetes": self._nested_text(clinical_exam, "endocrine", "diabetes"),
            "clinical_endocrine_thyroid": self._nested_text(clinical_exam, "endocrine", "thyroid"),
            "clinical_endocrine_others": self._nested_text(clinical_exam, "endocrine", "others"),
            "clinical_hematology_hemostasis": self._nested_text(clinical_exam, "hematology", "hemostasis"),
            "clinical_hematology_adenopathy": self._nested_text(clinical_exam, "hematology", "adenopathy"),
            "clinical_hematology_others": self._nested_text(clinical_exam, "hematology", "others"),
            "clinical_neuro_headaches_vertigo": self._nested_text(clinical_exam, "neuroPsychiatric", "headachesVertigo"),
            "clinical_neuro_neurological_signs": self._nested_text(clinical_exam, "neuroPsychiatric", "neurologicalSigns"),
            "clinical_neuro_personality_disorders": self._nested_text(clinical_exam, "neuroPsychiatric", "personalityDisorders"),
            "clinical_neuro_others": self._nested_text(clinical_exam, "neuroPsychiatric", "others"),
            "clinical_osteo_polyarthralgia": self._nested_text(clinical_exam, "osteoArticular", "polyarthralgia"),
            "clinical_dermatology_lesions": self._nested_text(clinical_exam, "dermatology", "lesions"),
            "clinical_dermatology_skin_allergies": self._nested_text(clinical_exam, "dermatology", "skinAllergies"),
            "clinical_dermatology_urticaria": self._nested_text(clinical_exam, "dermatology", "urticaria"),
            "clinical_general_comments": self._nested_text(clinical_exam, "doctorGeneralObservations", "comments"),
            "clinical_general_recommendations": self._nested_text(clinical_exam, "doctorGeneralObservations", "recommendations"),
            "complementary_cardiology_ecg": self._nested_text(complementary_exams, "cardiology", "ecg"),
            "complementary_audiology_audiogram": self._nested_text(complementary_exams, "audiology", "audiogram"),
            "complementary_respiratory_efr": self._nested_text(complementary_exams, "respiratory", "efr"),
            "complementary_biology_blood_group_rhesus": self._coerce_value(
                worker.blood_group or worker_medical_data.get("bloodGroup")
            ),
            "complementary_biology_glycemia": self._nested_text(complementary_exams, "biology", "glycemia"),
            "complementary_biology_hba1c": self._nested_text(complementary_exams, "biology", "hba1c"),
            "complementary_biology_urea": self._nested_text(complementary_exams, "biology", "urea"),
            "complementary_biology_creatinine": self._nested_text(complementary_exams, "biology", "creatinine"),
            "complementary_biology_cholesterol": self._nested_text(complementary_exams, "biology", "cholesterol"),
            "complementary_biology_triglycerides": self._nested_text(complementary_exams, "biology", "triglycerides"),
            "complementary_biology_hdl_ldl": self._nested_text(complementary_exams, "biology", "hdlLdl"),
            "complementary_biology_urine_chemistry": self._nested_text(complementary_exams, "biology", "urineChemistry"),
            "complementary_hematology_gr": self._nested_text(complementary_exams, "hematology", "gr"),
            "complementary_hematology_gb": self._nested_text(complementary_exams, "hematology", "gb"),
            "complementary_hematology_hb": self._nested_text(complementary_exams, "hematology", "hb"),
            "complementary_hematology_ht": self._nested_text(complementary_exams, "hematology", "ht"),
            "complementary_hematology_vgm": self._nested_text(complementary_exams, "hematology", "vgm"),
            "complementary_hematology_ccmh": self._nested_text(complementary_exams, "hematology", "ccmh"),
            "complementary_hematology_plt": self._nested_text(complementary_exams, "hematology", "plt"),
            "complementary_hematology_pn": self._nested_text(complementary_exams, "hematology", "pn"),
            "complementary_hematology_lymphocytes": self._nested_text(complementary_exams, "hematology", "lymphocytes"),
            "complementary_hematology_bem": self._nested_text(complementary_exams, "hematology", "bem"),
            "complementary_hematology_vs": self._nested_text(complementary_exams, "hematology", "vs"),
            "complementary_parasitology_stool_exam": self._nested_text(complementary_exams, "parasitology", "stoolExam"),
            "complementary_radiology_chest_xray": self._nested_text(complementary_exams, "radiology", "chestXray"),
            "complementary_radiology_others": self._nested_text(complementary_exams, "radiology", "others"),
            "complementary_other_exams": self._nested_text(complementary_exams, "otherExams", "freeText"),
            "decision_orientation_specialty": self._nested_text(medical_decision, "orientation", "specialty"),
            "decision_orientation_specialist_advice": self._mark_checkbox(self._nested_value(medical_decision, "orientation", "specialistAdvice")),
            "decision_orientation_specialist_advice_details": self._nested_text(medical_decision, "orientation", "specialistAdviceDetails"),
            "decision_orientation_treatment": self._mark_checkbox(self._nested_value(medical_decision, "orientation", "treatment")),
            "decision_orientation_treatment_details": self._nested_text(medical_decision, "orientation", "treatmentDetails"),
            "decision_orientation_hospitalization": self._mark_checkbox(self._nested_value(medical_decision, "orientation", "hospitalization")),
            "decision_orientation_hospitalization_details": self._nested_text(medical_decision, "orientation", "hospitalizationDetails"),
            "decision_specialist_response": self._nested_text(medical_decision, "specialistResponse", "response"),
            "decision_specialist_social_service": self._nested_text(medical_decision, "specialistResponse", "socialService"),
            "decision_specialist_employment_service": self._nested_text(medical_decision, "specialistResponse", "employmentService"),
            "decision_cat_conduct": self._nested_text(medical_decision, "cat", "conduct"),
            "decision_aptitude": self._translate_aptitude(medical_decision.get("aptitude")),
            "decision_aptitude_apte": self._aptitude_row_text(medical_decision, "apte"),
            "decision_aptitude_apte_with_restrictions": self._aptitude_row_text(
                medical_decision,
                "apte_with_restrictions",
            ),
            "decision_aptitude_temporarily_unfit": self._aptitude_row_text(
                medical_decision,
                "temporarily_unfit",
            ),
            "decision_aptitude_definitively_unfit": self._aptitude_row_text(
                medical_decision,
                "definitively_unfit",
            ),
            "decision_interpretation": self._nested_text(medical_decision, "interpretation", "decisionInterpretation"),
            "decision_next_visit_schedule": self._translate_next_visit_schedule(
                self._nested_text(medical_decision, "nextVisit", "nextVisitSchedule"),
                self._nested_text(medical_decision, "nextVisit", "nextVisitCustomMonths"),
            ),
            "decision_next_visit_date": self._format_date(self._nested_value(medical_decision, "nextVisit", "nextVisitDate")),
            "decision_validation_doctor": get_validator_display_name(
                validation,
                fallback=self._nested_text(medical_decision, "validation", "validatingDoctor"),
            ),
            "decision_validation_date": self._format_date(
                validation.get("validationDate") or self._nested_value(medical_decision, "validation", "validationDate")
            ),
            "decision_validation_signature": self._nested_text(medical_decision, "validation", "electronicSignature"),
        }

    def _extract_signature_image_bytes(
        self,
        worker: Worker,
        signature_png: str | None,
        form_data: dict[str, Any] | None = None,
    ) -> bytes | None:
        visit_data = self._normalize_visit_form_data(form_data if isinstance(form_data, dict) else {})
        validation = self._as_dict(
            visit_data.get("validation")
            or self._nested_value(self._as_dict(visit_data.get("medicalDecision")), "validation")
        )
        include_signature = False
        if isinstance(validation, dict):
            include_signature = bool(
                validation.get("includeValidatorSignature")
                if validation.get("includeValidatorSignature") is not None
                else (
                    validation.get("includeDoctorSignature")
                    if validation.get("includeDoctorSignature") is not None
                    else validation.get("includeWorkspaceSignature")
                )
            )
        if not include_signature:
            return None

        signature_path = validation.get("validatorSignatureImagePath") if isinstance(validation, dict) else None
        if isinstance(signature_path, str) and signature_path.strip():
            saved_bytes = UserSignatureService().read_signature_bytes(signature_path.strip())
            if saved_bytes:
                return saved_bytes

        signature_data = self._coerce_value(signature_png)
        if not signature_data:
            return None

        match = re.match(r"^data:image/png;base64,(.+)$", signature_data, flags=re.IGNORECASE)
        payload = match.group(1) if match else signature_data
        try:
            return base64.b64decode(payload)
        except (ValueError, TypeError):
            return None

    def _nested_value(self, source: dict[str, Any], *keys: str) -> Any:
        current: Any = source
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    def _nested_text(self, source: dict[str, Any], *keys: str) -> str:
        return self._coerce_value(self._nested_value(source, *keys))

    def _translate_aptitude(self, aptitude: Any) -> str:
        mapping = {
            "apte": "Apte",
            "apte_with_restrictions": "Apte avec reserves",
            "temporarily_unfit": "Inapte temporaire",
            "definitively_unfit": "Inapte definitive",
        }
        return mapping.get(self._coerce_value(aptitude), self._coerce_value(aptitude))

    def _aptitude_row_text(self, medical_decision: dict[str, Any], aptitude_key: str) -> str:
        selected_aptitude = self._coerce_value(medical_decision.get("aptitude"))
        if selected_aptitude != aptitude_key:
            return ""
        interpretation = self._nested_text(medical_decision, "interpretation", "decisionInterpretation")
        return interpretation or self._translate_aptitude(selected_aptitude)

    def _translate_next_visit_schedule(self, schedule: str, custom_months: str) -> str:
        normalized = schedule.strip().lower()
        if normalized == "6_months":
            return "6 mois"
        if normalized == "12_months":
            return "12 mois"
        if normalized == "custom":
            return f"{custom_months} mois" if custom_months else "Specifique"
        if normalized == "on_call":
            return "A convoquer"
        return schedule

    def _mark_checkbox(self, value: Any) -> str:
        return "X" if bool(value) else ""

    def _join_text(self, *parts: Any) -> str:
        return " ".join(part.strip() for part in map(self._coerce_value, parts) if part).strip()

    def _coerce_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _format_date(self, value: Any) -> str:
        raw = self._coerce_value(value)
        if not raw:
            return ""
        if "T" in raw:
            raw = raw.split("T", 1)[0]
        parts = raw.split("-")
        if len(parts) == 3 and all(parts):
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        return raw

    def _as_dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _normalize_visit_form_data(self, form_data: dict[str, Any]) -> dict[str, Any]:
        if isinstance(form_data.get("visitData"), dict):
            return self._as_dict(form_data.get("visitData"))
        return form_data

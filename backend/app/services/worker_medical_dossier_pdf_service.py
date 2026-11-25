from __future__ import annotations

from typing import Any

from app.models.worker import Worker
from app.services.worker_medical_visit_pdf_service import WorkerMedicalVisitPdfService


class WorkerMedicalDossierPdfService(WorkerMedicalVisitPdfService):
    def __init__(self) -> None:
        super().__init__()
        self.config_path = self.templates_dir / "dossier_medical.fields.json"
        self.default_filename = "Dossier médical.pdf"

    def generate_pdf(
        self,
        worker: Worker,
        workspace_settings: dict[str, Any] | None = None,
        signature_png: str | None = None,
        visit_id: int | None = None,
        form_data: dict[str, Any] | None = None,
    ) -> bytes:
        # The medical dossier export must only use the persisted worker folder.
        return super().generate_pdf(
            worker,
            workspace_settings=workspace_settings,
            signature_png=signature_png,
            visit_id=visit_id,
            form_data=None,
        )

    def _build_field_values(
        self,
        worker: Worker,
        form_data: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        _ = form_data
        medical_data = worker.medical_file_data or {}
        professional_history = medical_data.get("professionalHistory") or []
        vaccinations = medical_data.get("vaccinations") or []
        work_accidents = medical_data.get("workAccidents") or []
        occupational_diseases = medical_data.get("occupationalDiseases") or []
        consultations = medical_data.get("spontaneousConsultations") or []

        values = {
            "dossier_number": self._coerce_value(medical_data.get("medicalFileNumber")),
            "last_name": self._coerce_value(medical_data.get("lastName") or worker.last_name),
            "first_name": self._coerce_value(medical_data.get("firstName") or worker.first_name),
            "sex": self._coerce_value(medical_data.get("sex") or worker.gender),
            "birth_date": self._format_date(medical_data.get("dateOfBirth") or worker.birth_date),
            "birth_place": self._coerce_value(medical_data.get("birthPlace") or worker.birth_wilaya),
            "family_situation": self._coerce_value(medical_data.get("familySituation")),
            "phone": self._coerce_value(medical_data.get("phone") or worker.phone),
            "origin_address": self._coerce_value(medical_data.get("originAddress") or worker.address),
            "professional_address": self._coerce_value(medical_data.get("professionalAddress")),
            "school_education": self._coerce_value(medical_data.get("schoolEducation")),
            "professional_training": self._coerce_value(medical_data.get("professionalTraining")),
            "professional_qualification": self._coerce_value(medical_data.get("professionalQualification")),
            "service_national_accompli": self._mark_checkbox(
                self._coerce_value(medical_data.get("nationalServiceStatus")).lower() in {"accompli", "accomplit", "completed"}
            ),
            "service_national_dispense": self._mark_checkbox(
                self._coerce_value(medical_data.get("nationalServiceStatus")).lower() in {"dispense", "dispensé", "dispensee"}
            ),
            "service_national_inapte": self._mark_checkbox(
                self._coerce_value(medical_data.get("nationalServiceStatus")).lower() in {"inapte", "unfit"}
            ),
            "chronic_disease_notes": self._coerce_value(medical_data.get("chronicDiseaseNotes")),
            "blood_group_rhesus": self._coerce_value(medical_data.get("bloodGroup") or worker.blood_group),
            "congenital_diseases": self._coerce_value(medical_data.get("congenitalDiseases")),
            "general_diseases": self._coerce_value(medical_data.get("generalDiseases")),
            "surgical_interventions": self._coerce_value(medical_data.get("surgicalInterventions")),
            "accidents": self._coerce_value(medical_data.get("accidents")),
            "intoxications_tobacco": self._coerce_value(medical_data.get("tobacco")),
            "intoxications_chewing_tobacco": self._coerce_value(medical_data.get("chewingTobacco")),
            "intoxications_alcoholism": self._coerce_value(medical_data.get("alcoholism")),
            "intoxications_others": self._coerce_value(medical_data.get("otherIntoxications")),
            "family_history_father": self._coerce_value(medical_data.get("familyHistoryFather")),
            "family_history_mother": self._coerce_value(medical_data.get("familyHistoryMother")),
            "family_history_sisters": self._coerce_value(medical_data.get("familyHistorySisters")),
            "family_history_brothers": self._coerce_value(medical_data.get("familyHistoryBrothers")),
            "family_history_spouse": self._coerce_value(medical_data.get("familyHistorySpouse")),
            "family_history_children_boys": self._coerce_value(medical_data.get("familyHistoryChildrenBoys")),
            "family_history_children_girls": self._coerce_value(medical_data.get("familyHistoryChildrenGirls")),
            "professional_disease_notes": self._coerce_value(medical_data.get("professionalDiseaseNotes")),
        }

        for index in range(3):
            row = self._list_item(professional_history, index)
            values[f"professional_history_position_{index + 1}"] = self._coerce_value(row.get("occupiedPosition"))
            values[f"professional_history_from_{index + 1}"] = self._format_date(row.get("fromDate"))
            values[f"professional_history_to_{index + 1}"] = self._format_date(row.get("toDate"))
            values[f"professional_history_risks_{index + 1}"] = self._coerce_value(row.get("workplaceAndRisks"))

        for index in range(3):
            row = self._list_item(vaccinations, index)
            values[f"vaccination_name_{index + 1}"] = self._coerce_value(row.get("vaccineName"))
            values[f"vaccination_first_dose_{index + 1}"] = self._format_date(row.get("firstDose"))
            values[f"vaccination_second_dose_{index + 1}"] = self._format_date(row.get("secondDose"))
            values[f"vaccination_first_booster_{index + 1}"] = self._format_date(row.get("firstBooster"))
            values[f"vaccination_second_booster_{index + 1}"] = self._format_date(row.get("secondBooster"))

        for index in range(4):
            row = self._list_item(work_accidents, index)
            values[f"work_accident_date_{index + 1}"] = self._format_date(row.get("date"))
            values[f"work_accident_place_{index + 1}"] = self._coerce_value(row.get("place"))
            values[f"work_accident_consequences_{index + 1}"] = self._coerce_value(row.get("consequences"))

        for index in range(3):
            row = self._list_item(occupational_diseases, index)
            values[f"occupational_disease_date_{index + 1}"] = self._format_date(row.get("date"))
            values[f"occupational_disease_place_{index + 1}"] = self._coerce_value(row.get("place"))
            values[f"occupational_disease_products_{index + 1}"] = self._coerce_value(row.get("exposedProducts"))
            values[f"occupational_disease_symptoms_{index + 1}"] = self._coerce_value(row.get("symptoms"))
            values[f"occupational_disease_tmp_{index + 1}"] = self._coerce_value(row.get("tmpNumber"))
            values[f"occupational_disease_ipp_{index + 1}"] = self._coerce_value(row.get("ipp"))

        for index in range(12):
            row = self._list_item(consultations, index)
            values[f"consultation_date_{index + 1}"] = self._format_date(row.get("date"))
            values[f"consultation_observation_{index + 1}"] = self._coerce_value(row.get("observation"))

        return values

    def _list_item(self, items: Any, index: int) -> dict[str, Any]:
        if isinstance(items, list) and index < len(items) and isinstance(items[index], dict):
            return items[index]
        return {}

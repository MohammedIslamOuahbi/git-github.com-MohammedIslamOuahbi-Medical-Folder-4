from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import BadRequestException, NotFoundException
from app.models.campaign_worker import CampaignWorker
from app.models.import_job import ImportJob
from app.models.import_row import ImportRow
from app.models.medical_campaign import MedicalCampaign
from app.models.medical_visit import MedicalVisit
from app.models.prescription import Prescription
from app.models.user import User
from app.models.worker import Worker
from app.repositories.import_repository import ImportRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.worker_repository import WorkerRepository
from app.schemas.medical_visit import MedicalVisitCreate, MedicalVisitUpdate
from app.schemas.prescription import PrescriptionCreate, PrescriptionItemCreate, PrescriptionUpdate
from app.services.medical_visit_service import MedicalVisitService
from app.services.prescription_service import PrescriptionService
from app.utils.csv_reader import read_csv_rows
from app.utils.duplicate_detector import detect_duplicates
from app.utils.excel_reader import read_excel_rows
from app.utils.file_validator import validate_import_filename
from app.utils.helpers import ensure_directory
from app.utils.json_serializer import make_json_serializable


class ImportService:
    required_worker_fields = ["firstName", "lastName"]
    identity_alternates = ["employeeCode", "medicalFileNumber"]
    legacy_field_aliases = {
        "employee_number": "employeeCode",
        "national_id": "nationalId",
        "first_name": "firstName",
        "last_name": "lastName",
        "gender": "sex",
        "birth_date": "dateOfBirth",
        "birth_wilaya": "birthPlace",
        "marital_status": "familySituation",
        "blood_group": "bloodGroup",
        "phone": "phone",
        "address": "originAddress",
        "job_title": "position",
        "department": "department",
    }

    date_fields = {
        "dateOfBirth",
        "confirmationDate",
        "professionalHistory[].fromDate",
        "professionalHistory[].toDate",
        "workAccidents[].date",
        "occupationalDiseases[].date",
        "spontaneousConsultations[].date",
        "internalVisitDate",
        "profilTaGlycemie.rows[].date",
        "medicalDecision.nextVisit.nextVisitDate",
        "medicalDecision.validation.validationDate",
        "workStoppageCertificate.startDate",
        "workStoppageCertificate.endDate",
        "workStoppageCertificate.issuedAt",
        "aptitudeCertificate.issueDate",
        "aptitudeCertificate.visitDate",
        "aptitudeCertificate.validatedAt",
        "orientationCertificate.orientation_date",
        "orientationCertificate.validatedAt",
        "prescription.prescription_date",
    }

    boolean_fields = {
        "isLocked",
        "internalVisitHire",
        "internalVisitPeriodic",
        "medicalDecision.orientation.specialistAdvice",
        "medicalDecision.orientation.treatment",
        "medicalDecision.orientation.hospitalization",
        "medicalDecision.validation.includeValidatorSignature",
        "medicalDecision.validation.includeDoctorSignature",
        "medicalDecision.validation.includeWorkspaceSignature",
        "workStoppageCertificate.returnToWork",
        "workStoppageCertificate.includeValidatorSignature",
        "aptitudeCertificate.includeValidatorSignature",
        "orientationCertificate.orientationTypes.specialistAdvice",
        "orientationCertificate.orientationTypes.diagnosticCare",
        "orientationCertificate.orientationTypes.other",
        "orientationCertificate.includeValidatorSignature",
        "prescription.includeValidatorSignature",
    }

    number_fields = {
        "medicalDecision.validation.validatorId",
        "orientationCertificate.age",
        "orientationCertificate.validatorId",
        "workStoppageCertificate.workerAge",
    }

    def __init__(self) -> None:
        self.repository = ImportRepository()
        self.worker_repository = WorkerRepository()
        self.prescription_repository = PrescriptionRepository()

    def upload(
        self,
        db: Session,
        file: UploadFile,
        uploaded_by: int | None = None,
        campaign_id: int | None = None,
        company_id: int | None = None,
    ) -> ImportJob:
        if not campaign_id:
            raise BadRequestException("campaign_id is required for worker imports")
        campaign = db.scalar(select(MedicalCampaign).where(MedicalCampaign.id == campaign_id))
        if not campaign:
            raise NotFoundException("Campaign not found")
        validate_import_filename(file.filename or "")
        directory = ensure_directory("uploads/imports")
        suffix = Path(file.filename or "upload.csv").suffix.lower()
        saved_name = f"{int(datetime.now(timezone.utc).timestamp())}_{file.filename}"
        file_path = directory / saved_name
        file_bytes = file.file.read()
        if not file_bytes:
            raise BadRequestException("Le fichier importé est vide.")
        file_path.write_bytes(file_bytes)
        rows = self._read_uploaded_rows(file_path, suffix)
        if not rows:
            raise BadRequestException("Le fichier importé ne contient aucune ligne de données.")
        job = ImportJob(
            company_id=campaign.company_id or company_id,
            campaign_id=campaign.id,
            file_name=saved_name,
            original_file_name=file.filename or saved_name,
            file_type=suffix.replace(".", ""),
            file_size=len(file_bytes),
            status="uploaded",
            total_rows=len(rows),
            uploaded_by=uploaded_by,
        )
        job = self.repository.create_job(db, job)
        import_rows = [
            ImportRow(
                import_job_id=job.id,
                row_number=index,
                raw_data_json=make_json_serializable(row),
                validation_status="pending",
            )
            for index, row in enumerate(rows, start=1)
        ]
        if import_rows:
            self.repository.save_rows(db, import_rows)
        return job

    def _read_uploaded_rows(self, file_path: Path, suffix: str) -> list[dict]:
        if suffix == ".xls":
            raise BadRequestException(
                "Le format .xls n'est pas pris en charge pour l'import. Enregistrez le fichier en .xlsx ou .csv puis réessayez."
            )
        try:
            if suffix == ".xlsx":
                return read_excel_rows(str(file_path))
            return read_csv_rows(str(file_path))
        except BadRequestException:
            raise
        except Exception as exc:
            raise BadRequestException(
                "Impossible de lire ce fichier d'import. Vérifiez le format, l'encodage et la ligne d'en-tête du fichier."
            ) from exc

    def preview(self, db: Session, import_job_id: int) -> list[ImportRow]:
        job = self.repository.get_job(db, import_job_id)
        if not job:
            raise NotFoundException("Import job not found")
        return self.repository.get_rows(db, import_job_id)

    def map_fields(self, db: Session, import_job_id: int, mapping: dict[str, str]) -> ImportJob:
        job = self._get_job(db, import_job_id)
        rows = self.repository.get_rows(db, import_job_id)
        first_row = rows[0].raw_data_json if rows else {}
        available_columns = set(first_row.keys())
        selected_targets = [target for target in mapping.values() if target and "[]" not in target]
        if len(selected_targets) != len(set(selected_targets)):
            raise BadRequestException("Each scalar import field can only be mapped once.")
        invalid_columns = [column for column in mapping.keys() if column not in available_columns]
        if invalid_columns:
            raise BadRequestException(f"Unknown Excel columns in mapping: {', '.join(invalid_columns)}")
        job.mapping_json = make_json_serializable(mapping)
        job.status = "mapped"
        return self.repository.update_job(db, job)

    def validate(self, db: Session, import_job_id: int) -> ImportJob:
        job = self._get_job(db, import_job_id)
        rows = self.repository.get_rows(db, import_job_id)
        mapping = job.mapping_json or {}
        duplicate_indexes = set(
            detect_duplicates([self._duplicate_signature(self._build_import_payload(row.raw_data_json, mapping)) for row in rows])
        )
        valid = invalid = duplicates = 0
        errors: dict[int, list[str]] = {}
        selected_targets = [target for target in mapping.values() if target and "[]" not in target]
        if len(selected_targets) != len(set(selected_targets)):
            raise BadRequestException("Each scalar import field can only be mapped once.")
        for row in rows:
            parsed = self._build_import_payload(row.raw_data_json, mapping)
            row_errors = list(parsed["errors"])
            worker_payload = parsed["worker"]
            for field in self.required_worker_fields:
                if not parsed["medical_file_data"].get(field):
                    row_errors.append(f"{field} is required")
            if not any(parsed["medical_file_data"].get(field) for field in self.identity_alternates):
                row_errors.append("employeeCode or medicalFileNumber is required")
            if row.row_number in duplicate_indexes:
                row_errors.append("Duplicate row detected")
                duplicates += 1
            if worker_payload.get("national_id") and self.worker_repository.get_by_national_id(db, str(worker_payload["national_id"])):
                row_errors.append("Duplicate nationalId found in database")
            existing_duplicate = self.worker_repository.find_duplicate(db, worker_payload)
            if existing_duplicate and not any(message.startswith("Duplicate nationalId") for message in row_errors):
                row_errors.append("Duplicate worker found in database")
            row.validation_status = "valid" if not row_errors else "invalid"
            row.errors_json = make_json_serializable({"errors": row_errors}) if row_errors else None
            if row_errors:
                invalid += 1
                errors[row.row_number] = row_errors
            else:
                valid += 1
        job.valid_rows = valid
        job.invalid_rows = invalid
        job.duplicate_rows = duplicates
        job.errors_json = make_json_serializable({"rows": errors})
        job.status = "validated"
        self.repository.update_rows(db, rows)
        return self.repository.update_job(db, job)

    def confirm(
        self,
        db: Session,
        import_job_id: int,
        campaign_id: int | None = None,
        current_user: User | None = None,
    ) -> ImportJob:
        # This legacy batch commits worker rows before visit CAS/revision checks.
        # Keep upload/preview/validation available while confirmation is redesigned.
        from app.services.sync_safety import suspend_for_data_safety
        suspend_for_data_safety("legacy_import_confirm")
        job = self._get_job(db, import_job_id)
        rows = self.repository.get_rows(db, import_job_id)
        mapping = job.mapping_json or {}
        effective_campaign_id = job.campaign_id or campaign_id
        if not effective_campaign_id:
            raise BadRequestException("This import job is not linked to a campaign")
        campaign = db.scalar(select(MedicalCampaign).where(MedicalCampaign.id == effective_campaign_id))
        if not campaign:
            raise NotFoundException("Campaign not found")
        if job.campaign_id != campaign.id:
            job.campaign_id = campaign.id
            job.company_id = campaign.company_id

        existing_assignment_worker_ids = {
            item.worker_id
            for item in db.scalars(select(CampaignWorker).where(CampaignWorker.campaign_id == campaign.id)).all()
        }

        for row in rows:
            parsed = self._build_import_payload(row.raw_data_json, mapping)
            row_errors = (row.errors_json or {}).get("errors", []) if row.errors_json else []
            duplicate_only_error = len(row_errors) == 1 and row_errors[0] == "Duplicate worker found in database"
            if row.validation_status != "valid" and not duplicate_only_error and not row.matched_worker_id:
                continue

            worker = self._upsert_worker(db, campaign, parsed["worker"], parsed["medical_file_data"], row.matched_worker_id)
            if worker.id not in existing_assignment_worker_ids:
                db.add(
                    CampaignWorker(
                        campaign_id=campaign.id,
                        worker_id=worker.id,
                        added_by=job.uploaded_by,
                        status="pending",
                    )
                )
                existing_assignment_worker_ids.add(worker.id)
            db.commit()
            db.refresh(worker)

            if parsed["has_visit_data"] and current_user:
                visit = self._upsert_visit(db, campaign, worker, parsed, current_user)
                if visit and parsed["prescription"] and current_user:
                    self._upsert_prescription(db, campaign, worker, parsed["prescription"], current_user)

            row.matched_worker_id = worker.id
            row.validation_status = "valid"
            row.errors_json = None

        db.commit()
        self.repository.update_rows(db, rows)
        job.status = "confirmed"
        job.imported_at = datetime.now(timezone.utc)
        return self.repository.update_job(db, job)

    def history(self, db: Session) -> list[ImportJob]:
        return self.repository.list_jobs(db)

    def _get_job(self, db: Session, import_job_id: int) -> ImportJob:
        job = self.repository.get_job(db, import_job_id)
        if not job:
            raise NotFoundException("Import job not found")
        return job

    def _duplicate_signature(self, payload: dict) -> dict:
        worker = payload["worker"]
        return {
            "employee_number": worker.get("employee_number"),
            "national_id": worker.get("national_id"),
            "first_name": worker.get("first_name"),
            "last_name": worker.get("last_name"),
            "birth_date": worker.get("birth_date"),
        }

    def _build_import_payload(self, raw_row: dict, mapping: dict[str, str]) -> dict:
        payload = {
            "medical_file_data": {},
            "visit": {
                "internalVisit": {},
                "clinicalExam": {},
                "complementaryExams": {},
                "medicalDecision": {},
                "profilTaGlycemie": {},
                "aptitudeCertificate": {},
                "orientationCertificates": [],
                "workStoppageCertificate": None,
                "ordonnances": [],
                "validation": {},
                "auditTrail": [],
                "dynamicMedicalTests": {},
            },
            "prescription": {},
            "errors": [],
        }

        for source_key, target_key in mapping.items():
            if not target_key:
                continue
            value = raw_row.get(source_key)
            canonical = self.legacy_field_aliases.get(target_key, target_key)
            coerced, error = self._coerce_value(canonical, value)
            if error:
                payload["errors"].append(f"{canonical}: {error}")
                continue
            if coerced is None:
                continue
            source_index = self._extract_index_from_header(source_key)
            self._assign_payload_value(payload, canonical, coerced, source_index)

        payload["visit"]["validation"] = payload["visit"]["medicalDecision"].get("validation", {}) if isinstance(
            payload["visit"]["medicalDecision"].get("validation"), dict
        ) else {}
        payload["worker"] = self._build_worker_payload(payload["medical_file_data"])
        payload["has_visit_data"] = self._has_visit_content(payload["visit"])
        return payload

    def _assign_payload_value(self, payload: dict, path: str, value: object, source_index: int | None) -> None:
        if path in self.legacy_field_aliases:
            path = self.legacy_field_aliases[path]

        if path.startswith("aptitudeCertificate."):
            suffix = path.split(".", 1)[1]
            mapped_suffix = {
                "issueDate": "aptitudeDate",
                "validatedDoctorName": "validatorName",
                "validatorSignatureUrl": "validatorSignatureImagePath",
            }.get(suffix, suffix)
            self._set_nested_value(payload["visit"]["aptitudeCertificate"], mapped_suffix, value, source_index)
            return

        if path.startswith("orientationCertificate."):
            if not payload["visit"]["orientationCertificates"]:
                payload["visit"]["orientationCertificates"].append({})
            orientation_entry = payload["visit"]["orientationCertificates"][0]
            suffix = path.split(".", 1)[1]
            mapped_suffix = {
                "orientation_number": "orientationNumber",
                "orientation_date": "orientationDate",
                "doctor_name": "prescribingDoctor",
                "orientation_details": "orientationDetails",
                "validatorSignatureUrl": "validatorSignatureImagePath",
            }.get(suffix, suffix)
            self._set_nested_value(orientation_entry, mapped_suffix, value, source_index)
            if suffix.startswith("orientationTypes."):
                orientation_flags = orientation_entry.get("orientationTypes", {})
                orientation_entry["orientation_type"] = self._derive_orientation_type(orientation_flags)
            return

        if path.startswith("prescription."):
            suffix = path.split(".", 1)[1]
            self._set_nested_value(payload["prescription"], suffix, value, source_index)
            if not payload["visit"]["ordonnances"]:
                payload["visit"]["ordonnances"].append({})
            self._set_nested_value(payload["visit"]["ordonnances"][0], suffix, value, source_index)
            return

        if path.startswith("workStoppageCertificate."):
            if payload["visit"]["workStoppageCertificate"] is None:
                payload["visit"]["workStoppageCertificate"] = {}
            suffix = path.split(".", 1)[1]
            self._set_nested_value(payload["visit"]["workStoppageCertificate"], suffix, value, source_index)
            return

        visit_prefixes = (
            "clinicalExam.",
            "complementaryExams.",
            "profilTaGlycemie.",
            "medicalDecision.",
        )
        if path in {
            "internalVisitHire",
            "internalVisitPeriodic",
            "internalVisitDate",
            "internalVisitDoctor",
            "internalVisitWeightKg",
            "internalVisitHeightCm",
            "internalVisitTa",
            "internalVisitFc",
            "internalVisitDistanceOdSc",
            "internalVisitDistanceOdAc",
            "internalVisitDistanceOgSc",
            "internalVisitDistanceOgAc",
            "internalVisitDistanceOdg",
        }:
            mapping = {
                "internalVisitHire": "hire",
                "internalVisitPeriodic": "periodic",
                "internalVisitDate": "date",
                "internalVisitDoctor": "doctor",
                "internalVisitWeightKg": "weightKg",
                "internalVisitHeightCm": "heightCm",
                "internalVisitTa": "ta",
                "internalVisitFc": "fc",
                "internalVisitDistanceOdSc": "distanceOdSc",
                "internalVisitDistanceOdAc": "distanceOdAc",
                "internalVisitDistanceOgSc": "distanceOgSc",
                "internalVisitDistanceOgAc": "distanceOgAc",
                "internalVisitDistanceOdg": "distanceOdg",
            }
            payload["visit"]["internalVisit"][mapping[path]] = value
            return

        if path.startswith(visit_prefixes):
            self._set_nested_value(payload["visit"], path, value, source_index)
            return

        self._set_nested_value(payload["medical_file_data"], path, value, source_index)

    def _build_worker_payload(self, medical_file_data: dict) -> dict:
        birth_date = self._coerce_model_date(medical_file_data.get("dateOfBirth"))
        return {
            "employee_number": self._coerce_text(medical_file_data.get("employeeCode") or medical_file_data.get("medicalFileNumber")),
            "national_id": self._coerce_text(medical_file_data.get("nationalId")),
            "first_name": self._coerce_text(medical_file_data.get("firstName")),
            "last_name": self._coerce_text(medical_file_data.get("lastName")),
            "gender": self._coerce_gender(medical_file_data.get("sex")),
            "birth_date": birth_date,
            "birth_wilaya": self._coerce_text(medical_file_data.get("birthPlace")),
            "marital_status": self._coerce_text(medical_file_data.get("familySituation")),
            "blood_group": self._coerce_text(medical_file_data.get("bloodGroup")),
            "phone": self._coerce_text(medical_file_data.get("phone")),
            "address": self._coerce_text(medical_file_data.get("originAddress") or medical_file_data.get("professionalAddress")),
            "job_title": self._coerce_text(medical_file_data.get("position")),
            "department": self._coerce_text(medical_file_data.get("department")),
            "etat_actual": self._coerce_text(medical_file_data.get("etat_actual")) or "present",
        }

    def _upsert_worker(
        self,
        db: Session,
        campaign: MedicalCampaign,
        worker_payload: dict,
        medical_file_data: dict,
        matched_worker_id: int | None,
    ) -> Worker:
        worker = self.worker_repository.get(db, matched_worker_id) if matched_worker_id else None
        if worker is None:
            worker = self.worker_repository.find_duplicate(db, worker_payload)

        if worker is None:
            worker = Worker(
                company_id=campaign.company_id,
                branch_id=campaign.branch_id,
                drilling_site_id=campaign.drilling_site_id,
                employee_number=worker_payload.get("employee_number") or "",
                national_id=worker_payload.get("national_id"),
                first_name=worker_payload.get("first_name") or "",
                last_name=worker_payload.get("last_name") or "",
                gender=worker_payload.get("gender"),
                birth_date=worker_payload.get("birth_date"),
                birth_wilaya=worker_payload.get("birth_wilaya"),
                marital_status=worker_payload.get("marital_status"),
                blood_group=worker_payload.get("blood_group"),
                phone=worker_payload.get("phone"),
                address=worker_payload.get("address"),
                job_title=worker_payload.get("job_title"),
                department=worker_payload.get("department"),
                etat_actual=worker_payload.get("etat_actual") or "present",
                medical_file_data=medical_file_data or None,
            )
            db.add(worker)
            db.flush()
            return worker

        worker.company_id = campaign.company_id
        worker.branch_id = campaign.branch_id
        worker.drilling_site_id = campaign.drilling_site_id
        worker.employee_number = worker_payload.get("employee_number") or worker.employee_number
        worker.national_id = worker_payload.get("national_id") or worker.national_id
        worker.first_name = worker_payload.get("first_name") or worker.first_name
        worker.last_name = worker_payload.get("last_name") or worker.last_name
        worker.gender = worker_payload.get("gender") or worker.gender
        worker.birth_date = worker_payload.get("birth_date") or worker.birth_date
        worker.birth_wilaya = worker_payload.get("birth_wilaya") or worker.birth_wilaya
        worker.marital_status = worker_payload.get("marital_status") or worker.marital_status
        worker.blood_group = worker_payload.get("blood_group") or worker.blood_group
        worker.phone = worker_payload.get("phone") or worker.phone
        worker.address = worker_payload.get("address") or worker.address
        worker.job_title = worker_payload.get("job_title") or worker.job_title
        worker.department = worker_payload.get("department") or worker.department
        worker.etat_actual = worker_payload.get("etat_actual") or worker.etat_actual
        worker.medical_file_data = {**(worker.medical_file_data or {}), **medical_file_data}
        db.add(worker)
        db.flush()
        return worker

    def _upsert_visit(
        self,
        db: Session,
        campaign: MedicalCampaign,
        worker: Worker,
        parsed: dict,
        current_user: User,
    ) -> MedicalVisit | None:
        from app.services.sync_safety import suspend_for_data_safety
        suspend_for_data_safety("legacy_import_visit_upsert")
        visit_date = (
            parsed["visit"]["internalVisit"].get("date")
            or parsed["visit"]["aptitudeCertificate"].get("visitDate")
            or parsed["visit"]["orientationCertificates"][0].get("orientationDate")
            if parsed["visit"]["orientationCertificates"]
            else None
        ) or date.today().isoformat()
        form_data = make_json_serializable({
            "workerSnapshot": {
                **parsed["medical_file_data"],
                "firstName": parsed["medical_file_data"].get("firstName"),
                "lastName": parsed["medical_file_data"].get("lastName"),
                "dateOfBirth": parsed["medical_file_data"].get("dateOfBirth"),
                "birthPlace": parsed["medical_file_data"].get("birthPlace"),
                "bloodGroup": parsed["medical_file_data"].get("bloodGroup"),
                "position": parsed["medical_file_data"].get("position"),
            },
            "visitData": parsed["visit"],
        })

        existing_visit = db.scalar(
            select(MedicalVisit).where(
                MedicalVisit.deleted_at.is_(None),
                MedicalVisit.worker_id == worker.id,
                MedicalVisit.campaign_id == campaign.id,
                MedicalVisit.visit_date == visit_date,
            )
        )

        service = MedicalVisitService()
        if existing_visit is None:
            created = service.create(
                db,
                MedicalVisitCreate(
                    worker_id=worker.id,
                    campaign_id=campaign.id,
                    visit_date=visit_date,
                    site_name=campaign.drilling_site.name if getattr(campaign, "drilling_site", None) else None,
                    status="draft",
                    form_data=form_data,
                ),
                current_user,
            )
            return db.scalar(select(MedicalVisit).where(MedicalVisit.id == created.id))

        updated = service.update(
            db,
            existing_visit.id,
            MedicalVisitUpdate(
                visit_date=visit_date,
                status=existing_visit.status or "draft",
                form_data=form_data,
            ),
            current_user,
        )
        return db.scalar(select(MedicalVisit).where(MedicalVisit.id == updated.id))

    def _upsert_prescription(
        self,
        db: Session,
        campaign: MedicalCampaign,
        worker: Worker,
        prescription_data: dict,
        current_user: User,
    ) -> Prescription | None:
        if not prescription_data:
            return None

        items = [
            PrescriptionItemCreate(
                medication_name=str(item.get("medication_name") or "").strip(),
                dosage=self._coerce_text(item.get("dosage")),
                frequency=self._coerce_text(item.get("frequency")),
                duration=self._coerce_text(item.get("duration")),
                quantity=self._coerce_text(item.get("quantity")),
                instructions=self._coerce_text(item.get("instructions")),
            )
            for item in prescription_data.get("items", [])
            if self._coerce_text(item.get("medication_name"))
        ]

        prescription_number = self._coerce_text(prescription_data.get("prescription_number"))
        existing = None
        if prescription_number:
            existing = next(
                (
                    item
                    for item in self.prescription_repository.list(db, worker_id=worker.id, campaign_id=campaign.id)
                    if item.prescription_number == prescription_number
                ),
                None,
            )

        service = PrescriptionService()
        prescription_date = self._coerce_model_date(prescription_data.get("prescription_date")) or date.today()
        if existing is None:
            created = service.create_prescription(
                db,
                PrescriptionCreate(
                    worker_id=worker.id,
                    campaign_id=campaign.id,
                    prescription_number=prescription_number,
                    prescription_date=prescription_date,
                    diagnosis=self._coerce_text(prescription_data.get("diagnosis")),
                    notes=self._coerce_text(prescription_data.get("notes")),
                    includeValidatorSignature=bool(prescription_data.get("includeValidatorSignature")),
                    status=self._coerce_text(prescription_data.get("status")) or "draft",
                    items=items,
                ),
                current_user,
            )
            return db.scalar(select(Prescription).where(Prescription.id == created.id))

        updated = service.update_prescription(
            db,
            existing.id,
            PrescriptionUpdate(
                prescription_number=prescription_number,
                prescription_date=prescription_date,
                diagnosis=self._coerce_text(prescription_data.get("diagnosis")),
                notes=self._coerce_text(prescription_data.get("notes")),
                includeValidatorSignature=bool(prescription_data.get("includeValidatorSignature")),
                status=self._coerce_text(prescription_data.get("status")) or existing.status,
                items=items or None,
            ),
            current_user,
        )
        return db.scalar(select(Prescription).where(Prescription.id == updated.id))

    def _coerce_value(self, path: str, value: object) -> tuple[object | None, str | None]:
        if value in (None, ""):
            return None, None
        if path in self.boolean_fields:
            boolean_value = self._parse_boolean(value)
            if boolean_value is None:
                return None, "invalid boolean"
            return boolean_value, None
        if path in self.number_fields:
            try:
                return int(str(value).strip()), None
            except ValueError:
                return None, "invalid number"
        if path in self.date_fields:
            parsed = self._coerce_date_string(value)
            if parsed is None:
                return None, "invalid date"
            return parsed, None
        return self._coerce_text(value), None

    def _has_visit_content(self, visit_payload: dict) -> bool:
        return any(
            bool(visit_payload.get(key))
            for key in (
                "internalVisit",
                "clinicalExam",
                "complementaryExams",
                "medicalDecision",
                "profilTaGlycemie",
                "aptitudeCertificate",
                "orientationCertificates",
                "workStoppageCertificate",
                "ordonnances",
            )
        )

    def _set_nested_value(self, container: dict, path: str, value: object, source_index: int | None = None) -> None:
        tokens = []
        for segment in path.split("."):
            match = re.fullmatch(r"([^\[\]]+)(?:\[(\d*)\])?", segment)
            if not match:
                continue
            tokens.append((match.group(1), match.group(2)))
        current = container
        for index, (name, marker) in enumerate(tokens):
            is_last = index == len(tokens) - 1
            if marker is None:
                if is_last:
                    current[name] = value
                else:
                    current = current.setdefault(name, {})
                continue
            array = current.setdefault(name, [])
            item_index = source_index if source_index is not None else 0
            while len(array) <= item_index:
                array.append({})
            if is_last:
                array[item_index] = value
            else:
                if not isinstance(array[item_index], dict):
                    array[item_index] = {}
                current = array[item_index]

    def _extract_index_from_header(self, source_key: str) -> int | None:
        match = re.search(r"\[(\d+)\]", source_key)
        return int(match.group(1)) if match else None

    def _derive_orientation_type(self, flags: dict) -> str:
        if flags.get("specialistAdvice"):
            return "avis_specialise"
        if flags.get("diagnosticCare"):
            return "prise_en_charge_diagnostic"
        if flags.get("other"):
            return "autre"
        return ""

    def _coerce_text(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _coerce_date_string(self, value: object) -> str | None:
        parsed = self._coerce_model_date(value)
        return parsed.isoformat() if parsed else None

    def _coerce_model_date(self, value: object) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        text = str(value).strip()
        if not text:
            return None
        for parser in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(text[:10], parser).date()
            except ValueError:
                continue
        return None

    def _parse_boolean(self, value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "oui", "vrai"}:
            return True
        if normalized in {"0", "false", "no", "non", "faux"}:
            return False
        return None

    def _coerce_gender(self, value: object) -> str | None:
        text = self._coerce_text(value)
        if not text:
            return None
        normalized = text.lower()
        if normalized in {"m", "male", "homme", "masculin"}:
            return "Masculin"
        if normalized in {"f", "female", "femme", "feminin", "féminin"}:
            return "Feminin"
        return text

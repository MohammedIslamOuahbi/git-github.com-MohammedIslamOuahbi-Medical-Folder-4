from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.medicine import Medicine
from app.models.medicine_import import MedicineImport, MedicineImportError
from app.models.user import User
from app.repositories.medicine_import_repository import MedicineImportRepository
from app.repositories.medicine_repository import MedicineRepository
from app.schemas.medicine_import import (
    MedicineImportAnalysisRow,
    MedicineImportConfirmRequest,
    MedicineImportPreviewResponse,
)
from app.utils.helpers import ensure_directory


@dataclass
class InspectedSheet:
    sheet_name: str
    header_row_index: int | None
    headers: list[str]
    rows: list[list[Any]]


class MedicineImportService:
    allowed_extensions = {".xlsx", ".csv", ".json"}
    max_upload_size = 25 * 1024 * 1024
    required_mapping_targets = {"brand_name"}
    preview_sample_size = 30
    search_limit_default = 20
    search_limit_max = 50
    import_statuses = {
        "uploaded",
        "previewed",
        "processing",
        "completed",
        "completed_with_errors",
        "failed",
        "cancelled",
    }
    import_modes = {"preview", "merge", "replace"}
    text_null_tokens = {"", "-", "/", "N/A", "NA", "NON RENSEIGNE", "NON RENSEIGNÉ"}
    form_normalization = {
        "COMP": "Comprimé",
        "COMPRIME": "Comprimé",
        "COMPRIMÉ": "Comprimé",
        "CP": "Comprimé",
        "GELULE": "Gélule",
        "GÉLULE": "Gélule",
        "GEL": "Gélule",
        "SIROP": "Sirop",
        "SUSPENSION BUVABLE": "Suspension buvable",
    }
    column_aliases: dict[str, list[str]] = {
        "registration_number": [
            "N° ENREGISTREMENT",
            "N ENREGISTREMENT",
            "NUMERO ENREGISTREMENT",
            "N° D ENREGISTREMENT",
            "N° D'ENREGISTREMENT",
        ],
        "national_code": ["CODE", "CODE PRODUIT", "CODE NATIONAL", "N°", "NUMERO"],
        "international_nonproprietary_name": [
            "DENOMINATION COMMUNE INTERNATIONALE",
            "DCI",
            "DENOMINATION COMMUNE",
        ],
        "brand_name": ["NOM DE MARQUE", "DENOMINATION", "SPECIALITE", "SPÉCIALITÉ", "FULL NAME"],
        "full_name": ["DENOMINATION COMPLETE", "NOM COMPLET", "FULL NAME"],
        "pharmaceutical_form": ["FORME", "FORME PHARMACEUTIQUE"],
        "strength": ["DOSAGE", "TENEUR"],
        "packaging": ["CONDITIONNEMENT", "PRESENTATION", "PRÉSENTATION"],
        "list_category": ["LISTE", "LIST CATEGORY"],
        "p1": ["P1"],
        "p2": ["P2"],
        "observations": ["OBSERVATIONS", "OBSERVATION"],
        "laboratory": ["LABORATOIRE", "FABRICANT", "MANUFACTURER"],
        "registration_holder": [
            "DETENTEUR DE LA DECISION D ENREGISTREMENT",
            "DETENTEUR DE LA DECISION D'ENREGISTREMENT",
            "DETENTEUR DE DE",
            "DETENTEUR",
        ],
        "country": ["PAYS", "PAYS D ORIGINE", "PAYS D'ORIGINE"],
        "medicine_type": ["TYPE"],
        "status": ["STATUT", "STATUS"],
    }

    def __init__(self) -> None:
        self.import_repository = MedicineImportRepository()
        self.medicine_repository = MedicineRepository()

    def upload(
        self,
        db: Session,
        file: UploadFile,
        *,
        current_user: User,
        source_name: str,
        source_version: str | None,
        import_mode: str,
        notes: str | None,
    ) -> MedicineImport:
        self._ensure_catalog_manage_permission(current_user)
        suffix = Path(file.filename or "").suffix.lower()
        if suffix == ".xls":
            raise BadRequestException(
                "Le format .xls n'est pas pris en charge. Convertissez le fichier officiel en .xlsx puis réessayez."
            )
        if suffix not in self.allowed_extensions:
            raise BadRequestException("Format de fichier non pris en charge pour le catalogue des médicaments.")

        file_bytes = file.file.read()
        if not file_bytes:
            raise BadRequestException("Le fichier importé est vide.")
        if len(file_bytes) > self.max_upload_size:
            raise BadRequestException("Le fichier importé dépasse la taille maximale autorisée.")

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        existing = self.import_repository.get_by_hash(db, file_hash)

        directory = ensure_directory("uploads/medicine_imports")
        saved_name = f"{int(datetime.now(UTC).timestamp())}_{file.filename or 'catalogue'}"
        file_path = directory / saved_name
        file_path.write_bytes(file_bytes)

        item = MedicineImport(
            file_name=saved_name,
            original_file_name=file.filename or saved_name,
            file_hash=file_hash,
            source_name=source_name,
            source_version=source_version,
            import_mode=self._normalize_import_mode(import_mode),
            status="uploaded",
            started_by_user_id=current_user.id,
            started_at=datetime.now(UTC),
            notes=notes,
            summary_json={"duplicate_file_detected": bool(existing)},
        )
        return self.import_repository.create(db, item)

    def preview(
        self,
        db: Session,
        import_id: int,
        *,
        current_user: User,
        mapping_override: dict[str, str] | None = None,
    ) -> MedicineImportPreviewResponse:
        self._ensure_catalog_manage_permission(current_user)
        item = self._get_import(db, import_id)
        inspected = self._inspect_import_file(item)
        detected_sheet = next((sheet for sheet in inspected if sheet.header_row_index is not None), inspected[0] if inspected else None)
        detected_columns = detected_sheet.headers if detected_sheet else []
        selected_mapping = mapping_override or self._auto_map_headers(detected_columns)
        analysis = self._analyze_rows(db, item, detected_sheet, selected_mapping)

        item.mapping_json = selected_mapping
        item.status = "previewed"
        item.total_rows = analysis["total_rows"]
        item.valid_rows = analysis["valid_rows"]
        item.invalid_rows = analysis["invalid_rows"]
        item.duplicate_rows = analysis["duplicate_rows"]
        item.inserted_rows = analysis["potential_inserts"]
        item.updated_rows = analysis["potential_updates"]
        item.unchanged_rows = analysis["unchanged_rows"]
        item.skipped_rows = analysis["duplicate_rows"]
        item.summary_json = {
            "sheet_names": [sheet.sheet_name for sheet in inspected],
            "detected_header_row": detected_sheet.header_row_index if detected_sheet else None,
            "detected_columns": detected_columns,
            "warnings": analysis["warnings"],
        }
        self.import_repository.replace_errors(db, item.id, analysis["errors"])
        self.import_repository.update(db, item)

        return MedicineImportPreviewResponse(
            importId=item.id,
            status=item.status,
            sheetNames=[sheet.sheet_name for sheet in inspected],
            detectedSheet=detected_sheet.sheet_name if detected_sheet else None,
            detectedHeaderRow=detected_sheet.header_row_index if detected_sheet else None,
            detectedColumns=detected_columns,
            selectedMapping=selected_mapping,
            totalRows=analysis["total_rows"],
            validRows=analysis["valid_rows"],
            invalidRows=analysis["invalid_rows"],
            duplicateRows=analysis["duplicate_rows"],
            potentialInserts=analysis["potential_inserts"],
            potentialUpdates=analysis["potential_updates"],
            unchangedRows=analysis["unchanged_rows"],
            warnings=analysis["warnings"],
            sampleRows=analysis["sample_rows"],
            errors=analysis["error_reads"],
        )

    def confirm(
        self,
        db: Session,
        import_id: int,
        *,
        current_user: User,
        payload: MedicineImportConfirmRequest,
    ) -> MedicineImport:
        self._ensure_catalog_manage_permission(current_user)
        if payload.import_mode == "replace" and not self._is_super_admin(current_user):
            raise ForbiddenException("Seul un super administrateur peut remplacer complètement le catalogue.")

        item = self._get_import(db, import_id)
        duplicate_file_detected = bool((item.summary_json or {}).get("duplicate_file_detected"))
        if duplicate_file_detected and not payload.force_reimport:
            raise BadRequestException("Ce fichier a déjà été importé. Confirmez explicitement pour le réimporter.")

        preview = self.preview(db, import_id, current_user=current_user, mapping_override=payload.mapping)
        if not preview.selectedMapping or not self.required_mapping_targets.issubset(set(preview.selectedMapping.values())):
            raise BadRequestException("Le mapping doit contenir au minimum la colonne de nom de marque.")

        item = self._get_import(db, import_id)
        item.status = "processing"
        item.source_name = payload.source_name
        item.source_version = payload.source_version
        item.publication_date = payload.publication_date
        item.import_mode = self._normalize_import_mode(payload.import_mode)
        item.notes = payload.notes
        self.import_repository.update(db, item)

        inspected = self._inspect_import_file(item)
        detected_sheet = next((sheet for sheet in inspected if sheet.header_row_index is not None), inspected[0] if inspected else None)
        analysis = self._analyze_rows(db, item, detected_sheet, item.mapping_json or {})
        normalized_rows = analysis["normalized_rows"]

        try:
          existing = {
              medicine.stable_identity_key: medicine
              for medicine in self.medicine_repository.find_by_identity_keys(
                  db, [row["stable_identity_key"] for row in normalized_rows]
              )
          }

          inserted_rows = 0
          updated_rows = 0
          unchanged_rows = 0
          touched_keys: set[str] = set()

          for row in normalized_rows:
              touched_keys.add(row["stable_identity_key"])
              existing_item = existing.get(row["stable_identity_key"])
              if existing_item is None:
                  db.add(Medicine(**row))
                  inserted_rows += 1
                  continue

              changed = False
              for key, value in row.items():
                  if getattr(existing_item, key) != value:
                      setattr(existing_item, key, value)
                      changed = True
              if changed:
                  updated_rows += 1
              else:
                  unchanged_rows += 1
              db.add(existing_item)

          deactivated_rows = 0
          if item.import_mode == "replace":
              all_medicines = db.scalars(select(Medicine).where(Medicine.deleted_at.is_(None))).all()
              for medicine in all_medicines:
                  if medicine.stable_identity_key not in touched_keys and medicine.is_active:
                      medicine.is_active = False
                      db.add(medicine)
                      deactivated_rows += 1

          db.commit()
          item.status = "completed_with_errors" if analysis["invalid_rows"] > 0 else "completed"
          item.valid_rows = analysis["valid_rows"]
          item.invalid_rows = analysis["invalid_rows"]
          item.duplicate_rows = analysis["duplicate_rows"]
          item.inserted_rows = inserted_rows
          item.updated_rows = updated_rows
          item.unchanged_rows = unchanged_rows
          item.skipped_rows = analysis["duplicate_rows"]
          item.deactivated_rows = deactivated_rows
          item.completed_at = datetime.now(UTC)
          item.summary_json = {
              **(item.summary_json or {}),
              "detected_columns": preview.detectedColumns,
              "selected_mapping": preview.selectedMapping,
          }
          return self.import_repository.update(db, item)
        except Exception as exc:
          db.rollback()
          item.status = "failed"
          item.error_message = str(exc)
          item.completed_at = datetime.now(UTC)
          self.import_repository.update(db, item)
          raise

    def cancel(self, db: Session, import_id: int, *, current_user: User) -> MedicineImport:
        self._ensure_catalog_manage_permission(current_user)
        item = self._get_import(db, import_id)
        item.status = "cancelled"
        item.completed_at = datetime.now(UTC)
        return self.import_repository.update(db, item)

    def history(self, db: Session, *, current_user: User) -> list[MedicineImport]:
        self._ensure_catalog_manage_permission(current_user)
        return self.import_repository.list(db)

    def get(self, db: Session, import_id: int, *, current_user: User) -> MedicineImport:
        self._ensure_catalog_manage_permission(current_user)
        return self._get_import(db, import_id)

    def list_errors(self, db: Session, import_id: int, *, current_user: User) -> list[MedicineImportError]:
        self._ensure_catalog_manage_permission(current_user)
        self._get_import(db, import_id)
        return self.import_repository.list_errors(db, import_id)

    def export_errors_csv(self, db: Session, import_id: int, *, current_user: User) -> bytes:
        errors = self.list_errors(db, import_id, current_user=current_user)
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["sheet_name", "row_number", "field_name", "raw_value", "error_code", "error_message"])
        for item in errors:
            writer.writerow(
                [
                    item.sheet_name or "",
                    item.row_number or "",
                    item.field_name or "",
                    self._safe_csv_value(item.raw_value),
                    item.error_code,
                    self._safe_csv_value(item.error_message),
                ]
            )
        return buffer.getvalue().encode("utf-8-sig")

    def _analyze_rows(
        self,
        db: Session,
        item: MedicineImport,
        sheet: InspectedSheet | None,
        selected_mapping: dict[str, str],
    ) -> dict[str, Any]:
        if sheet is None:
            raise BadRequestException("Impossible de détecter la feuille de données du fichier officiel.")
        missing_targets = self.required_mapping_targets - set(selected_mapping.values())
        if missing_targets:
            raise BadRequestException("Le mapping automatique ne contient pas toutes les colonnes minimales requises.")

        rows = sheet.rows[(sheet.header_row_index or 0) + 1 :]
        normalized_rows: list[dict[str, Any]] = []
        sample_rows: list[MedicineImportAnalysisRow] = []
        warnings: list[str] = []
        errors: list[MedicineImportError] = []
        seen_keys: set[str] = set()
        duplicate_rows = 0
        invalid_rows = 0

        existing_by_key = {
            medicine.stable_identity_key: medicine
            for medicine in self.medicine_repository.find_by_identity_keys(
                db,
                [self._build_stable_identity_key_from_raw(self._row_to_payload(sheet.headers, row), selected_mapping) for row in rows],
            )
        }
        potential_inserts = 0
        potential_updates = 0
        unchanged_rows = 0

        for row_offset, raw_row in enumerate(rows, start=(sheet.header_row_index or 0) + 2):
            raw_payload = self._row_to_payload(sheet.headers, raw_row)
            if all(self._normalize_text(value) is None for value in raw_payload.values()):
                continue

            normalized, row_errors = self._normalize_import_row(
                raw_payload,
                selected_mapping,
                source=item,
                sheet_name=sheet.sheet_name,
                row_number=row_offset,
            )
            if row_errors:
                invalid_rows += 1
                errors.extend(row_errors)
                continue

            stable_identity_key = normalized["stable_identity_key"]
            if stable_identity_key in seen_keys:
                duplicate_rows += 1
                errors.append(
                    MedicineImportError(
                        medicine_import_id=item.id,
                        sheet_name=sheet.sheet_name,
                        row_number=row_offset,
                        field_name="stable_identity_key",
                        raw_value=stable_identity_key,
                        error_code="DUPLICATE_ROW",
                        error_message="Ligne dupliquée dans le fichier importé.",
                        raw_row_json=raw_payload,
                    )
                )
                continue
            seen_keys.add(stable_identity_key)
            normalized_rows.append(normalized)

            existing = existing_by_key.get(stable_identity_key)
            if existing is None:
                potential_inserts += 1
            elif self._medicine_has_changes(existing, normalized):
                potential_updates += 1
            else:
                unchanged_rows += 1

            if len(sample_rows) < self.preview_sample_size:
                sample_rows.append(
                    MedicineImportAnalysisRow(
                        row_number=row_offset,
                        values={
                            "brand_name": normalized["brand_name"],
                            "international_nonproprietary_name": normalized.get("international_nonproprietary_name"),
                            "strength": normalized.get("strength"),
                            "pharmaceutical_form": normalized.get("pharmaceutical_form"),
                            "registration_number": normalized.get("registration_number"),
                            "national_code": normalized.get("national_code"),
                        },
                    )
                )

        valid_rows = len(normalized_rows)
        if not valid_rows:
            warnings.append("Aucune ligne valide n'a été détectée après normalisation.")

        error_reads = [
            error
            for error in (
                [
                    MedicineImportError(
                        medicine_import_id=item.id,
                        sheet_name=error.sheet_name,
                        row_number=error.row_number,
                        field_name=error.field_name,
                        raw_value=error.raw_value,
                        error_code=error.error_code,
                        error_message=error.error_message,
                        raw_row_json=error.raw_row_json,
                    )
                    for error in errors
                ]
            )
        ]

        return {
            "total_rows": len(rows),
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "duplicate_rows": duplicate_rows,
            "potential_inserts": potential_inserts,
            "potential_updates": potential_updates,
            "unchanged_rows": unchanged_rows,
            "warnings": warnings,
            "errors": errors,
            "error_reads": error_reads,
            "sample_rows": sample_rows,
            "normalized_rows": normalized_rows,
        }

    def _normalize_import_row(
        self,
        raw_row: dict[str, Any],
        selected_mapping: dict[str, str],
        *,
        source: MedicineImport,
        sheet_name: str,
        row_number: int,
    ) -> tuple[dict[str, Any], list[MedicineImportError]]:
        mapped_values: dict[str, Any] = {}
        errors: list[MedicineImportError] = []

        for header, target in selected_mapping.items():
            if not target:
                continue
            mapped_values[target] = raw_row.get(header)

        brand_name = self._normalize_display_text(mapped_values.get("brand_name"))
        generic_name = self._normalize_display_text(mapped_values.get("international_nonproprietary_name"))
        if not brand_name and not generic_name:
            errors.append(
                MedicineImportError(
                    medicine_import_id=source.id,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field_name="brand_name",
                    raw_value=str(mapped_values.get("brand_name") or ""),
                    error_code="MISSING_REQUIRED_VALUE",
                    error_message="Le nom de marque ou la DCI est requis.",
                    raw_row_json=raw_row,
                )
            )
            return {}, errors

        source_form = self._normalize_display_text(mapped_values.get("pharmaceutical_form"))
        normalized_form = self._normalize_form(source_form)
        strength = self._normalize_strength(mapped_values.get("strength"))
        packaging = self._normalize_display_text(mapped_values.get("packaging"))
        registration_number = self._normalize_display_text(mapped_values.get("registration_number"))
        national_code = self._normalize_display_text(mapped_values.get("national_code"))
        stable_identity_key = self._build_stable_identity_key(
            registration_number=registration_number,
            national_code=national_code,
            brand_name=brand_name or "",
            generic_name=generic_name,
            strength=strength,
            pharmaceutical_form=normalized_form,
            packaging=packaging,
            laboratory=self._normalize_display_text(mapped_values.get("laboratory")),
        )

        normalized_brand_name = self._normalize_search_text(brand_name)
        normalized_generic_name = self._normalize_search_text(generic_name)

        normalized = {
            "registration_number": registration_number,
            "national_code": national_code,
            "stable_identity_key": stable_identity_key,
            "international_nonproprietary_name": generic_name,
            "brand_name": brand_name or generic_name or "Sans nom",
            "full_name": self._normalize_display_text(mapped_values.get("full_name")) or brand_name or generic_name,
            "pharmaceutical_form": normalized_form,
            "source_pharmaceutical_form": source_form,
            "strength": strength,
            "packaging": packaging,
            "list_category": self._normalize_display_text(mapped_values.get("list_category")),
            "p1": self._normalize_display_text(mapped_values.get("p1")),
            "p2": self._normalize_display_text(mapped_values.get("p2")),
            "observations": self._normalize_display_text(mapped_values.get("observations")),
            "laboratory": self._normalize_display_text(mapped_values.get("laboratory")),
            "registration_holder": self._normalize_display_text(mapped_values.get("registration_holder")),
            "country": self._normalize_display_text(mapped_values.get("country")),
            "medicine_type": self._normalize_display_text(mapped_values.get("medicine_type")),
            "status": self._normalize_display_text(mapped_values.get("status")),
            "is_active": self._derive_active_status(mapped_values.get("status")),
            "is_prescribable": True,
            "source_name": source.source_name,
            "source_version": source.source_version,
            "source_file_name": source.original_file_name,
            "source_row_number": row_number,
            "source_import_id": source.id,
            "source_updated_at": source.publication_date or datetime.now(UTC),
            "normalized_brand_name": normalized_brand_name,
            "normalized_generic_name": normalized_generic_name,
            "search_text": " ".join(
                item
                for item in [
                    normalized_brand_name,
                    normalized_generic_name,
                    self._normalize_search_text(registration_number),
                    self._normalize_search_text(national_code),
                    self._normalize_search_text(packaging),
                    self._normalize_search_text(mapped_values.get("laboratory")),
                ]
                if item
            ),
            "sync_status": "synced",
            "local_id": None,
            "deleted_at": None,
        }
        return normalized, errors

    def _inspect_import_file(self, item: MedicineImport) -> list[InspectedSheet]:
        file_path = Path("uploads/medicine_imports") / item.file_name
        if not file_path.exists():
            raise NotFoundException("Fichier d'import introuvable sur le disque.")
        suffix = file_path.suffix.lower()
        if suffix == ".xlsx":
            workbook = load_workbook(filename=file_path, read_only=True, data_only=True)
            sheets: list[InspectedSheet] = []
            for sheet_name in workbook.sheetnames:
                worksheet = workbook[sheet_name]
                rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
                header_index = self._detect_header_row_index(rows)
                headers = self._extract_headers(rows, header_index)
                sheets.append(InspectedSheet(sheet_name=sheet_name, header_row_index=header_index, headers=headers, rows=rows))
            return sheets
        if suffix == ".csv":
            text = file_path.read_text(encoding="utf-8-sig")
            rows = list(csv.reader(StringIO(text)))
            header_index = self._detect_header_row_index(rows)
            headers = self._extract_headers(rows, header_index)
            return [InspectedSheet(sheet_name="CSV", header_row_index=header_index, headers=headers, rows=rows)]
        if suffix == ".json":
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list) or not payload:
                raise BadRequestException("Le fichier JSON doit contenir une liste d'objets.")
            headers = list(payload[0].keys())
            rows = [headers] + [[item.get(header) for header in headers] for item in payload if isinstance(item, dict)]
            return [InspectedSheet(sheet_name="JSON", header_row_index=0, headers=headers, rows=rows)]
        raise BadRequestException("Format de fichier non pris en charge.")

    def _detect_header_row_index(self, rows: list[list[Any]]) -> int | None:
        best_index: int | None = None
        best_score = -1
        for index, row in enumerate(rows[:25]):
            normalized_headers = [self._normalize_header(cell) for cell in row]
            row_score = sum(
                1
                for aliases in self.column_aliases.values()
                if any(normalized_header in {self._normalize_header(alias) for alias in aliases} for normalized_header in normalized_headers)
            )
            if row_score > best_score and len([header for header in normalized_headers if header]) >= 2:
                best_score = row_score
                best_index = index
        return best_index

    def _extract_headers(self, rows: list[list[Any]], header_index: int | None) -> list[str]:
        if header_index is None or header_index >= len(rows):
            return []
        return [self._normalize_source_header(cell) for cell in rows[header_index]]

    def _auto_map_headers(self, headers: list[str]) -> dict[str, str]:
        selected: dict[str, str] = {}
        normalized_headers = {header: self._normalize_header(header) for header in headers}
        for target, aliases in self.column_aliases.items():
            normalized_aliases = {self._normalize_header(alias) for alias in aliases}
            for header, normalized in normalized_headers.items():
                if normalized and normalized in normalized_aliases:
                    selected[header] = target
                    break
        return selected

    def _row_to_payload(self, headers: list[str], row: list[Any]) -> dict[str, Any]:
        return {headers[index]: row[index] if index < len(row) else None for index in range(len(headers))}

    def _normalize_header(self, value: Any) -> str:
        text = self._normalize_source_header(value)
        normalized = unicodedata.normalize("NFD", text)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        normalized = normalized.replace("’", "'").replace("`", "'")
        normalized = re.sub(r"\s+", " ", normalized.replace("\n", " ").replace("\r", " ")).strip().upper()
        return normalized

    def _normalize_source_header(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").replace("\n", " ").replace("\r", " ")).strip()

    def _normalize_display_text(self, value: Any) -> str | None:
        normalized = self._normalize_text(value)
        if normalized is None:
            return None
        return normalized

    def _normalize_text(self, value: Any) -> str | None:
        text = re.sub(r"\s+", " ", str(value or "").replace("\n", " ").replace("\r", " ")).strip()
        if not text:
            return None
        if self._normalize_header(text) in self.text_null_tokens:
            return None
        return text

    def _normalize_search_text(self, value: Any) -> str | None:
        text = self._normalize_text(value)
        if text is None:
            return None
        ascii_text = unicodedata.normalize("NFD", text)
        ascii_text = "".join(char for char in ascii_text if unicodedata.category(char) != "Mn")
        ascii_text = ascii_text.lower()
        ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()
        return ascii_text or None

    def _normalize_strength(self, value: Any) -> str | None:
        text = self._normalize_text(value)
        if text is None:
            return None
        text = re.sub(r"(?i)\bMG\b", "mg", text)
        text = re.sub(r"(?i)\bML\b", "ml", text)
        text = re.sub(r"(?i)\bG\b", "g", text)
        text = re.sub(r"\s*/\s*", "/", text)
        text = re.sub(r"(\d)([A-Za-z])", r"\1 \2", text)
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_form(self, value: str | None) -> str | None:
        if not value:
            return None
        key = self._normalize_search_text(value)
        if not key:
            return value
        upper_key = key.replace(" ", "").upper()
        return self.form_normalization.get(upper_key, value)

    def _derive_active_status(self, status_value: Any) -> bool:
        text = self._normalize_search_text(status_value)
        if not text:
            return True
        return text not in {"inactive", "retire", "retiree", "suspendu", "supprime"}

    def _build_stable_identity_key(
        self,
        *,
        registration_number: str | None,
        national_code: str | None,
        brand_name: str,
        generic_name: str | None,
        strength: str | None,
        pharmaceutical_form: str | None,
        packaging: str | None,
        laboratory: str | None,
    ) -> str:
        raw = "|".join(
            [
                self._normalize_search_text(registration_number) or "",
                self._normalize_search_text(national_code) or "",
                self._normalize_search_text(brand_name) or "",
                self._normalize_search_text(generic_name) or "",
                self._normalize_search_text(strength) or "",
                self._normalize_search_text(pharmaceutical_form) or "",
                self._normalize_search_text(packaging) or "",
                self._normalize_search_text(laboratory) or "",
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _build_stable_identity_key_from_raw(self, raw_row: dict[str, Any], selected_mapping: dict[str, str]) -> str:
        mapped: dict[str, Any] = {}
        for header, target in selected_mapping.items():
            mapped[target] = raw_row.get(header)
        return self._build_stable_identity_key(
            registration_number=self._normalize_display_text(mapped.get("registration_number")),
            national_code=self._normalize_display_text(mapped.get("national_code")),
            brand_name=self._normalize_display_text(mapped.get("brand_name")) or self._normalize_display_text(mapped.get("international_nonproprietary_name")) or "",
            generic_name=self._normalize_display_text(mapped.get("international_nonproprietary_name")),
            strength=self._normalize_strength(mapped.get("strength")),
            pharmaceutical_form=self._normalize_form(self._normalize_display_text(mapped.get("pharmaceutical_form"))),
            packaging=self._normalize_display_text(mapped.get("packaging")),
            laboratory=self._normalize_display_text(mapped.get("laboratory")),
        )

    def _medicine_has_changes(self, existing: Medicine, normalized: dict[str, Any]) -> bool:
        for key, value in normalized.items():
            if getattr(existing, key) != value:
                return True
        return False

    def _normalize_import_mode(self, value: str) -> str:
        normalized = (value or "preview").strip().lower()
        if normalized not in self.import_modes:
            raise BadRequestException("Mode d'import non pris en charge.")
        return normalized

    def _get_import(self, db: Session, import_id: int) -> MedicineImport:
        item = self.import_repository.get(db, import_id)
        if item is None:
            raise NotFoundException("Import de médicaments introuvable.")
        return item

    def _ensure_catalog_manage_permission(self, user: User) -> None:
        role = (user.role or "").strip().lower()
        if role not in {"super_admin", "admin"}:
            raise ForbiddenException("Vous n'êtes pas autorisé à gérer le catalogue des médicaments.")

    def _is_super_admin(self, user: User) -> bool:
        return (user.role or "").strip().lower() == "super_admin"

    def _safe_csv_value(self, value: str | None) -> str:
        text = value or ""
        if text[:1] in {"=", "+", "-", "@"}:
            return f"'{text}"
        return text

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase, TimestampSchema


class MedicineImportUploadResponse(ORMBase):
    id: int
    file_name: str
    original_file_name: str
    file_hash: str
    source_name: str
    source_version: str | None = None
    import_mode: str
    status: str
    total_rows: int
    valid_rows: int
    inserted_rows: int
    updated_rows: int
    unchanged_rows: int
    skipped_rows: int
    invalid_rows: int
    duplicate_rows: int
    deactivated_rows: int
    mapping_json: dict[str, str] | None = None
    summary_json: dict[str, Any] | None = None
    error_message: str | None = None
    notes: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MedicineImportPreviewRequest(BaseModel):
    mapping: dict[str, str] | None = None


class MedicineImportConfirmRequest(BaseModel):
    source_name: str
    source_version: str | None = None
    publication_date: datetime | None = None
    import_mode: str = "merge"
    notes: str | None = None
    mapping: dict[str, str] | None = None
    force_reimport: bool = False


class MedicineImportErrorRead(TimestampSchema):
    id: int
    medicine_import_id: int
    sheet_name: str | None = None
    row_number: int | None = None
    field_name: str | None = None
    raw_value: str | None = None
    error_code: str
    error_message: str
    raw_row_json: dict[str, Any] | None = None


class MedicineImportAnalysisRow(BaseModel):
    row_number: int | None = None
    values: dict[str, Any]


class MedicineImportPreviewResponse(BaseModel):
    importId: int
    status: str
    sheetNames: list[str]
    detectedSheet: str | None = None
    detectedHeaderRow: int | None = None
    detectedColumns: list[str]
    selectedMapping: dict[str, str]
    totalRows: int
    validRows: int
    invalidRows: int
    duplicateRows: int
    potentialInserts: int
    potentialUpdates: int
    unchangedRows: int
    warnings: list[str] = Field(default_factory=list)
    sampleRows: list[MedicineImportAnalysisRow] = Field(default_factory=list)
    errors: list[MedicineImportErrorRead] = Field(default_factory=list)


class MedicineImportHistoryItem(ORMBase):
    id: int
    source_name: str
    source_version: str | None = None
    original_file_name: str
    status: str
    inserted_rows: int
    updated_rows: int
    unchanged_rows: int
    invalid_rows: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class MedicineImportUploadMetadata(BaseModel):
    source_name: str = "Ministère de l’Industrie Pharmaceutique"
    source_version: str | None = None
    import_mode: str = "preview"
    notes: str | None = None

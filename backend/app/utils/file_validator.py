from __future__ import annotations

from pathlib import Path

from app.exceptions import BadRequestException

ALLOWED_IMPORT_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def validate_import_filename(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMPORT_EXTENSIONS:
        raise BadRequestException("Invalid file type", {"allowed": sorted(ALLOWED_IMPORT_EXTENSIONS)})

from __future__ import annotations

import argparse
from pathlib import Path

from starlette.datastructures import UploadFile

from app.database import SessionLocal
from app.models.user import User
from app.services.medicine_import_service import MedicineImportService
from app.schemas.medicine_import import MedicineImportConfirmRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Algerian medicines catalogue")
    parser.add_argument("--file", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--version", default=None)
    parser.add_argument("--mode", default="merge", choices=["preview", "merge", "replace"])
    parser.add_argument("--notes", default=None)
    parser.add_argument("--user-id", type=int, default=1)
    args = parser.parse_args()

    service = MedicineImportService()
    file_path = Path(args.file)
    with SessionLocal() as db:
        user = db.get(User, args.user_id)
        if user is None:
            raise SystemExit(f"User {args.user_id} not found")
        with file_path.open("rb") as stream:
            upload = UploadFile(filename=file_path.name, file=stream)
            item = service.upload(
                db,
                upload,
                current_user=user,
                source_name=args.source,
                source_version=args.version,
                import_mode="preview",
                notes=args.notes,
            )
        preview = service.preview(db, item.id, current_user=user)
        print(f"Preview: {preview.model_dump_json(indent=2)}")
        if args.mode != "preview":
            confirmed = service.confirm(
                db,
                item.id,
                current_user=user,
                payload=MedicineImportConfirmRequest(
                    source_name=args.source,
                    source_version=args.version,
                    import_mode=args.mode,
                    notes=args.notes,
                ),
            )
            print(f"Imported catalogue #{confirmed.id} with status {confirmed.status}")


if __name__ == "__main__":
    main()

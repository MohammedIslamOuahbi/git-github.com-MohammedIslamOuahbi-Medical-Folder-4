from __future__ import annotations

from pathlib import Path


class DocumentPdfStorage:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parents[2] / "generated_pdfs"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_path(self, category: str, document_id: int) -> Path:
        folder = self.base_dir / category
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{document_id}.pdf"

    def exists(self, category: str, document_id: int) -> bool:
        return self.get_path(category, document_id).exists()

    def read(self, category: str, document_id: int) -> bytes | None:
        path = self.get_path(category, document_id)
        return path.read_bytes() if path.exists() else None

    def write(self, category: str, document_id: int, data: bytes) -> Path:
        path = self.get_path(category, document_id)
        path.write_bytes(data)
        return path

    def delete(self, category: str, document_id: int) -> None:
        path = self.get_path(category, document_id)
        if path.exists():
            path.unlink()

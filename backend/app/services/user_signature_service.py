from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.user import User
from app.services.signature_authorization import can_validate_documents
from app.utils.helpers import ensure_directory

SIGNATURE_UPLOAD_FORBIDDEN_MESSAGE = "Only authorized validators can upload a signature."
SIGNATURE_REQUIRED_MESSAGE = "You must upload your PNG signature in settings before signing this document."
SIGNATURES_DIRECTORY = Path("uploads/signatures/users")
ALLOWED_SIGNATURE_CONTENT_TYPES = {"image/png", "image/x-png", "application/octet-stream"}
MAX_SIGNATURE_BYTES = 2 * 1024 * 1024


class UserSignatureService:
    def ensure_signature_owner(self, user: User | None) -> User:
        if user and can_validate_documents(user):
            return user
        raise ForbiddenException(SIGNATURE_UPLOAD_FORBIDDEN_MESSAGE)

    def upload_signature(self, current_user: User, file: UploadFile) -> dict[str, object]:
        user = self.ensure_signature_owner(current_user)
        filename = (file.filename or "").strip()
        if not filename.lower().endswith(".png"):
            raise BadRequestException("Only PNG signature files are allowed.")
        content_type = (file.content_type or "").strip().lower()
        if content_type and content_type not in ALLOWED_SIGNATURE_CONTENT_TYPES:
            raise BadRequestException("Only PNG signature files are allowed.")

        file_bytes = file.file.read()
        if not file_bytes:
            raise BadRequestException("The uploaded signature file is empty.")
        if len(file_bytes) > MAX_SIGNATURE_BYTES:
            raise BadRequestException("Signature file must be 2 MB or smaller.")
        if not self._is_png(file_bytes):
            raise BadRequestException("Only PNG signature files are allowed.")

        directory = ensure_directory(str(SIGNATURES_DIRECTORY / str(user.id)))
        file_path = directory / "signature.png"
        file_path.write_bytes(file_bytes)

        now = datetime.now(timezone.utc)
        relative_path = self._to_relative_storage_path(file_path)
        user.signature_path = relative_path
        user.signature_png = f"data:image/png;base64,{base64.b64encode(file_bytes).decode('ascii')}"
        user.signature_uploaded_at = user.signature_uploaded_at or now
        user.signature_updated_at = now

        return self.serialize_signature(user)

    def remove_signature(self, current_user: User) -> dict[str, object]:
        user = self.ensure_signature_owner(current_user)
        try:
            file_path = self.get_signature_file_path(user)
        except NotFoundException:
            file_path = None
        if file_path and file_path.exists():
            file_path.unlink(missing_ok=True)
        user.signature_path = None
        user.signature_png = None
        user.signature_uploaded_at = None
        user.signature_updated_at = datetime.now(timezone.utc)
        return self.serialize_signature(user)

    def get_signature_file_path(self, user: User) -> Path:
        relative_path = (user.signature_path or "").strip()
        if not relative_path:
            raise NotFoundException("Signature file not found")

        root = Path.cwd().resolve()
        candidate = (root / relative_path).resolve()
        signatures_root = (root / SIGNATURES_DIRECTORY).resolve()
        if signatures_root not in candidate.parents and candidate != signatures_root:
            raise NotFoundException("Signature file not found")
        if not candidate.exists() or not candidate.is_file():
            raise NotFoundException("Signature file not found")
        return candidate

    def serialize_signature(self, user: User) -> dict[str, object]:
        has_signature = self.has_uploaded_signature(user)
        signature_url = self.build_signature_url(user) if has_signature else None
        return {
            "hasSignature": has_signature,
            "signatureImageUrl": signature_url,
            "signatureUrl": signature_url,
            "signature_url": signature_url,
            "signaturePngUrl": signature_url,
            "signature_png_url": signature_url,
            "signaturePath": user.signature_path if has_signature else None,
            "signature_path": user.signature_path if has_signature else None,
            "signatureUploadedAt": user.signature_uploaded_at.isoformat() if user.signature_uploaded_at else None,
        }

    def build_signature_url(self, user: User) -> str | None:
        if not self.has_uploaded_signature(user):
            return None
        stamp = user.signature_updated_at or user.signature_uploaded_at or user.updated_at
        suffix = f"?v={int(stamp.timestamp())}" if stamp else ""
        return f"/api/v1/users/me/signature/file{suffix}"

    def has_uploaded_signature(self, user: User | None) -> bool:
        if not user:
            return False
        relative_path = (getattr(user, "signature_path", None) or "").strip()
        if not relative_path:
            return False
        try:
            file_path = self.get_signature_file_path(user)
        except NotFoundException:
            return False
        return file_path.exists()

    def require_uploaded_signature(self, user: User | None) -> str:
        owner = self.ensure_signature_owner(user)
        if not self.has_uploaded_signature(owner):
            raise BadRequestException(SIGNATURE_REQUIRED_MESSAGE)
        return (owner.signature_path or "").strip()

    def read_signature_bytes(self, relative_path: str | None) -> bytes | None:
        if not relative_path:
            return None
        root = Path.cwd().resolve()
        candidate = (root / relative_path).resolve()
        signatures_root = (root / SIGNATURES_DIRECTORY).resolve()
        if signatures_root not in candidate.parents and candidate != signatures_root:
            return None
        if not candidate.exists() or not candidate.is_file():
            return None
        return candidate.read_bytes()

    def _to_relative_storage_path(self, file_path: Path) -> str:
        return file_path.resolve().relative_to(Path.cwd().resolve()).as_posix()

    def _is_png(self, file_bytes: bytes) -> bool:
        return file_bytes.startswith(b"\x89PNG\r\n\x1a\n")

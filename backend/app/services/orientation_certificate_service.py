# services/orientation_certificate_service.py
# ─────────────────────────────────────────────────────────────
#  Orientation Certificate Service
# ─────────────────────────────────────────────────────────────

import datetime
from datetime import timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.models.medical_visit import MedicalVisit
from app.models.orientation_certificate import OrientationCertificate
from app.models.worker import Worker
from app.schemas.orientation_certificate import (
    OrientationCertificateCreate,
    OrientationCertificateListResponse,
    OrientationCertificateResponse,
    OrientationCertificateUpdate,
)
from passlib.context import CryptContext

from app.core.security import verify_password
from app.exceptions import ConflictException, NotFoundException
from app.models.user import User
from app.services.signature_authorization import (
    build_validator_metadata,
    ensure_can_sign_medical_documents,
    get_validator_display_name,
    normalize_validator_signature_dict,
    ensure_signature_payload_authorized,
)
from app.services.user_signature_service import UserSignatureService

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class OrientationCertificateService:
    def __init__(self, db: Session):
        self.db = db
        self.user_signature_service = UserSignatureService()

    # ── List with pagination ──
    def list(
        self,
        db: Session,
        params=None,
        *,
        worker_id: int | None = None,
        campaign_id: int | None = None,
        medical_visit_id: int | None = None,
    ):
        """List orientation certificates with pagination."""
        query = self.db.query(OrientationCertificate).filter(
            OrientationCertificate.deleted_at.is_(None)
        )
        
        if worker_id is not None:
            query = query.filter(OrientationCertificate.worker_id == worker_id)
        if campaign_id is not None:
            query = query.filter(OrientationCertificate.campaign_id == campaign_id)
        if medical_visit_id is not None:
            query = query.filter(OrientationCertificate.medical_visit_id == medical_visit_id)
        
        total = query.count()
        
        # Apply pagination
        page = getattr(params, 'page', 1)
        per_page = getattr(params, 'limit', 20)
        offset = (page - 1) * per_page
        
        items = query.order_by(desc(OrientationCertificate.created_at)).offset(offset).limit(per_page).all()
        serialized_items = [self.to_response(item) for item in items]
        
        total_pages = (total + per_page - 1) // per_page
        
        return OrientationCertificateListResponse(
            items=serialized_items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    # ── Get last ID ──
    def get_last_id(self, db: Session) -> int:
        """Get the last orientation certificate ID."""
        last = self.db.query(OrientationCertificate).order_by(
            desc(OrientationCertificate.id)
        ).first()
        return last.id if last else 0

    # ── Get by ID ──
    def get(self, certificate_id: int):
        return (
            self.db.query(OrientationCertificate)
            .filter(
                OrientationCertificate.id == certificate_id,
                OrientationCertificate.deleted_at.is_(None)
            )
            .first()
        )

    def get_or_404(self, certificate_id: int) -> OrientationCertificate:
        item = self.get(certificate_id)
        if not item:
            raise NotFoundException("Orientation certificate not found")
        return item

    # ── Create ──
    def create(self, data: OrientationCertificateCreate, current_user: User | None = None):
        """Create a new orientation certificate with unique orientation_number."""
        from datetime import datetime
        ensure_signature_payload_authorized(user=current_user, payload=data.model_dump())
        if data.includeValidatorSignature:
            self.user_signature_service.require_uploaded_signature(current_user)
        normalized_signature = normalize_validator_signature_dict(
            data.model_dump(),
            current_user=current_user,
        )
        
        # Auto-generate orientation_number if not provided
        if not data.orientation_number:
            data.orientation_number = self._generate_orientation_number(
                data.campaign_id, 
                data.orientation_date
            )
        
        # Ensure uniqueness - if the generated number exists, increment until unique
        while self._orientation_number_exists(data.orientation_number):
            data.orientation_number = self._increment_orientation_number(data.orientation_number)

        payload = data.model_dump()
        payload["orientation_types"] = self._normalize_orientation_types(
            payload.get("orientation_types"),
            payload.get("orientation_type"),
        )
        payload["include_workspace_signature"] = normalized_signature.get("includeValidatorSignature", False)
        payload["validator_id"] = normalized_signature.get("validatorId")
        payload["validator_name"] = normalized_signature.get("validatorName")
        payload["validator_role"] = normalized_signature.get("validatorRole")
        payload["validated_at"] = self._parse_datetime(normalized_signature.get("validatedAt"))
        payload["validator_signature_image_path"] = normalized_signature.get("validatorSignatureImagePath")
        payload.pop("includeValidatorSignature", None)
        print("Payload keys:", payload.keys())
        allowed_columns = {
            column.key
            for column in inspect(OrientationCertificate).mapper.column_attrs
        }
        print("Allowed columns:", allowed_columns)
        print("Unexpected:", set(payload.keys()) - allowed_columns)
        payload = {key: value for key, value in payload.items() if key in allowed_columns}
        db_obj = OrientationCertificate(**payload)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def _generate_orientation_number(self, campaign_id: int, orientation_date: str) -> str:
        """Generate a unique orientation number.
        
        Format: ORI-{campaign_id}-{YYYYMMDD}-{daily_count:03d}
        Similar to prescription format: ORD-{campaign_id}-{date}-{daily_count:03d}
        """
        from datetime import datetime
        
        # Parse date
        if isinstance(orientation_date, str):
            try:
                date_obj = datetime.strptime(orientation_date, "%Y-%m-%d").date()
            except ValueError:
                date_obj = datetime.now().date()
        else:
            date_obj = orientation_date or datetime.now().date()
        
        date_str = date_obj.strftime("%Y%m%d")
        
        # Count existing certificates for this campaign on this date
        daily_count = self._count_for_campaign_on_date(campaign_id, date_obj) + 1
        
        return f"ORI-{campaign_id}-{date_str}-{daily_count:03d}"

    def _count_for_campaign_on_date(self, campaign_id: int, orientation_date) -> int:
        """Count orientation certificates for a campaign on a specific date."""
        from datetime import date
        
        if isinstance(orientation_date, str):
            try:
                orientation_date = datetime.strptime(orientation_date, "%Y-%m-%d").date()
            except ValueError:
                orientation_date = date.today()
        
        return self.db.query(OrientationCertificate).filter(
            OrientationCertificate.campaign_id == campaign_id,
            OrientationCertificate.orientation_date == orientation_date.isoformat(),
            OrientationCertificate.deleted_at.is_(None)
        ).count()

    def _orientation_number_exists(self, orientation_number: str) -> bool:
        """Check if a certificate number already exists."""
        return self.db.query(OrientationCertificate).filter(
            OrientationCertificate.orientation_number == orientation_number,
            OrientationCertificate.deleted_at.is_(None)
        ).first() is not None

    def _increment_orientation_number(self, orientation_number: str) -> str:
        """Increment the counter in a certificate number.
        
        ORI-2-20250619-001 -> ORI-2-20250619-002
        """
        import re
        match = re.match(r"(ORI-\d+-\d{8}-)(\d{3})", orientation_number)
        if match:
            prefix = match.group(1)
            counter = int(match.group(2)) + 1
            return f"{prefix}{counter:03d}"
        # Fallback: append timestamp
        return f"{orientation_number}-{datetime.datetimenow().strftime('%H%M%S')}"

    # ── Update ──
    def update(self, certificate_id: int, data: OrientationCertificateUpdate, current_user: User | None = None):
        """Update an existing orientation certificate."""
        item = self.get_or_404(certificate_id)
        ensure_signature_payload_authorized(
            user=current_user,
            payload=data.model_dump(exclude_unset=True),
            existing_payload={
                "includeValidatorSignature": item.include_workspace_signature,
                "validatorId": item.validator_id,
                "validatorName": item.validator_name,
                "validatorRole": item.validator_role,
                "validatedAt": item.validated_at.isoformat() if item.validated_at else None,
            },
        )
        normalized_signature = normalize_validator_signature_dict(
            data.model_dump(exclude_unset=True),
            current_user=current_user if data.includeValidatorSignature is not None else None,
            existing_payload={
                "includeValidatorSignature": item.include_workspace_signature,
                "validatorId": item.validator_id,
                "validatorName": item.validator_name,
                "validatorRole": item.validator_role,
                "validatedAt": item.validated_at.isoformat() if item.validated_at else None,
            },
        )
        if data.includeValidatorSignature:
            self.user_signature_service.require_uploaded_signature(current_user)
        
        update_data = data.model_dump(exclude_unset=True)
        if "orientation_types" in update_data or "orientation_type" in update_data:
            update_data["orientation_types"] = self._normalize_orientation_types(
                update_data.get("orientation_types"),
                update_data.get("orientation_type") or item.orientation_type,
            )
        if "includeValidatorSignature" in update_data:
            update_data["include_workspace_signature"] = normalized_signature.get("includeValidatorSignature", False)
            update_data["validator_id"] = normalized_signature.get("validatorId")
            update_data["validator_name"] = normalized_signature.get("validatorName")
            update_data["validator_role"] = normalized_signature.get("validatorRole")
            update_data["validated_at"] = self._parse_datetime(normalized_signature.get("validatedAt"))
            update_data["validator_signature_image_path"] = normalized_signature.get("validatorSignatureImagePath")
            update_data.pop("includeValidatorSignature", None)
        for field, value in update_data.items():
            setattr(item, field, value)
        item.updated_at = self._now()
        
        self.db.commit()
        self.db.refresh(item)
        return item

    

    def delete(
        self,
        certificate_id: int,
        current_user: User,
        password: str,
    ) -> OrientationCertificate:
        item = (
            self.db.query(OrientationCertificate)
            .filter(
                OrientationCertificate.id == certificate_id,
                OrientationCertificate.deleted_at.is_(None),
            )
            .first()
        )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Orientation certificate not found",
            )

        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required to remove an orientation certificate",
            )

        if not verify_password(password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password. Orientation certificate was not removed.",
            )
        from datetime import datetime, timezone    

        item.deleted_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(item)

        return item

    # ── Sign ──
    def sign_orientation(self, certificate_id: int , current_user):
        """Sign an orientation certificate."""
        item = self.get_or_404(certificate_id)
        ensure_can_sign_medical_documents(current_user)
        self.user_signature_service.require_uploaded_signature(current_user)
        if item.status == "signed":
            if item.validator_id == current_user.id:
                return item
            raise ConflictException("This orientation has already been signed by another validator.")
        if item.medical_visit_id:
            medical_visit = self.db.get(MedicalVisit, item.medical_visit_id)
            if not medical_visit:
                raise NotFoundException("Linked medical visit not found")
            item.worker_id = medical_visit.worker_id
            item.campaign_id = medical_visit.campaign_id
        validator_metadata = build_validator_metadata(current_user) if current_user else {}
        item.doctor_id = current_user.id
        item.include_workspace_signature = True
        item.validator_id = validator_metadata.get("validatorId")
        item.validator_name = validator_metadata.get("validatorName")
        item.validator_role = validator_metadata.get("validatorRole")
        item.validated_at = self._parse_datetime(validator_metadata.get("validatedAt"))
        item.validator_signature_image_path = validator_metadata.get("validatorSignatureImagePath")
        item.status = "signed"
        item.updated_at = self._now()
        self.db.commit()
        self.db.refresh(item)
        return item

    def _normalize_orientation_types(
        self,
        orientation_types: Any,
        orientation_type: str | None,
    ) -> dict[str, bool]:
        source = orientation_types if isinstance(orientation_types, dict) else {}
        legacy = (orientation_type or "").strip().lower()
        return {
            "specialistAdvice": bool(
                source.get("specialistAdvice")
                if "specialistAdvice" in source
                else legacy in {"avis_specialise", "cardiologie", "ophtalmologie"}
            ),
            "diagnosticCare": bool(
                source.get("diagnosticCare")
                if "diagnosticCare" in source
                else legacy == "prise_en_charge_diagnostic"
            ),
            "other": bool(
                source.get("other")
                if "other" in source
                else legacy == "autre"
            ),
        }
     

    # ── Mark as printed ──
    def mark_printed(self, certificate_id: int):
        """Mark orientation certificate as printed."""
        item = self.get_or_404(certificate_id)
        item.status = "printed"
        item.updated_at = self._now()
        self.db.commit()
        self.db.refresh(item)
        return item

    def _parse_datetime(self, value: object) -> datetime.datetime | None:
        if not value:
            return None
        if isinstance(value, datetime.datetime):
            return value
        normalized = str(value).strip().replace("Z", "+00:00")
        if not normalized:
            return None
        return datetime.datetime.fromisoformat(normalized)

    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(timezone.utc)

    def _build_validator_signature_url(self, certificate: OrientationCertificate) -> str | None:
        if not certificate.validator_signature_image_path:
            return None
        return f"/api/v1/orientation-certificates/{certificate.id}/validator-signature"

    def to_response(self, certificate: OrientationCertificate) -> OrientationCertificateResponse:
        worker = self.db.get(Worker, certificate.worker_id) if certificate.worker_id else None
        worker_name = None
        if worker:
            worker_name = f"{worker.first_name} {worker.last_name}".strip() or None
        doctor_name = get_validator_display_name(
            {"validatorName": certificate.validator_name},
            fallback=certificate.doctor_name or "",
        ) or None
        validator_signature_url = self._build_validator_signature_url(certificate)

        return OrientationCertificateResponse(
            id=certificate.id,
            worker_id=certificate.worker_id,
            campaign_id=certificate.campaign_id,
            medical_visit_id=certificate.medical_visit_id,
            doctor_id=certificate.doctor_id,
            orientation_number=certificate.orientation_number,
            orientation_date=certificate.orientation_date,
            orientation_type=certificate.orientation_type,
            orientation_types=certificate.orientation_types,
            orientation_type_other=certificate.orientation_type_other,
            orientation_details=certificate.orientation_details,
            includeValidatorSignature=bool(certificate.include_workspace_signature),
            includeDoctorSignature=bool(certificate.include_workspace_signature),
            includeWorkspaceSignature=bool(certificate.include_workspace_signature),
            validatorId=certificate.validator_id,
            validatorName=certificate.validator_name,
            validator_name=certificate.validator_name,
            validatorRole=certificate.validator_role,
            validator_role=certificate.validator_role,
            validatedAt=certificate.validated_at,
            validated_at=certificate.validated_at,
            validatorSignatureImagePath=certificate.validator_signature_image_path,
            validator_signature_image_path=certificate.validator_signature_image_path,
            validatorSignatureUrl=validator_signature_url,
            validator_signature_url=validator_signature_url,
            status=certificate.status,
            worker_name=worker_name,
            doctor_name=doctor_name,
            created_at=certificate.created_at,
            updated_at=certificate.updated_at,
            deleted_at=certificate.deleted_at,
        )

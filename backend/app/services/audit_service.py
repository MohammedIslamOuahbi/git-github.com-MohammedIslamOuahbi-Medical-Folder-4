from __future__ import annotations

from sqlalchemy.orm import Session

from app.exceptions import NotFoundException
from app.models.audit_log import AuditLog
from app.models.medical_campaign import MedicalCampaign
from app.repositories.audit_repository import AuditRepository
from app.schemas.pagination import PaginationParams
from app.utils.pagination import build_paginated_response
from sqlalchemy import select


class AuditService:
    def __init__(self) -> None:
        self.repository = AuditRepository()

    def _stringify_details(self, details: dict | None) -> str | None:
        if not details:
            return None
        parts: list[str] = []
        for key, value in details.items():
            if value in (None, "", [], {}):
                continue
            label = str(key).replace("_", " ").strip()
            if isinstance(value, list):
                rendered = ", ".join(str(item) for item in value if item not in (None, ""))
            elif isinstance(value, dict):
                rendered = ", ".join(f"{nested_key}: {nested_value}" for nested_key, nested_value in value.items())
            else:
                rendered = str(value)
            if rendered:
                parts.append(f"{label}: {rendered}")
        return " | ".join(parts) if parts else None

    def _resolve_entity_name(self, db: Session, item: AuditLog, campaigns_by_id: dict[int, str]) -> str | None:
        if item.entity_type == "campaign" and item.entity_id:
            return campaigns_by_id.get(item.entity_id)

        details = item.details_json or {}
        for key in ("name", "title", "entity_name", "campaign_name", "worker_name", "user_name"):
            value = details.get(key)
            if value:
                return str(value)
        return None

    def _serialize(self, db: Session, item: AuditLog, campaigns_by_id: dict[int, str]) -> dict:
        actor_name = None
        actor_email = None
        actor_role = None
        if item.user:
            actor_name = f"{item.user.first_name} {item.user.last_name}".strip() or item.user.email
            actor_email = item.user.email
            actor_role = item.user.role

        details_summary = self._stringify_details(item.details_json)
        entity_name = self._resolve_entity_name(db, item, campaigns_by_id)

        return {
            "id": item.id,
            "action": item.action,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "actor_name": actor_name,
            "actor_email": actor_email,
            "actor_role": actor_role,
            "entity_name": entity_name,
            "description": details_summary or entity_name or item.entity_type,
            "details_summary": details_summary,
            "ip_address": item.ip_address,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def list(self, db: Session, params: PaginationParams):
        items, total = self.repository.list(db, params)
        campaigns_by_id = {
            item.id: item.title
            for item in db.scalars(select(MedicalCampaign).where(MedicalCampaign.deleted_at.is_(None))).all()
        }
        serialized = [self._serialize(db, item, campaigns_by_id) for item in items]
        return build_paginated_response(serialized, total, params)

    def get(self, db: Session, audit_log_id: int):
        item = self.repository.get(db, audit_log_id)
        if not item:
            raise NotFoundException("Audit log not found")
        campaigns_by_id = {
            campaign.id: campaign.title
            for campaign in db.scalars(select(MedicalCampaign).where(MedicalCampaign.deleted_at.is_(None))).all()
        }
        return self._serialize(db, item, campaigns_by_id)

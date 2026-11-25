from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import has_role, user_has_permission
from app.core.security import hash_password, verify_password
from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.medical_campaign import MedicalCampaign
from app.models.user import User
from app.models.workspace import Workspace
from app.models.local_revision import LocalWriteOperation
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate


class WorkspaceService:
    def __init__(self) -> None:
        self.repository = WorkspaceRepository()

    def _default_workspace_code(self, campaign_id: int) -> str:
        return f"WS-{campaign_id:05d}"

    def _build_default_workspace(self, campaign: MedicalCampaign) -> Workspace:
        workspace_code = self._default_workspace_code(campaign.id)
        return Workspace(
            name=f"{campaign.title} Workspace",
            campaign_id=campaign.id,
            company_id=campaign.company_id,
            branch_id=campaign.branch_id,
            drilling_site_id=campaign.drilling_site_id,
            workspace_code=workspace_code,
            workspace_password_hash=hash_password(workspace_code),
            start_date=campaign.start_date,
            end_date=campaign.end_date,
            status=campaign.status,
            is_locked=campaign.status == "completed",
            settings_json={},
            sync_status="synced",
            local_id=f"workspace_campaign_{campaign.id}",
        )

    def ensure_workspace_exists(self, db: Session, campaign_id: int, current_user: User | None = None) -> Workspace:
        workspace = self.repository.get_by_campaign_id(db, campaign_id)
        if workspace:
            return workspace

        campaign = db.scalar(
            select(MedicalCampaign).where(
                MedicalCampaign.id == campaign_id,
                MedicalCampaign.deleted_at.is_(None),
            )
        )
        if not campaign:
            raise NotFoundException("Campaign not found")

        if current_user is None:
            raise NotFoundException("Workspace is not provisioned for this campaign")
        workspace = self._build_default_workspace(campaign)
        workspace.uuid = uuid.uuid4()
        operation_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"workspace:{campaign.uuid}")
        request_hash = hashlib.sha256(f"workspace:{campaign.id}:{workspace.uuid}".encode()).hexdigest()
        db.add(LocalWriteOperation(operation_uuid=operation_uuid, actor_user_uuid=current_user.uuid,
            request_hash=request_hash, entity_type="workspaces", entity_uuid=workspace.uuid,
            result_payload={}, created_at=datetime.now(timezone.utc)))
        db.info["local_operation_uuid"] = operation_uuid
        db.info["stage3_write_contract"] = True
        db.flush()
        try:
            result = self.repository.create(db, workspace)
            db.execute(LocalWriteOperation.__table__.update().where(LocalWriteOperation.operation_uuid == operation_uuid).values(result_payload={"id": result.id, "uuid": str(result.uuid)}))
            db.commit()
            return result
        finally:
            db.info.pop("local_operation_uuid", None)
            db.info.pop("stage3_write_contract", None)

    def _serialize(self, workspace: Workspace) -> WorkspaceRead:
        campaign = workspace.campaign
        doctors = []
        assistants = []
        if campaign:
            doctors = [
                {
                    "id": assignment.doctor.id,
                    "first_name": assignment.doctor.first_name,
                    "last_name": assignment.doctor.last_name,
                    "email": assignment.doctor.email,
                }
                for assignment in campaign.doctor_assignments
                if assignment.doctor
            ]
            assistants = [
                {
                    "id": assignment.assistant.id,
                    "first_name": assignment.assistant.first_name,
                    "last_name": assignment.assistant.last_name,
                    "email": assignment.assistant.email,
                }
                for assignment in campaign.assistant_assignments
                if assignment.assistant
            ]

        return WorkspaceRead.model_validate(
            {
                **workspace.__dict__,
                "campaign_name": campaign.title if campaign else None,
                "company_name": workspace.company.name if workspace.company else None,
                "branch_name": workspace.branch.name if workspace.branch else None,
                "drilling_site_name": workspace.drilling_site.name if workspace.drilling_site else None,
                "assigned_doctors": doctors,
                "assigned_assistants": assistants,
            }
        )

    def list(self, db: Session) -> list[WorkspaceRead]:
        return [self._serialize(item) for item in self.repository.list(db)]

    def get_by_campaign_id(self, db: Session, campaign_id: int, current_user: User | None = None) -> Workspace:
        return self.ensure_workspace_exists(db, campaign_id, current_user)

    def get_workspace_read_by_campaign_id(self, db: Session, campaign_id: int, current_user: User | None = None) -> WorkspaceRead:
        return self._serialize(self.get_by_campaign_id(db, campaign_id, current_user))

    def create(self, db: Session, payload: WorkspaceCreate) -> WorkspaceRead:
        workspace = Workspace(
            **payload.model_dump(exclude={"workspace_password"}),
            workspace_password_hash=hash_password(payload.workspace_password),
        )
        return self._serialize(self.repository.create(db, workspace))

    def update(self, db: Session, campaign_id: int, payload: WorkspaceUpdate) -> WorkspaceRead:
        workspace = self.get_by_campaign_id(db, campaign_id)
        data = payload.model_dump(exclude_unset=True, exclude_none=True)
        if "workspace_password" in data:
            workspace.workspace_password_hash = hash_password(data.pop("workspace_password"))
        for key, value in data.items():
            setattr(workspace, key, value)
        workspace.updated_at = datetime.now(timezone.utc)
        return self._serialize(self.repository.update(db, workspace))

    def _is_assigned_to_workspace(self, workspace: Workspace, user: User) -> bool:
        if not workspace.campaign:
            return False
        if has_role(user, "doctor"):
            return any(assignment.doctor_id == user.id for assignment in workspace.campaign.doctor_assignments)
        if has_role(user, "assistant"):
            return any(assignment.assistant_id == user.id for assignment in workspace.campaign.assistant_assignments)
        return False

    def ensure_access(self, workspace: Workspace, user: User) -> None:
        if has_role(user, "super_admin"):
            return
        if user_has_permission(user, "workspaces:manage"):
            return
        if self._is_assigned_to_workspace(workspace, user):
            return
        raise ForbiddenException("You are not assigned to this workspace")

    def access(self, db: Session, campaign_id: int, user: User, access_code: str) -> WorkspaceRead:
        workspace = self.get_by_campaign_id(db, campaign_id)
        self.ensure_access(workspace, user)
        if workspace.is_locked and not has_role(user, "super_admin") and not user_has_permission(user, "campaigns:lock"):
            raise ForbiddenException("Workspace is locked")
        if not verify_password(access_code, workspace.workspace_password_hash):
            raise ForbiddenException("Invalid workspace access code")
        return self._serialize(workspace)

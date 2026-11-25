from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.assistant_campaign import AssistantCampaign
from app.models.doctor_campaign import DoctorCampaign
from app.models.medical_campaign import MedicalCampaign
from app.models.workspace import Workspace


class WorkspaceRepository:
    def _base_query(self):
        return (
            select(Workspace)
            .options(
                joinedload(Workspace.company),
                joinedload(Workspace.branch),
                joinedload(Workspace.drilling_site),
                joinedload(Workspace.campaign)
                .selectinload(MedicalCampaign.doctor_assignments)
                .joinedload(DoctorCampaign.doctor),
                joinedload(Workspace.campaign)
                .selectinload(MedicalCampaign.assistant_assignments)
                .joinedload(AssistantCampaign.assistant),
            )
        )

    def list(self, db: Session) -> list[Workspace]:
        return db.scalars(self._base_query().order_by(Workspace.start_date.desc())).unique().all()

    def get(self, db: Session, workspace_id: int) -> Workspace | None:
        return db.scalar(self._base_query().where(Workspace.id == workspace_id))

    def get_by_campaign_id(self, db: Session, campaign_id: int) -> Workspace | None:
        return db.scalar(self._base_query().where(Workspace.campaign_id == campaign_id))

    def create(self, db: Session, workspace: Workspace) -> Workspace:
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return self.get(db, workspace.id) or workspace

    def update(self, db: Session, workspace: Workspace) -> Workspace:
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return self.get(db, workspace.id) or workspace

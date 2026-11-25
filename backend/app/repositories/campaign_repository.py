from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.assistant_campaign import AssistantCampaign
from app.models.campaign_test import CampaignTest
from app.models.campaign_worker import CampaignWorker
from app.models.doctor_campaign import DoctorCampaign
from app.models.medical_campaign import MedicalCampaign
from app.models.user import User
from app.schemas.pagination import PaginationParams
from app.utils.filters import build_search_filter


class CampaignRepository:
    searchable_fields = ["title", "description", "status"]

    def list(self, db: Session, params: PaginationParams, current_user: User | None = None) -> tuple[list[MedicalCampaign], int]:
        query = select(MedicalCampaign).where(MedicalCampaign.deleted_at.is_(None))
        count_query = select(func.count(MedicalCampaign.id)).where(MedicalCampaign.deleted_at.is_(None))
        normalized_role = (current_user.role or "").strip().lower() if current_user else None
        if current_user and normalized_role == "doctor":
            query = query.join(DoctorCampaign, DoctorCampaign.campaign_id == MedicalCampaign.id).where(
                DoctorCampaign.doctor_id == current_user.id
            )
            count_query = (
                select(func.count(distinct(MedicalCampaign.id)))
                .select_from(MedicalCampaign)
                .join(DoctorCampaign, DoctorCampaign.campaign_id == MedicalCampaign.id)
                .where(MedicalCampaign.deleted_at.is_(None), DoctorCampaign.doctor_id == current_user.id)
            )
        elif current_user and normalized_role == "assistant":
            query = query.join(AssistantCampaign, AssistantCampaign.campaign_id == MedicalCampaign.id).where(
                AssistantCampaign.assistant_id == current_user.id
            )
            count_query = (
                select(func.count(distinct(MedicalCampaign.id)))
                .select_from(MedicalCampaign)
                .join(AssistantCampaign, AssistantCampaign.campaign_id == MedicalCampaign.id)
                .where(MedicalCampaign.deleted_at.is_(None), AssistantCampaign.assistant_id == current_user.id)
            )
        if params.search:
            search_filter = build_search_filter(MedicalCampaign, params.search, self.searchable_fields)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        sort_column = getattr(MedicalCampaign, params.sort_by or "id", MedicalCampaign.id)
        query = query.order_by(sort_column.asc() if params.sort_order == "asc" else sort_column.desc())
        return db.scalars(query.offset(params.offset).limit(params.limit)).unique().all(), db.scalar(count_query) or 0

    def get(self, db: Session, campaign_id: int) -> MedicalCampaign | None:
        return db.scalar(select(MedicalCampaign).where(MedicalCampaign.id == campaign_id, MedicalCampaign.deleted_at.is_(None)))

    def get_workers(self, db: Session, campaign_id: int) -> list[CampaignWorker]:
        return db.scalars(
            select(CampaignWorker)
            .where(CampaignWorker.campaign_id == campaign_id)
            .options(selectinload(CampaignWorker.worker))
        ).all()

    def get_tests(self, db: Session, campaign_id: int) -> list[CampaignTest]:
        return db.scalars(
            select(CampaignTest)
            .where(CampaignTest.campaign_id == campaign_id)
            .options(selectinload(CampaignTest.test))
        ).all()

    def get_doctors(self, db: Session, campaign_id: int) -> list[DoctorCampaign]:
        return db.scalars(
            select(DoctorCampaign)
            .where(DoctorCampaign.campaign_id == campaign_id)
            .options(selectinload(DoctorCampaign.doctor))
        ).all()

    def get_assistants(self, db: Session, campaign_id: int) -> list[AssistantCampaign]:
        return db.scalars(
            select(AssistantCampaign)
            .where(AssistantCampaign.campaign_id == campaign_id)
            .options(selectinload(AssistantCampaign.assistant))
        ).all()

    def create(self, db: Session, campaign: MedicalCampaign) -> MedicalCampaign:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    def update(self, db: Session, campaign: MedicalCampaign) -> MedicalCampaign:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

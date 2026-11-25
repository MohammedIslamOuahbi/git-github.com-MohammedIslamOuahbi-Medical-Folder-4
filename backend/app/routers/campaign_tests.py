from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session 

from app.database import get_db
from app.schemas.campaign_test import CampaignTestCreate, CampaignTestResponse
from app.services import campaign_test_service


router = APIRouter(
    prefix="/campaigns",
    tags=["Campaign Tests"],
)


@router.get("/{campaign_id}/tests", response_model=list[CampaignTestResponse])
def get_campaign_tests(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    return campaign_test_service.list_campaign_tests(db, campaign_id)


@router.post("/{campaign_id}/tests", response_model=list[CampaignTestResponse])
def create_campaign_tests(
    campaign_id: int,
    payload: list[CampaignTestCreate],
    db: Session = Depends(get_db),
):
    return campaign_test_service.add_campaign_tests(db, campaign_id, payload)


@router.put("/{campaign_id}/tests", response_model=list[CampaignTestResponse])
def update_campaign_tests(
    campaign_id: int,
    payload: list[CampaignTestCreate],
    db: Session = Depends(get_db),
):
    return campaign_test_service.replace_campaign_tests(db, campaign_id, payload)


@router.delete("/{campaign_id}/tests/{test_id}")
def delete_campaign_test(
    campaign_id: int,
    test_id: int,
    db: Session = Depends(get_db),
):
    return campaign_test_service.remove_campaign_test(db, campaign_id, test_id)
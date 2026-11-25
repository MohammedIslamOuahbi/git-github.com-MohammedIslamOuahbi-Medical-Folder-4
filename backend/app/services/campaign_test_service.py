from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.campaign_test import CampaignTest
from app.schemas.campaign_test import CampaignTestCreate
from app.repositories import campaign_test_repository


ALLOWED_TEST_IDS = set(range(1, 21))


def _campaign_exists(db: Session, campaign_id: int) -> CampaignTest:
    campaign = db.query(CampaignTest).filter(CampaignTest.id == campaign_id).first()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Campaign not found."},
        )

    return campaign


def _validate_tests(payload: list[CampaignTestCreate]) -> None:
    seen: set[int] = set()

    for item in payload:
        if item.test_id not in ALLOWED_TEST_IDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": f"Invalid test_id: {item.test_id}."},
            )

        if item.test_id in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": f"Duplicate test_id: {item.test_id}."},
            )

        seen.add(item.test_id)


def list_campaign_tests(db: Session, campaign_id: int):
    _campaign_exists(db, campaign_id)
    return campaign_test_repository.get_by_campaign(db, campaign_id)


def replace_campaign_tests(
    db: Session,
    campaign_id: int,
    payload: list[CampaignTestCreate],
):
    _campaign_exists(db, campaign_id)
    _validate_tests(payload)

    campaign_test_repository.delete_by_campaign(db, campaign_id)

    campaign_test_repository.create_many(
        db,
        campaign_id,
        [item.model_dump() for item in payload],
    )

    db.commit()

    return campaign_test_repository.get_by_campaign(db, campaign_id)


def add_campaign_tests(
    db: Session,
    campaign_id: int,
    payload: list[CampaignTestCreate],
):
    _campaign_exists(db, campaign_id)
    _validate_tests(payload)

    existing = campaign_test_repository.get_by_campaign(db, campaign_id)
    existing_ids = {item.test_id for item in existing}

    for item in payload:
        if item.test_id in existing_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": f"Test {item.test_id} already exists for this campaign."},
            )

    campaign_test_repository.create_many(
        db,
        campaign_id,
        [item.model_dump() for item in payload],
    )

    db.commit()

    return campaign_test_repository.get_by_campaign(db, campaign_id)


def remove_campaign_test(db: Session, campaign_id: int, test_id: int):
    _campaign_exists(db, campaign_id)

    row = campaign_test_repository.get_one(db, campaign_id, test_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Campaign test not found."},
        )

    campaign_test_repository.delete_one(db, row)
    db.commit()

    return {"message": "Campaign test deleted successfully."}
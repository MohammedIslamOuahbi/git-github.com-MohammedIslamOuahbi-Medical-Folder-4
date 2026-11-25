from sqlalchemy.orm import Session

from app.models.campaign_test import CampaignTest


def get_by_campaign(db: Session, campaign_id: int) -> list[CampaignTest]:
    return (
        db.query(CampaignTest)
        .filter(CampaignTest.campaign_id == campaign_id)
        .order_by(CampaignTest.test_id.asc())
        .all()
    )


def delete_by_campaign(db: Session, campaign_id: int) -> None:
    for row in db.query(CampaignTest).filter(CampaignTest.campaign_id == campaign_id).all():
        db.delete(row)


def create_many(
    db: Session,
    campaign_id: int,
    tests: list[dict],
) -> list[CampaignTest]:
    rows = [
        CampaignTest(
            campaign_id=campaign_id,
            test_id=item["test_id"],
            required=item.get("required", False),
        )
        for item in tests
    ]

    db.add_all(rows)
    db.flush()

    return rows


def get_one(
    db: Session,
    campaign_id: int,
    test_id: int,
) -> CampaignTest | None:
    return (
        db.query(CampaignTest)
        .filter(
            CampaignTest.campaign_id == campaign_id,
            CampaignTest.test_id == test_id,
        )
        .first()
    )


def delete_one(db: Session, row: CampaignTest) -> None:
    db.delete(row)
    db.flush()

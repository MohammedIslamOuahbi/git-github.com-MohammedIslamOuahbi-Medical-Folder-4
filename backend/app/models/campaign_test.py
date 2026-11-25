from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from sqlalchemy.orm import relationship
from app.database import Base, SyncMetadataMixin


class CampaignTest(Base, SyncMetadataMixin):
    __tablename__ = "campaign_tests"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("medical_campaigns.id"), nullable=False, index=True)
    test_id = Column(Integer, ForeignKey("medical_tests.id"), nullable=False, index=True)
    required = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    

    __table_args__ = (
        UniqueConstraint("campaign_id", "test_id", name="uq_campaign_tests_campaign_id_test_id"),
    )
    
    campaign = relationship("MedicalCampaign", back_populates="campaign_tests")
    test = relationship("MedicalTest", back_populates="campaign_tests")

from __future__ import annotations

from app.services.sync_safety import suspend_for_data_safety

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assistant_campaign import AssistantCampaign
from app.models.branch import Branch
from app.models.campaign_test import CampaignTest
from app.models.campaign_worker import CampaignWorker
from app.models.company import Company
from app.models.doctor_campaign import DoctorCampaign
from app.models.drilling_site import DrillingSite
from app.models.import_job import ImportJob
from app.models.import_row import ImportRow
from app.models.medical_campaign import MedicalCampaign
from app.models.medical_test import MedicalTest
from app.models.user import User
from app.models.worker import Worker
from app.models.worker_test import WorkerTest


class SyncRepository:
    def __init__(self) -> None:
        self._conflicts: list[dict[str, Any]] = []
        self._last_sync_at: datetime | None = None

    def push_changes(self, changes: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        suspend_for_data_safety("legacy_sync_push")
        synced_at = datetime.now(timezone.utc)
        created = {key: len(value) for key, value in changes.items() if value}
        self._last_sync_at = synced_at
        return {
          "success": True,
          "synced_at": synced_at,
          "created": created,
          "updated": {},
          "deleted": {},
          "conflicts": self._conflicts,
        }

    def pull_changes(self) -> dict[str, Any]:
        server_time = datetime.now(timezone.utc)
        return {
            "success": True,
            "server_time": server_time,
            "changes": {
                "users": [],
                "companies": [],
                "branches": [],
                "drilling_sites": [],
                "workers": [],
                "medical_campaigns": [],
                "campaign_workers": [],
                "medical_tests": [],
                "campaign_tests": [],
                "worker_tests": [],
                "doctor_campaigns": [],
                "assistant_campaigns": [],
                "import_jobs": [],
                "import_rows": [],
            },
            "deleted": {
                "companies": [],
                "branches": [],
                "drilling_sites": [],
                "workers": [],
                "medical_campaigns": [],
                "campaign_workers": [],
                "medical_tests": [],
                "campaign_tests": [],
                "worker_tests": [],
            },
        }

    def resolve_conflict(self, entity_type: str, entity_id: int) -> dict[str, Any]:
        suspend_for_data_safety("legacy_conflict_resolution")
        self._conflicts = [
            conflict
            for conflict in self._conflicts
            if not (
                conflict.get("entity_type") == entity_type
                and conflict.get("entity_id") == entity_id
            )
        ]
        return {"success": True}

    def get_status(self) -> dict[str, Any]:
        return {
            "last_sync_at": self._last_sync_at,
            "pending_push_count": 0,
            "pending_pull_count": 0,
            "conflict_count": len(self._conflicts),
            "server_time": datetime.now(timezone.utc),
        }

    def pull_from_db(self, db: Session) -> dict[str, Any]:
        def rows(model):
            return [
                {key: value for key, value in item.__dict__.items() if not key.startswith("_sa_")}
                for item in db.scalars(select(model)).all()
            ]

        return {
            "users": rows(User),
            "companies": rows(Company),
            "branches": rows(Branch),
            "drilling_sites": rows(DrillingSite),
            "workers": rows(Worker),
            "medical_campaigns": rows(MedicalCampaign),
            "campaign_workers": rows(CampaignWorker),
            "medical_tests": rows(MedicalTest),
            "campaign_tests": rows(CampaignTest),
            "worker_tests": rows(WorkerTest),
            "doctor_campaigns": rows(DoctorCampaign),
            "assistant_campaigns": rows(AssistantCampaign),
            "import_jobs": rows(ImportJob),
            "import_rows": rows(ImportRow),
        }

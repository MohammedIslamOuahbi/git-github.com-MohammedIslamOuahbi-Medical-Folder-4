from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class ReportFilters(BaseModel):
    company_id: int | None = None
    branch_id: int | None = None
    campaign_id: int | None = None
    worker_id: int | None = None
    from_date: date | None = None
    to_date: date | None = None

from __future__ import annotations

from datetime import date

import pytest

from app.exceptions import BadRequestException
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.company_service import CompanyService


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_company_service_rejects_invalid_contract_date_range(db_session):
    service = CompanyService()

    with pytest.raises(BadRequestException) as exc_info:
        service.create(
            db_session,
            CompanyCreate(
                name="Invalid Contract Co",
                contract_start_date=date(2026, 6, 30),
                contract_end_date=date(2026, 6, 1),
            ),
        )

    assert exc_info.value.status_code == 400


def test_company_service_updates_contract_dates(db_session):
    service = CompanyService()
    company = service.create(
        db_session,
        CompanyCreate(
            name="Valid Contract Co",
            contract_start_date=date(2026, 1, 1),
            contract_end_date=date(2026, 12, 31),
        ),
    )

    updated = service.update(
        db_session,
        company.id,
        CompanyUpdate(contract_end_date=date(2027, 1, 31)),
    )

    assert updated.contract_start_date == date(2026, 1, 1)
    assert updated.contract_end_date == date(2027, 1, 31)

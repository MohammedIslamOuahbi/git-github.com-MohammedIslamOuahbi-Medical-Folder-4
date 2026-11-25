from __future__ import annotations

from datetime import date

from app.models.branch import Branch
from app.models.company import Company
from app.models.drilling_site import DrillingSite
from app.models.user import User


def _auth_headers(client, email: str, password: str):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_admin(db_session, email: str = "workers-admin@ibnsina-clinic.com", password: str = "admin12345"):
    from app.services.auth_service import AuthService

    return AuthService().create_admin_user(db_session, "Admin", "User", email, password)


def _seed_worker_prerequisites(db_session):
    company = Company(name="Worker Co")
    branch = Branch(company=company, name="Main Branch")
    site = DrillingSite(company=company, branch=branch, name="Main Site", location="HQ", status="active")
    db_session.add_all([company, branch, site])
    db_session.flush()
    return company, branch, site


def test_workers_requires_auth(client):
    response = client.get("/api/v1/workers")
    assert response.status_code in {401, 403}


def test_create_worker_without_dynamic_medical_tests(client, db_session):
    admin = _seed_admin(db_session)
    company, branch, site = _seed_worker_prerequisites(db_session)
    headers = _auth_headers(client, admin.email, "admin12345")

    payload = {
        "company_id": company.id,
        "branch_id": branch.id,
        "drilling_site_id": site.id,
        "employee_number": "W-001",
        "national_id": "123456789012345678",
        "first_name": "Amina",
        "last_name": "Bensalah",
        "gender": "F",
        "birth_date": "1995-05-14",
        "medical_file_data": {
            "clinicalExam": {},
        },
    }

    response = client.post("/api/v1/workers", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["medical_file_data"]["clinicalExam"] == {}
    assert "dynamicMedicalTests" not in data["medical_file_data"]


def test_create_worker_with_dynamic_medical_tests(client, db_session):
    admin = _seed_admin(db_session, email="workers-admin-2@ibnsina-clinic.com")
    company, branch, site = _seed_worker_prerequisites(db_session)
    headers = _auth_headers(client, admin.email, "admin12345")

    dynamic_tests = {
        "25": {
            "testId": 25,
            "testName": "Acuité visuelle dynamique",
            "values": {"od_sc": "10", "od_ac": "9", "comment": "Normal"},
        }
    }
    payload = {
        "company_id": company.id,
        "branch_id": branch.id,
        "drilling_site_id": site.id,
        "employee_number": "W-002",
        "national_id": "123456789012345679",
        "first_name": "Yacine",
        "last_name": "Amrani",
        "gender": "M",
        "birth_date": "1992-02-03",
        "medical_file_data": {
            "clinicalExam": {},
            "dynamicMedicalTests": dynamic_tests,
        },
    }

    response = client.post("/api/v1/workers", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["medical_file_data"]["dynamicMedicalTests"] == dynamic_tests


def test_read_worker_returns_dynamic_medical_tests(client, db_session):
    admin = _seed_admin(db_session, email="workers-admin-3@ibnsina-clinic.com")
    company, branch, site = _seed_worker_prerequisites(db_session)
    headers = _auth_headers(client, admin.email, "admin12345")

    dynamic_tests = {
        "31": {
            "testId": 31,
            "testName": "Evaluation Respiratoire",
            "values": {"symptom": "Toux chronique", "respiratory_rate": 18},
        }
    }
    create_response = client.post(
        "/api/v1/workers",
        json={
            "company_id": company.id,
            "branch_id": branch.id,
            "drilling_site_id": site.id,
            "employee_number": "W-003",
            "national_id": "123456789012345680",
            "first_name": "Sami",
            "last_name": "Belaid",
            "gender": "M",
            "birth_date": "1990-01-01",
            "medical_file_data": {"dynamicMedicalTests": dynamic_tests},
        },
        headers=headers,
    )
    worker_id = create_response.json()["data"]["id"]

    response = client.get(f"/api/v1/workers/{worker_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["medical_file_data"]["dynamicMedicalTests"] == dynamic_tests


def test_update_worker_preserves_existing_dynamic_medical_tests(client, db_session):
    admin = _seed_admin(db_session, email="workers-admin-4@ibnsina-clinic.com")
    company, branch, site = _seed_worker_prerequisites(db_session)
    headers = _auth_headers(client, admin.email, "admin12345")

    dynamic_tests = {
        "25": {
            "testId": 25,
            "testName": "Acuité visuelle dynamique",
            "values": {"od_sc": "10"},
        }
    }
    create_response = client.post(
        "/api/v1/workers",
        json={
            "company_id": company.id,
            "branch_id": branch.id,
            "drilling_site_id": site.id,
            "employee_number": "W-004",
            "national_id": "123456789012345681",
            "first_name": "Meriem",
            "last_name": "Khaldi",
            "gender": "F",
            "birth_date": "1991-04-05",
            "medical_file_data": {"dynamicMedicalTests": dynamic_tests, "clinicalExam": {}},
        },
        headers=headers,
    )
    worker_id = create_response.json()["data"]["id"]

    update_response = client.put(
        f"/api/v1/workers/{worker_id}",
        json={
            "department": "HSE",
            "medical_file_data": {"clinicalExam": {"ophtalmology": {"observations": "OK"}}},
        },
        headers=headers,
    )
    assert update_response.status_code == 200
    data = update_response.json()["data"]
    assert data["medical_file_data"]["dynamicMedicalTests"] == dynamic_tests
    assert data["medical_file_data"]["clinicalExam"]["ophtalmology"]["observations"] == "OK"


def test_update_worker_adds_new_dynamic_test_values(client, db_session):
    admin = _seed_admin(db_session, email="workers-admin-5@ibnsina-clinic.com")
    company, branch, site = _seed_worker_prerequisites(db_session)
    headers = _auth_headers(client, admin.email, "admin12345")

    create_response = client.post(
        "/api/v1/workers",
        json={
            "company_id": company.id,
            "branch_id": branch.id,
            "drilling_site_id": site.id,
            "employee_number": "W-005",
            "national_id": "123456789012345682",
            "first_name": "Nassim",
            "last_name": "Brahimi",
            "gender": "M",
            "birth_date": "1989-07-08",
            "medical_file_data": {},
        },
        headers=headers,
    )
    worker_id = create_response.json()["data"]["id"]

    dynamic_tests = {
        "31": {
            "testId": 31,
            "testName": "Evaluation Respiratoire",
            "values": {"symptom": "Toux chronique", "respiratory_rate": 18},
        }
    }
    update_response = client.put(
        f"/api/v1/workers/{worker_id}",
        json={
            "medical_file_data": {"dynamicMedicalTests": dynamic_tests},
        },
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["medical_file_data"]["dynamicMedicalTests"] == dynamic_tests


def test_invalid_dynamic_medical_tests_type_is_rejected(client, db_session):
    admin = _seed_admin(db_session, email="workers-admin-6@ibnsina-clinic.com")
    company, branch, site = _seed_worker_prerequisites(db_session)
    headers = _auth_headers(client, admin.email, "admin12345")

    response = client.post(
        "/api/v1/workers",
        json={
            "company_id": company.id,
            "branch_id": branch.id,
            "drilling_site_id": site.id,
            "employee_number": "W-006",
            "national_id": "123456789012345683",
            "first_name": "Sara",
            "last_name": "Ait Ali",
            "gender": "F",
            "birth_date": "1993-09-10",
            "medical_file_data": {
                "dynamicMedicalTests": "invalid",
            },
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert "dynamicMedicalTests must be an object." in response.text


def test_create_worker_rejects_duplicate_national_id(client, db_session):
    admin = _seed_admin(db_session, email="workers-admin-7@ibnsina-clinic.com")
    company, branch, site = _seed_worker_prerequisites(db_session)
    headers = _auth_headers(client, admin.email, "admin12345")

    base_payload = {
        "company_id": company.id,
        "branch_id": branch.id,
        "drilling_site_id": site.id,
        "employee_number": "W-007",
        "national_id": "123456789012345684",
        "first_name": "Imane",
        "last_name": "Khelifi",
        "gender": "F",
        "birth_date": "1994-03-11",
    }

    response = client.post("/api/v1/workers", json=base_payload, headers=headers)
    assert response.status_code == 201

    duplicate_payload = {
        **base_payload,
        "employee_number": "W-008",
        "first_name": "Sara",
        "last_name": "Mokhtar",
    }
    duplicate_response = client.post("/api/v1/workers", json=duplicate_payload, headers=headers)
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["message"] == "National identity number already exists."


def test_update_worker_rejects_duplicate_national_id(client, db_session):
    admin = _seed_admin(db_session, email="workers-admin-8@ibnsina-clinic.com")
    company, branch, site = _seed_worker_prerequisites(db_session)
    headers = _auth_headers(client, admin.email, "admin12345")

    first_worker = client.post(
        "/api/v1/workers",
        json={
            "company_id": company.id,
            "branch_id": branch.id,
            "drilling_site_id": site.id,
            "employee_number": "W-009",
            "national_id": "123456789012345685",
            "first_name": "Nadia",
            "last_name": "Brahimi",
            "gender": "F",
            "birth_date": "1990-06-16",
        },
        headers=headers,
    ).json()["data"]

    second_worker = client.post(
        "/api/v1/workers",
        json={
            "company_id": company.id,
            "branch_id": branch.id,
            "drilling_site_id": site.id,
            "employee_number": "W-010",
            "national_id": "123456789012345686",
            "first_name": "Yacine",
            "last_name": "Kadi",
            "gender": "M",
            "birth_date": "1988-12-01",
        },
        headers=headers,
    ).json()["data"]

    response = client.put(
        f"/api/v1/workers/{second_worker['id']}",
        json={"national_id": first_worker["national_id"]},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["message"] == "National identity number already exists."

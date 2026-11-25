def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_login_accepts_seeded_local_admin_email(client, db_session):
    from app.services.auth_service import AuthService

    AuthService().create_admin_user(
        db_session,
        first_name="System",
        last_name="Administrator",
        email="qa-admin@ibnsina-clinic.com",
        password="admin12345",
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "qa-admin@ibnsina-clinic.com", "password": "admin12345"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["access_token"]
    assert payload["data"]["refresh_token"]

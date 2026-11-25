def test_users_requires_auth(client):
    response = client.get("/api/v1/users")
    assert response.status_code in {401, 403}

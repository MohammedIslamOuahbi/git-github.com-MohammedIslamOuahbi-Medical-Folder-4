def test_import_history_requires_auth(client):
    response = client.get("/api/v1/imports/history")
    assert response.status_code in {401, 403}

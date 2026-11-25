def test_reports_require_auth(client):
    response = client.get("/api/v1/reports/campaign-summary")
    assert response.status_code in {401, 403}

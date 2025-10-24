
def test_create_run_from_latest_published(client, auth_headers):
    # Suponemos un workflow publicado en seeds (aún no implementado)
    r = client.post("/api/v0/runs", json={"workflow_id": "wf_demo"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("status") in ("queued", "running")

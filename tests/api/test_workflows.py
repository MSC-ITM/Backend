
def test_create_workflow_draft_ok(client, auth_headers):
    payload = {
        "name": "ETL Leads",
        "status": "draft",
        "nodes": [{
            "id": "n1",
            "type": "http.request",
            "label": "Fetch",
            "config": {"method": "GET", "url": "https://api.example.com"},
            "ports": {"in": [], "out": [{"name": "main"}, {"name": "error"}]},
            "ui": {"x": 120, "y": 80}
        }],
        "connections": [],
        "triggers": []
    }
    r = client.post("/api/v0/workflows", json=payload, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("id") and body.get("version") == 1 and body.get("status") == "draft"

def test_publish_creates_immutable_version(client, auth_headers):
    wf = client.post("/api/v0/workflows", json={"name": "W1", "status": "draft", "nodes": [], "connections": [], "triggers": []}, headers=auth_headers)
    assert wf.status_code == 201, wf.text
    wid = wf.json()["id"]
    pub = client.post(f"/api/v0/workflows/{wid}:publish", headers=auth_headers)
    assert pub.status_code == 200, pub.text
    upd = client.put(f"/api/v0/workflows/{wid}", json={"name": "W1-mod"}, headers=auth_headers)
    assert upd.status_code in (400, 409), upd.text

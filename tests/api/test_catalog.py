
def test_catalog_nodes_includes_http_and_switch(client, auth_headers):
    r = client.get("/api/v0/catalog/nodes", headers=auth_headers)
    assert r.status_code == 200
    types = {item["type"] for item in r.json()["items"]}
    assert {"http.request", "logic.switch"}.issubset(types)

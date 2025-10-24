
import pathlib, yaml

def test_openapi_file_exists_and_parses():
    path = pathlib.Path("spec/openapi/openapi.yaml")
    assert path.exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data.get("openapi", "").startswith("3."), "OpenAPI version missing"

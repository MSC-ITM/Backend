# tests/conftest.py
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient

# Añade `src/` al sys.path para permitir la importación del módulo de aplicación.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Importa la instancia de aplicación FastAPI expuesta por el módulo principal.
from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Cliente de pruebas para peticiones HTTP síncronas contra la app."""
    return TestClient(app)

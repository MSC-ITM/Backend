# tests/test_ia_client.py

import types
import importlib

def test_getter_returns_singleton_instance(monkeypatch):
    """
    El getter debe devolver siempre la MISMA instancia (patrón Singleton).
    """
    # Cargamos el módulo bajo prueba
    ia_mod = importlib.import_module("src.ia_client")

    # Reset interno para no depender de orden de ejecución en otros tests
    if hasattr(ia_mod, "_instance"):
        delattr(ia_mod, "_instance")

    a = ia_mod.get_ia_client()
    b = ia_mod.get_ia_client()
    assert a is b, "get_ia_client() debe implementar Singleton (misma instancia)"


def test_suggest_contract_minimum(monkeypatch):
    """
    suggest() debe devolver un contrato estable y determinístico
    útil para el Frontend y el Worker durante el mock.
    """
    ia_mod = importlib.import_module("src.ia_client")
    client = ia_mod.get_ia_client()

    definition = {"steps": [{"type": "HTTPS GET Request", "args": {"url": "https://x"}}]}
    out = client.suggest(definition)

    assert isinstance(out, dict)
    # Contrato mínimo esperado del mock:
    assert "suggested_changes" in out and isinstance(out["suggested_changes"], list)
    assert "confidence" in out and isinstance(out["confidence"], (int, float))
    assert 0.0 <= out["confidence"] <= 1.0
    assert "rationale" in out and isinstance(out["rationale"], str)


def test_fix_contract_minimum_accepts_logs_str_or_list(monkeypatch):
    """
    fix() debe aceptar logs como str o list[str] y normalizar internamente.
    Debe devolver una definición parcheada y notas.
    """
    ia_mod = importlib.import_module("src.ia_client")
    client = ia_mod.get_ia_client()

    definition = {"steps": [{"type": "Validate CSV File", "args": {"delimiter": ","}}]}

    out1 = client.fix(definition, logs="error: failed to open file")
    out2 = client.fix(definition, logs=["warn: header missing", "error: type mismatch"])

    for out in (out1, out2):
        assert isinstance(out, dict)
        assert "patched_definition" in out and isinstance(out["patched_definition"], dict)
        assert "notes" in out and isinstance(out["notes"], list)


def test_estimate_contract_minimum(monkeypatch):
    """
    estimate() debe devolver tiempos y costo aproximado determinísticos en el mock.
    """
    ia_mod = importlib.import_module("src.ia_client")
    client = ia_mod.get_ia_client()

    definition = {
        "steps": [
            {"type": "HTTPS GET Request", "args": {"url": "https://x"}},
            {"type": "Simple Transform", "args": {"op": "uppercase", "field": "name"}},
            {"type": "Save to Database", "args": {"table": "t1"}},
        ]
    }
    out = client.estimate(definition)

    assert isinstance(out, dict)
    assert "estimated_time_seconds" in out and isinstance(out["estimated_time_seconds"], int)
    assert "estimated_cost_usd" in out and isinstance(out["estimated_cost_usd"], (int, float))
    assert "assumptions" in out and isinstance(out["assumptions"], list)

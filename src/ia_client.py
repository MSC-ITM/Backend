# src/ia_client.py
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Union, cast

# --------------------------------------------------------------------------------------
# Patrón Singleton vía getter:
# - La instancia viva se mantiene en un símbolo de módulo (_instance).
# - get_ia_client() crea perezosamente la instancia y siempre devuelve la misma.
# - Este enfoque facilita pruebas (se puede monkeypatchear _instance o el getter).
# --------------------------------------------------------------------------------------
_instance: Optional["IAClient"] = None


def get_ia_client() -> "IAClient":
    """Devuelve la instancia única de IAClient (Singleton) de forma robusta para pruebas.

    Nota: Los tests pueden borrar el símbolo `_instance` con `delattr`.
    Por eso consultamos/escribimos en `globals()` en lugar de depender de
    una variable de módulo siempre presente.
    """
    inst = globals().get("_instance", None)
    if not isinstance(inst, IAClient):
        inst = IAClient()
        globals()["_instance"] = inst
    return inst



class IAClient:
    """
    Cliente de IA placeholder.

    Responsabilidades:
    - Ofrecer una interfaz estable para sugerencia, fix y estimación.
    - Mantener respuestas determinísticas durante pruebas.
    - Encapsular la dependencia externa futura (modelo/servicio real).

    Sustitución futura:
    - Reemplazar las implementaciones de suggest(), fix() y estimate()
      por llamadas reales al motor elegido, conservando la firma.
    """

    # Valores fijos para mantener determinismo en los mocks.
    _DEFAULT_CONFIDENCE = 0.66
    _DEFAULT_TIMEOUT_SEC = 30

    def suggest(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retorna un conjunto mínimo de sugerencias determinísticas.

        Contrato mínimo:
        {
          "suggested_changes": [ ... ],
          "confidence": float in [0,1],
          "rationale": str
        }
        """
        # Heurística neutra y estable para el mock.
        suggestions: List[Dict[str, Any]] = []

        # Ejemplo de sugerencia genérica para GET sin timeout.
        for idx, step in enumerate(definition.get("steps", [])):
            if step.get("type") == "HTTPS GET Request":
                args = step.get("args", {}) or {}
                if "timeout" not in args:
                    suggestions.append(
                        {
                            "op": "add_arg",
                            "target_step_index": idx,
                            "arg": {"timeout": self._DEFAULT_TIMEOUT_SEC},
                            "reason": "Definir timeout para tráfico HTTP predecible.",
                        }
                    )

        # Si no hay salida, sugerir notificación mock (solo como demostración).
        if not any(s.get("type") in ("Save to Database", "Mock Notification") for s in definition.get("steps", [])):
            suggestions.append(
                {
                    "op": "append_step",
                    "step": {"type": "Mock Notification", "args": {"channel": "log"}},
                    "reason": "Asegurar un paso de salida para observabilidad.",
                }
            )

        return {
            "suggested_changes": suggestions,
            "confidence": self._DEFAULT_CONFIDENCE,
            "rationale": "Sugerencias básicas para robustez (timeout) y salida observable.",
        }

    def fix(self, definition: Dict[str, Any], logs: Union[str, List[str], None]) -> Dict[str, Any]:
        """
        Devuelve una definición parcheada y notas.

        Contrato mínimo:
        {
          "patched_definition": {...},
          "notes": [str, ...]
        }

        Reglas determinísticas (mock):
        - Normalizar logs a lista de strings.
        - Asegurar 'timeout' en pasos HTTPS GET Request si falta.
        - Si no hay paso de salida (Save/Notification), agregar Mock Notification.
        """
        patched = deepcopy(definition)
        notes: List[str] = []

        # Normalización de logs
        norm_logs: List[str]
        if logs is None:
            norm_logs = []
        elif isinstance(logs, str):
            norm_logs = [logs]
        else:
            # Forzar a lista de str
            norm_logs = [str(x) for x in logs]

        # Timeout para GET si falta
        for step in patched.get("steps", []):
            if step.get("type") == "HTTPS GET Request":
                args = cast(Dict[str, Any], step.setdefault("args", {}))
                if "timeout" not in args:
                    args["timeout"] = self._DEFAULT_TIMEOUT_SEC
                    notes.append("Se agregó timeout a HTTPS GET Request.")

        # Asegurar salida
        has_output = any(s.get("type") in ("Save to Database", "Mock Notification") for s in patched.get("steps", []))
        if not has_output:
            patched.setdefault("steps", []).append(
                {"type": "Mock Notification", "args": {"channel": "log"}}
            )
            notes.append("Se agregó paso de salida (Mock Notification).")

        # Anotar que se leyeron logs (aunque el mock no aplique cambios por contenido)
        if norm_logs:
            notes.append(f"Se procesaron {len(norm_logs)} líneas de logs.")

        return {
            "patched_definition": patched,
            "notes": notes,
        }

    def estimate(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retorna una estimación determinística basada en conteo de pasos y un costo fijo por tipo.

        Contrato mínimo:
        {
          "estimated_time_seconds": int,
          "estimated_cost_usd": float,
          "assumptions": [str, ...]
        }
        """
        steps: List[Dict[str, Any]] = list(definition.get("steps", []))

        # Pesos determinísticos por tipo (mock).
        time_per_type = {
            "HTTPS GET Request": 2,
            "Validate CSV File": 1,
            "Simple Transform": 1,
            "Save to Database": 2,
            "Mock Notification": 0,
        }
        cost_per_type = {
            "HTTPS GET Request": 0.0005,
            "Validate CSV File": 0.0002,
            "Simple Transform": 0.0002,
            "Save to Database": 0.0005,
            "Mock Notification": 0.0,
        }

        est_time = 0
        est_cost = 0.0
        for s in steps:
            t = s.get("type", "")
            est_time += time_per_type.get(t, 1)  # valor por defecto estable
            est_cost += cost_per_type.get(t, 0.0001)

        return {
            "estimated_time_seconds": int(est_time),
            "estimated_cost_usd": float(round(est_cost, 6)),
            "assumptions": [
                "Estimación basada en reglas determinísticas por tipo de paso.",
                "No incluye latencias de red ni costos externos.",
            ],
        }

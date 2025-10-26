# src/ia/handlers.py
"""
Chain of Responsibility Pattern: Cadena de handlers para procesar sugerencias.

Cada handler se encarga de una regla específica y puede pasar al siguiente handler.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from copy import deepcopy


class SuggestionHandler(ABC):
    """Handler base para la cadena de responsabilidad de sugerencias."""

    def __init__(self, next_handler: Optional["SuggestionHandler"] = None):
        """
        Args:
            next_handler: Siguiente handler en la cadena
        """
        self._next_handler = next_handler

    def set_next(self, handler: "SuggestionHandler") -> "SuggestionHandler":
        """Establece el siguiente handler en la cadena."""
        self._next_handler = handler
        return handler

    def handle(self, definition: Dict[str, Any], suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Procesa la definición y agrega sugerencias.

        Args:
            definition: Definición del workflow
            suggestions: Lista de sugerencias acumuladas

        Returns:
            Lista de sugerencias actualizada
        """
        # Procesar en este handler
        suggestions = self._process(definition, suggestions)

        # Pasar al siguiente handler si existe
        if self._next_handler:
            return self._next_handler.handle(definition, suggestions)

        return suggestions

    @abstractmethod
    def _process(self, definition: Dict[str, Any], suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Lógica específica de procesamiento del handler."""
        pass


class TimeoutHandler(SuggestionHandler):
    """Handler que verifica que los requests HTTP tengan timeout."""

    def _process(self, definition: Dict[str, Any], suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Verifica timeout en HTTPS GET Request."""
        for idx, step in enumerate(definition.get("steps", [])):
            if step.get("type") == "HTTPS GET Request":
                args = step.get("args", {}) or {}
                if "timeout" not in args:
                    suggestions.append({
                        "op": "add_arg",
                        "target_step_index": idx,
                        "arg": {"timeout": 30},
                        "reason": "Agregar timeout para prevenir bloqueos indefinidos en requests HTTP.",
                    })
        return suggestions


class OutputNodeHandler(SuggestionHandler):
    """Handler que verifica la existencia de nodos de salida."""

    def _process(self, definition: Dict[str, Any], suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Verifica que exista al menos un nodo de salida."""
        steps = definition.get("steps", [])
        has_output = any(
            s.get("type") in ("Save to Database", "Mock Notification")
            for s in steps
        )

        if not has_output:
            suggestions.append({
                "op": "append_step",
                "step": {"type": "Mock Notification", "args": {"channel": "log"}},
                "reason": "Agregar nodo de salida para registrar resultados del workflow.",
            })

        return suggestions


class ValidationOrderHandler(SuggestionHandler):
    """Handler que verifica el orden correcto de validación y transformación."""

    def _process(self, definition: Dict[str, Any], suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Verifica que Validate CSV File esté antes de Simple Transform."""
        steps = definition.get("steps", [])
        validate_idx = -1
        transform_idx = -1

        for i, step in enumerate(steps):
            step_type = step.get("type")
            if step_type == "Validate CSV File":
                validate_idx = i
            elif step_type == "Simple Transform":
                transform_idx = i

        # Si ambos existen y validate está después de transform
        if validate_idx != -1 and transform_idx != -1 and validate_idx > transform_idx:
            suggestions.append({
                "op": "reorder",
                "reason": "Mover 'Validate CSV File' antes de 'Simple Transform' para validar datos antes de transformarlos.",
                "detail": {
                    "move_step_from": validate_idx,
                    "move_step_to": transform_idx
                }
            })

        return suggestions


class PerformanceHandler(SuggestionHandler):
    """Handler que sugiere optimizaciones de rendimiento."""

    def _process(self, definition: Dict[str, Any], suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analiza pasos que podrían paralelizarse o optimizarse."""
        steps = definition.get("steps", [])

        # Detectar pasos independientes que podrían ejecutarse en paralelo
        if len(steps) >= 3:
            # Heurística simple: si hay múltiples GET requests independientes
            get_requests = [i for i, s in enumerate(steps) if s.get("type") == "HTTPS GET Request"]

            if len(get_requests) >= 2:
                suggestions.append({
                    "op": "optimize",
                    "reason": "Considerar ejecución paralela de múltiples HTTPS GET Requests para reducir tiempo total.",
                    "detail": {
                        "parallel_candidates": get_requests
                    }
                })

        return suggestions


class SuggestionChainFactory:
    """Factory para crear la cadena de handlers de sugerencias."""

    @staticmethod
    def create_default_chain() -> SuggestionHandler:
        """
        Crea la cadena por defecto de handlers.

        Orden:
        1. TimeoutHandler - Verifica timeouts
        2. OutputNodeHandler - Verifica nodos de salida
        3. ValidationOrderHandler - Verifica orden de validación
        4. PerformanceHandler - Optimizaciones de rendimiento
        """
        timeout_handler = TimeoutHandler()
        output_handler = OutputNodeHandler()
        validation_handler = ValidationOrderHandler()
        performance_handler = PerformanceHandler()

        # Construir la cadena
        timeout_handler.set_next(output_handler)
        output_handler.set_next(validation_handler)
        validation_handler.set_next(performance_handler)

        return timeout_handler

    @staticmethod
    def create_basic_chain() -> SuggestionHandler:
        """
        Crea una cadena básica solo con handlers esenciales.

        Orden:
        1. TimeoutHandler
        2. OutputNodeHandler
        """
        timeout_handler = TimeoutHandler()
        output_handler = OutputNodeHandler()

        timeout_handler.set_next(output_handler)

        return timeout_handler

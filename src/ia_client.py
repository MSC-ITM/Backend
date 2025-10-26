# src/ia_client.py
"""
Cliente de IA mejorado con arquitectura extensible.

Integra:
- Strategy Pattern: Múltiples proveedores de IA (Mock, OpenAI)
- Command Pattern: Operaciones de fix estructuradas
- Observer Pattern: Notificaciones de eventos
- Servicios: Optimización de rutas y predicción de costos
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Union, cast

# Importar componentes de la nueva arquitectura
from .ia.factory import IAProviderFactory
from .ia.providers import IAProviderStrategy
from .ia.commands import FixCommandInvoker, FixCommandFactory
from .ia.observers import WorkflowSubject, LogObserver, MetricsObserver
from .ia.services import RouteOptimizer, CostPredictor

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
    Cliente de IA mejorado con arquitectura extensible.

    Integra todos los patrones de diseño y servicios de IA:
    - Strategy Pattern para proveedores intercambiables
    - Command Pattern para operaciones de fix
    - Observer Pattern para monitoreo
    - Servicios de optimización y predicción

    Responsabilidades:
    - Ofrecer una interfaz estable para sugerencia, fix y estimación
    - Coordinar entre diferentes componentes de IA
    - Mantener compatibilidad con tests existentes
    """

    # Valores fijos para mantener determinismo en los mocks.
    _DEFAULT_CONFIDENCE = 0.66
    _DEFAULT_TIMEOUT_SEC = 30

    def __init__(self, provider: Optional[IAProviderStrategy] = None):
        """
        Inicializa el cliente de IA.

        Args:
            provider: Proveedor de IA a usar. Si es None, se crea desde configuración.
        """
        # Proveedor de IA (Strategy Pattern)
        self.provider = provider or IAProviderFactory.create_from_config()

        # Subject para notificaciones (Observer Pattern)
        self.subject = WorkflowSubject()

        # Observadores por defecto
        self.log_observer = LogObserver(verbose=False)
        self.metrics_observer = MetricsObserver()
        self.subject.attach(self.log_observer)
        self.subject.attach(self.metrics_observer)

        # Servicios
        self.route_optimizer = RouteOptimizer()
        self.cost_predictor = CostPredictor()

    def suggest(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera sugerencias para mejorar el workflow usando el proveedor configurado.

        Contrato mínimo:
        {
          "suggested_changes": [ ... ],
          "confidence": float in [0,1],
          "rationale": str
        }

        Raises:
            Exception: Si el proveedor falla después de todos los reintentos
        """
        # Delegar al proveedor (Strategy Pattern)
        result = self.provider.suggest(definition)

        # Notificar a observadores
        workflow_id = definition.get("name", "unknown")
        self.subject.notify_suggestion(
            workflow_id=workflow_id,
            suggestions=result.get("suggested_changes", [])
        )

        return result

    def fix(self, definition: Dict[str, Any], logs: Union[str, List[str], None]) -> Dict[str, Any]:
        """
        Aplica correcciones al workflow usando el proveedor de IA.

        Contrato mínimo:
        {
          "patched_definition": {...},
          "notes": [str, ...]
        }

        Raises:
            Exception: Si el proveedor falla después de todos los reintentos
        """
        # Usar el proveedor de IA
        result = self.provider.fix(definition, logs)

        # Notificar a observadores
        workflow_id = definition.get("name", "unknown")
        self.subject.notify_fix(
            workflow_id=workflow_id,
            changes=result.get("notes", [])
        )

        return result

    def estimate(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estima tiempo, costo y complejidad usando el proveedor de IA.

        Contrato mínimo:
        {
          "estimated_time_seconds": int,
          "estimated_cost_usd": float,
          "complexity_score": float,
          "breakdown": List[Dict],
          "assumptions": [str, ...],
          "confidence": float
        }

        Raises:
            Exception: Si el proveedor falla después de todos los reintentos
        """
        # Usar el proveedor de IA
        result = self.provider.estimate(definition)

        # Notificar a observadores
        workflow_id = definition.get("name", "unknown")
        self.subject.notify_estimate(
            workflow_id=workflow_id,
            estimate_data=result
        )

        return result

    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas recopiladas por el observer."""
        return self.metrics_observer.get_metrics()

    def get_logs(self) -> List[Dict[str, Any]]:
        """Retorna logs recopilados por el observer."""
        return self.log_observer.get_logs()

    def optimize_workflow(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimiza el workflow usando el servicio de optimización de rutas.

        Args:
            definition: Definición del workflow a optimizar

        Returns:
            Dict con definición optimizada y reporte de optimizaciones
        """
        optimized = self.route_optimizer.optimize(definition)
        report = self.route_optimizer.get_optimization_report()

        return {
            "optimized_definition": optimized,
            "optimization_report": report
        }

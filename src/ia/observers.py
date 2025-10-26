# src/ia/observers.py
"""
Observer Pattern: Observadores para monitoreo de workflows.

Permite que diferentes componentes reaccionen a eventos del sistema de IA.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime, UTC
import json


class WorkflowEvent:
    """Representa un evento en el workflow."""

    def __init__(self, event_type: str, workflow_id: str, data: Dict[str, Any]):
        self.event_type = event_type
        self.workflow_id = workflow_id
        self.data = data
        self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el evento a diccionario."""
        return {
            "event_type": self.event_type,
            "workflow_id": self.workflow_id,
            "data": self.data,
            "timestamp": self.timestamp
        }


class WorkflowObserver(ABC):
    """Observador base para eventos de workflow."""

    @abstractmethod
    def update(self, event: WorkflowEvent) -> None:
        """
        Recibe notificación de un evento.

        Args:
            event: Evento ocurrido en el workflow
        """
        pass


class LogObserver(WorkflowObserver):
    """Observador que registra eventos en logs."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._logs: List[Dict[str, Any]] = []

    def update(self, event: WorkflowEvent) -> None:
        """Registra el evento en el log."""
        log_entry = event.to_dict()
        self._logs.append(log_entry)

        if self.verbose:
            print(f"[LogObserver] {event.event_type} @ {event.timestamp}")
            print(f"  Workflow: {event.workflow_id}")
            print(f"  Data: {json.dumps(event.data, indent=2)}")

    def get_logs(self) -> List[Dict[str, Any]]:
        """Retorna todos los logs registrados."""
        return self._logs.copy()

    def clear_logs(self) -> None:
        """Limpia los logs."""
        self._logs.clear()


class MetricsObserver(WorkflowObserver):
    """Observador que recopila métricas de workflows."""

    def __init__(self):
        self._metrics: Dict[str, Any] = {
            "total_events": 0,
            "events_by_type": {},
            "workflows_processed": set(),
            "suggestions_made": 0,
            "fixes_applied": 0,
            "estimates_requested": 0,
        }

    def update(self, event: WorkflowEvent) -> None:
        """Actualiza métricas basadas en el evento."""
        self._metrics["total_events"] += 1

        # Contar por tipo
        event_type = event.event_type
        self._metrics["events_by_type"][event_type] = (
            self._metrics["events_by_type"].get(event_type, 0) + 1
        )

        # Trackear workflows únicos
        self._metrics["workflows_processed"].add(event.workflow_id)

        # Métricas específicas por tipo de evento
        if event_type == "suggestion":
            self._metrics["suggestions_made"] += 1
        elif event_type == "fix":
            self._metrics["fixes_applied"] += 1
        elif event_type == "estimate":
            self._metrics["estimates_requested"] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Retorna las métricas recopiladas."""
        metrics = self._metrics.copy()
        metrics["workflows_processed"] = len(self._metrics["workflows_processed"])
        return metrics

    def reset_metrics(self) -> None:
        """Resetea todas las métricas."""
        self._metrics = {
            "total_events": 0,
            "events_by_type": {},
            "workflows_processed": set(),
            "suggestions_made": 0,
            "fixes_applied": 0,
            "estimates_requested": 0,
        }


class AlertObserver(WorkflowObserver):
    """Observador que genera alertas para eventos críticos."""

    def __init__(self, alert_threshold: int = 5):
        self.alert_threshold = alert_threshold
        self._alerts: List[Dict[str, Any]] = []
        self._error_count = 0

    def update(self, event: WorkflowEvent) -> None:
        """Genera alertas si se detectan problemas."""
        # Detectar eventos de error
        if event.event_type == "error" or "error" in event.data:
            self._error_count += 1

            if self._error_count >= self.alert_threshold:
                alert = {
                    "severity": "high",
                    "message": f"Se han detectado {self._error_count} errores",
                    "timestamp": event.timestamp,
                    "workflow_id": event.workflow_id
                }
                self._alerts.append(alert)
                print(f"[ALERT] {alert['message']}")

        # Detectar workflows muy complejos
        if event.event_type == "estimate":
            complexity = event.data.get("complexity_score", 0)
            if complexity > 0.8:
                alert = {
                    "severity": "medium",
                    "message": f"Workflow con alta complejidad: {complexity}",
                    "timestamp": event.timestamp,
                    "workflow_id": event.workflow_id
                }
                self._alerts.append(alert)

    def get_alerts(self) -> List[Dict[str, Any]]:
        """Retorna todas las alertas generadas."""
        return self._alerts.copy()

    def clear_alerts(self) -> None:
        """Limpia las alertas."""
        self._alerts.clear()
        self._error_count = 0


class WorkflowSubject:
    """
    Subject del patrón Observer.

    Gestiona la lista de observadores y notifica eventos.
    """

    def __init__(self):
        self._observers: List[WorkflowObserver] = []

    def attach(self, observer: WorkflowObserver) -> None:
        """Agrega un observador."""
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: WorkflowObserver) -> None:
        """Remueve un observador."""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event: WorkflowEvent) -> None:
        """Notifica a todos los observadores sobre un evento."""
        for observer in self._observers:
            observer.update(event)

    def notify_suggestion(self, workflow_id: str, suggestions: List[Dict[str, Any]]) -> None:
        """Helper para notificar evento de sugerencia."""
        event = WorkflowEvent(
            event_type="suggestion",
            workflow_id=workflow_id,
            data={"suggestions_count": len(suggestions), "suggestions": suggestions}
        )
        self.notify(event)

    def notify_fix(self, workflow_id: str, changes: List[str]) -> None:
        """Helper para notificar evento de fix."""
        event = WorkflowEvent(
            event_type="fix",
            workflow_id=workflow_id,
            data={"changes_count": len(changes), "changes": changes}
        )
        self.notify(event)

    def notify_estimate(self, workflow_id: str, estimate_data: Dict[str, Any]) -> None:
        """Helper para notificar evento de estimación."""
        event = WorkflowEvent(
            event_type="estimate",
            workflow_id=workflow_id,
            data=estimate_data
        )
        self.notify(event)

    def notify_error(self, workflow_id: str, error_message: str) -> None:
        """Helper para notificar evento de error."""
        event = WorkflowEvent(
            event_type="error",
            workflow_id=workflow_id,
            data={"error": error_message}
        )
        self.notify(event)

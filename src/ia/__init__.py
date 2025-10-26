# src/ia/__init__.py
"""
Módulo de IA para el sistema de orquestación de workflows.

Componentes principales:
- Providers: Implementaciones de diferentes proveedores de IA (Strategy Pattern)
- Handlers: Cadena de responsabilidad para procesamiento de sugerencias
- Commands: Comandos para operaciones de fix
- Observers: Observadores para notificaciones de cambios
- Services: Servicios de optimización y estimación
"""

from .providers import IAProviderStrategy, MockIAProvider, GeminiProvider
from .factory import IAProviderFactory

__all__ = [
    "IAProviderStrategy",
    "MockIAProvider",
    "GeminiProvider",
    "IAProviderFactory",
]

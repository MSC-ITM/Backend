# src/ia/factory.py
"""
Factory Pattern: Creación de proveedores de IA.

Permite crear diferentes proveedores según configuración.
"""
import os
from typing import Optional
from .providers import IAProviderStrategy, MockIAProvider, GeminiProvider, OpenAIProvider


class IAProviderFactory:
    """
    Factory para crear instancias de proveedores de IA.

    Utiliza variables de entorno para determinar qué proveedor usar.
    """

    @staticmethod
    def create_provider(
        provider_type: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> IAProviderStrategy:
        """
        Crea un proveedor de IA basado en el tipo especificado.

        Args:
            provider_type: Tipo de proveedor ("mock", "openai"). Si es None, lee de IA_PROVIDER env var
            api_key: API key para el proveedor (solo para OpenAI)
            **kwargs: Argumentos adicionales para el proveedor

        Returns:
            Instancia del proveedor de IA

        Raises:
            ValueError: Si el tipo de proveedor no es válido
        """
        # Determinar tipo de proveedor
        if provider_type is None:
            provider_type = os.getenv("IA_PROVIDER", "mock").lower()
        else:
            provider_type = provider_type.lower()

        # Crear proveedor según tipo
        if provider_type == "mock":
            return MockIAProvider()

        elif provider_type == "gemini":
            model = kwargs.get("model") or os.getenv("GEMINI_MODEL", "gemini-pro")
            return GeminiProvider(api_key=api_key, model=model)

        elif provider_type == "openai":
            model = kwargs.get("model") or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            return OpenAIProvider(api_key=api_key, model=model)

        else:
            raise ValueError(
                f"Tipo de proveedor desconocido: {provider_type}. "
                f"Tipos válidos: 'mock', 'gemini', 'openai'"
            )

    @staticmethod
    def create_from_config() -> IAProviderStrategy:
        """
        Crea un proveedor de IA basado completamente en variables de entorno.

        Variables de entorno utilizadas:
        - IA_PROVIDER: Tipo de proveedor ("mock", "gemini" o "openai")
        - GEMINI_API_KEY: API key de Google AI Studio (requerido si IA_PROVIDER=gemini) o OpenAI
        - GEMINI_MODEL: Modelo de Gemini a usar (default: gemini-pro)
        - OPENAI_API_KEY: API key de OpenAI (opcional, puede usar GEMINI_API_KEY)
        - OPENAI_MODEL: Modelo de OpenAI a usar (default: gpt-3.5-turbo)

        Returns:
            Instancia del proveedor configurado
        """
        return IAProviderFactory.create_provider()

    @staticmethod
    def get_available_providers() -> list[str]:
        """
        Retorna lista de proveedores disponibles.

        Returns:
            Lista de nombres de proveedores
        """
        return ["mock", "gemini", "openai"]

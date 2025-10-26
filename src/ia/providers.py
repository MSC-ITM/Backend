# src/ia/providers.py
"""
Strategy Pattern: Diferentes proveedores de IA.

Permite intercambiar entre Mock, OpenAI u otros proveedores sin cambiar el código cliente.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from copy import deepcopy
import os
import json


class IAProviderStrategy(ABC):
    """Interfaz común para todos los proveedores de IA."""

    @abstractmethod
    def suggest(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera sugerencias para mejorar un workflow.

        Args:
            definition: Definición del workflow a analizar

        Returns:
            Dict con estructura:
            {
                "suggested_changes": List[Dict],
                "confidence": float,
                "rationale": str
            }
        """
        pass

    @abstractmethod
    def fix(self, definition: Dict[str, Any], logs: Union[str, List[str], None]) -> Dict[str, Any]:
        """
        Aplica correcciones a un workflow basándose en errores.

        Args:
            definition: Definición del workflow a corregir
            logs: Logs de error (opcional)

        Returns:
            Dict con estructura:
            {
                "patched_definition": Dict,
                "notes": List[str]
            }
        """
        pass

    @abstractmethod
    def estimate(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estima tiempo, costo y complejidad de un workflow.

        Args:
            definition: Definición del workflow a estimar

        Returns:
            Dict con estructura:
            {
                "estimated_time_seconds": int,
                "estimated_cost_usd": float,
                "complexity_score": float,
                "breakdown": List[Dict],
                "assumptions": List[str],
                "confidence": float
            }
        """
        pass


class MockIAProvider(IAProviderStrategy):
    """
    Proveedor mock determinístico para testing.

    Implementa reglas simples y predecibles sin llamadas externas.
    """

    _DEFAULT_CONFIDENCE = 0.66
    _DEFAULT_TIMEOUT_SEC = 30

    def suggest(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Genera sugerencias determinísticas basadas en reglas simples."""
        suggestions: List[Dict[str, Any]] = []

        # Sugerir timeout para GET sin timeout
        for idx, step in enumerate(definition.get("steps", [])):
            if step.get("type") == "HTTPS GET Request":
                args = step.get("args", {}) or {}
                if "timeout" not in args:
                    suggestions.append({
                        "op": "add_arg",
                        "target_step_index": idx,
                        "arg": {"timeout": self._DEFAULT_TIMEOUT_SEC},
                        "reason": "Definir timeout para tráfico HTTP predecible.",
                    })

        # Sugerir nodo de salida si no existe
        if not any(s.get("type") in ("Save to Database", "Mock Notification")
                   for s in definition.get("steps", [])):
            suggestions.append({
                "op": "append_step",
                "step": {"type": "Mock Notification", "args": {"channel": "log"}},
                "reason": "Asegurar un paso de salida para observabilidad.",
            })

        return {
            "suggested_changes": suggestions,
            "confidence": self._DEFAULT_CONFIDENCE,
            "rationale": "Sugerencias básicas para robustez (timeout) y salida observable.",
        }

    def fix(self, definition: Dict[str, Any], logs: Union[str, List[str], None]) -> Dict[str, Any]:
        """Aplica correcciones determinísticas."""
        patched = deepcopy(definition)
        notes: List[str] = []

        # Normalizar logs
        norm_logs: List[str]
        if logs is None:
            norm_logs = []
        elif isinstance(logs, str):
            norm_logs = [logs]
        else:
            norm_logs = [str(x) for x in logs]

        # Agregar timeout a HTTPS GET Request
        for step in patched.get("steps", []):
            if step.get("type") == "HTTPS GET Request":
                args = step.setdefault("args", {})
                if "timeout" not in args:
                    args["timeout"] = self._DEFAULT_TIMEOUT_SEC
                    notes.append("Se agregó timeout a HTTPS GET Request.")

        # Asegurar nodo de salida
        has_output = any(s.get("type") in ("Save to Database", "Mock Notification")
                         for s in patched.get("steps", []))
        if not has_output:
            patched.setdefault("steps", []).append(
                {"type": "Mock Notification", "args": {"channel": "log"}}
            )
            notes.append("Se agregó paso de salida (Mock Notification).")

        if norm_logs:
            notes.append(f"Se procesaron {len(norm_logs)} líneas de logs.")

        return {
            "patched_definition": patched,
            "notes": notes,
        }

    def estimate(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula estimación determinística basada en tipos de pasos."""
        steps: List[Dict[str, Any]] = list(definition.get("steps", []))

        # Pesos por tipo de paso
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
        breakdown = []

        for idx, s in enumerate(steps):
            t = s.get("type", "")
            step_time = time_per_type.get(t, 1)
            step_cost = cost_per_type.get(t, 0.0001)

            est_time += step_time
            est_cost += step_cost

            breakdown.append({
                "step_index": idx,
                "type": t,
                "time": float(step_time),
                "cost": float(step_cost)
            })

        # Calcular complejidad basada en número de pasos y dependencias
        complexity_score = min(1.0, len(steps) * 0.15)

        return {
            "estimated_time_seconds": int(est_time),
            "estimated_cost_usd": float(round(est_cost, 6)),
            "complexity_score": complexity_score,
            "breakdown": breakdown,
            "assumptions": [
                "Estimación basada en reglas determinísticas por tipo de paso.",
                "No incluye latencias de red ni costos externos.",
            ],
            "confidence": 0.75
        }


class GeminiProvider(IAProviderStrategy):
    """
    Proveedor que usa Google Gemini para análisis inteligente de workflows.

    Usa Google AI Studio API (gratis con límites generosos).

    Características:
    - Análisis semántico de workflows
    - Sugerencias contextuales
    - Correcciones inteligentes basadas en errores
    - Estimaciones basadas en patrones aprendidos
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-pro"):
        """
        Inicializa el proveedor de Gemini.

        Args:
            api_key: API key de Google AI Studio (si no se provee, se lee de GEMINI_API_KEY)
            model: Modelo a usar (por defecto gemini-pro)
        """
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "El paquete 'google-generativeai' no está instalado. "
                "Ejecuta: pip install google-generativeai"
            )

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key de Gemini no encontrada. "
                "Configura la variable de entorno GEMINI_API_KEY o pasa api_key al constructor."
            )

        self.model_name = model
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model)

    def _call_gemini(self, system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
        """
        Realiza llamada a Gemini API con reintentos.

        Args:
            system_prompt: Prompt del sistema
            user_prompt: Prompt del usuario
            max_retries: Número máximo de intentos (default: 3)

        Returns:
            Respuesta de texto de Gemini

        Raises:
            RuntimeError: Si todos los intentos fallan
        """
        import google.generativeai as genai
        import time

        # Combinar system y user prompt para Gemini
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        # Configuración de seguridad más permisiva
        safety_settings = {
            genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    full_prompt,
                    generation_config={
                        "temperature": 0.7,
                        "top_p": 0.95,
                        "top_k": 40,
                        "max_output_tokens": 2048,
                    },
                    safety_settings=safety_settings
                )
                return response.text
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Esperar antes de reintentar (exponential backoff)
                    wait_time = 2 ** attempt  # 1s, 2s, 4s...
                    print(f"[GeminiProvider] Intento {attempt + 1}/{max_retries} falló: {str(e)}. Reintentando en {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"[GeminiProvider] Todos los {max_retries} intentos fallaron.")

        raise RuntimeError(f"Error llamando a Gemini API después de {max_retries} intentos: {str(last_error)}")

    def _extract_json(self, text: str) -> str:
        """Extrae JSON limpio de una respuesta que puede contener markdown."""
        import re

        # Intentar extraer JSON de bloques de código markdown
        json_block_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if json_block_match:
            return json_block_match.group(1).strip()

        # Si no hay bloques de código, buscar objetos JSON directamente
        json_object_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_object_match:
            return json_object_match.group(0).strip()

        # Si no se encuentra JSON, devolver el texto original
        return text.strip()

    def suggest(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Genera sugerencias inteligentes usando Gemini."""

        system_prompt = """Eres un experto en optimización de workflows y orquestación de procesos.
Analiza la definición del workflow y proporciona sugerencias para mejorar:
- Eficiencia (reducir tiempo de ejecución)
- Robustez (manejar errores)
- Costos (optimizar recursos)
- Orden lógico de operaciones

Responde SIEMPRE en formato JSON con esta estructura:
{
    "suggested_changes": [
        {
            "op": "add_arg|append_step|reorder|remove_step",
            "target_step_index": <índice del paso afectado, si aplica>,
            "arg": <objeto con argumentos si op=add_arg>,
            "step": <objeto con paso completo si op=append_step>,
            "reason": "<explicación clara de por qué sugieres este cambio>"
        }
    ],
    "confidence": <float entre 0 y 1>,
    "rationale": "<explicación general de las sugerencias>"
}"""

        user_prompt = f"""Analiza este workflow y sugiere mejoras:

Workflow:
{json.dumps(definition, indent=2)}

Tipos de pasos disponibles:
- HTTPS GET Request: Obtiene datos de una URL
- Validate CSV File: Valida formato CSV
- Simple Transform: Transforma datos
- Save to Database: Guarda en base de datos
- Mock Notification: Envía notificación

Proporciona sugerencias concretas y accionables."""

        response_text = self._call_gemini(system_prompt, user_prompt)
        clean_json = self._extract_json(response_text)
        return json.loads(clean_json)

    def fix(self, definition: Dict[str, Any], logs: Union[str, List[str], None]) -> Dict[str, Any]:
        """Aplica correcciones inteligentes basadas en logs de error."""

        # Normalizar logs
        norm_logs: List[str]
        if logs is None:
            norm_logs = []
        elif isinstance(logs, str):
            norm_logs = [logs]
        else:
            norm_logs = [str(x) for x in logs]

        system_prompt = """Eres un experto en debugging y corrección de workflows.
Analiza la definición del workflow y los logs de error, luego proporciona una versión corregida.

Reglas comunes a aplicar:
1. HTTPS GET Request debe tener timeout (valor recomendado: 10-30 segundos)
2. Siempre debe haber un paso de salida (Save to Database o Mock Notification)
3. Validate CSV File debe ejecutarse ANTES de Simple Transform
4. Los parámetros requeridos deben estar presentes

Responde SIEMPRE en formato JSON con esta estructura:
{
    "patched_definition": <definición completa corregida>,
    "notes": ["<descripción de cambio 1>", "<descripción de cambio 2>", ...]
}"""

        logs_text = "\n".join(norm_logs) if norm_logs else "No hay logs de error disponibles."

        user_prompt = f"""Corrige este workflow basándote en las reglas y los logs:

Workflow original:
{json.dumps(definition, indent=2)}

Logs de error:
{logs_text}

Proporciona la versión corregida del workflow."""

        response_text = self._call_gemini(system_prompt, user_prompt)
        clean_json = self._extract_json(response_text)
        return json.loads(clean_json)

    def estimate(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Estima tiempo, costo y complejidad usando IA."""

        system_prompt = """Eres un experto en estimación de rendimiento de workflows.
Analiza la definición del workflow y proporciona estimaciones precisas.

Considera:
- Tipo y número de operaciones
- Dependencias entre pasos
- Operaciones costosas (I/O, red, base de datos)
- Complejidad del grafo de ejecución

Responde SIEMPRE en formato JSON con esta estructura:
{
    "estimated_time_seconds": <tiempo total estimado en segundos>,
    "estimated_cost_usd": <costo estimado en USD>,
    "complexity_score": <float entre 0 y 1>,
    "breakdown": [
        {
            "step_index": <índice>,
            "type": "<tipo de paso>",
            "time": <segundos>,
            "cost": <USD>
        }
    ],
    "assumptions": ["<asunción 1>", "<asunción 2>", ...],
    "confidence": <float entre 0 y 1>
}"""

        user_prompt = f"""Estima el rendimiento de este workflow:

Workflow:
{json.dumps(definition, indent=2)}

Costos de referencia (ajusta según análisis):
- HTTPS GET Request: ~2-5 segundos, ~$0.0005
- Validate CSV File: ~1-2 segundos, ~$0.0002
- Simple Transform: ~1-3 segundos, ~$0.0002
- Save to Database: ~2-4 segundos, ~$0.0005
- Mock Notification: ~0 segundos, ~$0

Proporciona estimaciones detalladas."""

        response_text = self._call_gemini(system_prompt, user_prompt)
        clean_json = self._extract_json(response_text)
        return json.loads(clean_json)

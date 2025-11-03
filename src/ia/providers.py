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

        system_prompt = """You are a workflow optimization expert.
Analyze workflow definitions and suggest improvements for efficiency, robustness and organization.

Response format (JSON):
{
    "suggested_changes": [],
    "confidence": 0.8,
    "rationale": "explanation"
}"""

        # Simplificar la definición para evitar bloqueos
        nodes_count = len(definition.get("nodes", []))
        node_types = [n.get("type", "unknown") for n in definition.get("nodes", [])]

        user_prompt = f"""Analyze this data processing workflow:

Nodes: {nodes_count}
Types: {', '.join(node_types)}

Available node types:
- http_get: HTTP requests (needs url, optional timeout)
- validate_csv: CSV validation (needs path)
- transform_simple: Data transformation (needs table_name)
- save_db: Save to SQLite database
- notify_mock: Send notifications (needs channel and message)

Best practices:
- Add timeout to http_get nodes
- Validate before transform
- Include notification at end
- Use descriptive table names

Provide concrete suggestions in JSON format."""

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

ARQUITECTURA DEL SISTEMA:
- Workflows compuestos por nodos (nodes) con dependencias (depends_on)
- Cada nodo tiene: id, type, params, depends_on
- Los nodos se ejecutan en orden según dependencias
- El contexto se comparte entre nodos para pasar datos

REGLAS DE CORRECCIÓN:
1. http_get debe tener:
   - url (requerido)
   - timeout opcional pero recomendado (10-30 segundos)

2. validate_csv debe tener:
   - path (requerido, ruta del archivo CSV)
   - columns (opcional pero recomendado)
   - Debe ejecutarse ANTES de transform_simple si hay transformaciones

3. transform_simple debe tener:
   - table_name (requerido)
   - format opcional ("csv" o "sql")
   - Debe depender de un nodo que provea datos (http_get o validate_csv)

4. save_db debe tener:
   - path opcional
   - Debe depender de transform_simple para recibir SQL statements

5. notify_mock debe tener:
   - channel (requerido, usar "desknotification")
   - message (requerido)
   - Usualmente al final del workflow para confirmar éxito

PATRONES COMUNES DE ERRORES:
- Falta timeout en http_get → Agregar timeout de 30 segundos
- Sin nodo de salida → Agregar notify_mock al final
- transform_simple sin table_name → Agregar nombre de tabla descriptivo
- Orden incorrecto de nodos → Ajustar depends_on
- Falta channel en notify_mock → Agregar "desknotification"

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

        system_prompt = """You are a workflow performance estimation expert.
Analyze workflows and provide time, cost and complexity estimates.

Response format (JSON):
{
    "estimated_time_seconds": 10,
    "estimated_cost_usd": 0.001,
    "complexity_score": 0.5,
    "breakdown": [],
    "assumptions": [],
    "confidence": 0.8
}"""

        # Simplificar para evitar bloqueos
        nodes_count = len(definition.get("nodes", []))
        node_types = [n.get("type", "unknown") for n in definition.get("nodes", [])]

        user_prompt = f"""Estimate performance for this workflow:

Node count: {nodes_count}
Node types: {', '.join(node_types)}

System: Python worker with SQLite, sequential execution

Reference times (adjust as needed):
- http_get: 2-10 sec
- validate_csv: 1-5 sec
- transform_simple: 2-15 sec
- save_db: 1-8 sec
- notify_mock: <1 sec

Provide detailed estimates in JSON format."""

        response_text = self._call_gemini(system_prompt, user_prompt)
        clean_json = self._extract_json(response_text)
        return json.loads(clean_json)


class OpenAIProvider(IAProviderStrategy):
    """Proveedor que usa OpenAI para análisis inteligente de workflows."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("El paquete 'openai' no está instalado. Ejecuta: pip install openai")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("API key de OpenAI no encontrada.")

        self.model = model
        self.client = OpenAI(api_key=self.api_key)

    def _call_openai(self, system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
        import time
        last_error = None
        for attempt in range(max_retries):
            try:
                # Preparar parámetros base
                params = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                }

                # gpt-5-nano solo soporta temperature=1 (valor por defecto)
                # Otros modelos pueden usar temperature personalizada
                if "gpt-5-nano" not in self.model.lower():
                    params["temperature"] = 0.7

                # gpt-5-nano y modelos más nuevos usan max_completion_tokens
                # gpt-5-nano es un reasoning model que usa tokens para "pensar"
                # Necesita tokens adicionales: reasoning_tokens + output_tokens
                # Modelos antiguos usan max_tokens
                if "gpt-5" in self.model or "gpt-4" in self.model:
                    # Para reasoning models como gpt-5-nano, necesitamos más tokens
                    # ya que usa tokens para razonamiento interno + respuesta
                    params["max_completion_tokens"] = 8192
                else:
                    params["max_tokens"] = 2048

                response = self.client.chat.completions.create(**params)
                content = response.choices[0].message.content or ""

                if not content:
                    print(f"[OpenAIProvider._call_openai] WARNING: Empty content from OpenAI")
                    print(f"[OpenAIProvider._call_openai] Response object: {response}")

                print(f"[OpenAIProvider._call_openai] Received {len(content)} characters")
                return content
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"[OpenAIProvider] Intento {attempt + 1}/{max_retries} falló: {str(e)}. Reintentando en {wait_time}s...")
                    time.sleep(wait_time)
        raise RuntimeError(f"Error llamando a OpenAI API: {str(last_error)}")

    def _extract_json(self, text: str) -> str:
        """Extrae JSON de la respuesta de OpenAI, manejando varios formatos."""
        import re

        if not text or not text.strip():
            print(f"[OpenAIProvider._extract_json] WARNING: Empty response text")
            return "{}"

        # Intento 1: Buscar bloque de código JSON (```json ... ```)
        json_block_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if json_block_match:
            extracted = json_block_match.group(1).strip()
            print(f"[OpenAIProvider._extract_json] Found JSON code block")
            return extracted

        # Intento 2: Buscar desde la primera llave hasta la última (greedy)
        # Esto captura objetos JSON con anidamiento profundo
        first_brace = text.find('{')
        if first_brace != -1:
            # Buscar desde la primera { hasta la última } usando conteo de llaves
            brace_count = 0
            start_pos = first_brace

            for i in range(first_brace, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Encontramos el cierre del objeto principal
                        extracted = text[start_pos:i+1].strip()
                        print(f"[OpenAIProvider._extract_json] Found complete JSON object ({len(extracted)} chars)")
                        return extracted

        # Intento 3: Si no se pudo balancear, buscar con greedy match
        greedy_match = re.search(r'\{.*\}', text, re.DOTALL)
        if greedy_match:
            extracted = greedy_match.group(0).strip()
            print(f"[OpenAIProvider._extract_json] Found JSON with greedy pattern")
            return extracted

        # Intento 4: Si no hay JSON, retornar el texto completo
        print(f"[OpenAIProvider._extract_json] No JSON pattern found, returning text as-is")
        return text.strip()

    def suggest(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Genera sugerencias inteligentes usando OpenAI."""

        system_prompt = """Eres un experto en optimización de workflows de procesamiento de datos.

ARQUITECTURA DEL SISTEMA:
- Los workflows están compuestos por nodos que se ejecutan secuencialmente según dependencias
- Cada nodo tiene: id, type, params, y depends_on (array de IDs de nodos)
- Los datos fluyen entre nodos a través de un contexto de ejecución compartido
- El sistema usa Python Worker + FastAPI + SQLite

TIPOS DE NODOS DISPONIBLES:
1. http_get - Solicitudes HTTP GET
   Params requeridos: url (string)
   Params opcionales: timeout (integer, segundos)

2. validate_csv - Validación de estructura CSV
   Params requeridos: path (string, ruta del archivo)
   Params opcionales: columns (array de nombres de columnas)

3. transform_simple - Transformación de datos a formato SQL
   Params requeridos: table_name (string)
   Params opcionales: format (string: "csv" o "sql")

4. save_db - Guardar datos en SQLite
   Params opcionales: path (string, ruta de BD)

5. notify_mock - Enviar notificaciones
   Params requeridos: channel (string), message (string)

REGLAS DE OPTIMIZACIÓN - SOLO SUGIERE SI APLICA:

Para http_get:
- Si falta timeout: Agrega timeout de 10-30 segundos
- Si la URL es lenta: Cambia a URL más rápida de la misma API
- Si es API de Pokemon: Prueba con un Pokemon diferente (ej: pikachu, ditto, bulbasaur)

Para validate_csv:
- Si el archivo es muy grande: Cambia a un CSV más pequeño
- Si falta validación de columnas: Agrégala solo si es crítico

Para transform_simple:
- Si falta table_name: Agrega nombre descriptivo
- Si el table_name es genérico: Cámbialo a uno más específico

Para save_db:
- Generalmente está bien, solo optimiza si hay un problema evidente

Para notify_mock:
- Si el mensaje es muy largo: Acórtalo
- Si falta notificación al final: Agrégala

IMPORTANTE:
- NO agregues nodos nuevos a menos que falten completamente
- NO sugieras cambios si el workflow ya está bien optimizado
- Si el workflow está optimizado, retorna suggested_changes vacío
- Todas las razones deben estar en ESPAÑOL

FORMATO DE RESPUESTA (JSON estricto):
{
    "suggested_changes": [
        {
            "op": "add_arg",
            "target_step_index": 0,
            "arg_name": "timeout",
            "arg_value": 20,
            "reason": "Agregar timeout para evitar bloqueos en la solicitud HTTP"
        },
        {
            "op": "modify_arg",
            "target_step_index": 0,
            "arg_name": "url",
            "arg_value": "https://pokeapi.co/api/v2/pokemon/pikachu",
            "reason": "Cambiar a un Pokemon diferente para mejorar rendimiento"
        }
    ],
    "confidence": 0.85,
    "rationale": "Explicación breve en ESPAÑOL de la estrategia de optimización"
}

IMPORTANTE SOBRE arg_name:
- arg_name debe ser SOLO el nombre del parámetro: "url", "timeout", "message", etc.
- NO uses "params.url" ni notación de punto
- Ejemplos correctos: "timeout", "url", "message", "table_name"
- Ejemplos incorrectos: "params.timeout", "params.url"

OPERACIONES DISPONIBLES:
- "add_arg": Agregar parámetro faltante
- "modify_arg": Modificar valor de parámetro existente"""

        # Enviar la definición completa del workflow
        nodes = definition.get("nodes", [])
        nodes_summary = []
        for i, node in enumerate(nodes):
            nodes_summary.append({
                "index": i,
                "id": node.get("id"),
                "type": node.get("type"),
                "params": node.get("params", {}),
                "depends_on": node.get("depends_on", [])
            })

        user_prompt = f"""Analiza este workflow y proporciona sugerencias de optimización PRÁCTICAS y REALISTAS:

NODOS DEL WORKFLOW:
{json.dumps(nodes_summary, indent=2)}

ANALIZA CUIDADOSAMENTE:
1. ¿Falta timeout en nodos http_get? → Si sí, agregar timeout de 15-20 segundos
2. ¿La URL de http_get es lenta? → Si es API de Pokemon, sugerir cambiar a un Pokemon más rápido
3. ¿Falta table_name o es genérico en transform_simple? → Sugerir nombre descriptivo
4. ¿El mensaje de notify_mock es muy largo? → Sugerir acortar
5. ¿El CSV de validate_csv es muy grande? → Sugerir usar archivo más pequeño

IMPORTANTE:
- Si el workflow YA está bien optimizado (tiene timeout, buenos nombres, etc.), retorna suggested_changes VACÍO []
- NO inventes nodos que no existen
- NO agregues nodos innecesarios
- SOLO modifica parámetros de nodos existentes
- Todas las razones en ESPAÑOL

Proporciona respuesta en el formato JSON especificado."""

        try:
            response_text = self._call_openai(system_prompt, user_prompt)
            print(f"[OpenAIProvider.suggest] Raw response: {response_text[:500]}...")

            clean_json = self._extract_json(response_text)
            print(f"[OpenAIProvider.suggest] Extracted JSON: {clean_json[:300]}...")

            result = json.loads(clean_json)

            # Validar estructura de respuesta
            if "suggested_changes" not in result:
                result["suggested_changes"] = []
            if "confidence" not in result:
                result["confidence"] = 0.5 if result.get("suggested_changes") else 0.9
            if "rationale" not in result:
                if not result.get("suggested_changes"):
                    result["rationale"] = "El workflow ya está optimizado. No se detectaron mejoras adicionales."
                else:
                    result["rationale"] = "Optimizaciones sugeridas aplicadas"

            print(f"[OpenAIProvider.suggest] Final result: {len(result.get('suggested_changes', []))} suggestions")
            return result

        except json.JSONDecodeError as e:
            print(f"[OpenAIProvider.suggest] JSON parse error: {str(e)}")
            print(f"[OpenAIProvider.suggest] Failed to parse: {clean_json}")
            # Retornar respuesta por defecto en caso de error
            return {
                "suggested_changes": [],
                "confidence": 0.0,
                "rationale": f"Error parsing AI response: {str(e)}"
            }
        except Exception as e:
            print(f"[OpenAIProvider.suggest] Unexpected error: {str(e)}")
            raise

    def fix(self, definition: Dict[str, Any], logs: Union[str, List[str], None]) -> Dict[str, Any]:
        """Aplica correcciones inteligentes basadas en logs de error usando OpenAI."""

        # Normalizar logs
        norm_logs: List[str] = []
        if logs:
            norm_logs = [logs] if isinstance(logs, str) else [str(x) for x in logs]

        system_prompt = """You are a workflow debugging and repair expert for a data processing system.

SYSTEM ARCHITECTURE:
- Workflows composed of nodes executing sequentially based on dependencies
- Each node has: id, type, params, depends_on (array of node IDs)
- Data flows between nodes through shared execution context
- System: Python Worker + FastAPI + SQLite

AVAILABLE NODE TYPES AND REQUIRED PARAMETERS:

1. http_get - HTTP GET requests
   REQUIRED: url (string)
   OPTIONAL: timeout (integer, seconds, default: 10)
   Common errors: Missing url, no timeout causing hangs, invalid URL format

2. validate_csv - CSV validation
   REQUIRED: path (string, file path to CSV)
   OPTIONAL: columns (array of expected column names)
   Common errors: Missing path, file not found, incorrect path format

3. transform_simple - Data transformation to SQL
   REQUIRED: table_name (string)
   OPTIONAL: format (string: "csv" or "sql")
   Common errors: Missing table_name, executing before data is available, no depends_on

4. save_db - Save to SQLite database
   OPTIONAL: path (string, database file path)
   Common errors: Executing before transform_simple, missing depends_on

5. notify_mock - Send notifications
   REQUIRED: channel (string, must be "desknotification"), message (string)
   Common errors: Missing channel or message, wrong channel value

COMMON ERROR PATTERNS AND FIXES:

1. Missing required parameters
   - Fix: Add the required parameter with appropriate default value

2. Timeout errors in http_get
   - Fix: Add or increase timeout parameter (recommend 30 seconds)

3. File not found errors
   - Fix: Verify path parameter, ensure file exists or adjust path

4. Dependency errors (node executes before data is ready)
   - Fix: Add proper depends_on array to ensure correct execution order

5. Missing validation
   - Fix: Add validate_csv node before transform_simple

6. Missing notification
   - Fix: Add notify_mock node at end with channel="desknotification"

7. Type errors in parameters
   - Fix: Ensure correct parameter types (timeout as integer, not string)

RESPONSE FORMAT (strict JSON):
{
    "patched_definition": {
        "nodes": [
            {
                "id": "node_id",
                "type": "node_type",
                "params": {"param": "value"},
                "depends_on": ["previous_node_id"]
            }
        ]
    },
    "notes": [
        "Description of fix 1: Added timeout=30 to http_get node to prevent hanging",
        "Description of fix 2: Added validate_csv before transform_simple"
    ]
}

IMPORTANT:
- Return the COMPLETE corrected workflow definition in patched_definition
- Include ALL nodes, even if only some were modified
- Maintain correct node IDs and dependencies
- Each note should clearly describe what was fixed and why
- If no errors detected, return original definition with note explaining it's already correct"""

        logs_text = "\n".join(norm_logs) if norm_logs else "No error logs provided. Perform general workflow health check."

        # Preparar definición del workflow para el prompt
        nodes = definition.get("nodes", [])
        workflow_json = json.dumps({"nodes": nodes}, indent=2)

        user_prompt = f"""Analyze and fix this workflow based on the error logs:

CURRENT WORKFLOW DEFINITION:
{workflow_json}

ERROR LOGS:
{logs_text}

REPAIR INSTRUCTIONS:
1. Identify the root cause of errors from the logs
2. Apply appropriate fixes based on error patterns listed above
3. Ensure all required parameters are present and correct
4. Verify proper node execution order (depends_on arrays)
5. Add missing best practices (timeouts, validation, notifications)
6. Return the COMPLETE corrected workflow with detailed notes

Provide the repaired workflow in the specified JSON format."""

        response_text = self._call_openai(system_prompt, user_prompt)
        clean_json = self._extract_json(response_text)
        result = json.loads(clean_json)

        # Validar estructura de respuesta
        if "patched_definition" not in result:
            result["patched_definition"] = definition
        if "notes" not in result:
            result["notes"] = ["No se encontraron errores para corregir"]

        return result

    def estimate(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Estima tiempo, costo y complejidad usando OpenAI."""

        system_prompt = """You are a workflow performance estimation expert for a data processing system.

SYSTEM ARCHITECTURE:
- Python-based Worker with FastAPI backend
- SQLite database for data persistence
- Sequential node execution based on dependencies
- Each node runs in same process, sharing context
- Network I/O is the primary bottleneck

AVAILABLE NODE TYPES AND PERFORMANCE CHARACTERISTICS:

1. http_get - HTTP GET requests
   Execution time: 2-10 seconds (depends on API response time)
   Variability: HIGH (network dependent)
   Cost factors: Network latency, API rate limits
   Typical time: 5 seconds
   Complexity contribution: Medium

2. validate_csv - CSV validation
   Execution time: 1-5 seconds (depends on file size)
   Variability: MEDIUM (file size dependent)
   Cost factors: Number of rows, columns to validate
   Typical time: 2 seconds
   Complexity contribution: Low

3. transform_simple - Data transformation
   Execution time: 2-15 seconds (depends on data volume)
   Variability: HIGH (data volume dependent)
   Cost factors: Rows to transform, complexity of transformations
   Typical time: 8 seconds
   Complexity contribution: Medium-High

4. save_db - Save to SQLite
   Execution time: 1-8 seconds (depends on data volume)
   Variability: MEDIUM (data volume dependent)
   Cost factors: Number of SQL statements, database size
   Typical time: 4 seconds
   Complexity contribution: Medium

5. notify_mock - Send notifications
   Execution time: <1 second
   Variability: LOW
   Cost factors: Minimal
   Typical time: 0.5 seconds
   Complexity contribution: Very Low

ESTIMATION GUIDELINES:

Time Calculation:
- Sum individual node times
- Add 10% overhead for context switching and orchestration
- Sequential execution (no parallelization)
- Account for dependencies (nodes wait for dependencies)

Cost Calculation (in USD):
- Primarily computational cost (negligible for this system)
- Base cost: $0.0001 per node
- http_get: +$0.001 (network cost)
- transform_simple: +$0.002 (CPU intensive)
- save_db: +$0.001 (I/O cost)
- Others: +$0.0001 (minimal)

Complexity Score (0.0 to 1.0):
- 0.0-0.2: Simple (1-2 nodes, all low complexity types)
- 0.2-0.4: Low (3-4 nodes, mostly low complexity)
- 0.4-0.6: Medium (5-7 nodes, mixed complexity)
- 0.6-0.8: High (8-10 nodes, includes high complexity)
- 0.8-1.0: Very High (10+ nodes, multiple high complexity, complex dependencies)

Factors increasing complexity:
- Number of nodes (more = higher)
- Deep dependency chains (more = higher)
- Data transformation nodes (higher contribution)
- Missing validation or error handling (higher risk)

RESPONSE FORMAT (strict JSON):
{
    "estimated_time_seconds": 25,
    "estimated_cost_usd": 0.005,
    "complexity_score": 0.45,
    "breakdown": [
        {
            "step_index": 0,
            "type": "http_get",
            "time": 5.0,
            "cost": 0.0011
        },
        {
            "step_index": 1,
            "type": "validate_csv",
            "time": 2.0,
            "cost": 0.0001
        }
    ],
    "assumptions": [
        "Assuming average API response time of 5 seconds",
        "Assuming CSV file with ~1000 rows",
        "Sequential execution with no parallel processing"
    ],
    "confidence": 0.75
}

IMPORTANT:
- estimated_time_seconds: Total workflow execution time in seconds
- estimated_cost_usd: Total cost in US dollars (usually very small)
- complexity_score: Float between 0.0 and 1.0
- breakdown: Array with estimate for EACH node (use step_index from nodes array)
- assumptions: Array of strings explaining estimation assumptions
- confidence: Float between 0.0 and 1.0 indicating estimate reliability"""

        # Preparar información detallada de los nodos
        nodes = definition.get("nodes", [])
        nodes_detail = []
        for i, node in enumerate(nodes):
            nodes_detail.append({
                "step_index": i,
                "id": node.get("id"),
                "type": node.get("type"),
                "params": node.get("params", {}),
                "depends_on": node.get("depends_on", [])
            })

        nodes_json = json.dumps(nodes_detail, indent=2)

        user_prompt = f"""Estimate the performance characteristics of this workflow:

WORKFLOW NODES:
{nodes_json}

ESTIMATION REQUIREMENTS:
1. Calculate total execution time (sum of all nodes + 10% overhead)
2. Estimate total cost based on node types
3. Calculate complexity score based on node count, types, and dependencies
4. Provide detailed breakdown for EACH node with step_index, type, time, and cost
5. List key assumptions made in the estimation
6. Provide confidence score based on available information

Consider:
- Sequential execution (nodes execute one after another based on depends_on)
- Network latency for http_get nodes
- Data volume impact on validate_csv, transform_simple, and save_db
- Dependency chain depth affects overall complexity
- Missing timeouts or validation increase risk

Provide detailed estimates in the specified JSON format with ALL required fields."""

        response_text = self._call_openai(system_prompt, user_prompt)
        clean_json = self._extract_json(response_text)
        result = json.loads(clean_json)

        # Validar y normalizar estructura de respuesta
        if "estimated_time_seconds" not in result:
            result["estimated_time_seconds"] = 10.0
        if "estimated_cost_usd" not in result:
            result["estimated_cost_usd"] = 0.001
        if "complexity_score" not in result:
            result["complexity_score"] = 0.5
        if "breakdown" not in result:
            result["breakdown"] = []
        if "assumptions" not in result:
            result["assumptions"] = ["Estimación basada en valores promedio"]
        if "confidence" not in result:
            result["confidence"] = 0.7

        # Asegurar que complexity_score esté en rango [0, 1]
        result["complexity_score"] = max(0.0, min(1.0, float(result["complexity_score"])))
        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))

        return result

# src/ia/commands.py
"""
Command Pattern: Comandos para operaciones de fix/corrección de workflows.

Cada comando encapsula una operación específica de corrección.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from copy import deepcopy


class FixCommand(ABC):
    """Comando base para operaciones de fix."""

    def __init__(self):
        self._executed = False
        self._change_description: str = ""

    @abstractmethod
    def execute(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta el comando sobre la definición del workflow.

        Args:
            definition: Definición del workflow a modificar

        Returns:
            Definición modificada
        """
        pass

    def get_change_description(self) -> str:
        """Retorna descripción del cambio realizado."""
        return self._change_description

    def was_executed(self) -> bool:
        """Retorna si el comando fue ejecutado."""
        return self._executed


class AddTimeoutCommand(FixCommand):
    """Comando para agregar timeout a HTTPS GET Requests."""

    def __init__(self, timeout: int = 10):
        super().__init__()
        self.timeout = timeout

    def execute(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Agrega timeout a todos los HTTPS GET Request que no lo tengan."""
        patched = deepcopy(definition)
        changes_made = False

        for step in patched.get("steps", []):
            if step.get("type") == "HTTPS GET Request":
                args = step.setdefault("args", {})
                if "timeout" not in args:
                    args["timeout"] = self.timeout
                    changes_made = True

        if changes_made:
            self._executed = True
            self._change_description = f"Se estableció timeout={self.timeout} en HTTPS GET Request."

        return patched


class AddOutputNodeCommand(FixCommand):
    """Comando para agregar nodo de salida si no existe."""

    def __init__(self, output_type: str = "Mock Notification"):
        super().__init__()
        self.output_type = output_type

    def execute(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Agrega nodo de salida si no existe uno."""
        patched = deepcopy(definition)

        has_output = any(
            s.get("type") in ("Save to Database", "Mock Notification")
            for s in patched.get("steps", [])
        )

        if not has_output:
            new_step = {"type": self.output_type, "args": {"channel": "log"}}
            patched.setdefault("steps", []).append(new_step)
            self._executed = True
            self._change_description = f"Se agregó paso de salida ({self.output_type})."

        return patched


class ReorderNodesCommand(FixCommand):
    """Comando para reordenar nodos según reglas lógicas."""

    def execute(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Reordena nodos para que Validate CSV File esté antes de Simple Transform."""
        patched = deepcopy(definition)
        steps_list = patched.get("steps", [])

        validate_idx = -1
        transform_idx = -1

        for i, step in enumerate(steps_list):
            step_type = step.get("type")
            if step_type == "Validate CSV File":
                validate_idx = i
            elif step_type == "Simple Transform":
                transform_idx = i

        # Si validate está después de transform, reordenar
        if validate_idx != -1 and transform_idx != -1 and validate_idx > transform_idx:
            temp_steps = deepcopy(steps_list)
            validate_step = temp_steps.pop(validate_idx)
            temp_steps.insert(transform_idx, validate_step)
            patched["steps"] = temp_steps

            self._executed = True
            self._change_description = "Se reordenó 'Validate CSV File' antes de 'Simple Transform'."

        return patched


class SetParameterCommand(FixCommand):
    """Comando genérico para establecer un parámetro en un paso específico."""

    def __init__(self, step_type: str, param_name: str, param_value: Any):
        super().__init__()
        self.step_type = step_type
        self.param_name = param_name
        self.param_value = param_value

    def execute(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Establece el parámetro en el paso especificado."""
        patched = deepcopy(definition)
        changes_made = False

        for step in patched.get("steps", []):
            if step.get("type") == self.step_type:
                args = step.setdefault("args", {})
                if self.param_name not in args:
                    args[self.param_name] = self.param_value
                    changes_made = True

        if changes_made:
            self._executed = True
            self._change_description = (
                f"Se estableció {self.param_name}={self.param_value} en {self.step_type}."
            )

        return patched


class RemoveInvalidStepsCommand(FixCommand):
    """Comando para remover pasos inválidos o malformados."""

    def __init__(self, valid_types: List[str]):
        super().__init__()
        self.valid_types = valid_types

    def execute(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Remueve pasos que no tienen tipo válido."""
        patched = deepcopy(definition)
        original_steps = patched.get("steps", [])

        valid_steps = [
            step for step in original_steps
            if step.get("type") in self.valid_types
        ]

        if len(valid_steps) < len(original_steps):
            patched["steps"] = valid_steps
            removed_count = len(original_steps) - len(valid_steps)
            self._executed = True
            self._change_description = f"Se removieron {removed_count} paso(s) inválido(s)."

        return patched


class FixCommandInvoker:
    """
    Invoker del patrón Command.

    Ejecuta una secuencia de comandos y recopila los cambios realizados.
    """

    def __init__(self):
        self._commands: List[FixCommand] = []

    def add_command(self, command: FixCommand) -> "FixCommandInvoker":
        """Agrega un comando a la lista de ejecución."""
        self._commands.append(command)
        return self

    def execute_all(self, definition: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
        """
        Ejecuta todos los comandos en secuencia.

        Args:
            definition: Definición inicial del workflow

        Returns:
            Tupla con (definición modificada, lista de descripciones de cambios)
        """
        current_definition = definition
        changes: List[str] = []

        for command in self._commands:
            current_definition = command.execute(current_definition)
            if command.was_executed():
                changes.append(command.get_change_description())

        return current_definition, changes

    def clear(self) -> None:
        """Limpia la lista de comandos."""
        self._commands.clear()


class FixCommandFactory:
    """Factory para crear comandos de fix comunes."""

    @staticmethod
    def create_standard_fixes() -> List[FixCommand]:
        """
        Crea la lista estándar de comandos de fix.

        Returns:
            Lista de comandos en el orden recomendado de ejecución
        """
        return [
            AddTimeoutCommand(timeout=10),
            ReorderNodesCommand(),
            AddOutputNodeCommand(),
        ]

    @staticmethod
    def create_basic_fixes() -> List[FixCommand]:
        """
        Crea una lista básica de comandos de fix.

        Returns:
            Lista de comandos esenciales
        """
        return [
            AddTimeoutCommand(timeout=10),
            AddOutputNodeCommand(),
        ]

    @staticmethod
    def create_validation_fixes() -> List[FixCommand]:
        """
        Crea comandos para validación y corrección de tipos.

        Returns:
            Lista de comandos de validación
        """
        valid_types = [
            "HTTPS GET Request",
            "Validate CSV File",
            "Simple Transform",
            "Save to Database",
            "Mock Notification"
        ]

        return [
            RemoveInvalidStepsCommand(valid_types),
            AddTimeoutCommand(timeout=10),
            ReorderNodesCommand(),
            AddOutputNodeCommand(),
        ]

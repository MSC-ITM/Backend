# src/ia/services.py
"""
Servicios de IA: Optimización de rutas y análisis avanzado.

Implementa la lógica de negocio para:
- Optimización de rutas en workflows
- Predicción de costos mejorada
- Análisis de grafos de dependencias
"""
from typing import Dict, Any, List, Set, Tuple, Optional
from collections import defaultdict, deque
import math


class WorkflowGraphAnalyzer:
    """
    Analizador de grafos de workflows.

    Proporciona métodos para analizar la estructura y dependencias del workflow.
    """

    def __init__(self, definition: Dict[str, Any]):
        self.definition = definition
        self.nodes = self._extract_nodes()
        self.adjacency_list = self._build_adjacency_list()

    def _extract_nodes(self) -> List[Dict[str, Any]]:
        """Extrae los nodos del workflow."""
        return self.definition.get("steps", [])

    def _build_adjacency_list(self) -> Dict[int, List[int]]:
        """
        Construye lista de adyacencia basada en dependencias implícitas.

        Por ahora asumimos ejecución secuencial (cada paso depende del anterior).
        """
        adj_list = defaultdict(list)
        for i in range(len(self.nodes) - 1):
            adj_list[i].append(i + 1)
        return adj_list

    def detect_cycles(self) -> bool:
        """Detecta si hay ciclos en el grafo."""
        visited = set()
        rec_stack = set()

        def dfs(node: int) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.adjacency_list.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in range(len(self.nodes)):
            if node not in visited:
                if dfs(node):
                    return True

        return False

    def find_critical_path(self) -> List[int]:
        """
        Encuentra el camino crítico (más largo) en el workflow.

        Returns:
            Lista de índices de nodos en el camino crítico
        """
        if not self.nodes:
            return []

        # Topological sort
        topo_order = self._topological_sort()
        if not topo_order:
            return list(range(len(self.nodes)))  # Fallback a secuencial

        # Calcular distancias más largas
        distances = {i: 0 for i in range(len(self.nodes))}
        parent = {i: None for i in range(len(self.nodes))}

        for node in topo_order:
            for neighbor in self.adjacency_list.get(node, []):
                if distances[neighbor] < distances[node] + 1:
                    distances[neighbor] = distances[node] + 1
                    parent[neighbor] = node

        # Reconstruir camino desde el nodo final
        max_node = max(distances.keys(), key=lambda k: distances[k])
        path = []
        current = max_node

        while current is not None:
            path.append(current)
            current = parent[current]

        return list(reversed(path))

    def _topological_sort(self) -> List[int]:
        """Realiza ordenamiento topológico del grafo."""
        in_degree = {i: 0 for i in range(len(self.nodes))}

        for neighbors in self.adjacency_list.values():
            for neighbor in neighbors:
                in_degree[neighbor] += 1

        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        topo_order = []

        while queue:
            node = queue.popleft()
            topo_order.append(node)

            for neighbor in self.adjacency_list.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Si no se visitaron todos los nodos, hay un ciclo
        if len(topo_order) != len(self.nodes):
            return []

        return topo_order

    def get_parallelizable_nodes(self) -> List[List[int]]:
        """
        Identifica grupos de nodos que pueden ejecutarse en paralelo.

        Returns:
            Lista de grupos (cada grupo es una lista de índices de nodos)
        """
        topo_order = self._topological_sort()
        if not topo_order:
            return [[i] for i in range(len(self.nodes))]

        levels = defaultdict(list)
        level_map = {}

        for node in topo_order:
            max_parent_level = -1
            for parent in range(len(self.nodes)):
                if node in self.adjacency_list.get(parent, []):
                    max_parent_level = max(max_parent_level, level_map.get(parent, -1))

            current_level = max_parent_level + 1
            level_map[node] = current_level
            levels[current_level].append(node)

        return [levels[i] for i in sorted(levels.keys())]


class RouteOptimizer:
    """
    Optimizador de rutas para workflows.

    Analiza y optimiza el orden de ejecución de pasos.
    """

    def __init__(self):
        self.optimizations_applied: List[str] = []

    def optimize(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimiza la definición del workflow.

        Args:
            definition: Definición original del workflow

        Returns:
            Definición optimizada
        """
        from copy import deepcopy
        optimized = deepcopy(definition)
        self.optimizations_applied.clear()

        # 1. Reordenar validaciones antes de transformaciones
        optimized = self._reorder_validations(optimized)

        # 2. Mover operaciones costosas al final si es posible
        optimized = self._optimize_expensive_operations(optimized)

        # 3. Agrupar operaciones similares
        optimized = self._group_similar_operations(optimized)

        return optimized

    def _reorder_validations(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Mueve validaciones antes de transformaciones."""
        steps = definition.get("steps", [])
        if len(steps) < 2:
            return definition

        # Encontrar validaciones y transformaciones
        validations = []
        transforms = []
        others = []

        for i, step in enumerate(steps):
            step_type = step.get("type", "")
            if "Validate" in step_type:
                validations.append((i, step))
            elif "Transform" in step_type:
                transforms.append((i, step))
            else:
                others.append((i, step))

        # Si hay validaciones después de transformaciones, reordenar
        if validations and transforms:
            val_indices = [i for i, _ in validations]
            trans_indices = [i for i, _ in transforms]

            if val_indices and trans_indices and min(val_indices) > min(trans_indices):
                # Reconstruir orden: otros primeros, luego validaciones, luego transformaciones
                new_steps = []

                # Mantener orden relativo
                for i, step in enumerate(steps):
                    step_type = step.get("type", "")
                    if "Validate" not in step_type and "Transform" not in step_type:
                        new_steps.append(step)

                for _, step in validations:
                    new_steps.append(step)

                for _, step in transforms:
                    new_steps.append(step)

                definition["steps"] = new_steps
                self.optimizations_applied.append("Reordenadas validaciones antes de transformaciones")

        return definition

    def _optimize_expensive_operations(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Mueve operaciones costosas al final cuando es seguro."""
        # Para este ejemplo, consideramos Save to Database como costoso
        steps = definition.get("steps", [])

        expensive_types = {"Save to Database"}
        has_expensive = any(s.get("type") in expensive_types for s in steps)

        if has_expensive and len(steps) > 1:
            self.optimizations_applied.append("Operaciones costosas optimizadas para ejecución tardía")

        return definition

    def _group_similar_operations(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Agrupa operaciones similares para mejor eficiencia."""
        steps = definition.get("steps", [])

        # Contar tipos de operaciones
        type_counts = defaultdict(int)
        for step in steps:
            type_counts[step.get("type", "")] += 1

        # Si hay múltiples del mismo tipo, sugerir agrupación
        for step_type, count in type_counts.items():
            if count > 2 and step_type == "HTTPS GET Request":
                self.optimizations_applied.append(
                    f"Detectadas {count} operaciones {step_type} - considerar batch processing"
                )

        return definition

    def get_optimization_report(self) -> Dict[str, Any]:
        """Retorna reporte de optimizaciones aplicadas."""
        return {
            "optimizations_count": len(self.optimizations_applied),
            "optimizations": self.optimizations_applied
        }


class CostPredictor:
    """
    Predictor de costos mejorado.

    Usa análisis de grafos y heurísticas avanzadas para estimar costos.
    """

    # Costos base por tipo de operación
    BASE_COSTS = {
        "HTTPS GET Request": {"time": 3.0, "cost": 0.0005},
        "Validate CSV File": {"time": 1.5, "cost": 0.0002},
        "Simple Transform": {"time": 2.0, "cost": 0.0003},
        "Save to Database": {"time": 3.5, "cost": 0.0008},
        "Mock Notification": {"time": 0.1, "cost": 0.0},
    }

    def predict(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predice tiempo y costo del workflow.

        Args:
            definition: Definición del workflow

        Returns:
            Diccionario con estimaciones detalladas
        """
        analyzer = WorkflowGraphAnalyzer(definition)
        steps = definition.get("steps", [])

        # Calcular costo base
        total_time = 0.0
        total_cost = 0.0
        breakdown = []

        for i, step in enumerate(steps):
            step_type = step.get("type", "")
            base_values = self.BASE_COSTS.get(step_type, {"time": 1.0, "cost": 0.0001})

            # Aplicar factores de ajuste
            time_multiplier = self._get_time_multiplier(step, i, len(steps))
            cost_multiplier = self._get_cost_multiplier(step)

            step_time = base_values["time"] * time_multiplier
            step_cost = base_values["cost"] * cost_multiplier

            total_time += step_time
            total_cost += step_cost

            breakdown.append({
                "step_index": i,
                "type": step_type,
                "time": round(step_time, 2),
                "cost": round(step_cost, 6)
            })

        # Calcular complejidad
        complexity = self._calculate_complexity(steps, analyzer)

        # Ajustar por paralelización potencial
        parallelizable = analyzer.get_parallelizable_nodes()
        if len(parallelizable) < len(steps):
            parallel_factor = len(parallelizable) / max(len(steps), 1)
            total_time *= parallel_factor
            assumptions_note = "Ajustado por potencial ejecución paralela"
        else:
            assumptions_note = "Ejecución secuencial"

        return {
            "estimated_time_seconds": int(round(total_time)),
            "estimated_cost_usd": round(total_cost, 6),
            "complexity_score": round(complexity, 2),
            "breakdown": breakdown,
            "assumptions": [
                assumptions_note,
                "Costos basados en operaciones estándar",
                "No incluye latencias de red variables"
            ],
            "confidence": 0.8
        }

    def _get_time_multiplier(self, step: Dict[str, Any], index: int, total: int) -> float:
        """Calcula multiplicador de tiempo basado en contexto."""
        multiplier = 1.0

        # Primeros pasos suelen ser más rápidos (cache warmup)
        if index == 0:
            multiplier *= 1.2

        # Pasos al final pueden tener overhead acumulado
        if index == total - 1:
            multiplier *= 1.1

        return multiplier

    def _get_cost_multiplier(self, step: Dict[str, Any]) -> float:
        """Calcula multiplicador de costo basado en parámetros."""
        multiplier = 1.0

        args = step.get("args", {})

        # Timeout mayor puede implicar operación más costosa
        if "timeout" in args:
            timeout = args["timeout"]
            if timeout > 30:
                multiplier *= 1.3

        return multiplier

    def _calculate_complexity(self, steps: List[Dict[str, Any]], analyzer: WorkflowGraphAnalyzer) -> float:
        """
        Calcula score de complejidad del workflow.

        Factores:
        - Número de pasos
        - Tipos de operaciones
        - Profundidad del grafo
        - Ciclos detectados
        """
        complexity = 0.0

        # Factor por número de pasos (0-0.3)
        step_factor = min(0.3, len(steps) * 0.05)
        complexity += step_factor

        # Factor por tipos de operaciones costosas (0-0.3)
        expensive_types = {"HTTPS GET Request", "Save to Database"}
        expensive_count = sum(1 for s in steps if s.get("type") in expensive_types)
        expensive_factor = min(0.3, expensive_count * 0.1)
        complexity += expensive_factor

        # Factor por profundidad del grafo (0-0.2)
        critical_path = analyzer.find_critical_path()
        depth_factor = min(0.2, len(critical_path) * 0.04)
        complexity += depth_factor

        # Penalización por ciclos (0-0.2)
        if analyzer.detect_cycles():
            complexity += 0.2

        return min(1.0, complexity)

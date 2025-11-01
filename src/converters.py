"""
Format Converters
Translates between Frontend format (Steps + Edges) and Worker format (Nodes with depends_on)
"""

from typing import List, Dict, Any, Tuple
from .models import StepDTO, EdgeDTO, StepResponse, EdgeResponse
from uuid import uuid4


def steps_and_edges_to_nodes(steps: List[StepDTO], edges: List[EdgeDTO]) -> List[Dict[str, Any]]:
    """
    Convert Frontend format (steps + edges) to Worker format (nodes with depends_on).

    Frontend format:
        steps = [
            {node_key: "A", type: "http_get", params: {...}},
            {node_key: "B", type: "validate_csv", params: {...}}
        ]
        edges = [
            {from_node_key: "A", to_node_key: "B"}
        ]

    Worker format:
        nodes = [
            {id: "A", type: "http_get", params: {...}, depends_on: []},
            {id: "B", type: "validate_csv", params: {...}, depends_on: ["A"]}
        ]

    Args:
        steps: List of step DTOs from Frontend
        edges: List of edge DTOs from Frontend

    Returns:
        List of nodes in Worker format (dicts with id, type, params, depends_on)
    """
    # Build dependency map: node_key -> [list of nodes it depends on]
    dependencies: Dict[str, List[str]] = {}
    for edge in edges:
        if edge.to_node_key not in dependencies:
            dependencies[edge.to_node_key] = []
        dependencies[edge.to_node_key].append(edge.from_node_key)

    # Convert steps to nodes
    nodes = []
    for step in steps:
        node = {
            "id": step.node_key,  # Worker uses 'id', Frontend uses 'node_key'
            "type": step.type,
            "params": step.params,
            "depends_on": dependencies.get(step.node_key, [])
        }
        nodes.append(node)

    return nodes


def nodes_to_steps_and_edges(
    nodes: List[Dict[str, Any]],
    workflow_id: str
) -> Tuple[List[StepResponse], List[EdgeResponse]]:
    """
    Convert Worker format (nodes with depends_on) to Frontend format (steps + edges).

    Worker format:
        nodes = [
            {id: "A", type: "http_get", params: {...}, depends_on: []},
            {id: "B", type: "validate_csv", params: {...}, depends_on: ["A"]}
        ]

    Frontend format:
        steps = [
            {id: "step_xxx", workflow_id: "wf_yyy", node_key: "A", type: "http_get", params: {...}},
            {id: "step_zzz", workflow_id: "wf_yyy", node_key: "B", type: "validate_csv", params: {...}}
        ]
        edges = [
            {id: "edge_aaa", workflow_id: "wf_yyy", from_node_key: "A", to_node_key: "B"}
        ]

    Args:
        nodes: List of nodes in Worker format
        workflow_id: Workflow ID to assign to steps and edges

    Returns:
        Tuple of (steps, edges) in Frontend format
    """
    steps: List[StepResponse] = []
    edges: List[EdgeResponse] = []

    for node in nodes:
        # Create step
        step = StepResponse(
            id=f"step_{uuid4().hex[:8]}",
            workflow_id=workflow_id,
            node_key=node["id"],  # Worker 'id' becomes Frontend 'node_key'
            type=node["type"],
            params=node.get("params", {})
        )
        steps.append(step)

        # Create edges from depends_on
        for dep_node_id in node.get("depends_on", []):
            edge = EdgeResponse(
                id=f"edge_{uuid4().hex[:8]}",
                workflow_id=workflow_id,
                from_node_key=dep_node_id,
                to_node_key=node["id"]
            )
            edges.append(edge)

    return steps, edges


def map_worker_status_to_frontend(worker_status: str) -> str:
    """
    Map Worker workflow status to Frontend run state.

    Worker statuses:
        - "en_espera" -> workflow queued for execution
        - "en_progreso" -> workflow currently executing
        - "completado" -> workflow finished successfully
        - "fallido" -> workflow failed

    Frontend run states:
        - "Pending" -> not started yet
        - "Running" -> currently executing
        - "Succeeded" -> completed successfully
        - "Failed" -> execution failed
        - "Canceled" -> manually canceled

    Args:
        worker_status: Status from Worker ("en_espera", "en_progreso", etc.)

    Returns:
        Frontend state string
    """
    status_map = {
        "en_espera": "Pending",
        "en_progreso": "Running",
        "completado": "Succeeded",
        "fallido": "Failed",
        # Worker engine statuses (English, uppercase)
        "SUCCESS": "Succeeded",
        "RUNNING": "Running",
        "FAILED": "Failed",
        "PARTIAL_SUCCESS": "Succeeded",
    }
    return status_map.get(worker_status, "Pending")


def map_frontend_state_to_worker(frontend_state: str) -> str:
    """
    Map Frontend run state to Worker workflow status.

    Args:
        frontend_state: State from Frontend ("Pending", "Running", etc.)

    Returns:
        Worker status string
    """
    state_map = {
        "Pending": "en_espera",
        "Running": "en_progreso",
        "Succeeded": "completado",
        "Failed": "fallido",
        "Canceled": "fallido",  # Treat cancel as failure
    }
    return state_map.get(frontend_state, "en_espera")


def map_worker_node_status_to_frontend(worker_node_status: str) -> str:
    """
    Map Worker node/task status to Frontend task instance state.

    Worker node statuses:
        - "SUCCESS" -> node executed successfully
        - "FAILED" -> node execution failed
        - "SKIPPED" -> node skipped due to dependency failure

    Frontend task states:
        - "Pending" -> not started
        - "Running" -> currently executing
        - "Succeeded" -> completed successfully
        - "Failed" -> execution failed
        - "Retry" -> retrying after failure

    Args:
        worker_node_status: Status from Worker NodeRun

    Returns:
        Frontend task state string
    """
    status_map = {
        "SUCCESS": "Succeeded",
        "FAILED": "Failed",
        "SKIPPED": "Failed",  # Treat skipped as failed for Frontend
        "RUNNING": "Running",
    }
    return status_map.get(worker_node_status, "Pending")

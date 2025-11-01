"""
Repository Layer
Handles all database operations for workflows, steps, edges, and runs.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
from uuid import uuid4
from sqlmodel import Session, select, create_engine
from sqlalchemy import Engine

from .models import (
    WorkflowTable,
    WorkflowMetadata,
    StepTable,
    EdgeTable,
    Workflow,
    WorkflowListItem,
    WorkflowDetailDTO,
    CreateWorkflowDTO,
    UpdateWorkflowDTO,
    StepDTO,
    StepResponse,
    EdgeDTO,
    EdgeResponse,
    Run,
    TaskInstance,
    RunDetailDTO,
)
from .converters import (
    steps_and_edges_to_nodes,
    nodes_to_steps_and_edges,
    map_worker_status_to_frontend,
    map_worker_node_status_to_frontend,
)


class WorkflowRepository:
    """Repository for workflow CRUD operations"""

    def __init__(self, engine: Engine):
        self.engine = engine

    def create_schema(self):
        """Create all database tables"""
        from .models import SQLModel
        SQLModel.metadata.create_all(self.engine)

    def create_workflow(self, data: CreateWorkflowDTO) -> WorkflowDetailDTO:
        """
        Create a new workflow with steps and edges.
        Converts Frontend format to Worker format and stores in shared DB.
        """
        workflow_id = f"wf_{uuid4().hex[:8]}"
        now = datetime.now(UTC).replace(microsecond=0).isoformat()

        with Session(self.engine) as session:
            # Convert Frontend format (steps + edges) to Worker format (nodes with depends_on)
            nodes = steps_and_edges_to_nodes(data.steps, data.edges)
            definition = {"nodes": nodes}

            # Create workflow in shared table (Worker format)
            workflow_record = WorkflowTable(
                id=workflow_id,
                name=data.name,
                status="en_espera",  # Initial status for Worker polling
                created_at=now,
                updated_at=now,
                definition=json.dumps(definition)
            )
            session.add(workflow_record)

            # Create metadata record (Frontend-specific fields)
            metadata = WorkflowMetadata(
                id=workflow_id,
                description=data.description,
                schedule_cron=data.schedule_cron,
                active=True
            )
            session.add(metadata)

            # Create steps
            step_responses = []
            for step_data in data.steps:
                step_id = f"step_{uuid4().hex[:8]}"
                step = StepTable(
                    id=step_id,
                    workflow_id=workflow_id,
                    node_key=step_data.node_key,
                    type=step_data.type,
                    params=json.dumps(step_data.params)
                )
                session.add(step)
                step_responses.append(StepResponse(
                    id=step_id,
                    workflow_id=workflow_id,
                    node_key=step_data.node_key,
                    type=step_data.type,
                    params=step_data.params
                ))

            # Create edges
            edge_responses = []
            for edge_data in data.edges:
                edge_id = f"edge_{uuid4().hex[:8]}"
                edge = EdgeTable(
                    id=edge_id,
                    workflow_id=workflow_id,
                    from_node_key=edge_data.from_node_key,
                    to_node_key=edge_data.to_node_key
                )
                session.add(edge)
                edge_responses.append(EdgeResponse(
                    id=edge_id,
                    workflow_id=workflow_id,
                    from_node_key=edge_data.from_node_key,
                    to_node_key=edge_data.to_node_key
                ))

            session.commit()

            # Return complete workflow with steps and edges
            return WorkflowDetailDTO(
                workflow=Workflow(
                    id=workflow_id,
                    name=data.name,
                    description=data.description,
                    schedule_cron=data.schedule_cron,
                    active=True,
                    created_at=now
                ),
                steps=step_responses,
                edges=edge_responses
            )

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDetailDTO]:
        """Get workflow by ID with steps and edges"""
        with Session(self.engine) as session:
            # Get workflow and metadata
            workflow = session.get(WorkflowTable, workflow_id)
            if not workflow:
                return None

            metadata = session.get(WorkflowMetadata, workflow_id)
            if not metadata:
                # Create default metadata if missing
                metadata = WorkflowMetadata(
                    id=workflow_id,
                    description="",
                    schedule_cron=None,
                    active=True
                )

            # Get steps
            step_records = session.exec(
                select(StepTable).where(StepTable.workflow_id == workflow_id)
            ).all()
            steps = [
                StepResponse(
                    id=s.id,
                    workflow_id=s.workflow_id,
                    node_key=s.node_key,
                    type=s.type,
                    params=json.loads(s.params)
                )
                for s in step_records
            ]

            # Get edges
            edge_records = session.exec(
                select(EdgeTable).where(EdgeTable.workflow_id == workflow_id)
            ).all()
            edges = [
                EdgeResponse(
                    id=e.id,
                    workflow_id=e.workflow_id,
                    from_node_key=e.from_node_key,
                    to_node_key=e.to_node_key
                )
                for e in edge_records
            ]

            return WorkflowDetailDTO(
                workflow=Workflow(
                    id=workflow.id,
                    name=workflow.name,
                    description=metadata.description,
                    schedule_cron=metadata.schedule_cron,
                    active=metadata.active,
                    created_at=workflow.created_at
                ),
                steps=steps,
                edges=edges
            )

    def list_workflows(self) -> List[WorkflowListItem]:
        """List all workflows"""
        with Session(self.engine) as session:
            workflows = session.exec(select(WorkflowTable)).all()
            result = []

            for wf in workflows:
                metadata = session.get(WorkflowMetadata, wf.id)
                result.append(WorkflowListItem(
                    id=wf.id,
                    name=wf.name,
                    description=metadata.description if metadata else "",
                    schedule_cron=metadata.schedule_cron if metadata else None,
                    active=metadata.active if metadata else True,
                    created_at=wf.created_at
                ))

            return result

    def update_workflow(
        self,
        workflow_id: str,
        data: UpdateWorkflowDTO
    ) -> Optional[WorkflowDetailDTO]:
        """Update workflow and optionally its steps/edges"""
        with Session(self.engine) as session:
            workflow = session.get(WorkflowTable, workflow_id)
            if not workflow:
                return None

            metadata = session.get(WorkflowMetadata, workflow_id)
            if not metadata:
                metadata = WorkflowMetadata(
                    id=workflow_id,
                    description="",
                    schedule_cron=None,
                    active=True
                )
                session.add(metadata)

            # Update basic fields
            if data.name is not None:
                workflow.name = data.name
            if data.description is not None:
                metadata.description = data.description
            if data.schedule_cron is not None:
                metadata.schedule_cron = data.schedule_cron
            if data.active is not None:
                metadata.active = data.active

            workflow.updated_at = datetime.now(UTC).replace(microsecond=0).isoformat()

            # Update steps and edges if provided
            if data.steps is not None and data.edges is not None:
                # Delete existing steps and edges
                session.exec(
                    select(StepTable).where(StepTable.workflow_id == workflow_id)
                ).all()
                for step in session.exec(select(StepTable).where(StepTable.workflow_id == workflow_id)):
                    session.delete(step)

                for edge in session.exec(select(EdgeTable).where(EdgeTable.workflow_id == workflow_id)):
                    session.delete(edge)

                # Create new steps
                for step_data in data.steps:
                    step = StepTable(
                        id=f"step_{uuid4().hex[:8]}",
                        workflow_id=workflow_id,
                        node_key=step_data.node_key,
                        type=step_data.type,
                        params=json.dumps(step_data.params)
                    )
                    session.add(step)

                # Create new edges
                for edge_data in data.edges:
                    edge = EdgeTable(
                        id=f"edge_{uuid4().hex[:8]}",
                        workflow_id=workflow_id,
                        from_node_key=edge_data.from_node_key,
                        to_node_key=edge_data.to_node_key
                    )
                    session.add(edge)

                # Update Worker definition
                nodes = steps_and_edges_to_nodes(data.steps, data.edges)
                workflow.definition = json.dumps({"nodes": nodes})

            session.commit()

            # Return updated workflow
            return self.get_workflow(workflow_id)

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete workflow and all related data"""
        with Session(self.engine) as session:
            workflow = session.get(WorkflowTable, workflow_id)
            if not workflow:
                return False

            # Delete metadata
            metadata = session.get(WorkflowMetadata, workflow_id)
            if metadata:
                session.delete(metadata)

            # Delete steps
            for step in session.exec(select(StepTable).where(StepTable.workflow_id == workflow_id)):
                session.delete(step)

            # Delete edges
            for edge in session.exec(select(EdgeTable).where(EdgeTable.workflow_id == workflow_id)):
                session.delete(edge)

            # Delete workflow
            session.delete(workflow)
            session.commit()

            return True

    def trigger_workflow(self, workflow_id: str) -> Optional[Run]:
        """
        Trigger workflow execution by setting status to 'en_espera'.
        Worker will create the run record when it picks up the workflow.
        Returns a placeholder Run object for Frontend navigation.
        """
        with Session(self.engine) as session:
            workflow = session.get(WorkflowTable, workflow_id)
            if not workflow:
                return None

            # Update workflow status so Worker picks it up
            now = datetime.now(UTC).replace(microsecond=0)
            workflow.status = "en_espera"
            workflow.updated_at = now.isoformat()
            session.commit()

            # Return placeholder Run object - Worker will create the real run
            # Use workflow_id as temporary run_id so Frontend can redirect
            return Run(
                id=workflow_id,  # Use workflow_id as placeholder
                workflow_id=workflow_id,
                state="Pending",
                started_at=now.isoformat(),
                finished_at=None
            )

    def get_workflow_runs(self, workflow_id: str) -> List[Run]:
        """
        Get execution history for a workflow.
        Reads from Worker's workflowrun table.
        """
        # Import Worker's model
        try:
            import sys
            import os
            worker_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Worker")
            if worker_path not in sys.path:
                sys.path.insert(0, worker_path)

            from workflow.workflow_persistence import WorkflowRun

            with Session(self.engine) as session:
                # Query Worker's execution records
                runs = session.exec(
                    select(WorkflowRun).where(WorkflowRun.name == workflow_id)
                ).all()

                return [
                    Run(
                        id=f"run_{r.id}",
                        workflow_id=workflow_id,
                        state=map_worker_status_to_frontend(r.status),
                        started_at=r.started_at.isoformat() if r.started_at else None,
                        finished_at=r.finished_at.isoformat() if r.finished_at else None
                    )
                    for r in runs
                ]
        except Exception as e:
            # If Worker tables don't exist yet, return empty list
            print(f"Warning: Could not read Worker runs: {e}")
            return []

    def get_run_detail(self, run_id: str) -> Optional[RunDetailDTO]:
        """
        Get run details with task instances.
        Reads from workflowrun and noderun tables.

        If run_id is a workflow_id (like "wf_xxx"), returns the most recent run for that workflow,
        or a placeholder if no runs exist yet (workflow in queue).
        """
        from sqlalchemy import text
        from dateutil import parser as date_parser

        try:
            # Try to extract numeric ID - handle both "run_123" and "123" formats
            numeric_id = None
            is_workflow_id = False

            try:
                if run_id.startswith("run_"):
                    numeric_id = int(run_id.replace("run_", ""))
                elif run_id.startswith("wf_"):
                    # This is a workflow_id, need to find the most recent run
                    is_workflow_id = True
                else:
                    numeric_id = int(run_id)
            except ValueError:
                # Not a numeric ID, treat as workflow_id
                is_workflow_id = True

            with Session(self.engine) as session:
                if is_workflow_id:
                    # Look for the most recent run for this workflow
                    result = session.execute(
                        text("SELECT id, name, status, started_at, finished_at FROM workflowrun WHERE name = :workflow_id ORDER BY id DESC LIMIT 1"),
                        {"workflow_id": run_id}
                    ).fetchone()

                    if not result:
                        # No run exists yet - workflow is in queue
                        # Return a placeholder run with Pending state
                        workflow = session.get(WorkflowTable, run_id)
                        if not workflow:
                            return None

                        return RunDetailDTO(
                            run=Run(
                                id=run_id,
                                workflow_id=run_id,
                                state="Pending",
                                started_at=datetime.now(UTC).isoformat(),
                                finished_at=None
                            ),
                            tasks=[]
                        )

                    numeric_id = result[0]
                else:
                    # Query by numeric ID
                    result = session.execute(
                        text("SELECT id, name, status, started_at, finished_at FROM workflowrun WHERE id = :id"),
                        {"id": numeric_id}
                    ).fetchone()

                    if not result:
                        return None

                run_id_numeric, name, status, started_at, finished_at = result

                # Helper to format datetime - SQLite returns strings
                def format_datetime(dt):
                    if dt is None:
                        return None
                    if isinstance(dt, str):
                        return dt  # Already a string, return as-is
                    return dt.isoformat()

                # Query noderun table for tasks
                node_results = session.execute(
                    text("SELECT id, node_id, type, status, started_at, finished_at FROM noderun WHERE workflow_id = :workflow_id"),
                    {"workflow_id": numeric_id}
                ).fetchall()

                tasks = [
                    TaskInstance(
                        id=f"task_{nr[0]}",
                        run_id=str(numeric_id),
                        node_key=nr[1],
                        type=nr[2],
                        state=map_worker_node_status_to_frontend(nr[3]),
                        try_count=1,
                        max_retries=3,
                        started_at=format_datetime(nr[4]),
                        finished_at=format_datetime(nr[5]),
                        error=None
                    )
                    for nr in node_results
                ]

                return RunDetailDTO(
                    run=Run(
                        id=str(numeric_id),
                        workflow_id=name,
                        state=map_worker_status_to_frontend(status),
                        started_at=format_datetime(started_at),
                        finished_at=format_datetime(finished_at)
                    ),
                    tasks=tasks
                )
        except Exception as e:
            print(f"Warning: Could not read run detail: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_run_logs(self, run_id: str, task_filter: Optional[str] = None) -> list:
        """
        Generate synthetic logs from noderun table data.
        Since Worker doesn't expose structured logs, we create them from execution results.
        """
        from sqlalchemy import text
        from .models import LogEntry

        try:
            # Convert run_id to numeric ID if needed
            numeric_id = None
            is_workflow_id = False

            try:
                if run_id.startswith("run_"):
                    numeric_id = int(run_id.replace("run_", ""))
                elif run_id.startswith("wf_"):
                    is_workflow_id = True
                else:
                    numeric_id = int(run_id)
            except ValueError:
                is_workflow_id = True

            with Session(self.engine) as session:
                if is_workflow_id:
                    # Find most recent run for this workflow
                    result = session.execute(
                        text("SELECT id FROM workflowrun WHERE name = :workflow_id ORDER BY id DESC LIMIT 1"),
                        {"workflow_id": run_id}
                    ).fetchone()

                    if not result:
                        # No run exists yet
                        return []

                    numeric_id = result[0]

                # Query noderun table for execution data
                query = text("""
                    SELECT id, node_id, type, status, started_at, finished_at, result_data
                    FROM noderun
                    WHERE workflow_id = :workflow_id
                    ORDER BY id ASC
                """)

                node_results = session.execute(query, {"workflow_id": numeric_id}).fetchall()

                logs = []
                log_counter = 0

                def create_log(run_id_str: str, task_key: str, timestamp_str: str, level: str, message: str) -> LogEntry:
                    """Helper to create LogEntry with all required fields"""
                    nonlocal log_counter
                    log_counter += 1
                    return LogEntry(
                        id=f"log_{log_counter}",
                        run_id=run_id_str,
                        task_instance_id=task_key,
                        ts=timestamp_str,
                        level=level.upper(),  # Frontend expects uppercase: INFO, WARNING, ERROR, DEBUG
                        message=message
                    )

                for nr in node_results:
                    node_id, node_key, node_type, status, started_at, finished_at, result_data_str = nr

                    # Filter by task if specified
                    if task_filter and node_key != task_filter:
                        continue

                    # Parse result data
                    result_data = {}
                    if result_data_str:
                        try:
                            result_data = json.loads(result_data_str)
                        except:
                            pass

                    # Calculate duration
                    duration_ms = 0
                    if started_at and finished_at:
                        try:
                            from dateutil import parser as date_parser
                            start = date_parser.parse(started_at) if isinstance(started_at, str) else started_at
                            end = date_parser.parse(finished_at) if isinstance(finished_at, str) else finished_at
                            duration_ms = int((end - start).total_seconds() * 1000)
                        except:
                            pass

                    # Format duration nicely
                    if duration_ms < 1000:
                        duration_str = f"{duration_ms}ms"
                    else:
                        duration_str = f"{duration_ms / 1000:.2f}s"

                    run_id_str = str(numeric_id)
                    ts = started_at if started_at else datetime.now(UTC).isoformat()

                    # Task start log
                    logs.append(create_log(run_id_str, node_key, ts, "info", f"[{node_key}] Starting task: {node_type}"))

                    # Task-specific logs based on type
                    if node_type == "http_get" and result_data:
                        # HTTP GET specific logging
                        status_code = result_data.get("status_code", "N/A")
                        url = result_data.get("url", "N/A")
                        body = result_data.get("body", "")
                        headers = result_data.get("headers", {})

                        logs.append(create_log(run_id_str, node_key, ts, "info", f"[{node_key}] HTTP GET to {url}"))
                        logs.append(create_log(run_id_str, node_key, ts, "info", f"[{node_key}] Response Status: {status_code}"))

                        # Log response headers
                        if headers:
                            content_type = headers.get("Content-Type", headers.get("content-type", "N/A"))
                            logs.append(create_log(run_id_str, node_key, ts, "info", f"[{node_key}] Content-Type: {content_type}"))

                        # Log response body preview
                        if body:
                            # Try to parse as JSON to show structured data
                            try:
                                import json as json_parser
                                parsed_body = json_parser.loads(body)
                                if isinstance(parsed_body, dict):
                                    field_count = len(parsed_body.keys())
                                    sample_fields = list(parsed_body.keys())[:5]
                                    logs.append(create_log(run_id_str, node_key, ts, "info",
                                        f"[{node_key}] Response JSON: {field_count} fields - {', '.join(sample_fields)}{'...' if field_count > 5 else ''}"))
                                elif isinstance(parsed_body, list):
                                    logs.append(create_log(run_id_str, node_key, ts, "info",
                                        f"[{node_key}] Response JSON: Array with {len(parsed_body)} items"))
                            except:
                                # Not JSON or parse error, show as text preview
                                logs.append(create_log(run_id_str, node_key, ts, "info",
                                    f"[{node_key}] Response body: {body[:200]}{'...' if len(body) > 200 else ''}"))

                    elif node_type == "validate_csv" and result_data:
                        valid = result_data.get("valid", False)
                        rows = result_data.get("rows", 0)
                        logs.append(create_log(run_id_str, node_key, ts, "info",
                            f"[{node_key}] CSV validation: {rows} rows - {'Valid' if valid else 'Invalid'}"))

                    elif result_data:
                        # Generic result data logging
                        logs.append(create_log(run_id_str, node_key, ts, "info",
                            f"[{node_key}] Result: {json.dumps(result_data)[:200]}"))

                    # Task completion log
                    ts_end = finished_at if finished_at else datetime.now(UTC).isoformat()
                    if status == "SUCCESS":
                        logs.append(create_log(run_id_str, node_key, ts_end, "info",
                            f"[{node_key}] Task completed successfully in {duration_str}"))
                    elif status == "FAILED":
                        error_msg = result_data.get("error", "Unknown error") if result_data else "Unknown error"
                        logs.append(create_log(run_id_str, node_key, ts_end, "error",
                            f"[{node_key}] Task failed after {duration_str}: {error_msg}"))
                    else:
                        logs.append(create_log(run_id_str, node_key, ts_end, "info",
                            f"[{node_key}] Task finished with status {status} in {duration_str}"))

                return logs

        except Exception as e:
            print(f"Warning: Could not generate logs: {e}")
            import traceback
            traceback.print_exc()
            return []

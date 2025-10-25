# src/worker.py
import time
import sys
import os
from sqlmodel import Session, select

# Añadir el directorio raíz del proyecto al path para encontrar el módulo 'src'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src.main import engine, WorkflowTable # noqa: E402


def run_worker():
    """
    Simula un worker que procesa workflows.

    Este worker se ejecuta en un bucle infinito, buscando workflows en estado
    'en_espera' y cambiándolos a 'en_progreso' y luego a 'completado'.
    """
    print("🚀 Worker iniciado. Buscando tareas...")
    while True:
        try:
            with Session(engine) as session:
                # 1. Buscar workflows listos para ser procesados
                statement = select(WorkflowTable).where(WorkflowTable.status == "en_espera")
                pending_workflows = session.exec(statement).all()

                if not pending_workflows:
                    # Si no hay trabajo, esperar un poco antes de volver a consultar y mostrar un indicador
                    print("⏳", end="", flush=True)
                    time.sleep(5)
                    continue

                for workflow in pending_workflows:
                    print(f"⚙️  Procesando workflow: {workflow.id} ({workflow.name})")

                    # 2. Cambiar estado a "en_progreso"
                    workflow.status = "en_progreso"
                    session.add(workflow)
                    session.commit()
                    print(f"   -> Estado cambiado a: {workflow.status}")

                    # 3. Simular trabajo y completar
                    time.sleep(3)  # Simula una tarea que toma 3 segundos
                    workflow.status = "completado"
                    session.add(workflow)
                    session.commit()
                    print() # Salto de línea para la siguiente espera
                    print(f"   -> ✅ Estado cambiado a: {workflow.status}")

        except Exception as e:
            print(f"Error en el worker: {e}")
            time.sleep(15)  # Esperar más tiempo si hay un error

if __name__ == "__main__":
    run_worker()
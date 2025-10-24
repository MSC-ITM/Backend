from __future__ import annotations

import os, sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

# Asegura imports relativos al proyecto
sys.path.append(os.getcwd())

# Config de Alembic (lee alembic.ini o pyproject si está soportado)
config = context.config

# Logging
if config.config_file_name:
    fileConfig(config.config_file_name)

# ---- Ajustes mínimos requeridos ----
# Si quieres fijar el path aquí (opción B), descomenta:
config.set_main_option("script_location", "alembic")

# Inyecta la URL de la DB desde tu settings o env
from app.config import settings
config.set_main_option("sqlalchemy.url", settings.database_url)

# Metadata objetivo para autogenerate
from sqlmodel import SQLModel
target_metadata = SQLModel.metadata

# ---- Runners ----
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        render_as_batch=True,  # útil para SQLite
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,  # útil para SQLite
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

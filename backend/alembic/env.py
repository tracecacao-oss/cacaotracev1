"""Entorno de Alembic: usa DATABASE_URL de app.config y los modelos de app.models."""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Tablas que crean PostGIS u otras extensiones; Alembic no las administra.
TABLAS_DE_EXTENSIONES = {"spatial_ref_sys"}


def incluir_objeto(objeto, nombre, tipo, reflejado, comparado_con):
    return not (tipo == "table" and nombre in TABLAS_DE_EXTENSIONES)


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=incluir_objeto,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata, include_object=incluir_objeto)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

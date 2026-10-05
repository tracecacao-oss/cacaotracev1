"""Entorno de Alembic: usa DATABASE_URL de app.config y los modelos de app.models."""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool, text

from alembic import context
from app.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Tablas creadas por extensiones (PostGIS, topology, tiger geocoder de la imagen de Docker…).
# Alembic no las administra y no deben aparecer como diferencias en `alembic check`.
TABLAS_DE_EXTENSIONES = {"spatial_ref_sys"}
CONSULTA_TABLAS_DE_EXTENSIONES = text(
    """
    SELECT c.relname
    FROM pg_class c
    JOIN pg_depend d ON d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e'
    WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
    """
)


def incluir_objeto(objeto, nombre, tipo, reflejado, comparado_con):
    # Una tabla de extensión que no está en los modelos no es una diferencia.
    return not (tipo == "table" and comparado_con is None and nombre in TABLAS_DE_EXTENSIONES)


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
        TABLAS_DE_EXTENSIONES.update(fila[0] for fila in conexion.execute(CONSULTA_TABLAS_DE_EXTENSIONES))
        conexion.commit()
        context.configure(connection=conexion, target_metadata=target_metadata, include_object=incluir_objeto)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

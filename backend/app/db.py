"""Engine y sesión de SQLAlchemy. Solo la API se conecta a Postgres."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def crear_engine(url: str) -> Engine:
    # El plan gratuito de Supabase admite pocas conexiones simultáneas.
    return create_engine(
        url,
        pool_size=5,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


engine = crear_engine(get_settings().database_url)
SesionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def obtener_sesion() -> Iterator[Session]:
    with SesionLocal() as sesion:
        yield sesion

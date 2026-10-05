"""Modelos SQLAlchemy. Cada parte agrega aquí sus tablas; Alembic las detecta desde Base.metadata."""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nombres de restricciones estables para que las migraciones autogeneradas sean reproducibles.
CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


class ConFechas:
    """creado_en y actualizado_en en UTC; la interfaz las muestra en hora de Lima."""

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


from app.models.acceso import (  # noqa: E402
    ESTADOS_AFILIACION,
    ESTADOS_COOPERATIVA,
    ORIGENES_CONSENTIMIENTO,
    ROLES,
    ROLES_PERSONAL,
    Afiliacion,
    Auditoria,
    Cooperativa,
    Perfil,
    Productor,
)

__all__ = [
    "ESTADOS_AFILIACION",
    "ESTADOS_COOPERATIVA",
    "ORIGENES_CONSENTIMIENTO",
    "ROLES",
    "ROLES_PERSONAL",
    "Afiliacion",
    "Auditoria",
    "Base",
    "ConFechas",
    "Cooperativa",
    "Perfil",
    "Productor",
]

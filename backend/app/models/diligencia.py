"""Tablas de la adenda 6: la política de la organización y sus actuaciones de diligencia.

No se editan ni se borran: se anulan con motivo. Una actuación alcanza, si se quiere, a algunos productores
(`actuacion_productores`), que se marcan al registrarla. Tres triggers lo aseguran en la base.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.catalogos import actuaciones, requisitos_organizacion
from app.models import Base
from app.models.padron import _en

ANULACION = (
    "(anulada_en IS NULL) = (anulada_por IS NULL) AND (anulada_en IS NULL) = (motivo_anulacion IS NULL)"
)


def _temas_validos(columna: str, temas: tuple[str, ...]) -> str:
    return f"cardinality({columna}) > 0 AND {columna} <@ ARRAY[{_en(temas)}]::text[]"


class PoliticaOrganizacion(Base):
    """Una política que la organización adoptó y los temas que cubre (adenda 6, sección 5)."""

    __tablename__ = "politicas_organizacion"
    __table_args__ = (
        CheckConstraint(_temas_validos("temas", requisitos_organizacion.CODIGOS_TEMAS), name="temas_validos"),
        CheckConstraint("char_length(organo) BETWEEN 2 AND 200", name="organo_valido"),
        CheckConstraint(ANULACION, name="anulacion_completa"),
        Index("ix_politicas_organizacion_cooperativa", "cooperativa_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documentos.id"))
    temas: Mapped[list[str]] = mapped_column(ARRAY(Text))
    adoptada_en: Mapped[date] = mapped_column(Date)
    organo: Mapped[str] = mapped_column(Text)
    version_plantilla: Mapped[int | None] = mapped_column(Integer)
    registrada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    registrada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    anulada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)


class ActuacionDiligencia(Base):
    """Algo que la organización hizo para conocer o reducir un riesgo de legalidad (adenda 6, sección 6.5)."""

    __tablename__ = "actuaciones_diligencia"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_en(actuaciones.CODIGOS_TIPOS)})", name="tipo_valido"),
        CheckConstraint(_temas_validos("temas", actuaciones.CODIGOS_TEMAS), name="temas_validos"),
        CheckConstraint(
            f"char_length(descripcion) >= {actuaciones.LARGO_DESCRIPCION}", name="descripcion_minima"
        ),
        CheckConstraint(f"char_length(resultado) >= {actuaciones.LARGO_RESULTADO}", name="resultado_minimo"),
        CheckConstraint("participantes IS NULL OR participantes > 0", name="participantes_positivos"),
        CheckConstraint(ANULACION, name="anulacion_completa"),
        Index("ix_actuaciones_diligencia_cooperativa_fecha", "cooperativa_id", "fecha"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    tipo: Mapped[str] = mapped_column(Text)
    temas: Mapped[list[str]] = mapped_column(ARRAY(Text))
    fecha: Mapped[date] = mapped_column(Date)
    descripcion: Mapped[str] = mapped_column(Text)
    contraparte: Mapped[str | None] = mapped_column(Text)
    resultado: Mapped[str] = mapped_column(Text)
    participantes: Mapped[int | None] = mapped_column(Integer)
    departamento: Mapped[str | None] = mapped_column(Text)
    provincia: Mapped[str | None] = mapped_column(Text)
    distrito: Mapped[str | None] = mapped_column(Text)
    registrada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    registrada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    anulada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)


class ActuacionProductor(Base):
    """Un productor que la actuación alcanzó. Opcional; se marca al registrar la actuación."""

    __tablename__ = "actuacion_productores"
    __table_args__ = (Index("ix_actuacion_productores_productor", "productor_id"),)

    actuacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actuaciones_diligencia.id"), primary_key=True)
    productor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productores.id"), primary_key=True)

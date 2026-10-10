"""Tablas de la adenda 4: el perfil legal de la parcela y sus incidencias.

Las filas de `parcela_variables` no se editan ni se borran: un valor nuevo deja el anterior con
`vigente = false`. Las incidencias no se borran; solo se cierran. Dos triggers lo aseguran en la base.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.catalogos import perfil_legal
from app.models import Base
from app.models.padron import _en

ORIGENES_VARIABLE = ("declarado", "cruce")
TIPOS_INCIDENCIA = ("tenencia", "ambiental", "otra")
ESTADOS_INCIDENCIA = ("abierta", "cerrada")


class ParcelaVariable(Base):
    """Un valor del perfil legal de una parcela, declarado por una persona o calculado por el cruce."""

    __tablename__ = "parcela_variables"
    __table_args__ = (
        CheckConstraint(f"variable IN ({_en(perfil_legal.CODIGOS)})", name="variable_valida"),
        CheckConstraint(f"origen IN ({_en(ORIGENES_VARIABLE)})", name="origen_valido"),
        CheckConstraint("origen = 'declarado' OR fuente IS NOT NULL", name="cruce_con_fuente"),
        CheckConstraint("origen = 'cruce' OR registrada_por IS NOT NULL", name="declarado_con_persona"),
        # Una sola fila vigente por parcela, variable y origen: se guardan y se muestran el cruce y la
        # declaración; manda el más exigente (adenda 4, sección 4).
        Index(
            "uq_parcela_variables_vigente",
            "parcela_id",
            "variable",
            "origen",
            unique=True,
            postgresql_where=text("vigente"),
        ),
        Index("ix_parcela_variables_parcela", "parcela_id", "variable"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    variable: Mapped[str] = mapped_column(Text)
    valor: Mapped[str] = mapped_column(Text)
    detalle: Mapped[dict | None] = mapped_column(JSONB)
    origen: Mapped[str] = mapped_column(Text)
    fuente: Mapped[str | None] = mapped_column(Text)  # capa y fecha de consulta, cuando es un cruce
    registrada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    registrada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    vigente: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class ParcelaIncidencia(Base):
    """Un conflicto, litigio o denuncia sobre la parcela que la organización encontró (adenda 4, 5.3)."""

    __tablename__ = "parcela_incidencias"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_en(TIPOS_INCIDENCIA)})", name="tipo_valido"),
        CheckConstraint(f"estado IN ({_en(ESTADOS_INCIDENCIA)})", name="estado_valido"),
        CheckConstraint("char_length(descripcion) >= 50", name="descripcion_minima"),
        CheckConstraint(
            "estado = 'abierta' OR "
            "(cierre_nota IS NOT NULL AND cerrada_por IS NOT NULL AND cerrada_en IS NOT NULL)",
            name="cierre_completo",
        ),
        Index("ix_parcela_incidencias_parcela", "parcela_id", "estado"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    tipo: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[str] = mapped_column(Text)
    fuente: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, server_default="abierta")
    registrada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    registrada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cierre_nota: Mapped[str | None] = mapped_column(Text)
    cerrada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

"""Tablas de la adenda 5: la declaración anual del productor y los productos que declara.

Las declaraciones no se editan ni se borran: para corregir se registra otra. Solo cambian su estado, su fecha
de declaración (al cargar la hoja firmada) y la nota de seguimiento. De un producto solo cambia su revisión.
Dos triggers lo aseguran en la base.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.catalogos.declaracion_productor import TIPOS_PRODUCTO
from app.models import Base
from app.models.padron import _en

ORIGENES_DECLARACION = ("productor", "personal")
ESTADOS_DECLARACION = ("por_firmar", "vigente", "reemplazada")
REVISIONES_PRODUCTO = ("sin_revisar", "figura", "no_figura")


class DeclaracionProductor(Base):
    """La declaración anual de un productor ante una organización (adenda 5, sección 5)."""

    __tablename__ = "declaraciones_productor"
    __table_args__ = (
        CheckConstraint(f"origen IN ({_en(ORIGENES_DECLARACION)})", name="origen_valido"),
        CheckConstraint(f"estado IN ({_en(ESTADOS_DECLARACION)})", name="estado_valido"),
        # La que registró el personal no vale hasta tener la hoja firmada.
        CheckConstraint(
            "estado = 'reemplazada' OR (estado = 'por_firmar') = (declarada_en IS NULL)",
            name="declarada_salvo_por_firmar",
        ),
        CheckConstraint(
            "(declarada_en IS NULL) = (vigente_hasta IS NULL)", name="vigencia_con_declaracion"
        ),
        CheckConstraint(
            "seguimiento_nota IS NULL OR char_length(seguimiento_nota) >= 50", name="seguimiento_minimo"
        ),
        # Como máximo una vigente y una por firmar por productor y organización (sección 5.2, regla 2).
        Index(
            "uq_declaraciones_productor_vigente",
            "productor_id",
            "cooperativa_id",
            unique=True,
            postgresql_where=text("estado = 'vigente'"),
        ),
        Index(
            "uq_declaraciones_productor_por_firmar",
            "productor_id",
            "cooperativa_id",
            unique=True,
            postgresql_where=text("estado = 'por_firmar'"),
        ),
        Index("ix_declaraciones_productor_productor", "productor_id", "cooperativa_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    productor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productores.id"))
    version_cuestionario: Mapped[int] = mapped_column(Integer)
    version_texto: Mapped[int] = mapped_column(Integer)
    respuestas: Mapped[dict] = mapped_column(JSONB)
    contexto: Mapped[dict] = mapped_column(JSONB)
    origen: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text)
    registrada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    registrada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    declarada_en: Mapped[date | None] = mapped_column(Date)
    vigente_hasta: Mapped[date | None] = mapped_column(Date)
    seguimiento_nota: Mapped[str | None] = mapped_column(Text)
    seguimiento_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    seguimiento_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeclaracionProducto(Base):
    """Un agroquímico declarado y su revisión en el registro de SENASA (adenda 5, sección 5.6)."""

    __tablename__ = "declaracion_productos"
    __table_args__ = (
        CheckConstraint("char_length(nombre) BETWEEN 2 AND 80", name="nombre_valido"),
        CheckConstraint(f"tipo IN ({_en(TIPOS_PRODUCTO)})", name="tipo_valido"),
        CheckConstraint(f"revision IN ({_en(REVISIONES_PRODUCTO)})", name="revision_valida"),
        CheckConstraint(
            "revision = 'sin_revisar' OR (revisado_por IS NOT NULL AND revisado_en IS NOT NULL)",
            name="revision_con_persona",
        ),
        Index("ix_declaracion_productos_declaracion", "declaracion_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    declaracion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("declaraciones_productor.id"))
    nombre: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    revision: Mapped[str] = mapped_column(Text, server_default="sin_revisar")
    registro: Mapped[str | None] = mapped_column(Text)
    revisado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    copiada_de: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("declaracion_productos.id"))

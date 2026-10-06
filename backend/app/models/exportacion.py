"""Tablas de la Parte 7: importadores, órdenes de compra, lotes de exportación con su selección de stock y
la genealogía del lote por parcela."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, ConFechas
from app.models.padron import _en

ESTADOS_ORDEN = ("abierta", "con_lote", "cerrada", "anulada")
# Las Partes 8 y 9 agregan los estados siguientes del lote.
ESTADOS_LOTE = ("en_armado", "armado", "anulado")
PARTIDA_SA = "1801"
MOTIVO_DESVIACION_MINIMO = 30


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


class Importador(ConFechas, Base):
    """Registro de la cooperativa, no un usuario: no inicia sesión."""

    __tablename__ = "importadores"
    __table_args__ = (Index("ix_importadores_cooperativa", "cooperativa_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    razon_social: Mapped[str] = mapped_column(Text)
    direccion: Mapped[str] = mapped_column(Text)
    pais: Mapped[str] = mapped_column(Text)
    correo: Mapped[str] = mapped_column(Text)
    eori: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class OrdenCompra(ConFechas, Base):
    __tablename__ = "ordenes_compra"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_en(ESTADOS_ORDEN)})", name="estado_valido"),
        CheckConstraint("cantidad_kg > 0", name="cantidad_positiva"),
        CheckConstraint("tolerancia_pct >= 0 AND tolerancia_pct <= 100", name="tolerancia_valida"),
        CheckConstraint(f"partida_sa = '{PARTIDA_SA}'", name="partida_cacao_en_grano"),
        CheckConstraint(
            "(estado = 'anulada') = (anulada_en IS NOT NULL AND motivo_anulacion IS NOT NULL)",
            name="anulacion_completa",
        ),
        UniqueConstraint("cooperativa_id", "codigo", name="uq_ordenes_compra_codigo"),
        Index("ix_ordenes_compra_cooperativa_estado", "cooperativa_id", "estado"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    codigo: Mapped[str] = mapped_column(Text)
    importador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("importadores.id"))
    referencia_importador: Mapped[str | None] = mapped_column(Text)
    cantidad_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    tolerancia_pct: Mapped[Decimal] = mapped_column(Numeric(4, 1), server_default=text("0"))
    calidad_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calidades.id"))
    partida_sa: Mapped[str] = mapped_column(Text, server_default=PARTIDA_SA)
    pais_destino: Mapped[str] = mapped_column(Text)
    lugar_destino: Mapped[str] = mapped_column(Text)
    fecha_entrega: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(Text, server_default="abierta")
    creada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    anulada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)


class Lote(ConFechas, Base):
    """El lote de exportación que atiende una orden. Nace en_armado con la sugerencia FIFO; al confirmarse
    descuenta los saldos y fija su genealogía."""

    __tablename__ = "lotes"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_en(ESTADOS_LOTE)})", name="estado_valido"),
        CheckConstraint("masa_neta_kg IS NULL OR masa_neta_kg > 0", name="masa_positiva"),
        CheckConstraint(
            f"NOT desviacion_fifo OR char_length(motivo_desviacion) >= {MOTIVO_DESVIACION_MINIMO}",
            name="motivo_de_la_desviacion",
        ),
        CheckConstraint(
            "estado = 'en_armado' OR anulado_en IS NOT NULL "
            "OR (masa_neta_kg IS NOT NULL AND armado_en IS NOT NULL)",
            name="armado_completo",
        ),
        CheckConstraint(
            "(estado = 'anulado') = (anulado_en IS NOT NULL AND motivo_anulacion IS NOT NULL)",
            name="anulacion_completa",
        ),
        UniqueConstraint("cooperativa_id", "codigo", name="uq_lotes_codigo"),
        # Una orden tiene un solo lote no anulado.
        Index(
            "uq_lotes_orden_vigente",
            "orden_compra_id",
            unique=True,
            postgresql_where=text("estado <> 'anulado'"),
        ),
        Index("ix_lotes_cooperativa_estado", "cooperativa_id", "estado"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    codigo: Mapped[str] = mapped_column(Text)
    orden_compra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ordenes_compra.id"))
    estado: Mapped[str] = mapped_column(Text, server_default="en_armado")
    masa_neta_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    desviacion_fifo: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    motivo_desviacion: Mapped[str | None] = mapped_column(Text)
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    armado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    armado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)


class LoteAsignacion(Base):
    """Kilos que el lote toma de una tanda final."""

    __tablename__ = "lote_asignaciones"
    __table_args__ = (
        CheckConstraint("kg_asignados > 0", name="kg_positivos"),
        UniqueConstraint("lote_id", "tanda_final_id", name="uq_lote_asignaciones_tanda_final"),
        Index("ix_lote_asignaciones_tanda_final", "tanda_final_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lotes.id"))
    tanda_final_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tandas_finales.id"))
    kg_asignados: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class LoteGenealogia(Base):
    """Una fila por cada combinación de asignación y tanda de origen. No se edita ni se borra; si el lote se
    anula, la marca es el estado del lote."""

    __tablename__ = "lote_genealogia"
    __table_args__ = (
        CheckConstraint("kg_atribuidos >= 0", name="kg_no_negativos"),
        CheckConstraint("proporcion_lote >= 0 AND proporcion_lote <= 1", name="proporcion_valida"),
        Index("ix_lote_genealogia_lote", "lote_id"),
        Index("ix_lote_genealogia_tanda", "tanda_id"),
        Index("ix_lote_genealogia_parcela", "parcela_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lotes.id"))
    tanda_final_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tandas_finales.id"))
    dpp_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dpps.id"))
    tanda_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tandas.id"))
    dop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dops.id"))
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    productor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productores.id"))
    kg_atribuidos: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    proporcion_lote: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

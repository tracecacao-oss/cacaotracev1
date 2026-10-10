"""Tablas de la Parte 7: importadores, órdenes de compra, lotes de exportación con su selección de stock y
la genealogía del lote por parcela. Desde la adenda 7, la declaración aduanera de cada lote."""

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, ConFechas
from app.models.padron import _en

ESTADOS_ORDEN = ("abierta", "con_lote", "cerrada", "anulada")
# Parte 8: bloqueado y listo los fija la recomprobación; cerrado, la emisión del DEX (Parte 9).
ESTADOS_LOTE = ("en_armado", "armado", "bloqueado", "listo", "cerrado", "anulado")
RESULTADOS_RECOMPROBACION = ("sin_observaciones", "con_observaciones")
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
    # Parte 8: alertas que llegan después de cerrar el lote, como exclusion_posterior_al_cierre.
    alertas: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))


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


class Recomprobacion(Base):
    """Las nueve comprobaciones de un lote con la fecha del día (Parte 8). No se edita ni se borra."""

    __tablename__ = "recomprobaciones"
    __table_args__ = (
        CheckConstraint(f"resultado IN ({_en(RESULTADOS_RECOMPROBACION)})", name="resultado_valido"),
        Index("ix_recomprobaciones_lote_ejecutada", "lote_id", "ejecutada_en"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lotes.id"))
    # Nulo cuando la ejecutó el sistema (tarea diaria).
    ejecutada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    ejecutada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[str] = mapped_column(Text)
    detalle: Mapped[dict] = mapped_column(JSONB)


ANULACION = (
    "(anulada_en IS NULL) = (anulada_por IS NULL) AND (anulada_en IS NULL) = (motivo_anulacion IS NULL)"
)


class DeclaracionAduanera(Base):
    """La declaración aduanera de un lote (adenda 7, sección 4): los cuatro datos que escribe la persona, con
    su archivo de tipo `dam`. No se edita ni se borra: se anula con motivo y se carga otra. Un lote tiene como
    máximo una sin anular. Un trigger lo asegura en la base."""

    __tablename__ = "declaraciones_aduaneras"
    __table_args__ = (
        CheckConstraint("char_length(numero) BETWEEN 5 AND 30", name="numero_valido"),
        CheckConstraint("peso_neto_kg > 0", name="peso_positivo"),
        CheckConstraint("subpartida ~ '^[0-9]{4,10}$'", name="subpartida_solo_digitos"),
        CheckConstraint(ANULACION, name="anulacion_completa"),
        # Sección 4.1, regla 1: como máximo una sin anular por lote.
        Index(
            "uq_declaraciones_aduaneras_lote_vigente",
            "lote_id",
            unique=True,
            postgresql_where=text("anulada_en IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lotes.id"))
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documentos.id"))
    numero: Mapped[str] = mapped_column(Text)
    fecha_numeracion: Mapped[date] = mapped_column(Date)
    peso_neto_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    subpartida: Mapped[str] = mapped_column(Text)
    registrada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    registrada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    # Verdadero si se cargó con el lote cerrado, después de emitir el DEX.
    posterior_al_dex: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    anulada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)

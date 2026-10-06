"""Tablas de la Parte 5: configuración de la cooperativa, lugares, correlativos, tandas, decisiones sobre
la tanda y DOP."""

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
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, ConFechas
from app.models.padron import _en

TIPOS_LUGAR = ("cancha_acopio", "planta", "almacen", "otro")
ESTADOS_PRODUCTO = ("baba", "seco")
ESTADOS_TANDA = ("registrada", "observada", "validada", "anulada")
DECISIONES_TANDA = ("validar", "observar", "anular")
ESTADOS_DOP = ("vigente", "anulado")
# Parte 6: corridas, tandas finales y DPP.
TIPOS_CORRELATIVO = ("tanda", "dop", "corrida", "tanda_final", "dpp")
# Adenda 3 de la Parte 5. El Comprobante de Operaciones de la Ley N.° 29972 queda fuera: esa ley está
# derogada por la Ley N.° 31335 (decisión del equipo del 2026-10-06, adenda 3, sección 12).
TIPOS_DOC_ENTREGA = ("guia_remision", "liquidacion_compra")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


class ConfiguracionCooperativa(ConFechas, Base):
    """Parámetros de la cooperativa. Una fila por cooperativa; solo el administrador la cambia."""

    __tablename__ = "configuracion_cooperativa"
    __table_args__ = (
        CheckConstraint("tope_kg_seco_ha_anio IS NULL OR tope_kg_seco_ha_anio > 0", name="tope_positivo"),
        CheckConstraint("factor_baba_a_seco > 0 AND factor_baba_a_seco < 1", name="factor_entre_0_y_1"),
        CheckConstraint(
            "rendimiento_min > 0 AND rendimiento_min < rendimiento_max AND rendimiento_max < 1",
            name="banda_rendimiento_valida",
        ),
        CheckConstraint(
            "dias_max_cosecha_entrega_baba >= 0 AND dias_max_cosecha_entrega_seco >= 0",
            name="dias_no_negativos",
        ),
        CheckConstraint("tolerancia_peso_guia_pct >= 0", name="tolerancia_no_negativa"),
        CheckConstraint("dias_max_emision_doc_entrega >= 0", name="dias_emision_no_negativos"),
    )

    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"), primary_key=True)
    tope_kg_seco_ha_anio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    factor_baba_a_seco: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default=text("0.390"))
    rendimiento_min: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default=text("0.330"))
    rendimiento_max: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default=text("0.450"))
    dias_max_cosecha_entrega_baba: Mapped[int] = mapped_column(Integer, server_default=text("7"))
    dias_max_cosecha_entrega_seco: Mapped[int] = mapped_column(Integer, server_default=text("90"))
    tolerancia_peso_guia_pct: Mapped[Decimal] = mapped_column(Numeric(4, 1), server_default=text("5.0"))
    # Adenda 3: días para emitir la liquidación de compra después de la recepción.
    dias_max_emision_doc_entrega: Mapped[int] = mapped_column(Integer, server_default=text("7"))


class Lugar(ConFechas, Base):
    """Sitio físico de la cooperativa: la tanda se pesa en una cancha de acopio."""

    __tablename__ = "lugares"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_en(TIPOS_LUGAR)})", name="tipo_valido"),
        CheckConstraint("latitud IS NULL OR latitud BETWEEN -90 AND 90", name="latitud_valida"),
        CheckConstraint("longitud IS NULL OR longitud BETWEEN -180 AND 180", name="longitud_valida"),
        UniqueConstraint("cooperativa_id", "nombre", name="uq_lugares_cooperativa_nombre"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    nombre: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    departamento: Mapped[str] = mapped_column(Text)
    provincia: Mapped[str] = mapped_column(Text)
    distrito: Mapped[str] = mapped_column(Text)
    latitud: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Correlativo(Base):
    """Último número usado por cooperativa, tipo y año. Se toma con un UPSERT que bloquea la fila."""

    __tablename__ = "correlativos"
    __table_args__ = (CheckConstraint(f"tipo IN ({_en(TIPOS_CORRELATIVO)})", name="tipo_valido"),)

    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"), primary_key=True)
    tipo: Mapped[str] = mapped_column(Text, primary_key=True)
    anio: Mapped[int] = mapped_column(Integer, primary_key=True)
    ultimo: Mapped[int] = mapped_column(Integer)


class Tanda(ConFechas, Base):
    """Cacao de una sola parcela que un productor entrega y la cooperativa pesa en cancha."""

    __tablename__ = "tandas"
    __table_args__ = (
        CheckConstraint(f"estado_producto IN ({_en(ESTADOS_PRODUCTO)})", name="estado_producto_valido"),
        CheckConstraint(f"estado IN ({_en(ESTADOS_TANDA)})", name="estado_valido"),
        CheckConstraint("peso_kg > 0", name="peso_positivo"),
        CheckConstraint("numero_sacos IS NULL OR numero_sacos > 0", name="sacos_positivos"),
        CheckConstraint(
            "humedad_pct IS NULL OR (estado_producto = 'seco' AND humedad_pct BETWEEN 0 AND 100)",
            name="humedad_solo_en_seco",
        ),
        CheckConstraint("cosecha_desde <= cosecha_hasta", name="cosecha_ordenada"),
        CheckConstraint(
            "doc_entrega_ruc_emisor IS NULL OR doc_entrega_ruc_emisor ~ '^[0-9]{11}$'",
            name="doc_entrega_ruc_11_digitos",
        ),
        CheckConstraint(
            "doc_entrega_peso_kg IS NULL OR doc_entrega_peso_kg > 0", name="doc_entrega_peso_positivo"
        ),
        CheckConstraint(
            f"doc_entrega_tipo IS NULL OR doc_entrega_tipo IN ({_en(TIPOS_DOC_ENTREGA)})",
            name="doc_entrega_tipo_valido",
        ),
        CheckConstraint("(variedad = 'otra') = (variedad_otra IS NOT NULL)", name="variedad_otra_si_otra"),
        UniqueConstraint("cooperativa_id", "codigo", name="uq_tandas_cooperativa_codigo"),
        Index("ix_tandas_parcela_recibida", "parcela_id", "recibida_en"),
        Index("ix_tandas_doc_entrega", "doc_entrega_ruc_emisor", "doc_entrega_numero"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    codigo: Mapped[str] = mapped_column(Text)
    productor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productores.id"))
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    lugar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lugares.id"))
    recibida_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado_producto: Mapped[str] = mapped_column(Text)
    peso_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    numero_sacos: Mapped[int | None] = mapped_column(Integer)
    humedad_pct: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    variedad: Mapped[str] = mapped_column(Text)
    # Con la variedad "otra", el nombre que escribió el usuario.
    variedad_otra: Mapped[str | None] = mapped_column(Text)
    tipo_semilla: Mapped[str | None] = mapped_column(Text)
    cosecha_desde: Mapped[date] = mapped_column(Date)
    cosecha_hasta: Mapped[date] = mapped_column(Date)
    # Adenda 3: el documento de entrega (antes, solo la guía de remisión).
    doc_entrega_tipo: Mapped[str | None] = mapped_column(Text)
    doc_entrega_numero: Mapped[str | None] = mapped_column(Text)
    doc_entrega_fecha_emision: Mapped[date | None] = mapped_column(Date)
    doc_entrega_ruc_emisor: Mapped[str | None] = mapped_column(String(11))
    doc_entrega_peso_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    estado: Mapped[str] = mapped_column(Text, server_default="registrada")
    registrada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))


class DecisionTanda(Base):
    """Cada decisión sobre una tanda. Un trigger rechaza UPDATE y DELETE: no se edita ni se borra."""

    __tablename__ = "decisiones_tanda"
    __table_args__ = (
        CheckConstraint(f"decision IN ({_en(DECISIONES_TANDA)})", name="decision_valida"),
        Index("ix_decisiones_tanda_tanda", "tanda_id", "decidida_en"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tanda_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tandas.id"))
    decision: Mapped[str] = mapped_column(Text)
    decidida_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    decidida_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    nota: Mapped[str | None] = mapped_column(Text)
    requisitos: Mapped[dict] = mapped_column(JSONB)


class Dop(Base):
    """Copia sellada de lo que respalda una tanda al validarla. Un trigger rechaza todo UPDATE sobre
    contenido, contenido_sha256, codigo y tanda_id, y todo DELETE."""

    __tablename__ = "dops"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_en(ESTADOS_DOP)})", name="estado_valido"),
        CheckConstraint("contenido_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint(
            "(estado = 'anulado') = "
            "(anulado_en IS NOT NULL AND anulado_por IS NOT NULL AND motivo_anulacion IS NOT NULL)",
            name="anulacion_completa",
        ),
        Index("ix_dops_cooperativa_emitido", "cooperativa_id", "emitido_en"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    codigo: Mapped[str] = mapped_column(Text, unique=True)
    tanda_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tandas.id"), unique=True)
    productor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productores.id"))
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    emitido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    emitido_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    contenido: Mapped[dict] = mapped_column(JSONB)
    contenido_sha256: Mapped[str] = mapped_column(String(64))
    pdf_documento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos.id"))
    estado: Mapped[str] = mapped_column(Text, server_default="vigente")
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)

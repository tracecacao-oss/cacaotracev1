"""Tablas de la Parte 6: calidades, plantilla de proceso, corridas con sus tandas y sus 23 etapas, tandas
finales en stock y DPP."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, ConFechas
from app.models.padron import _en

RUTAS = ("completa", "seco")
TIPOS_MANEJO = ("segregado", "mezclado")
ESTADOS_CORRIDA = ("abierta", "en_proceso", "consolidada", "anulada")
SITUACIONES_ETAPA = ("pendiente", "registrada", "no_aplica", "no_ocurrio")
ESTADOS_TANDA_FINAL = ("en_stock", "agotada", "anulada")
ESTADOS_DPP = ("vigente", "anulado")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


class Calidad(ConFechas, Base):
    """Catálogo de calidades de la cooperativa. La etapa 17 y la tanda final usan uno de sus valores."""

    __tablename__ = "calidades"
    __table_args__ = (UniqueConstraint("cooperativa_id", "nombre", name="uq_calidades_cooperativa_nombre"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    nombre: Mapped[str] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class PlantillaEtapa(ConFechas, Base):
    """Valores habituales de una etapa en la cooperativa: un punto de partida que el operador confirma."""

    __tablename__ = "plantilla_proceso"
    __table_args__ = (
        CheckConstraint("numero BETWEEN 1 AND 23", name="numero_valido"),
        CheckConstraint("distancia_m IS NULL OR distancia_m >= 0", name="distancia_no_negativa"),
        CheckConstraint("duracion_horas IS NULL OR duracion_horas >= 0", name="duracion_no_negativa"),
        # Las etapas fijas no se desactivan (app/catalogos/etapas_proceso.FIJAS).
        CheckConstraint("activa OR numero NOT IN (1, 3, 4, 13, 17, 19, 21)", name="etapa_fija_activa"),
    )

    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"), primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, primary_key=True)
    lugar_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lugares.id"))
    metodo: Mapped[str | None] = mapped_column(Text)
    distancia_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    duracion_horas: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    # Una etapa desactivada nace como "no aplica" en las corridas nuevas.
    activa: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Corrida(ConFechas, Base):
    """Una o varias tandas validadas que pasan juntas por las etapas del proceso."""

    __tablename__ = "corridas"
    __table_args__ = (
        CheckConstraint(f"ruta IN ({_en(RUTAS)})", name="ruta_valida"),
        CheckConstraint(f"tipo_manejo IN ({_en(TIPOS_MANEJO)})", name="tipo_manejo_valido"),
        CheckConstraint(f"estado IN ({_en(ESTADOS_CORRIDA)})", name="estado_valido"),
        CheckConstraint(
            "(estado = 'anulada') = (anulada_en IS NOT NULL AND motivo_anulacion IS NOT NULL)",
            name="anulacion_completa",
        ),
        UniqueConstraint("cooperativa_id", "codigo", name="uq_corridas_cooperativa_codigo"),
        Index("ix_corridas_cooperativa_estado", "cooperativa_id", "estado"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    codigo: Mapped[str] = mapped_column(Text)
    ruta: Mapped[str] = mapped_column(Text)
    tipo_manejo: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, server_default="abierta")
    abierta_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    abierta_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    iniciada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consolidada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)


class CorridaTanda(Base):
    """Una tanda dentro de una corrida, con su peso al entrar. Una tanda está en una sola corrida no anulada:
    al anular la corrida, la fila queda como historial con `liberada_en`."""

    __tablename__ = "corrida_tandas"
    __table_args__ = (
        CheckConstraint("peso_kg > 0", name="peso_positivo"),
        CheckConstraint(
            "proporcion IS NULL OR (proporcion > 0 AND proporcion <= 1)", name="proporcion_valida"
        ),
        Index(
            "uq_corrida_tandas_tanda_activa",
            "tanda_id",
            unique=True,
            postgresql_where=text("liberada_en IS NULL"),
        ),
        Index("ix_corrida_tandas_corrida", "corrida_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    corrida_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("corridas.id"))
    tanda_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tandas.id"))
    peso_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    observacion_calidad: Mapped[str | None] = mapped_column(Text)
    proporcion: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    agregada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    liberada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CorridaEtapa(Base):
    """Una de las 23 etapas de una corrida. Nace llena con la plantilla y cuenta como registrada cuando una
    persona la confirma con su inicio y su fin reales."""

    __tablename__ = "corrida_etapas"
    __table_args__ = (
        CheckConstraint("numero BETWEEN 1 AND 23", name="numero_valido"),
        CheckConstraint(f"situacion IN ({_en(SITUACIONES_ETAPA)})", name="situacion_valida"),
        CheckConstraint("fin IS NULL OR inicio IS NULL OR fin >= inicio", name="fin_despues_de_inicio"),
        CheckConstraint("distancia_m IS NULL OR distancia_m >= 0", name="distancia_no_negativa"),
        UniqueConstraint("corrida_id", "numero", name="uq_corrida_etapas_corrida_numero"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    corrida_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("corridas.id"))
    numero: Mapped[int] = mapped_column(Integer)
    situacion: Mapped[str] = mapped_column(Text, server_default="pendiente")
    lugar_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lugares.id"))
    inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metodo: Mapped[str | None] = mapped_column(Text)
    responsable: Mapped[str | None] = mapped_column(Text)
    observacion: Mapped[str | None] = mapped_column(Text)
    distancia_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    datos: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # Si al registrarla el lugar, el método y la distancia quedaron iguales a los de la plantilla.
    desde_plantilla: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    registrada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    registrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TandaFinal(ConFechas, Base):
    """Lo que sale de una corrida consolidada y entra al stock. La Parte 7 descuenta su saldo."""

    __tablename__ = "tandas_finales"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_en(ESTADOS_TANDA_FINAL)})", name="estado_valido"),
        CheckConstraint("peso_seco_kg > 0", name="peso_positivo"),
        CheckConstraint("saldo_kg >= 0 AND saldo_kg <= peso_seco_kg", name="saldo_valido"),
        CheckConstraint("humedad_pct IS NULL OR humedad_pct BETWEEN 0 AND 100", name="humedad_valida"),
        CheckConstraint("numero_sacos > 0", name="sacos_positivos"),
        UniqueConstraint("cooperativa_id", "codigo", name="uq_tandas_finales_cooperativa_codigo"),
        Index(
            "uq_tandas_finales_corrida_vigente",
            "corrida_id",
            unique=True,
            postgresql_where=text("estado <> 'anulada'"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    codigo: Mapped[str] = mapped_column(Text)
    corrida_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("corridas.id"))
    peso_seco_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    saldo_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    humedad_pct: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    calidad: Mapped[str] = mapped_column(Text)
    calidad_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calidades.id"))
    numero_sacos: Mapped[int] = mapped_column(Integer)
    lugar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lugares.id"))
    ingreso_stock_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(Text, server_default="en_stock")


class Dpp(Base):
    """Copia sellada de una corrida consolidada. Un trigger rechaza todo UPDATE sobre contenido,
    contenido_sha256, codigo, corrida_id y tanda_final_id, y todo DELETE."""

    __tablename__ = "dpps"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_en(ESTADOS_DPP)})", name="estado_valido"),
        CheckConstraint("contenido_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint(
            "(estado = 'anulado') = "
            "(anulado_en IS NOT NULL AND anulado_por IS NOT NULL AND motivo_anulacion IS NOT NULL)",
            name="anulacion_completa",
        ),
        Index("ix_dpps_cooperativa_emitido", "cooperativa_id", "emitido_en"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    codigo: Mapped[str] = mapped_column(Text, unique=True)
    corrida_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("corridas.id"))
    tanda_final_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tandas_finales.id"), unique=True)
    emitido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    emitido_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    contenido: Mapped[dict] = mapped_column(JSONB)
    contenido_sha256: Mapped[str] = mapped_column(String(64))
    pdf_documento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos.id"))
    estado: Mapped[str] = mapped_column(Text, server_default="vigente")
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)

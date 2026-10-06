"""Tablas de la Parte 9: el DEX sellado de un lote, las certificaciones de la cooperativa y la configuración
de plataforma con la clasificación de riesgo del país."""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, ConFechas
from app.models.padron import _en

ESTADOS_DEX = ("vigente", "anulado")
CLASIFICACIONES_PAIS = ("bajo", "estandar", "alto")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


class Dex(Base):
    """Copia sellada de un lote al emitirse (Parte 9). Un trigger rechaza todo UPDATE sobre el contenido, la
    huella, el código y el lote, y todo DELETE: un DEX no se borra, se anula."""

    __tablename__ = "dex"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_en(ESTADOS_DEX)})", name="estado_valido"),
        CheckConstraint("contenido_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint(
            "(estado = 'anulado') = "
            "(anulado_en IS NOT NULL AND anulado_por IS NOT NULL AND motivo_anulacion IS NOT NULL)",
            name="anulacion_completa",
        ),
        Index("uq_dex_lote_vigente", "lote_id", unique=True, postgresql_where=text("estado <> 'anulado'")),
        Index("ix_dex_cooperativa_emitido", "cooperativa_id", "emitido_en"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    codigo: Mapped[str] = mapped_column(Text, unique=True)
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lotes.id"))
    emitido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    emitido_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    contenido: Mapped[dict] = mapped_column(JSONB)
    contenido_sha256: Mapped[str] = mapped_column(String(64))
    # Identificador de documento de cada archivo generado: {"pdf_es": "...", "paquete": "...", ...}.
    archivos: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    estado: Mapped[str] = mapped_column(Text, server_default="vigente")
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)


class Certificacion(ConFechas, Base):
    """Certificación vigente de la cooperativa (criterio 7 del informe). La mantiene un administrador."""

    __tablename__ = "certificaciones"
    __table_args__ = (
        CheckConstraint("vigente_hasta >= vigente_desde", name="periodo_valido"),
        CheckConstraint(
            "(anulada_en IS NULL) = (motivo_anulacion IS NULL)",
            name="anulacion_completa",
        ),
        Index("ix_certificaciones_cooperativa", "cooperativa_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    nombre: Mapped[str] = mapped_column(Text)
    entidad_certificadora: Mapped[str] = mapped_column(Text)
    numero: Mapped[str] = mapped_column(Text)
    vigente_desde: Mapped[date] = mapped_column(Date)
    vigente_hasta: Mapped[date] = mapped_column(Date)
    documento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos.id"))
    registrada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    anulada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)


class ConfiguracionPlataforma(Base):
    """Una sola fila. Si la clasificación está vacía, el informe dice "clasificación del país no registrada":
    el sistema no asume un valor."""

    __tablename__ = "configuracion_plataforma"
    __table_args__ = (
        CheckConstraint("id = 1", name="una_sola_fila"),
        CheckConstraint(
            f"clasificacion_pais IS NULL OR clasificacion_pais IN ({_en(CLASIFICACIONES_PAIS)})",
            name="clasificacion_valida",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default=text("1"))
    clasificacion_pais: Mapped[str | None] = mapped_column(Text)
    clasificacion_fecha: Mapped[date | None] = mapped_column(Date)
    clasificacion_referencia: Mapped[str | None] = mapped_column(Text)
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))

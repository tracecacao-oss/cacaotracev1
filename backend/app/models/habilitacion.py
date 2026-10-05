"""Tablas de la Parte 4: análisis de cobertura forestal, visitas de campo, exenciones de documentos
legales y decisiones de habilitación."""

import uuid
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, ConFechas
from app.models.padron import _en

FUENTES = ("whisp", "gfw")
ESTADOS_ANALISIS = ("pendiente", "en_proceso", "completado", "error")
MOTIVOS_VISITA = ("analisis_requiere_revision", "verificacion_de_coordenadas", "otro")
USOS_OBSERVADOS = ("cacao_bajo_sombra", "cacao_sin_sombra", "bosque", "otro_cultivo", "mixto")
# Los dos documentos de tenencia no admiten exención.
TIPOS_CON_EXENCION = ("cusaf", "autorizacion_serfor", "sunafil", "sunat", "zonificacion")
DECISIONES = ("habilitar", "observar", "excluir")


class AnalisisCobertura(ConFechas, Base):
    """Una consulta a una fuente sobre la geometría exacta de una parcela. No se borra ni se sobrescribe."""

    __tablename__ = "analisis_cobertura"
    __table_args__ = (
        CheckConstraint(f"fuente IN ({_en(FUENTES)})", name="fuente_valida"),
        CheckConstraint(f"estado IN ({_en(ESTADOS_ANALISIS)})", name="estado_valido"),
        CheckConstraint("geometria_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        Index("ix_analisis_cobertura_parcela", "parcela_id", "fuente"),
        Index("ix_analisis_cobertura_cola", "estado", "reintentar_en"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    fuente: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, server_default="pendiente")
    geometria = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False), nullable=False
    )
    geometria_sha256: Mapped[str] = mapped_column(String(64))
    es_aproximacion: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    resultado_fuente: Mapped[str | None] = mapped_column(Text)
    indicadores: Mapped[dict | None] = mapped_column(JSONB)
    version_fuente: Mapped[str | None] = mapped_column(Text)
    respuesta_documento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos.id"))
    solicitado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    solicitado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intentos: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    error_detalle: Mapped[str | None] = mapped_column(Text)
    # Cola: una fila pendiente se toma cuando llega este momento (reintentos con espera).
    reintentar_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VisitaCampo(ConFechas, Base):
    """Lo que un técnico vio en la parcela. No se edita: se anula con motivo y se registra otra."""

    __tablename__ = "visitas_campo"
    __table_args__ = (
        CheckConstraint(f"motivo IN ({_en(MOTIVOS_VISITA)})", name="motivo_valido"),
        CheckConstraint(f"uso_observado IN ({_en(USOS_OBSERVADOS)})", name="uso_observado_valido"),
        CheckConstraint("char_length(descripcion) >= 30", name="descripcion_minima"),
        Index("ix_visitas_campo_parcela", "parcela_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    fecha: Mapped[date] = mapped_column(Date)
    realizada_por_nombre: Mapped[str] = mapped_column(Text)
    realizada_por_cargo: Mapped[str] = mapped_column(Text)
    registrada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    motivo: Mapped[str] = mapped_column(Text)
    perimetro_recorrido: Mapped[bool] = mapped_column(Boolean)
    uso_observado: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[str] = mapped_column(Text)
    anulada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)


class ExencionDocumento(Base):
    """Declaración motivada de que un documento legal no aplica a una parcela."""

    __tablename__ = "exenciones_documento"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_en(TIPOS_CON_EXENCION)})", name="tipo_valido"),
        CheckConstraint("char_length(motivo) >= 30", name="motivo_minimo"),
        # Una sola exención vigente por parcela y tipo.
        Index(
            "uq_exenciones_vigente",
            "parcela_id",
            "tipo",
            unique=True,
            postgresql_where=text("retirada_en IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    tipo: Mapped[str] = mapped_column(Text)
    motivo: Mapped[str] = mapped_column(Text)
    declarada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    declarada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    retirada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))


class DecisionHabilitacion(Base):
    """Cada decisión sobre una parcela. Un trigger rechaza UPDATE y DELETE: no se edita ni se borra."""

    __tablename__ = "decisiones_habilitacion"
    __table_args__ = (
        CheckConstraint(f"decision IN ({_en(DECISIONES)})", name="decision_valida"),
        CheckConstraint("geometria_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        Index("ix_decisiones_habilitacion_parcela", "parcela_id", "decidida_en"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    decision: Mapped[str] = mapped_column(Text)
    decidida_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    decidida_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    nota: Mapped[str | None] = mapped_column(Text)
    requisitos: Mapped[dict] = mapped_column(JSONB)
    geometria_sha256: Mapped[str] = mapped_column(String(64))
    evidencia_visita_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visitas_campo.id"))
    evidencia_analisis_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("analisis_cobertura.id"))

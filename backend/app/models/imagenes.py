"""Tablas de la adenda 2 de la Parte 4: imágenes satelitales de la parcela, revisiones de imágenes y
consumo de unidades de procesamiento de Copernicus."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, ConFechas
from app.models.padron import _en

# `externa`: imagen que carga el administrador cuando las demás no permiten distinguir (7.1).
FUENTES_IMAGEN = ("sentinel2", "esri_wayback", "externa")
PAPELES_IMAGEN = ("anterior_al_corte", "anual", "reciente", "alta_resolucion", "externa")
ESTADOS_IMAGEN = ("pendiente", "generada", "sin_imagen_utilizable", "error")
OBSERVACIONES_2020 = ("bosque", "cultivo_o_uso_agricola", "mixto", "no_se_distingue")
OBSERVACIONES_CAMBIO = ("sin_cambio_visible", "cambio_visible", "no_se_distingue")


class ImagenParcela(ConFechas, Base):
    """Una imagen del juego de una parcela. La genera el sistema (o la carga el administrador, si es
    externa); nadie la edita ni la anula a mano. Queda obsoleta si cambia la geometría de la parcela."""

    __tablename__ = "imagenes_parcela"
    __table_args__ = (
        CheckConstraint(f"fuente IN ({_en(FUENTES_IMAGEN)})", name="fuente_valida"),
        CheckConstraint(f"papel IN ({_en(PAPELES_IMAGEN)})", name="papel_valido"),
        CheckConstraint(f"estado IN ({_en(ESTADOS_IMAGEN)})", name="estado_valido"),
        CheckConstraint("geometria_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint(
            "nubes_parcela_pct IS NULL OR nubes_parcela_pct BETWEEN 0 AND 100", name="nubes_porcentaje"
        ),
        CheckConstraint("estado <> 'generada' OR fecha_captura IS NOT NULL", name="generada_con_fecha"),
        Index("ix_imagenes_parcela_parcela", "parcela_id", "geometria_sha256"),
        Index("ix_imagenes_parcela_cola", "estado", "creado_en"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    fuente: Mapped[str] = mapped_column(Text)
    papel: Mapped[str] = mapped_column(Text)
    # Año del período que cubre una imagen anual (también cuando quedó sin imagen utilizable).
    periodo: Mapped[int | None] = mapped_column(Integer)
    fecha_captura: Mapped[date | None] = mapped_column(Date)
    dias_respecto_al_corte: Mapped[int | None] = mapped_column(Integer)
    resolucion_m: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    nubes_parcela_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    identificador_fuente: Mapped[str | None] = mapped_column(Text)
    proveedor: Mapped[str | None] = mapped_column(Text)
    geometria_sha256: Mapped[str] = mapped_column(String(64))
    documento_natural_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos.id"))
    documento_infrarrojo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos.id"))
    estado: Mapped[str] = mapped_column(Text, server_default="pendiente")
    error_detalle: Mapped[str | None] = mapped_column(Text)
    # "Regenerar" deja el juego anterior como historial: la revisión que lo citó sigue apuntando a él.
    reemplazada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cargada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))


class RevisionImagenes(ConFechas, Base):
    """Lo que una persona con nombre observó en imágenes identificadas. No es un veredicto del sistema.
    No se edita: si está mal, se anula con motivo y se registra otra."""

    __tablename__ = "revisiones_imagenes"
    __table_args__ = (
        CheckConstraint(f"observacion_2020 IN ({_en(OBSERVACIONES_2020)})", name="observacion_2020_valida"),
        CheckConstraint(
            f"observacion_cambio IN ({_en(OBSERVACIONES_CAMBIO)})", name="observacion_cambio_valida"
        ),
        CheckConstraint("char_length(descripcion) >= 50", name="descripcion_minima"),
        CheckConstraint("geometria_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint(
            "(anulada_en IS NULL) = (anulada_por IS NULL AND motivo_anulacion IS NULL)",
            name="anulacion_completa",
        ),
        Index("ix_revisiones_imagenes_parcela", "parcela_id", "revisada_en"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    revisada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    revisada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    imagenes: Mapped[list] = mapped_column(JSONB)
    observacion_2020: Mapped[str] = mapped_column(Text)
    observacion_cambio: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[str] = mapped_column(Text)
    geometria_sha256: Mapped[str] = mapped_column(String(64))
    anulada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)


class ConsumoImagenes(Base):
    """Unidades de procesamiento de Copernicus usadas en cada generación (11.1: cuota del mes)."""

    __tablename__ = "consumo_imagenes"
    __table_args__ = (
        CheckConstraint("pu >= 0", name="pu_no_negativas"),
        Index("ix_consumo_imagenes_mes", "mes"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    mes: Mapped[date] = mapped_column(Date)  # primer día del mes, en UTC (la cuota de Copernicus)
    parcela_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    pu: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    peticiones: Mapped[int] = mapped_column(Integer)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

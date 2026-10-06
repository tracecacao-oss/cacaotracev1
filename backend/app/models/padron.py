"""Tablas de la Parte 3 (documentos de sustento, parcelas y superposiciones), ampliadas en la Parte 4."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from geoalchemy2 import Geometry
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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, ConFechas

# Los 7 documentos del expediente legal de la parcela (Parte 4); su catálogo vive en
# app/catalogos/documentos_legales.py.
TIPOS_LEGALES = (
    "titulo_sunarp",
    "constancia_posesion",
    "cusaf",
    "autorizacion_serfor",
    "sunafil",
    "sunat",
    "zonificacion",
)
TIPOS_DOCUMENTO = (
    "dni",
    "constancia_ppa",
    "sustento_midagri",
    "archivo_geometria",
    *TIPOS_LEGALES,
    "foto_visita",
    "respuesta_analisis",
    # Parte 5; la adenda 3 cambió "guia_remision" por "documento_entrega"
    "documento_entrega",
    "dop_pdf",
    # Adenda 2 de la Parte 4
    "imagen_satelital",
    "imagen_externa",
)
ENTIDADES_DOCUMENTO = ("productor", "parcela", "visita", "analisis", "tanda", "dop", "imagen")
ESTADOS_HABILITACION = ("pendiente", "habilitada", "observada", "excluida")
ESTADOS_MIDAGRI = ("no_registrada", "sin_observacion", "en_revision", "validado")
ESTADOS_PARCELA = ("activa", "inactiva")
ESTADOS_SUPERPOSICION = ("abierta", "resuelta", "aceptada")


def _en(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class Documento(Base):
    """Todo archivo cargado. El archivo vive en Storage; aquí se guarda dónde está y qué respalda.

    No se borra: se anula con un motivo.
    """

    __tablename__ = "documentos"
    __table_args__ = (
        CheckConstraint(f"entidad IN ({_en(ENTIDADES_DOCUMENTO)})", name="entidad_valida"),
        CheckConstraint(f"tipo IN ({_en(TIPOS_DOCUMENTO)})", name="tipo_valido"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        # Solo la respuesta de un análisis y las imágenes satelitales las guarda el sistema, sin persona.
        CheckConstraint(
            "subido_por IS NOT NULL OR tipo IN ('respuesta_analisis', 'imagen_satelital')",
            name="subido_por_si_no_sistema",
        ),
        CheckConstraint(
            "fecha_vencimiento IS NULL OR fecha_emision IS NULL OR fecha_vencimiento > fecha_emision",
            name="vencimiento_despues_de_emision",
        ),
        Index("ix_documentos_entidad", "entidad", "entidad_id"),
        # El mismo contenido no se carga dos veces para el mismo registro y tipo.
        Index(
            "uq_documentos_vigente_contenido",
            "entidad",
            "entidad_id",
            "tipo",
            "sha256",
            unique=True,
            postgresql_where=text("anulado_en IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    entidad: Mapped[str] = mapped_column(Text)
    entidad_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    tipo: Mapped[str] = mapped_column(Text)
    ruta: Mapped[str] = mapped_column(Text)
    nombre_original: Mapped[str] = mapped_column(Text)
    tipo_mime: Mapped[str] = mapped_column(Text)
    tamano_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    subido_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)
    # Parte 4: datos de los documentos legales y su cotejo en fuente. Opcionales para los demás tipos.
    numero: Mapped[str | None] = mapped_column(Text)
    entidad_emisora: Mapped[str | None] = mapped_column(Text)
    fecha_emision: Mapped[date | None] = mapped_column(Date)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)
    cotejado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cotejado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    cotejo_nota: Mapped[str | None] = mapped_column(Text)


class Parcela(ConFechas, Base):
    """Porción continua de tierra de un productor, en WGS 84. No se elimina: pasa a inactiva."""

    __tablename__ = "parcelas"
    __table_args__ = (
        CheckConstraint("codigo ~ '^PA-[0-9]{5}$'", name="codigo_formato"),
        CheckConstraint("tipo_geometria IN ('poligono', 'punto')", name="tipo_geometria_valido"),
        CheckConstraint(
            "(tipo_geometria = 'poligono' AND GeometryType(geometria) = 'POLYGON')"
            " OR (tipo_geometria = 'punto' AND GeometryType(geometria) = 'POINT')",
            name="geometria_segun_tipo",
        ),
        CheckConstraint(
            "tipo_geometria <> 'poligono' OR area_calculada_ha IS NOT NULL", name="area_calculada_si_poligono"
        ),
        CheckConstraint(
            "tipo_geometria <> 'punto' OR area_declarada_ha IS NOT NULL", name="area_declarada_si_punto"
        ),
        CheckConstraint(
            "area_cultivada_ha <= CASE WHEN tipo_geometria = 'poligono'"
            " THEN area_calculada_ha ELSE area_declarada_ha END",
            name="cultivada_no_supera_total",
        ),
        CheckConstraint("origen_geometria IN ('dibujada', 'archivo')", name="origen_valido"),
        CheckConstraint(
            "origen_geometria <> 'archivo' OR archivo_documento_id IS NOT NULL",
            name="archivo_si_origen_archivo",
        ),
        CheckConstraint(f"midagri_estado IN ({_en(ESTADOS_MIDAGRI)})", name="midagri_estado_valido"),
        CheckConstraint(f"estado IN ({_en(ESTADOS_PARCELA)})", name="estado_valido"),
        CheckConstraint(
            f"habilitacion_estado IN ({_en(ESTADOS_HABILITACION)})", name="habilitacion_estado_valido"
        ),
        UniqueConstraint("cooperativa_registro_id", "codigo", name="uq_parcelas_cooperativa_codigo"),
        Index("uq_parcelas_productor_nombre", "productor_id", text("lower(nombre)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    codigo: Mapped[str] = mapped_column(Text)
    productor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productores.id"), index=True)
    nombre: Mapped[str] = mapped_column(Text)
    departamento: Mapped[str] = mapped_column(Text)
    provincia: Mapped[str] = mapped_column(Text)
    distrito: Mapped[str] = mapped_column(Text)
    centro_poblado: Mapped[str | None] = mapped_column(Text)
    tipo_geometria: Mapped[str] = mapped_column(Text)
    geometria = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True), nullable=False
    )
    area_calculada_ha: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    area_declarada_ha: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    area_cultivada_ha: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    origen_geometria: Mapped[str] = mapped_column(Text)
    archivo_documento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos.id"))
    midagri_estado: Mapped[str] = mapped_column(Text, server_default="no_registrada")
    midagri_codigo: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, server_default="activa")
    registrada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfiles.id"))
    registrada_por_rol: Mapped[str] = mapped_column(Text)
    cooperativa_registro_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    # Parte 4: compuerta de habilitación y momento del último cambio de geometría.
    habilitacion_estado: Mapped[str] = mapped_column(Text, server_default="pendiente")
    geometria_actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Superposicion(ConFechas, Base):
    """Par de parcelas activas cuya tierra se superpone. a es siempre el identificador menor."""

    __tablename__ = "superposiciones"
    __table_args__ = (
        CheckConstraint("parcela_a_id < parcela_b_id", name="par_ordenado"),
        CheckConstraint("tipo IN ('poligono_poligono', 'punto_en_poligono')", name="tipo_valido"),
        CheckConstraint(f"estado IN ({_en(ESTADOS_SUPERPOSICION)})", name="estado_valido"),
        UniqueConstraint("parcela_a_id", "parcela_b_id", name="uq_superposiciones_par"),
        Index("ix_superposiciones_parcela_b", "parcela_b_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parcela_a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    parcela_b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parcelas.id"))
    tipo: Mapped[str] = mapped_column(Text)
    area_ha: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    porcentaje: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    estado: Mapped[str] = mapped_column(Text, server_default="abierta")
    nota: Mapped[str | None] = mapped_column(Text)
    cerrada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

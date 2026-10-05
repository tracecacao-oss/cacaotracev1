import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.schemas.comunes import Entrada, Salida, Texto, TextoOpcional

EstadoMidagri = Literal["no_registrada", "sin_observacion", "en_revision", "validado"]
Hectareas = Annotated[Decimal, Field(ge=0, le=100000, max_digits=10, decimal_places=4)]


class ParcelaDatos(Entrada):
    nombre: Texto
    departamento: Texto
    provincia: Texto
    distrito: Texto
    centro_poblado: TextoOpcional | None = None
    area_declarada_ha: Hectareas | None = None
    area_cultivada_ha: Annotated[Hectareas, Field(gt=0)]
    midagri_estado: EstadoMidagri = "no_registrada"
    midagri_codigo: TextoOpcional | None = None


class ParcelaCambios(Entrada):
    nombre: Texto | None = None
    departamento: Texto | None = None
    provincia: Texto | None = None
    distrito: Texto | None = None
    centro_poblado: TextoOpcional | None = None
    area_declarada_ha: Hectareas | None = None
    area_cultivada_ha: Annotated[Hectareas, Field(gt=0)] | None = None
    midagri_estado: EstadoMidagri | None = None
    midagri_codigo: TextoOpcional | None = None
    # Cambiar la geometría exige un motivo.
    geometria: dict[str, Any] | None = None
    motivo: TextoOpcional | None = None


class ErrorGeometriaSalida(BaseModel):
    codigo: str
    mensaje: str


class SuperposicionPrevista(BaseModel):
    """Lo que pasaría al guardar. De otra cooperativa no se revela la parcela."""

    propia: bool
    otra_cooperativa: bool
    codigo: str | None
    nombre: str | None
    tipo: str
    area_ha: Decimal | None
    porcentaje: Decimal | None


class GeometriaAnalizada(BaseModel):
    indice: int
    nombre: str | None
    tipo: str | None
    area_ha: Decimal | None
    geometria: dict[str, Any] | None
    valida: bool
    errores: list[ErrorGeometriaSalida]
    # Solo si se indica el productor: superposiciones que se abrirían al guardar.
    superposiciones: list[SuperposicionPrevista] = []


class AnalisisArchivo(BaseModel):
    geometrias: list[GeometriaAnalizada]


class DocumentoSalida(Salida):
    id: uuid.UUID
    tipo: str
    nombre_original: str
    tipo_mime: str
    tamano_bytes: int
    creado_en: datetime
    subido_por_nombre: str | None = None
    anulado_en: datetime | None
    motivo_anulacion: str | None
    vigente: bool = True
    # Parte 4: datos de los documentos legales y su cotejo en fuente.
    numero: str | None = None
    entidad_emisora: str | None = None
    fecha_emision: date | None = None
    fecha_vencimiento: date | None = None
    cotejado_en: datetime | None = None
    cotejo_nota: str | None = None


class ProductorDeParcela(BaseModel):
    id: uuid.UUID
    dni: str
    nombres: str
    apellidos: str


class ParcelaSalida(BaseModel):
    id: uuid.UUID
    codigo: str
    productor: ProductorDeParcela
    nombre: str
    departamento: str
    provincia: str
    distrito: str
    centro_poblado: str | None
    tipo_geometria: str
    geometria: dict[str, Any]
    area_calculada_ha: Decimal | None
    area_declarada_ha: Decimal | None
    area_cultivada_ha: Decimal
    area_total_ha: Decimal
    origen_geometria: str
    midagri_estado: str
    midagri_codigo: str | None
    nivel_midagri: str
    estado: str
    alertas: list[str]
    creado_en: datetime
    # Parte 4: compuerta de habilitación.
    habilitacion_estado: str = "pendiente"
    requisitos_pendientes: list[str] = []


class SuperposicionDeParcela(BaseModel):
    id: uuid.UUID
    tipo: str
    estado: str
    area_ha: Decimal | None
    porcentaje: Decimal | None
    otra_cooperativa: bool
    # Solo si la otra parcela es de la misma cooperativa.
    otra_parcela: dict[str, Any] | None


class HistorialSalida(BaseModel):
    ocurrido_en: datetime
    accion: str
    usuario_nombre: str | None
    detalle: dict[str, Any]


class ProcedenciaSalida(BaseModel):
    origen_geometria: str
    registrada_por_rol: str
    recorrida_en_campo: bool
    fecha_recorrido: date | None


class ParcelaDetalle(ParcelaSalida):
    documentos: list[DocumentoSalida]
    superposiciones: list[SuperposicionDeParcela]
    historial: list[HistorialSalida]
    procedencia: ProcedenciaSalida | None = None


class Anulacion(Entrada):
    motivo: Texto


class UrlDescarga(BaseModel):
    url: str
    vence_en_segundos: int

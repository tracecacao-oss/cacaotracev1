"""Adenda 5: declaración anual del productor."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.parcelas import DocumentoSalida

EstadoDeclaracion = Literal["por_firmar", "vigente", "vencida", "reemplazada"]
EstadoProductor = Literal["sin_declaracion", "por_firmar", "vigente", "por_vencer", "vencida"]
FiltroDeclaracion = Literal["vencida", "por_vencer", "por_firmar", "sin_declaracion"]


class DeclaracionNueva(BaseModel):
    """El personal registra las respuestas en nombre del productor. Queda por firmar."""

    model_config = ConfigDict(extra="forbid")

    respuestas: dict[str, Any]


class MiDeclaracion(BaseModel):
    """El productor responde y toca "Declaro"."""

    model_config = ConfigDict(extra="forbid")

    respuestas: dict[str, Any]
    declaro: bool


class RevisionProducto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: Literal["figura", "no_figura"]
    registro: str | None = Field(default=None, max_length=60)

    @field_validator("registro")
    @classmethod
    def _limpia(cls, valor: str | None) -> str | None:
        valor = (valor or "").strip()
        return valor or None


class NotaSeguimiento(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nota: str = Field(max_length=2000)

    @field_validator("nota")
    @classmethod
    def _minimo(cls, valor: str) -> str:
        valor = " ".join(valor.split())
        if len(valor) < 50:
            raise ValueError("La nota de seguimiento lleva 50 caracteres como mínimo.")
        return valor


# ---------- Cuestionario ----------


class OpcionPregunta(BaseModel):
    valor: str
    etiqueta: str


class PreguntaSalida(BaseModel):
    codigo: str
    texto: str
    texto_personal: str
    ayuda: str
    ayuda_personal: str
    tipo: str
    valores: list[OpcionPregunta]
    minimo: float | None
    maximo: float | None
    referencias: list[str]
    cuando: list[str]


class BloqueAnexo(BaseModel):
    tipo: str
    texto: str
    en_pantalla: bool = False


class CuestionarioSalida(BaseModel):
    version: int
    version_texto: int
    preguntas: list[PreguntaSalida]
    tipos_producto: list[OpcionPregunta]
    maximo_productos: int
    area_agricultura_familiar_ha: float
    uit_soles: float | None
    uit_anio: int | None
    jornal_minimo_referencia: float | None
    jornal_referencia_nota: str | None
    consultas_senasa: list[OpcionPregunta]
    anexo: list[BloqueAnexo]


# ---------- Declaración ----------


class RespuestaSalida(BaseModel):
    codigo: str
    pregunta: str
    valor: Any
    etiqueta: str


class ProductoSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str
    revision: str
    registro: str | None
    revisado_por_nombre: str | None
    revisado_en: datetime | None
    copiada: bool


class SeguimientoSalida(BaseModel):
    nota: str
    por_nombre: str | None
    en: datetime


class DeclaracionSalida(BaseModel):
    id: uuid.UUID
    origen: str
    estado: EstadoDeclaracion
    version_cuestionario: int
    version_texto: int
    registrada_por_nombre: str | None
    registrada_en: datetime
    declarada_en: date | None
    vigente_hasta: date | None
    respuestas: list[RespuestaSalida]
    contexto: dict[str, Any]
    productos: list[ProductoSalida]
    documentos: list[DocumentoSalida]
    seguimiento: SeguimientoSalida | None = None


class DeclaracionResumen(BaseModel):
    id: uuid.UUID
    origen: str
    estado: EstadoDeclaracion
    registrada_por_nombre: str | None
    registrada_en: datetime
    declarada_en: date | None
    vigente_hasta: date | None


class HechoSalida(BaseModel):
    pregunta: str
    texto: str
    valor: str


class RequisitoProductorSalida(BaseModel):
    codigo: str
    nombre: str
    referencias: list[str]
    nivel: str
    diligencia: str
    nivel_texto: str
    estado: str
    etiqueta: str
    motivo: str
    siguiente: str | None
    hechos: list[HechoSalida]
    falta: list[str]
    nivel_verificacion: str | None


class DeclaracionProductorSalida(BaseModel):
    estado: EstadoProductor
    vigente: DeclaracionSalida | None
    por_firmar: DeclaracionSalida | None
    historial: list[DeclaracionResumen]
    calculados: dict[str, Any]
    requisitos: list[RequisitoProductorSalida]
    aviso_area: str | None
    pendientes: list[str]
    falta: str | None
    sugerencias_productos: list[str]

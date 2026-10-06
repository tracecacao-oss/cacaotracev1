"""Entradas y salidas de la Parte 4: análisis, visitas, expediente y compuerta de habilitación."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, StringConstraints

from app.schemas.comunes import Entrada, Salida
from app.schemas.parcelas import DocumentoSalida

TextoLargo30 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=30, max_length=4000)]
TextoLargo50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=50, max_length=4000)]
Nota = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=4000)]
TipoExencion = Literal["cusaf", "autorizacion_serfor", "sunafil", "sunat", "zonificacion"]

# ---------- Análisis de cobertura ----------


class FuenteSalida(BaseModel):
    fuente: Literal["whisp", "gfw", "mapbiomas"]
    nombre: str
    configurada: bool


class AnalisisSalida(BaseModel):
    id: uuid.UUID
    parcela_id: uuid.UUID
    fuente: str
    estado: str
    es_aproximacion: bool
    resultado_fuente: str | None
    resultado_texto: str | None
    indicadores: dict[str, Any] | None
    version_fuente: str | None
    solicitado_en: datetime
    solicitado_por_nombre: str | None
    completado_en: datetime | None
    intentos: int
    error_detalle: str | None
    obsoleto: bool
    vigente: bool
    # Si lo que dijo la fuente pide que una persona revise la parcela (regla de cada fuente). La interfaz
    # muestra el detalle abierto solo en ese caso.
    requiere_revision: bool = False
    # El productor no recibe la respuesta completa de la fuente.
    respuesta_documento_id: uuid.UUID | None = None


class AnalisisDetalle(AnalisisSalida):
    respuesta_url: str | None = None


class AnalisisSolicitado(BaseModel):
    analisis: list[AnalisisSalida]


class MedidaSalida(BaseModel):
    via: str
    nombre: str
    valor: Any
    unidad: str | None
    mide_bosque: bool
    serie: bool


class FilaConvergencia(BaseModel):
    conjunto: str
    nombre: str
    vias: list[str]
    fechas: dict[str, datetime]
    # None: ese conjunto no mide esa pregunta; la celda queda vacía.
    al_2020: list[MedidaSalida] | None
    despues_2020: list[MedidaSalida] | None
    registra_bosque_2020: bool | None
    registra_cambio: bool | None


class ConvergenciaSalida(BaseModel):
    filas: list[FilaConvergencia]
    frase: str
    conteos: dict[str, int]
    discrepan: dict[str, bool]
    umbral_bosque_2020_pct: float
    # Cuántos conjuntos deben registrar bosque el 31/12/2020 para pedir revisión, y si se alcanzan.
    mapas_minimos_bosque_2020: int = 3
    hubo_bosque_2020: bool = False
    area_ha: float | None


# ---------- Procedencia ----------


class Procedencia(BaseModel):
    origen_geometria: str
    registrada_por_rol: str
    recorrida_en_campo: bool
    fecha_recorrido: date | None


# ---------- Expediente legal ----------


class ExencionNueva(Entrada):
    tipo: TipoExencion
    motivo: TextoLargo30


class ExencionSalida(BaseModel):
    id: uuid.UUID
    tipo: str
    motivo: str
    declarada_en: datetime
    declarada_por_nombre: str | None
    retirada_en: datetime | None


class CasillaSalida(BaseModel):
    codigo: str
    nombre: str
    grupo: str
    tenencia: bool
    registro_consultable: bool
    admite_exencion: bool
    estado: Literal["vigente", "por_vencer", "vencido", "no_aplica", "faltante"]
    nivel: Literal["documentado", "verificado_en_fuente"] | None
    vence_en: date | None
    documentos: list[DocumentoSalida]
    exencion: ExencionSalida | None


class ExpedienteSalida(BaseModel):
    estado: Literal["completo", "incompleto"]
    faltan: list[str]
    tenencia_solo_posesion: bool
    casillas: list[CasillaSalida]


class CotejoNuevo(Entrada):
    nota: Nota


# ---------- Compuerta de habilitación ----------


class Requisito(BaseModel):
    codigo: str
    cumple: bool
    detalle: str


class DecisionSalida(Salida):
    id: uuid.UUID
    decision: str
    decidida_por_nombre: str | None = None
    decidida_en: datetime
    nota: str | None
    requisitos: dict[str, Any]
    evidencia_visita_id: uuid.UUID | None
    evidencia_analisis_id: uuid.UUID | None
    evidencia_revision_id: uuid.UUID | None = None


class HabilitacionSalida(BaseModel):
    parcela_id: uuid.UUID
    estado: Literal["pendiente", "habilitada", "observada", "excluida"]
    requisitos: list[Requisito]
    puede_habilitar: bool
    alertas: list[str]
    nota_obligatoria: bool
    decisiones: list[DecisionSalida]


class HabilitarEntrada(Entrada):
    nota: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None = None


class ExcluirEntrada(Entrada):
    descripcion: TextoLargo50
    # Adenda 2 (8.5): la evidencia es una revisión de imágenes o un análisis; ya no una visita.
    evidencia_revision_id: uuid.UUID | None = None
    evidencia_analisis_id: uuid.UUID | None = None
    confirmacion: str


class PorVencerSalida(BaseModel):
    parcela_id: uuid.UUID
    parcela_codigo: str
    parcela_nombre: str
    productor_nombre: str
    tipo: str
    tipo_nombre: str
    estado: str
    vence_en: date


class ResumenHabilitacion(BaseModel):
    por_estado: dict[str, int]
    por_vencer: list[PorVencerSalida]

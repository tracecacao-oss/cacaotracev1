"""Entradas y salidas de la adenda 4: perfil legal, requisitos e incidencias de la parcela."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, StringConstraints

from app.catalogos import perfil_legal
from app.models.legalidad import TIPOS_INCIDENCIA
from app.schemas.comunes import Entrada
from app.schemas.habilitacion import ExencionSalida, Requisito
from app.schemas.parcelas import DocumentoSalida

Texto = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Nota = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=4000)]
TextoLargo50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=50, max_length=4000)]
Corto = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]

EstadoRequisito = Literal["sin_dato", "no_aplica", "sustentado", "por_vencer", "vencido", "sin_sustento"]
Nivel = Literal["declarado", "documentado", "verificado_en_fuente"]


# ---------- Entradas ----------


class DetalleDeclarado(Entrada):
    comunidad_nombre: Corto | None = None
    comunidad_tipo: Literal[perfil_legal.TIPOS_COMUNIDAD] | None = None
    inscrita: Literal[perfil_legal.COMUNIDAD_INSCRITA] | None = None
    area_nombre: Corto | None = None


class DeclaracionNueva(Entrada):
    variable: Literal[perfil_legal.CODIGOS]
    valor: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    nota: Texto | None = None
    detalle: DetalleDeclarado | None = None


class NotaRequisito(Entrada):
    nota: Nota


class IncidenciaNueva(Entrada):
    tipo: Literal[TIPOS_INCIDENCIA]
    descripcion: TextoLargo50
    fuente: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=400)]


class CierreIncidencia(Entrada):
    nota: Nota


# ---------- Salidas ----------


class Opcion(BaseModel):
    valor: str
    etiqueta: str


class ValorSalida(BaseModel):
    """Una fila vigente del perfil: lo que dijo el cruce o lo que declaró una persona."""

    valor: str
    etiqueta: str
    origen: Literal["cruce", "declarado"]
    fuente: str | None
    detalle: dict[str, Any] | None
    registrada_en: datetime
    registrada_por_nombre: str | None


class VariableSalida(BaseModel):
    codigo: str
    pregunta: str
    ayuda: str
    fuente_orientador: str
    cruzable: bool
    opciones: list[Opcion]  # vacío: un año de 4 dígitos
    # reserva_bosque_30 solo se pregunta con la excepción de la Ley N.º 31973.
    se_pregunta: bool
    valor: str | None
    etiqueta: str | None
    origen: Literal["cruce", "declarado"] | None
    nivel: Literal["verificado_en_fuente", "declarado"] | None
    cruce: ValorSalida | None
    declarado: ValorSalida | None
    # Hallazgo perfil_declarado_sin_cruce: tiene capa oficial pero manda lo declarado.
    declarado_sin_cruce: bool = False
    aviso: str | None = None


class TipoAceptado(BaseModel):
    codigo: str
    nombre: str


class RequisitoLegalSalida(BaseModel):
    codigo: str
    nombre: str
    referencias: list[str]
    nivel_orientador: Literal["alto", "bajo"]
    diligencia: Literal["aligerada", "estandar"]
    bloquea: bool
    que_pide: str
    estado: EstadoRequisito
    motivo: str
    sustento: DocumentoSalida | None
    sustento_nivel: Nivel | None
    nota: str | None
    pide_nota: bool
    por_excepcion: bool
    aceptados: list[TipoAceptado]
    documentos: list[DocumentoSalida]  # los cargados de los tipos aceptados, también los vencidos
    # La plantilla para firmar que se ofrece, si la hay: "declaracion-jurada-tenencia" o "constancia-comunal".
    plantilla: str | None = None
    # Lo que trajo un cruce de apoyo, para comparar con el documento cargado (cesiones en uso de SERFOR).
    registro_oficial: list[dict[str, Any]] = []


class IncidenciaSalida(BaseModel):
    id: uuid.UUID
    tipo: str
    descripcion: str
    fuente: str
    estado: Literal["abierta", "cerrada"]
    registrada_en: datetime
    registrada_por_nombre: str | None
    cierre_nota: str | None
    cerrada_en: datetime | None
    cerrada_por_nombre: str | None


class CapaSalida(BaseModel):
    codigo: str
    nombre: str
    entidad: str
    variable: str
    estado: Literal["hecho", "fallo", "pendiente"]
    consultada_en: datetime | None
    error: str | None
    servicio: str
    numeros: list[int]


class CruceSalida(BaseModel):
    en_cola: bool
    solicitado_en: datetime | None
    aproximacion: bool
    capas: list[CapaSalida]


class LegalidadSalida(BaseModel):
    parcela_id: uuid.UUID
    orientador: str
    perfil: list[VariableSalida]
    perfil_completo: bool
    requisitos: list[RequisitoLegalSalida]
    compuerta: list[Requisito]
    alertas: list[str]
    incidencias: list[IncidenciaSalida]
    cruce: CruceSalida
    plantillas: list[str]
    documentos_anteriores: list[DocumentoSalida]
    exenciones: list[ExencionSalida]  # historial: ya no cubren nada
    area_total_ha: float | None

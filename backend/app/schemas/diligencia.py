"""Entradas y salidas de la adenda 6: la política de la organización, sus actuaciones de diligencia, el cuadro
de señales y la lista de productos buscados en el registro del SENASA."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.catalogos import actuaciones, requisitos_organizacion
from app.schemas.comunes import Entrada
from app.schemas.cooperativa import ConsultaPublica, RequisitoOrganizacionSalida
from app.schemas.parcelas import DocumentoSalida

TemaPolitica = Literal[requisitos_organizacion.CODIGOS_TEMAS]
TipoActuacion = Literal[actuaciones.CODIGOS_TIPOS]
TemaActuacion = Literal[actuaciones.CODIGOS_TEMAS]
Descripcion = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=actuaciones.LARGO_DESCRIPCION, max_length=4000)
]
Resultado = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=actuaciones.LARGO_RESULTADO, max_length=4000)
]
Contraparte = Annotated[str, StringConstraints(strip_whitespace=True, max_length=400)]
Lugar = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Motivo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=4000)]

# ---------- Política ----------


class TemaPoliticaSalida(BaseModel):
    codigo: str
    nombre: str
    que_dice: str
    referencias: list[str]
    estado: Literal["sustentado", "sin_sustento"]
    # La adopción más reciente entre las políticas vigentes que lo cubren.
    adoptada_en: date | None
    politicas: int
    falta: str | None = None


class PoliticaSalida(BaseModel):
    id: uuid.UUID
    temas: list[str]
    adoptada_en: date
    organo: str
    version_plantilla: int | None
    documento: DocumentoSalida | None
    registrada_por_nombre: str | None
    registrada_en: datetime
    vigente: bool
    anulada_en: datetime | None
    anulada_por_nombre: str | None
    motivo_anulacion: str | None


class PoliticasSalida(BaseModel):
    temas: list[TemaPoliticaSalida]
    requisito: RequisitoOrganizacionSalida
    politicas: list[PoliticaSalida]
    canal_denuncias_contacto: str | None
    organo_sugerido: str
    version_plantilla: int


class Anulacion(Entrada):
    motivo: Motivo


# ---------- Actuaciones ----------


class ActuacionNueva(Entrada):
    tipo: TipoActuacion
    temas: list[TemaActuacion] = Field(min_length=1)
    fecha: date
    descripcion: Descripcion
    resultado: Resultado
    contraparte: Contraparte | None = None
    participantes: int | None = Field(None, gt=0, le=100_000)
    departamento: Lugar | None = None
    provincia: Lugar | None = None
    distrito: Lugar | None = None
    productor_ids: list[uuid.UUID] = Field(default_factory=list, max_length=2000)


class ProductorAlcanzado(BaseModel):
    id: uuid.UUID
    nombre: str
    dni: str


class ActuacionSalida(BaseModel):
    id: uuid.UUID
    tipo: str
    tipo_nombre: str
    temas: list[str]
    fecha: date
    descripcion: str
    contraparte: str | None
    resultado: str
    participantes: int | None
    departamento: str | None
    provincia: str | None
    distrito: str | None
    # Sección 6.5, regla 3: declarado sin evidencia, documentado con ella.
    nivel: Literal["declarado", "documentado"]
    vigente: bool
    vigente_hasta: date
    productores: int
    evidencias: int
    registrada_por_nombre: str | None
    registrada_en: datetime
    anulada_en: datetime | None
    anulada_por_nombre: str | None
    motivo_anulacion: str | None


class ActuacionDetalle(ActuacionSalida):
    productores_alcanzados: list[ProductorAlcanzado]
    documentos: list[DocumentoSalida]


# ---------- Cuadro de señales ----------


class SenalSalida(BaseModel):
    codigo: str
    nombre: str
    referencias: list[str]
    diligencia: str
    regla: str
    cuenta: int | None
    # Lo que hay detrás de la señal, dicho con la cuenta: "5 parcelas en tierra forestal".
    texto: str
    esperada: bool
    actuaciones_vigentes: int
    ultima: date | None
    estado: Literal["sustentado", "sin_sustento", "no_se_espera"]


class TipoActuacionSalida(BaseModel):
    codigo: str
    nombre: str
    que_es: str
    ejemplos: str
    pide_contraparte: bool


class FuenteSugeridaSalida(BaseModel):
    nombre: str
    temas: list[str]
    enlace: str | None


class DiligenciaSalida(BaseModel):
    senales: list[SenalSalida]
    requisito: RequisitoOrganizacionSalida
    tipos: list[TipoActuacionSalida]
    fuentes: list[FuenteSugeridaSalida]
    vigencia_meses: int


# ---------- Lista de productos ----------


class ProductoRevisado(BaseModel):
    nombre: str
    tipo: str
    revision: Literal["figura", "no_figura", "sin_revisar"]
    registro: str | None
    revisado_en: datetime | None
    productores: int


class ProductosRevisadosSalida(BaseModel):
    productos: list[ProductoRevisado]
    consultas: list[ConsultaPublica]

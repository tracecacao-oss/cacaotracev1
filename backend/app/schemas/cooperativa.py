"""Entradas y salidas de la Parte 8: datos de la cooperativa, su expediente legal, documentos de embarque,
recomprobación del lote y pendientes."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, StringConstraints

from app.schemas.comunes import Correo, Dni, Entrada, Texto
from app.schemas.habilitacion import CasillaSalida
from app.schemas.parcelas import DocumentoSalida

Direccion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]

# ---------- Cooperativa ----------


class CooperativaPropia(BaseModel):
    id: uuid.UUID
    razon_social: str
    nombre_comercial: str | None
    ruc: str
    codigo: str | None
    tipo_organizacion: str
    departamento: str
    provincia: str
    distrito: str
    direccion_postal: str | None
    correo: str | None
    representante_nombre: str | None
    representante_dni: str | None
    # Los cuatro datos que el DEX necesita y que faltan; vacío si están completos.
    faltan_datos: list[str]


class CooperativaCambios(Entrada):
    direccion_postal: Direccion | None = None
    correo: Correo | None = None
    representante_nombre: Texto | None = None
    representante_dni: Dni | None = None


class ExpedienteCooperativa(BaseModel):
    estado: Literal["completo", "incompleto"]
    # Casillas que no están vigentes ni por vencer.
    faltan: list[str]
    casillas: list[CasillaSalida]


# ---------- Documentos de embarque ----------


class DocumentoEmbarque(BaseModel):
    codigo: str
    nombre: str
    emisor_habitual: str
    cargado: bool
    documentos: list[DocumentoSalida]


class EmbarqueSalida(BaseModel):
    completo: bool
    faltan: list[str]
    # Se cargan y se anulan en un lote armado, bloqueado o listo.
    editable: bool
    tipos: list[DocumentoEmbarque]


# ---------- Recomprobación ----------

TipoCaso = Literal[
    "parcela", "dop", "dpp", "lote", "cooperativa", "expediente_cooperativa", "importador", "embarque"
]


class Caso(BaseModel):
    """Lo que falla, con el registro donde se corrige."""

    texto: str
    detalle: str | None = None
    tipo: TipoCaso
    id: str | None = None
    codigo: str | None = None


class Comprobacion(BaseModel):
    codigo: str
    nombre: str
    sobre: str
    resultado: Literal["sin_observaciones", "con_observaciones"]
    casos: list[Caso]


class RecomprobacionSalida(BaseModel):
    id: uuid.UUID
    lote_id: uuid.UUID
    ejecutada_por_nombre: str | None
    ejecutada_en: datetime
    resultado: Literal["sin_observaciones", "con_observaciones"]
    comprobaciones: list[Comprobacion]
    # Estado del lote después de esta recomprobación.
    estado_lote: str | None = None


# ---------- Pendientes ----------


class Pendiente(BaseModel):
    titulo: str
    detalle: str | None = None
    enlace: str
    fecha: date | None = None


class GrupoPendientes(BaseModel):
    clave: str
    titulo: str
    # Orden de la pantalla: primero lo vencido, luego lo que está por vencer y al final lo demás.
    prioridad: Literal["vencido", "por_vencer", "otro"]
    cantidad: int
    items: list[Pendiente]


class PendientesSalida(BaseModel):
    total: int
    grupos: list[GrupoPendientes]
    extra: dict[str, Any] = {}

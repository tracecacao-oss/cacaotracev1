"""Entradas y salidas de la Parte 8: datos de la cooperativa, su expediente legal, documentos de embarque,
recomprobación del lote y pendientes."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, StringConstraints

from app.schemas.comunes import Correo, Dni, Entrada, Texto
from app.schemas.habilitacion import CasillaSalida
from app.schemas.parcelas import DocumentoSalida

Direccion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
# Adenda 6, sección 5, regla 2: un teléfono, un correo o la ubicación de un buzón.
ContactoCanal = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]

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
    # Adenda 6: el contacto del canal de quejas y denuncias.
    canal_denuncias_contacto: str | None = None
    # Los cuatro datos que el DEX necesita y que faltan; vacío si están completos.
    faltan_datos: list[str]


class CooperativaCambios(Entrada):
    direccion_postal: Direccion | None = None
    correo: Correo | None = None
    representante_nombre: Texto | None = None
    representante_dni: Dni | None = None
    canal_denuncias_contacto: ContactoCanal | None = None


class CasillaOrganizacion(CasillaSalida):
    """Adenda 6, sección 4: el documento dice si es de identidad (frena un lote si falta) y, si ya no se
    carga, que es un documento anterior."""

    identidad: bool = False
    frena_lote: bool = False
    anterior: bool = False
    # renta_anual vence sola a los RENTA_VIGENCIA_MESES de su presentación.
    vence_solo: bool = False


class RequisitoOrganizacionSalida(BaseModel):
    """Adenda 6, sección 3: un requisito de la organización con su estado."""

    codigo: str
    nombre: str
    referencias: list[str]
    nivel: str | None
    diligencia: str | None
    bloquea: bool
    que_pide: str
    estado: Literal["no_aplica", "sustentado", "por_vencer", "vencido", "sin_sustento"]
    motivo: str
    # Lo que falta para sustentarlo: documentos, temas de la política o temas sin actuación, con su nombre y
    # con su código.
    falta: list[str] = []
    falta_codigos: list[str] = []


class ExpedienteCooperativa(BaseModel):
    # Desde la adenda 6: completo cuando los tres documentos de identidad están vigentes o por vencer.
    estado: Literal["completo", "incompleto"]
    # Documentos de identidad que no están vigentes ni por vencer.
    faltan: list[str]
    tipo_organizacion: str | None = None
    # Los documentos que aplican al tipo de organización.
    casillas: list[CasillaOrganizacion]
    requisitos: list[RequisitoOrganizacionSalida] = []
    # Adenda 6, sección 4, reglas 4 y 5: los que ya no se cargan y los que no aplican, con lo que se cargó.
    anteriores: list[CasillaOrganizacion] = []
    consulta_ruc: str | None = None


# ---------- Documentos de embarque ----------


class ConsultaPublica(BaseModel):
    url: str
    nombre: str


class DocumentoEmbarque(BaseModel):
    codigo: str
    nombre: str
    emisor_habitual: str
    # Adenda 6, sección 7: solo los obligatorios cuentan para documentos_embarque_completos.
    obligatorio: bool = True
    registro_consultable: bool = False
    # Se puede cargar y anular en el estado de hoy del lote (la dam también con el lote cerrado).
    editable: bool = False
    consultas: list[ConsultaPublica] = []
    cargado: bool
    documentos: list[DocumentoSalida]


class ComparacionAduanera(BaseModel):
    """Adenda 7, sección 4.2: lo que la persona escribió de la declaración aduanera frente al lote. No
    bloquea."""

    peso_lote_kg: Decimal | None
    peso_declarado_kg: Decimal
    diferencia_kg: Decimal | None
    diferencia_pct: Decimal | None
    tolerancia_pct: Decimal
    peso_difiere: bool
    partida_orden: str
    subpartida: str
    subpartida_difiere: bool
    difiere: bool


class DeclaracionAduaneraSalida(BaseModel):
    id: uuid.UUID
    numero: str
    fecha_numeracion: date
    peso_neto_kg: Decimal
    subpartida: str
    posterior_al_dex: bool
    registrada_por_nombre: str | None
    registrada_en: datetime
    documento: DocumentoSalida | None
    comparacion: ComparacionAduanera


class EmbarqueSalida(BaseModel):
    # Los obligatorios.
    completo: bool
    faltan: list[str]
    # Se cargan y se anulan en un lote armado, bloqueado o listo.
    editable: bool
    tipos: list[DocumentoEmbarque]
    # Adenda 7: la declaración aduanera sin anular, con sus cuatro datos y la comparación con el lote.
    declaracion: DeclaracionAduaneraSalida | None = None


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
    # Adenda 7: en una parcela no habilitada, su productor.
    productor_id: str | None = None
    productor: str | None = None


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

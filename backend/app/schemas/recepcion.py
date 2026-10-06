"""Entradas y salidas de la Parte 5: configuración, lugares, tandas, decisiones y DOP."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.comunes import Entrada, Ruc, Salida, Texto, TextoOpcional
from app.schemas.parcelas import DocumentoSalida

Kilos = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
NotaLarga = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Variedad = Literal["ccn_51", "ics_95", "imc_67", "tsh_565", "trinitario", "chuncho", "sin_variedad", "otra"]
TipoLugar = Literal["cancha_acopio", "planta", "almacen", "otro"]
NumeroDocumento = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, max_length=20)]
# Adenda 3: el Comprobante de Operaciones de la Ley N.° 29972 queda fuera (ley derogada).
TipoDocEntrega = Literal["guia_remision", "liquidacion_compra"]
TipoOrganizacion = Literal["cooperativa_agraria", "asociacion", "empresa"]

# ---------- Configuración ----------


class ConfiguracionSalida(BaseModel):
    tope_kg_seco_ha_anio: Decimal | None
    factor_baba_a_seco: Decimal
    rendimiento_min: Decimal
    rendimiento_max: Decimal
    dias_max_cosecha_entrega_baba: int
    dias_max_cosecha_entrega_seco: int
    tolerancia_peso_guia_pct: Decimal
    dias_max_emision_doc_entrega: int
    codigo_cooperativa: str | None
    # Adenda 3: con la liquidación de compra, el RUC del emisor es el de la organización.
    ruc_cooperativa: str
    tipo_organizacion: str
    # Sin tope ni código de cooperativa no se registran tandas.
    lista: bool


class ConfiguracionCambio(Entrada):
    tope_kg_seco_ha_anio: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
    factor_baba_a_seco: Annotated[Decimal, Field(gt=0, lt=1, max_digits=4, decimal_places=3)]
    rendimiento_min: Annotated[Decimal, Field(gt=0, lt=1, max_digits=4, decimal_places=3)]
    rendimiento_max: Annotated[Decimal, Field(gt=0, lt=1, max_digits=4, decimal_places=3)]
    dias_max_cosecha_entrega_baba: Annotated[int, Field(ge=0, le=3650)]
    dias_max_cosecha_entrega_seco: Annotated[int, Field(ge=0, le=3650)]
    tolerancia_peso_guia_pct: Annotated[Decimal, Field(ge=0, le=100, max_digits=4, decimal_places=1)]
    dias_max_emision_doc_entrega: Annotated[int, Field(ge=0, le=365)]


# ---------- Lugares ----------


class LugarNuevo(Entrada):
    nombre: Texto
    tipo: TipoLugar
    departamento: Texto
    provincia: Texto
    distrito: Texto
    latitud: Annotated[Decimal, Field(ge=-90, le=90, max_digits=9, decimal_places=6)] | None = None
    longitud: Annotated[Decimal, Field(ge=-180, le=180, max_digits=9, decimal_places=6)] | None = None


class LugarCambios(Entrada):
    nombre: Texto | None = None
    tipo: TipoLugar | None = None
    departamento: Texto | None = None
    provincia: Texto | None = None
    distrito: Texto | None = None
    latitud: Annotated[Decimal, Field(ge=-90, le=90, max_digits=9, decimal_places=6)] | None = None
    longitud: Annotated[Decimal, Field(ge=-180, le=180, max_digits=9, decimal_places=6)] | None = None
    activo: bool | None = None


class LugarSalida(Salida):
    id: uuid.UUID
    nombre: str
    tipo: str
    departamento: str
    provincia: str
    distrito: str
    latitud: Decimal | None
    longitud: Decimal | None
    activo: bool


# ---------- Tandas ----------


class DatosTanda(Entrada):
    lugar_id: uuid.UUID
    recibida_en: datetime
    estado_producto: Literal["baba", "seco"]
    peso_kg: Kilos
    numero_sacos: Annotated[int, Field(gt=0, le=100_000)] | None = None
    humedad_pct: Annotated[Decimal, Field(ge=0, le=100, max_digits=4, decimal_places=1)] | None = None
    variedad: Variedad
    variedad_otra: TextoOpcional | None = None
    tipo_semilla: TextoOpcional | None = None
    cosecha_desde: date
    cosecha_hasta: date
    doc_entrega_tipo: TipoDocEntrega | None = None
    doc_entrega_numero: NumeroDocumento | None = None
    doc_entrega_fecha_emision: date | None = None
    doc_entrega_ruc_emisor: Ruc | None = None
    doc_entrega_peso_kg: Kilos | None = None


class TandaNueva(DatosTanda):
    productor_id: uuid.UUID
    parcela_id: uuid.UUID


class TandaCambios(Entrada):
    lugar_id: uuid.UUID | None = None
    recibida_en: datetime | None = None
    estado_producto: Literal["baba", "seco"] | None = None
    peso_kg: Kilos | None = None
    numero_sacos: Annotated[int, Field(gt=0, le=100_000)] | None = None
    humedad_pct: Annotated[Decimal, Field(ge=0, le=100, max_digits=4, decimal_places=1)] | None = None
    variedad: Variedad | None = None
    variedad_otra: TextoOpcional | None = None
    tipo_semilla: TextoOpcional | None = None
    cosecha_desde: date | None = None
    cosecha_hasta: date | None = None
    doc_entrega_tipo: TipoDocEntrega | None = None
    doc_entrega_numero: NumeroDocumento | None = None
    doc_entrega_fecha_emision: date | None = None
    doc_entrega_ruc_emisor: Ruc | None = None
    doc_entrega_peso_kg: Kilos | None = None


class Validacion(Entrada):
    nota: NotaLarga | None = None


class Motivo(Entrada):
    motivo: Texto


class Requisito(BaseModel):
    codigo: str
    cumple: bool
    detalle: str


class ProductorDeTanda(BaseModel):
    id: uuid.UUID
    dni: str
    nombres: str
    apellidos: str


class ParcelaDeTanda(BaseModel):
    id: uuid.UUID
    codigo: str
    nombre: str
    habilitacion_estado: str


class DopDeTanda(BaseModel):
    id: uuid.UUID
    codigo: str
    estado: str


class DecisionTandaSalida(BaseModel):
    id: uuid.UUID
    decision: str
    decidida_por_nombre: str | None
    decidida_en: datetime
    nota: str | None


class ProcesoDeTanda(BaseModel):
    """Parte 6: en qué fase está la corrida de la tanda, o si ya entró al stock. Parte 7: estado
    "en_lote_de_exportacion" cuando parte de su cacao entró a un lote confirmado."""

    estado: str
    fase: str
    fase_nombre: str


class TandaSalida(BaseModel):
    id: uuid.UUID
    codigo: str
    estado: str
    productor: ProductorDeTanda
    parcela: ParcelaDeTanda
    lugar_id: uuid.UUID
    lugar_nombre: str
    recibida_en: datetime
    estado_producto: str
    peso_kg: Decimal
    peso_seco_equivalente_kg: Decimal
    numero_sacos: int | None
    humedad_pct: Decimal | None
    variedad: str
    variedad_otra: str | None
    variedad_nombre: str
    tipo_semilla: str | None
    cosecha_desde: date
    cosecha_hasta: date
    doc_entrega_tipo: str | None
    doc_entrega_tipo_nombre: str | None
    doc_entrega_numero: str | None
    doc_entrega_fecha_emision: date | None
    doc_entrega_ruc_emisor: str | None
    doc_entrega_peso_kg: Decimal | None
    registrada_por_nombre: str | None
    creado_en: datetime
    dop: DopDeTanda | None
    proceso: ProcesoDeTanda | None = None


class TandaDetalle(TandaSalida):
    requisitos: list[Requisito]
    alertas: list[str]
    alertas_detalle: dict[str, Any]
    puede_validar: bool
    nota_obligatoria: bool
    documentos: list[DocumentoSalida]
    decisiones: list[DecisionTandaSalida]


# ---------- DOP ----------


class DopSalida(BaseModel):
    id: uuid.UUID
    codigo: str
    estado: str
    tanda_id: uuid.UUID
    tanda_codigo: str
    productor: ProductorDeTanda
    parcela_codigo: str
    parcela_nombre: str
    peso_kg: Decimal
    estado_producto: str
    emitido_en: datetime
    contenido_sha256: str


class DopDetalle(DopSalida):
    contenido: dict[str, Any]
    url_verificacion: str
    # Matriz del código QR: una cadena de "0" y "1" por fila. La interfaz la dibuja sin HTML.
    qr: list[str]
    anulado_en: datetime | None
    anulado_por_nombre: str | None
    motivo_anulacion: str | None


class DopPublico(BaseModel):
    """Solo cinco datos: ni datos personales, ni geometría, ni pesos."""

    codigo: str
    estado: str
    emitido_en: datetime
    contenido_sha256: str
    cooperativa: str

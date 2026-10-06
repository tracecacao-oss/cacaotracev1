"""Entradas y salidas de la Parte 7: importadores, órdenes de compra, lotes de exportación, genealogía,
indicadores y trazabilidad."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.comunes import Correo, Entrada, Texto, TextoOpcional
from app.schemas.cooperativa import RecomprobacionSalida
from app.schemas.proceso import Referencia
from app.schemas.recepcion import Kilos, NotaLarga, ProductorDeTanda

Direccion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
# EORI: código de país de dos letras y hasta 15 caracteres alfanuméricos.
Eori = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z]{2}[A-Za-z0-9]{1,15}$")
]
Tolerancia = Annotated[Decimal, Field(ge=0, le=100, max_digits=4, decimal_places=1)]
KilosAsignados = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
EstadoOrden = Literal["abierta", "con_lote", "cerrada", "anulada"]
EstadoLote = Literal["en_armado", "armado", "anulado"]

# ---------- Importadores ----------


class ImportadorNuevo(Entrada):
    razon_social: Texto
    direccion: Direccion
    pais: Texto
    correo: Correo
    eori: Eori | None = None


class ImportadorCambios(Entrada):
    razon_social: Texto | None = None
    direccion: Direccion | None = None
    pais: Texto | None = None
    correo: Correo | None = None
    eori: Eori | None = None
    activo: bool | None = None


class ImportadorSalida(BaseModel):
    id: uuid.UUID
    razon_social: str
    direccion: str
    pais: str
    correo: str
    eori: str | None
    activo: bool


# ---------- Órdenes de compra ----------


class OrdenNueva(Entrada):
    importador_id: uuid.UUID
    referencia_importador: TextoOpcional | None = None
    cantidad_kg: Kilos
    tolerancia_pct: Tolerancia = Decimal("0")
    calidad_id: uuid.UUID
    pais_destino: Texto
    lugar_destino: Texto
    fecha_entrega: date


class OrdenCambios(Entrada):
    importador_id: uuid.UUID | None = None
    referencia_importador: TextoOpcional | None = None
    cantidad_kg: Kilos | None = None
    tolerancia_pct: Tolerancia | None = None
    calidad_id: uuid.UUID | None = None
    pais_destino: Texto | None = None
    lugar_destino: Texto | None = None
    fecha_entrega: date | None = None


class ImportadorDeOrden(BaseModel):
    id: uuid.UUID
    razon_social: str
    pais: str


class LoteDeOrden(BaseModel):
    id: uuid.UUID
    codigo: str
    estado: str
    masa_neta_kg: Decimal | None


class OrdenSalida(BaseModel):
    id: uuid.UUID
    codigo: str
    importador: ImportadorDeOrden
    referencia_importador: str | None
    cantidad_kg: Decimal
    tolerancia_pct: Decimal
    calidad_id: uuid.UUID
    calidad: str
    partida_sa: str
    pais_destino: str
    lugar_destino: str
    fecha_entrega: date
    estado: str
    creada_en: datetime
    lote: LoteDeOrden | None


class OrdenDetalle(OrdenSalida):
    creada_por_nombre: str | None
    anulada_en: datetime | None
    motivo_anulacion: str | None
    # Kilos mínimo y máximo que admite la tolerancia.
    minimo_kg: Decimal
    maximo_kg: Decimal
    lotes_anulados: list[LoteDeOrden]


# ---------- Lotes ----------


class Asignacion(Entrada):
    tanda_final_id: uuid.UUID
    kg_asignados: KilosAsignados


class Seleccion(Entrada):
    asignaciones: Annotated[list[Asignacion], Field(max_length=500)]


class Confirmacion(Entrada):
    motivo_desviacion: NotaLarga | None = None


class TandaFinalDeLote(BaseModel):
    tanda_final_id: uuid.UUID
    codigo: str
    corrida_codigo: str
    calidad: str
    ingreso_stock_en: datetime
    saldo_kg: Decimal
    estado: str
    dpp: Referencia | None


class AsignacionSalida(TandaFinalDeLote):
    kg_asignados: Decimal


class Candidata(TandaFinalDeLote):
    """Una tanda final de la calidad de la orden, con los kilos que le asigna la sugerencia FIFO."""

    kg_sugeridos: Decimal


class SugerenciaFifo(BaseModel):
    cantidad_kg: Decimal
    minimo_kg: Decimal
    maximo_kg: Decimal
    disponible_kg: Decimal
    total_kg: Decimal
    faltan_kg: Decimal
    # El stock de la calidad alcanza para el mínimo que admite la tolerancia.
    alcanza: bool
    asignaciones: list[Asignacion]
    candidatas: list[Candidata]


class Indicador(BaseModel):
    clave: str
    nombre: str
    valor: Any
    explicacion: str


class LoteSalida(BaseModel):
    id: uuid.UUID
    codigo: str
    estado: str
    orden: Referencia
    importador: str
    calidad: str
    cantidad_kg: Decimal
    masa_neta_kg: Decimal | None
    # Kilos seleccionados: la masa neta si ya se confirmó.
    seleccionado_kg: Decimal
    numero_parcelas: int | None
    desviacion_fifo: bool
    creado_en: datetime
    armado_en: datetime | None


class LoteDetalle(LoteSalida):
    tolerancia_pct: Decimal
    minimo_kg: Decimal
    maximo_kg: Decimal
    motivo_desviacion: str | None
    creado_por_nombre: str | None
    armado_por_nombre: str | None
    anulado_en: datetime | None
    anulado_por_nombre: str | None
    motivo_anulacion: str | None
    asignaciones: list[AsignacionSalida]
    indicadores: list[Indicador] | None
    # Parte 8: alertas posteriores al cierre y la última recomprobación, si la hay.
    alertas: list[dict[str, Any]] = []
    recomprobacion: RecomprobacionSalida | None = None


class ParcelaDeGenealogia(BaseModel):
    parcela_id: uuid.UUID
    codigo: str
    nombre: str
    productor: ProductorDeTanda
    kg: Decimal
    proporcion: Decimal
    geometria: dict[str, Any]


class ProductorDeGenealogia(BaseModel):
    productor: ProductorDeTanda
    numero_parcelas: int
    kg: Decimal
    proporcion: Decimal


class FilaGenealogia(BaseModel):
    tanda_final: Referencia
    dpp: Referencia
    corrida: Referencia
    tipo_manejo: str
    tanda: Referencia
    dop: Referencia
    parcela_id: uuid.UUID
    parcela_codigo: str
    productor_id: uuid.UUID
    kg_atribuidos: Decimal
    proporcion_lote: Decimal


class Genealogia(BaseModel):
    lote: Referencia
    # Un lote anulado conserva su genealogía como historial.
    anulada: bool
    masa_neta_kg: Decimal
    filas: list[FilaGenealogia]
    por_parcela: list[ParcelaDeGenealogia]
    por_productor: list[ProductorDeGenealogia]
    indicadores: list[Indicador]


# ---------- Trazabilidad ----------


class LoteDeRecorrido(BaseModel):
    lote: Referencia
    orden: Referencia
    kg: Decimal


class TandaDeRecorrido(BaseModel):
    tanda: Referencia
    recibida_en: datetime
    peso_kg: Decimal
    estado_producto: str
    parcela_codigo: str
    productor: ProductorDeTanda
    dop: Referencia | None
    corrida: Referencia | None
    proporcion: Decimal | None
    tanda_final: Referencia | None
    # Proporción de la tanda por el peso seco de la tanda final.
    kg_en_tanda_final: Decimal | None
    lotes: list[LoteDeRecorrido]


class Recorrido(BaseModel):
    tipo: Literal["parcela", "productor", "dop"]
    id: uuid.UUID
    titulo: str
    subtitulo: str
    tandas: list[TandaDeRecorrido]
    # Por lote, la suma de lo que llegó desde el origen. Los anulados se listan aparte.
    lotes: list[LoteDeRecorrido]
    lotes_anulados: list[LoteDeRecorrido]
    kg_en_lotes: Decimal

"""Entradas y salidas de la Parte 6: etapas, plantilla, calidades, corridas, tandas finales y DPP."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.comunes import Entrada, Texto, TextoOpcional
from app.schemas.recepcion import Kilos, NotaLarga, ProductorDeTanda

Ruta = Literal["completa", "seco"]
TipoManejo = Literal["segregado", "mezclado"]
Metros = Annotated[Decimal, Field(ge=0, le=9_999_999, max_digits=8, decimal_places=1)]
Horas = Annotated[Decimal, Field(ge=0, le=9999, max_digits=6, decimal_places=2)]
Humedad = Annotated[Decimal, Field(ge=0, le=100, max_digits=4, decimal_places=1)]

# ---------- Catálogo, plantilla y calidades ----------


class DatoCatalogo(BaseModel):
    clave: str
    etiqueta: str
    tipo: str
    minimo: float | None
    maximo: float | None
    unidad: str | None


class EtapaCatalogo(BaseModel):
    numero: int
    nombre: str
    tipo: str
    tipo_nombre: str
    fase: str
    fase_nombre: str
    en_ruta_seco: bool
    automatica: bool
    opcional: bool
    transporte: bool
    datos: list[DatoCatalogo]
    # Métodos sugeridos para elegir; si el de la cooperativa no está, se escribe.
    metodos: list[str] = []
    # Fija: la cooperativa no la desactiva en su plantilla.
    fija: bool = False


class PlantillaFila(Entrada):
    numero: Annotated[int, Field(ge=1, le=23)]
    lugar_id: uuid.UUID | None = None
    metodo: TextoOpcional | None = None
    distancia_m: Metros | None = None
    duracion_horas: Horas | None = None
    # Falsa: la cooperativa no usa la etapa y nace como "no aplica" en las corridas nuevas.
    activa: bool = True


class PlantillaCambio(Entrada):
    filas: Annotated[list[PlantillaFila], Field(max_length=23)]


class CalidadNueva(Entrada):
    nombre: Texto


class CalidadCambios(Entrada):
    nombre: Texto | None = None
    activo: bool | None = None


class CalidadSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    activo: bool


# ---------- Corridas ----------


class CorridaNueva(Entrada):
    ruta: Ruta
    tipo_manejo: TipoManejo


class TandaACorrida(Entrada):
    tanda_id: uuid.UUID
    observacion_calidad: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None = (
        None
    )


class EtapaRegistro(Entrada):
    """Confirma o corrige una etapa. Con "no_ocurrio" (solo etapas 7 y 14) no se piden más datos."""

    situacion: Literal["registrada", "no_ocurrio"] = "registrada"
    lugar_id: uuid.UUID | None = None
    inicio: datetime | None = None
    fin: datetime | None = None
    metodo: TextoOpcional | None = None
    responsable: TextoOpcional | None = None
    distancia_m: Metros | None = None
    observacion: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None = None
    datos: dict[str, Any] = Field(default_factory=dict)


class Consolidacion(Entrada):
    """El peso final debe coincidir con el de la etapa 19; la calidad y los sacos salen de las etapas 17
    y 21."""

    peso_final_kg: Kilos | None = None
    humedad_pct: Humedad
    lugar_id: uuid.UUID
    explicacion: NotaLarga | None = None


class Referencia(BaseModel):
    id: uuid.UUID
    codigo: str
    estado: str


class ParcelaDeCorrida(BaseModel):
    id: uuid.UUID
    codigo: str
    nombre: str
    habilitacion_estado: str


class TandaDeCorrida(BaseModel):
    tanda_id: uuid.UUID
    codigo: str
    productor: ProductorDeTanda
    parcela: ParcelaDeCorrida
    dop: Referencia | None
    estado_producto: str
    recibida_en: datetime
    peso_kg: Decimal
    observacion_calidad: str | None
    proporcion: Decimal | None


class PlantillaDeEtapa(BaseModel):
    lugar_id: uuid.UUID | None
    metodo: str | None
    distancia_m: Decimal | None
    duracion_horas: Decimal | None


class EtapaDeCorrida(BaseModel):
    numero: int
    nombre: str
    tipo: str
    fase: str
    situacion: str
    automatica: bool
    opcional: bool
    transporte: bool
    editable: bool
    lugar_id: uuid.UUID | None
    lugar_nombre: str | None
    inicio: datetime | None
    fin: datetime | None
    duracion_horas: Decimal | None
    metodo: str | None
    responsable: str | None
    observacion: str | None
    distancia_m: Decimal | None
    datos: dict[str, Any]
    desde_plantilla: bool
    registrada_por_nombre: str | None
    registrada_en: datetime | None
    plantilla: PlantillaDeEtapa | None


class Rendimiento(BaseModel):
    entrada_kg: Decimal
    peso_final_kg: Decimal | None
    # Ruta completa: peso final entre la baba de entrada. Ruta seco: peso final entre el seco de entrada.
    rendimiento: Decimal | None
    banda_min: Decimal | None
    banda_max: Decimal | None
    alerta: str | None


class CorridaSalida(BaseModel):
    id: uuid.UUID
    codigo: str
    ruta: str
    tipo_manejo: str
    estado: str
    fase: str
    fase_nombre: str
    etapa_actual: int | None
    etapa_actual_nombre: str | None
    numero_tandas: int
    entrada_kg: Decimal
    abierta_en: datetime
    iniciada_en: datetime | None
    consolidada_en: datetime | None
    alertas: list[str]
    tanda_final: Referencia | None
    dpp: Referencia | None


class CorridaDetalle(CorridaSalida):
    abierta_por_nombre: str | None
    anulada_en: datetime | None
    motivo_anulacion: str | None
    tandas: list[TandaDeCorrida]
    etapas: list[EtapaDeCorrida]
    rendimiento: Rendimiento
    faltan_para_consolidar: list[str]
    puede_consolidar: bool
    dpps: list[Referencia]


class TandaDisponible(BaseModel):
    tanda_id: uuid.UUID
    codigo: str
    productor: ProductorDeTanda
    parcela: ParcelaDeCorrida
    dop: Referencia
    estado_producto: str
    recibida_en: datetime
    peso_kg: Decimal
    # La parcela pasó a observada después de emitirse el DOP: entra con alerta.
    parcela_observada: bool


# ---------- Tandas finales y DPP ----------


class TandaFinalSalida(BaseModel):
    id: uuid.UUID
    codigo: str
    corrida_id: uuid.UUID
    corrida_codigo: str
    peso_seco_kg: Decimal
    saldo_kg: Decimal
    humedad_pct: Decimal | None
    calidad: str
    calidad_id: uuid.UUID
    numero_sacos: int
    lugar_id: uuid.UUID
    lugar_nombre: str
    ingreso_stock_en: datetime
    estado: str
    dpp: Referencia | None
    # Parte 8: tiene cacao de una parcela excluida; no se sugiere ni se acepta en un lote.
    retenida: bool = False


class ComponenteDeTandaFinal(BaseModel):
    tanda_id: uuid.UUID
    tanda_codigo: str
    dop: Referencia | None
    productor: ProductorDeTanda
    parcela_codigo: str
    parcela_nombre: str
    peso_entrada_kg: Decimal
    proporcion: Decimal
    # Proporción por el peso seco de la tanda final.
    kg_atribuibles: Decimal


class TandaFinalDetalle(TandaFinalSalida):
    composicion: list[ComponenteDeTandaFinal]


class DppSalida(BaseModel):
    id: uuid.UUID
    codigo: str
    estado: str
    corrida_id: uuid.UUID
    corrida_codigo: str
    tanda_final_id: uuid.UUID
    tanda_final_codigo: str
    peso_seco_kg: Decimal
    emitido_en: datetime
    contenido_sha256: str


class DppDetalle(DppSalida):
    contenido: dict[str, Any]
    url_verificacion: str
    qr: list[str]
    anulado_en: datetime | None
    anulado_por_nombre: str | None
    motivo_anulacion: str | None


class DppPublico(BaseModel):
    """Solo cinco datos, como el DOP: ni datos personales, ni pesos. Más la marca de demostración."""

    codigo: str
    estado: str
    emitido_en: datetime
    contenido_sha256: str
    cooperativa: str
    # Parte 10: la página pública avisa que es un documento de demostración.
    es_demo: bool = False

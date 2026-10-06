"""Entradas y salidas de la adenda 2 de la Parte 4: imágenes de la parcela y revisiones de imágenes."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.comunes import Entrada
from app.schemas.habilitacion import TextoLargo50

Observacion2020 = Literal["bosque", "cultivo_o_uso_agricola", "mixto", "no_se_distingue"]
ObservacionCambio = Literal["sin_cambio_visible", "cambio_visible", "no_se_distingue"]


class ImagenSalida(BaseModel):
    id: uuid.UUID
    fuente: str
    papel: str
    periodo: int | None
    fecha_captura: date | None
    dias_respecto_al_corte: int | None
    resolucion_m: Decimal | None
    nubes_parcela_pct: Decimal | None
    identificador_fuente: str | None
    proveedor: str | None
    estado: str
    error_detalle: str | None
    # URLs firmadas de Storage; nulas en Wayback, que la interfaz muestra desde Esri con sus teselas.
    url_natural: str | None
    url_infrarrojo: str | None
    sha256_natural: str | None


class ImagenesSalida(BaseModel):
    # sin_alerta: la parcela no tiene la alerta de análisis; no se generan imágenes.
    estado: Literal["sin_alerta", "no_configurada", "pendiente", "pausada", "generada"]
    tiene_alerta: bool
    imagenes: list[ImagenSalida]
    teselas_wayback: str
    subdominios_wayback: list[str]
    atribucion_sentinel: str
    atribucion_wayback: str


class ConsumoSalida(BaseModel):
    mes: date
    usadas_pu: float
    cuota_pu: float
    umbral_pu: float
    en_pausa: bool
    configurada: bool
    pendientes: int


class RevisionNueva(Entrada):
    observacion_2020: Observacion2020
    observacion_cambio: ObservacionCambio
    descripcion: TextoLargo50


class RevisionSalida(BaseModel):
    id: uuid.UUID
    parcela_id: uuid.UUID
    revisada_por_nombre: str | None
    revisada_en: datetime
    imagenes: list[str]
    observacion_2020: str
    observacion_cambio: str
    descripcion: str
    anulada_en: datetime | None
    anulada_por_nombre: str | None
    motivo_anulacion: str | None
    # Vigente: no anulada y de la geometría actual. Un análisis nuevo no la vence.
    vigente: bool

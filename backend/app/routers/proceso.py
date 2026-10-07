"""Parte 6: catálogo de etapas, plantilla, calidades, corridas, DPP y stock. El operador y el administrador
operan la corrida; solo el administrador cambia la plantilla y las calidades y anula un DPP."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from app.catalogos import etapas_proceso as catalogo
from app.contexto import Contexto, requiere_rol
from app.errores import no_encontrado
from app.schemas.parcelas import UrlDescarga
from app.schemas.proceso import (
    CalidadCambios,
    CalidadNueva,
    CalidadSalida,
    Consolidacion,
    CorridaDetalle,
    CorridaNueva,
    CorridaSalida,
    DppDetalle,
    DppSalida,
    EtapaCatalogo,
    EtapaRegistro,
    PlantillaCambio,
    PlantillaFila,
    Ruta,
    TandaACorrida,
    TandaDisponible,
    TandaFinalDetalle,
    TandaFinalSalida,
)
from app.schemas.recepcion import Motivo
from app.services import corridas, dpps, proceso
from app.storage import VIGENCIA_URL_FIRMADA, ClienteStorage, obtener_storage

router = APIRouter(tags=["proceso"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]
EstadoCorrida = Literal["abierta", "en_proceso", "consolidada", "anulada"]
Fase = Literal["ingreso", "fermentacion", "secado", "seleccion", "envasado", "stock", "anulada"]

# ---------- Proceso ----------


@router.get("/proceso/etapas", response_model=list[EtapaCatalogo])
def catalogo_de_etapas(contexto: Lectura):
    return proceso.etapas()


@router.get("/proceso/plantilla", response_model=list[PlantillaFila])
def plantilla(contexto: Lectura):
    return proceso.plantilla(contexto)


@router.get("/proceso/plantilla/sugerida", response_model=list[PlantillaFila])
def plantilla_sugerida(contexto: Administrador):
    """Valores habituales para llenar la plantilla de una vez. No guarda nada."""
    return proceso.plantilla_sugerida(contexto)


@router.put("/proceso/plantilla", response_model=list[PlantillaFila])
def cambiar_plantilla(datos: PlantillaCambio, contexto: Administrador):
    return proceso.cambiar_plantilla(contexto, datos)


@router.get("/calidades", response_model=list[CalidadSalida])
def calidades(contexto: Lectura):
    return proceso.calidades(contexto)


@router.post("/calidades", response_model=CalidadSalida, status_code=201)
def crear_calidad(datos: CalidadNueva, contexto: Administrador):
    return proceso.crear_calidad(contexto, datos)


@router.patch("/calidades/{calidad_id}", response_model=CalidadSalida)
def editar_calidad(calidad_id: uuid.UUID, datos: CalidadCambios, contexto: Administrador):
    return proceso.editar_calidad(contexto, calidad_id, datos)


# ---------- Corridas ----------


@router.get("/corridas", response_model=list[CorridaSalida])
def listar_corridas(contexto: Lectura, estado: EstadoCorrida | None = None, fase: Fase | None = None):
    return corridas.listar(contexto, estado=estado, fase_=fase)


@router.post("/corridas", response_model=CorridaDetalle, status_code=201)
def crear_corrida(datos: CorridaNueva, contexto: Registro):
    return corridas.crear(contexto, datos)


@router.get("/corridas/tandas-disponibles", response_model=list[TandaDisponible])
def tandas_disponibles(contexto: Lectura, ruta: Ruta, productor_id: uuid.UUID | None = None):
    return corridas.tandas_disponibles(contexto, ruta, productor_id)


@router.get("/corridas/{corrida_id}", response_model=CorridaDetalle)
def detalle_corrida(corrida_id: uuid.UUID, contexto: Lectura):
    return corridas.obtener(contexto, corrida_id)


@router.post("/corridas/{corrida_id}/tandas", response_model=CorridaDetalle, status_code=201)
def agregar_tanda(corrida_id: uuid.UUID, datos: TandaACorrida, contexto: Registro):
    return corridas.agregar_tanda(contexto, corrida_id, datos)


@router.delete("/corridas/{corrida_id}/tandas/{tanda_id}", response_model=CorridaDetalle)
def quitar_tanda(corrida_id: uuid.UUID, tanda_id: uuid.UUID, contexto: Registro):
    return corridas.quitar_tanda(contexto, corrida_id, tanda_id)


@router.post("/corridas/{corrida_id}/iniciar", response_model=CorridaDetalle)
def iniciar_corrida(corrida_id: uuid.UUID, contexto: Registro):
    return corridas.iniciar(contexto, corrida_id)


@router.patch("/corridas/{corrida_id}/etapas/{numero}", response_model=CorridaDetalle)
def registrar_etapa(corrida_id: uuid.UUID, numero: int, datos: EtapaRegistro, contexto: Registro):
    if numero not in catalogo.POR_NUMERO:
        raise no_encontrado("La etapa no existe.")
    return corridas.registrar_etapa(contexto, corrida_id, numero, datos)


@router.post("/corridas/{corrida_id}/consolidar", response_model=CorridaDetalle)
def consolidar_corrida(corrida_id: uuid.UUID, datos: Consolidacion, contexto: Registro, storage: Storage):
    return corridas.consolidar(contexto, storage, corrida_id, datos)


@router.post("/corridas/{corrida_id}/anular", response_model=CorridaDetalle)
def anular_corrida(corrida_id: uuid.UUID, datos: Motivo, contexto: Registro):
    return corridas.anular(contexto, corrida_id, datos.motivo)


# ---------- DPP y stock ----------


@router.get("/dpps", response_model=list[DppSalida])
def listar_dpps(contexto: Lectura, estado: Literal["vigente", "anulado"] | None = None):
    return dpps.listar(contexto, estado)


@router.get("/dpps/{dpp_id}", response_model=DppDetalle)
def detalle_dpp(dpp_id: uuid.UUID, contexto: Lectura):
    return dpps.obtener(contexto, dpp_id)


@router.get("/dpps/{dpp_id}/pdf", response_model=UrlDescarga)
def pdf_dpp(dpp_id: uuid.UUID, contexto: Lectura, storage: Storage):
    return UrlDescarga(url=dpps.url_pdf(contexto, storage, dpp_id), vence_en_segundos=VIGENCIA_URL_FIRMADA)


@router.post("/dpps/{dpp_id}/anular", response_model=DppDetalle)
def anular_dpp(dpp_id: uuid.UUID, datos: Motivo, contexto: Administrador):
    return dpps.anular(contexto, dpp_id, datos.motivo)


@router.get("/tandas-finales", response_model=list[TandaFinalSalida])
def listar_tandas_finales(
    contexto: Lectura,
    estado: Literal["en_stock", "agotada", "anulada"] | None = None,
    calidad_id: uuid.UUID | None = None,
):
    return dpps.listar_finales(contexto, estado, calidad_id)


@router.get("/tandas-finales/{tanda_final_id}", response_model=TandaFinalDetalle)
def detalle_tanda_final(tanda_final_id: uuid.UUID, contexto: Lectura):
    return dpps.obtener_final(contexto, tanda_final_id)

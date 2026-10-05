"""Parte 5: configuración de la cooperativa, lugares, tandas y DOP. El personal registra y valida en
cancha; solo el administrador cambia la configuración, crea lugares y anula un DOP."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.contexto import Contexto, requiere_rol
from app.routers.comun import leer_archivo
from app.schemas.parcelas import UrlDescarga
from app.schemas.recepcion import (
    ConfiguracionCambio,
    ConfiguracionSalida,
    DopDetalle,
    DopSalida,
    LugarCambios,
    LugarNuevo,
    LugarSalida,
    Motivo,
    TandaCambios,
    TandaDetalle,
    TandaNueva,
    TandaSalida,
    Validacion,
)
from app.services import configuracion, dops, lugares, tandas
from app.storage import VIGENCIA_URL_FIRMADA, ClienteStorage, obtener_storage

router = APIRouter(tags=["recepcion"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]
EstadoTanda = Literal["registrada", "observada", "validada", "anulada"]

# ---------- Configuración y lugares ----------


@router.get("/configuracion", response_model=ConfiguracionSalida)
def ver_configuracion(contexto: Lectura):
    return configuracion.obtener(contexto)


@router.put("/configuracion", response_model=ConfiguracionSalida)
def cambiar_configuracion(datos: ConfiguracionCambio, contexto: Administrador):
    return configuracion.cambiar(contexto, datos)


@router.get("/lugares", response_model=list[LugarSalida])
def listar_lugares(contexto: Lectura, tipo: str | None = None, activos: bool | None = None):
    return lugares.listar(contexto, tipo=tipo, activos=activos)


@router.post("/lugares", response_model=LugarSalida, status_code=201)
def crear_lugar(datos: LugarNuevo, contexto: Administrador):
    return lugares.crear(contexto, datos)


@router.patch("/lugares/{lugar_id}", response_model=LugarSalida)
def editar_lugar(lugar_id: uuid.UUID, datos: LugarCambios, contexto: Administrador):
    return lugares.editar(contexto, lugar_id, datos)


# ---------- Tandas ----------


@router.get("/tandas", response_model=list[TandaSalida])
def listar_tandas(
    contexto: Lectura,
    estado: EstadoTanda | None = None,
    productor_id: uuid.UUID | None = None,
    parcela_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    q: str | None = None,
):
    return tandas.listar(
        contexto,
        estado=estado,
        productor_id=productor_id,
        parcela_id=parcela_id,
        desde=desde,
        hasta=hasta,
        busqueda=q,
    )


@router.post("/tandas", response_model=TandaDetalle, status_code=201)
def registrar_tanda(datos: TandaNueva, contexto: Registro):
    return tandas.registrar(contexto, datos)


@router.get("/tandas/{tanda_id}", response_model=TandaDetalle)
def detalle_tanda(tanda_id: uuid.UUID, contexto: Lectura):
    return tandas.obtener(contexto, tanda_id)


@router.patch("/tandas/{tanda_id}", response_model=TandaDetalle)
def editar_tanda(tanda_id: uuid.UUID, datos: TandaCambios, contexto: Registro):
    return tandas.editar(contexto, tanda_id, datos)


@router.post("/tandas/{tanda_id}/documentos", response_model=TandaDetalle, status_code=201)
def cargar_guia(
    tanda_id: uuid.UUID,
    contexto: Registro,
    storage: Storage,
    archivo: Annotated[UploadFile, File()],
    tipo: Annotated[Literal["guia_remision"], Form()] = "guia_remision",
):
    return tandas.cargar_guia(contexto, storage, tanda_id, leer_archivo(archivo))


@router.post("/tandas/{tanda_id}/validar", response_model=TandaDetalle)
def validar_tanda(tanda_id: uuid.UUID, datos: Validacion, contexto: Registro, storage: Storage):
    return tandas.validar(contexto, storage, tanda_id, datos.nota)


@router.post("/tandas/{tanda_id}/observar", response_model=TandaDetalle)
def observar_tanda(tanda_id: uuid.UUID, datos: Motivo, contexto: Registro):
    return tandas.observar(contexto, tanda_id, datos.motivo)


@router.post("/tandas/{tanda_id}/anular", response_model=TandaDetalle)
def anular_tanda(tanda_id: uuid.UUID, datos: Motivo, contexto: Registro):
    return tandas.anular(contexto, tanda_id, datos.motivo)


# ---------- DOP ----------


@router.get("/dops", response_model=list[DopSalida])
def listar_dops(
    contexto: Lectura,
    estado: Literal["vigente", "anulado"] | None = None,
    productor_id: uuid.UUID | None = None,
    parcela_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
):
    return dops.listar(
        contexto, estado=estado, productor_id=productor_id, parcela_id=parcela_id, desde=desde, hasta=hasta
    )


@router.get("/dops/{dop_id}", response_model=DopDetalle)
def detalle_dop(dop_id: uuid.UUID, contexto: Lectura):
    return dops.obtener(contexto, dop_id)


@router.get("/dops/{dop_id}/pdf", response_model=UrlDescarga)
def pdf_dop(dop_id: uuid.UUID, contexto: Lectura, storage: Storage):
    return UrlDescarga(url=dops.url_pdf(contexto, storage, dop_id), vence_en_segundos=VIGENCIA_URL_FIRMADA)


@router.post("/dops/{dop_id}/anular", response_model=DopDetalle)
def anular_dop(dop_id: uuid.UUID, datos: Motivo, contexto: Administrador):
    return dops.anular(contexto, dop_id, datos.motivo)

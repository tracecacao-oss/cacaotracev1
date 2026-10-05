"""Productores: padrón, ficha, afiliación, acceso, documentos y parcelas de cada productor."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile

from app.auth_admin import ClienteAuthAdmin, obtener_auth_admin
from app.contexto import Contexto, requiere_rol
from app.routers.comun import json_desde_formulario, leer_archivo, modelo_desde_json
from app.schemas.comunes import ClaveTemporal, Pagina
from app.schemas.parcelas import DocumentoSalida, ParcelaDatos, ParcelaDetalle, ParcelaSalida
from app.schemas.productores import (
    CargaMasiva,
    CierreAfiliacion,
    ProductorCambios,
    ProductorDetalle,
    ProductorNuevo,
    ProductorSalida,
)
from app.services import carga_productores, documentos, parcelas
from app.services import productores as servicio
from app.services.geometria import TAMANO_MAXIMO_ARCHIVO
from app.services.paginacion import ParametrosPaginacion
from app.services.productores import documento_salida
from app.storage import ClienteStorage, obtener_storage

router = APIRouter(prefix="/productores", tags=["productores"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
AuthAdmin = Annotated[ClienteAuthAdmin, Depends(obtener_auth_admin)]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]


@router.get("", response_model=Pagina[ProductorSalida])
def listar_productores(
    contexto: Lectura,
    paginacion: ParametrosPaginacion,
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    items, total = servicio.listar(contexto, q, paginacion)
    return Pagina(items=items, total=total, pagina=paginacion.pagina, por_pagina=paginacion.por_pagina)


@router.post("", response_model=ProductorDetalle, status_code=201)
def crear_productor(datos: ProductorNuevo, contexto: Registro):
    return servicio.crear(contexto, datos)


@router.post("/carga-masiva/analizar", response_model=CargaMasiva)
def analizar_carga_masiva(contexto: Registro, archivo: Annotated[UploadFile, File()]):
    return carga_productores.analizar(contexto, leer_archivo(archivo, carga_productores.TAMANO_MAXIMO))


@router.post("/carga-masiva", response_model=CargaMasiva, status_code=201)
def registrar_carga_masiva(contexto: Registro, archivo: Annotated[UploadFile, File()]):
    return carga_productores.registrar(contexto, leer_archivo(archivo, carga_productores.TAMANO_MAXIMO))


@router.get("/{productor_id}", response_model=ProductorDetalle)
def detalle_productor(productor_id: uuid.UUID, contexto: Lectura):
    return servicio.obtener(contexto, productor_id)


@router.patch("/{productor_id}", response_model=ProductorDetalle)
def editar_productor(productor_id: uuid.UUID, datos: ProductorCambios, contexto: Registro, auth: AuthAdmin):
    return servicio.editar(contexto, auth, productor_id, datos)


@router.post("/{productor_id}/afiliacion/cerrar", status_code=204)
def cerrar_afiliacion(
    productor_id: uuid.UUID, datos: CierreAfiliacion, contexto: Administrador, auth: AuthAdmin
) -> Response:
    servicio.cerrar_afiliacion(contexto, auth, productor_id, datos.motivo)
    return Response(status_code=204)


@router.post("/{productor_id}/acceso", response_model=ClaveTemporal, status_code=201)
def crear_acceso(productor_id: uuid.UUID, contexto: Registro, auth: AuthAdmin):
    return ClaveTemporal(clave_temporal=servicio.crear_acceso(contexto, auth, productor_id))


@router.post("/{productor_id}/acceso/restablecer-clave", response_model=ClaveTemporal)
def restablecer_acceso(productor_id: uuid.UUID, contexto: Registro, auth: AuthAdmin):
    return ClaveTemporal(clave_temporal=servicio.restablecer_acceso(contexto, auth, productor_id))


@router.delete("/{productor_id}/acceso", status_code=204)
def desactivar_acceso(productor_id: uuid.UUID, contexto: Registro, auth: AuthAdmin) -> Response:
    servicio.desactivar_acceso(contexto, auth, productor_id)
    return Response(status_code=204)


@router.post("/{productor_id}/documentos", response_model=DocumentoSalida, status_code=201)
def cargar_documento(
    productor_id: uuid.UUID,
    contexto: Registro,
    storage: Storage,
    tipo: Annotated[Literal["dni", "constancia_ppa"], Form()],
    archivo: Annotated[UploadFile, File()],
):
    servicio.obtener(contexto, productor_id)  # 404 si no es de la cooperativa
    documento = documentos.cargar(
        contexto,
        storage,
        entidad="productor",
        entidad_id=productor_id,
        tipo=tipo,
        archivo=leer_archivo(archivo),
    )
    return documento_salida(documento, None)


@router.get("/{productor_id}/parcelas", response_model=list[ParcelaSalida])
def parcelas_del_productor(productor_id: uuid.UUID, contexto: Lectura):
    servicio.obtener(contexto, productor_id)
    return parcelas.listar(contexto, productor_id=productor_id)


def crear_parcela_desde_formulario(
    contexto: Contexto,
    storage: ClienteStorage,
    productor_id: uuid.UUID,
    datos: str,
    geometria: str | None,
    archivo: UploadFile | None,
    indice: int | None,
) -> ParcelaDetalle:
    """Formulario multipart: `datos` (JSON) y, o bien `geometria` (GeoJSON dibujado), o bien
    `archivo` (GeoJSON o KML) con el `indice` de la geometría elegida."""
    return parcelas.crear(
        contexto,
        storage,
        productor_id,
        modelo_desde_json(ParcelaDatos, datos, "datos"),
        geometria_dibujada=json_desde_formulario(geometria, "geometria"),
        archivo=leer_archivo(archivo, TAMANO_MAXIMO_ARCHIVO) if archivo is not None else None,
        indice=indice,
    )


@router.post("/{productor_id}/parcelas", response_model=ParcelaDetalle, status_code=201)
def crear_parcela(
    productor_id: uuid.UUID,
    contexto: Registro,
    storage: Storage,
    datos: Annotated[str, Form()],
    geometria: Annotated[str | None, Form()] = None,
    archivo: Annotated[UploadFile | None, File()] = None,
    indice: Annotated[int | None, Form()] = None,
):
    return crear_parcela_desde_formulario(contexto, storage, productor_id, datos, geometria, archivo, indice)

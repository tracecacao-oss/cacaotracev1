"""Adenda 2 de la Parte 4: imágenes satelitales de la parcela y revisiones de imágenes.

El personal ve las imágenes y las revisiones; el administrador las revisa, busca más fechas y carga una
imagen externa; el operador puede pedir que se regeneren. El productor las ve en /mi (routers/mi.py).
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from app.contexto import Contexto, requiere_rol
from app.routers.comun import leer_archivo
from app.schemas.comunes import Texto
from app.schemas.imagenes import ConsumoSalida, ImagenesSalida, RevisionNueva, RevisionSalida
from app.schemas.parcelas import Anulacion
from app.services import imagenes, revisiones_imagenes
from app.services.parcelas import parcela_visible
from app.storage import ClienteStorage, obtener_storage

router = APIRouter(tags=["imagenes"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Superadmin = Annotated[Contexto, Depends(requiere_rol("superadmin"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]


@router.get("/parcelas/{parcela_id}/imagenes", response_model=ImagenesSalida)
def imagenes_de_parcela(parcela_id: uuid.UUID, contexto: Lectura, storage: Storage):
    return imagenes.salida(contexto.sesion, storage, parcela_visible(contexto, parcela_id))


@router.post("/parcelas/{parcela_id}/imagenes", status_code=202)
def regenerar_imagenes(parcela_id: uuid.UUID, contexto: Registro):
    imagenes.regenerar(contexto, parcela_visible(contexto, parcela_id))
    return Response(status_code=202)


@router.post("/parcelas/{parcela_id}/imagenes/buscar-mas", status_code=202)
def buscar_mas_imagenes(parcela_id: uuid.UUID, contexto: Administrador):
    imagenes.buscar_mas(contexto, parcela_visible(contexto, parcela_id))
    return Response(status_code=202)


@router.post("/parcelas/{parcela_id}/imagenes/externa", response_model=ImagenesSalida, status_code=201)
def cargar_imagen_externa(
    parcela_id: uuid.UUID,
    contexto: Administrador,
    storage: Storage,
    archivo: Annotated[UploadFile, File()],
    fuente: Annotated[Texto, Form()],
    fecha_captura: Annotated[date, Form()],
):
    parcela = parcela_visible(contexto, parcela_id)
    imagenes.cargar_externa(contexto, storage, parcela, leer_archivo(archivo), fuente, fecha_captura)
    return imagenes.salida(contexto.sesion, storage, parcela)


@router.get("/parcelas/{parcela_id}/revisiones-imagenes", response_model=list[RevisionSalida])
def revisiones_de_parcela(parcela_id: uuid.UUID, contexto: Lectura):
    return revisiones_imagenes.listar(contexto.sesion, parcela_visible(contexto, parcela_id))


@router.post(
    "/parcelas/{parcela_id}/revisiones-imagenes", response_model=list[RevisionSalida], status_code=201
)
def registrar_revision(parcela_id: uuid.UUID, datos: RevisionNueva, contexto: Administrador):
    return revisiones_imagenes.registrar(contexto, parcela_visible(contexto, parcela_id), datos)


@router.post("/revisiones-imagenes/{revision_id}/anular", response_model=list[RevisionSalida])
def anular_revision(revision_id: uuid.UUID, datos: Anulacion, contexto: Administrador):
    return revisiones_imagenes.anular(contexto, revision_id, datos.motivo)


@router.get("/admin/imagenes/consumo", response_model=ConsumoSalida)
def consumo_de_imagenes(contexto: Superadmin):
    """Unidades de procesamiento de Copernicus usadas en el mes, para la pantalla de plataforma (11.1)."""
    return imagenes.consumo_salida(contexto.sesion)

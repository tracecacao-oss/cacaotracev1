"""Adenda 5: declaración anual del productor (sección 5.8).

Registran en nombre del productor, cargan la hoja firmada y los papeles, y revisan los productos el
administrador y el operador; la nota de seguimiento, solo el administrador. El productor declara desde /mi.
Otra organización recibe 404.
"""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.contexto import Contexto, cooperativa_del_contexto, obtener_contexto, requiere_rol
from app.routers.comun import leer_archivo
from app.routers.legalidad import pdf
from app.schemas.declaracion import (
    CuestionarioSalida,
    DeclaracionNueva,
    DeclaracionProductorSalida,
    NotaSeguimiento,
    RevisionProducto,
)
from app.schemas.parcelas import DocumentoSalida
from app.services import declaracion_productor as servicio
from app.services.productores import documento_salida
from app.storage import ClienteStorage, obtener_storage

router = APIRouter(tags=["declaraciones"])
Sesion = Annotated[Contexto, Depends(obtener_contexto)]
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]
Papel = Literal["relacion_trabajadores", "declaracion_renta"]


def _salida(contexto: Contexto, productor_id: uuid.UUID) -> DeclaracionProductorSalida:
    return servicio.salida(contexto.sesion, productor_id, cooperativa_del_contexto(contexto))


@router.get("/declaraciones-productor/cuestionario", response_model=CuestionarioSalida)
def cuestionario(contexto: Sesion):
    return servicio.cuestionario_salida(contexto.sesion)


@router.get("/productores/{productor_id}/declaracion", response_model=DeclaracionProductorSalida)
def declaracion_del_productor(productor_id: uuid.UUID, contexto: Lectura):
    servicio.productor_afiliado(contexto, productor_id)
    return _salida(contexto, productor_id)


@router.post(
    "/productores/{productor_id}/declaraciones", response_model=DeclaracionProductorSalida, status_code=201
)
def registrar_declaracion(productor_id: uuid.UUID, datos: DeclaracionNueva, contexto: Registro):
    servicio.registrar(contexto, productor_id, datos.respuestas)
    return _salida(contexto, productor_id)


@router.get("/productores/{productor_id}/declaraciones/{declaracion_id}/hoja")
def hoja_de_la_declaracion(productor_id: uuid.UUID, declaracion_id: uuid.UUID, contexto: Lectura):
    _, declaracion = servicio.declaracion_visible(contexto, productor_id, declaracion_id)
    return pdf(*servicio.hoja(contexto.sesion, declaracion))


@router.post(
    "/productores/{productor_id}/declaraciones/{declaracion_id}/hoja-firmada",
    response_model=DeclaracionProductorSalida,
)
def cargar_hoja_firmada(
    productor_id: uuid.UUID,
    declaracion_id: uuid.UUID,
    contexto: Registro,
    storage: Storage,
    fecha_firma: Annotated[date, Form()],
    archivo: Annotated[UploadFile, File()],
):
    servicio.cargar_hoja_firmada(
        contexto, storage, productor_id, declaracion_id, leer_archivo(archivo), fecha_firma
    )
    return _salida(contexto, productor_id)


@router.post(
    "/productores/{productor_id}/declaraciones/{declaracion_id}/documentos",
    response_model=DocumentoSalida,
    status_code=201,
)
def cargar_papel(
    productor_id: uuid.UUID,
    declaracion_id: uuid.UUID,
    contexto: Registro,
    storage: Storage,
    tipo: Annotated[Papel, Form()],
    archivo: Annotated[UploadFile, File()],
):
    documento = servicio.cargar_papel(
        contexto, storage, productor_id, declaracion_id, tipo, leer_archivo(archivo)
    )
    return documento_salida(documento, None)


@router.patch(
    "/productores/{productor_id}/declaraciones/{declaracion_id}/productos/{producto_id}",
    response_model=DeclaracionProductorSalida,
)
def revisar_producto(
    productor_id: uuid.UUID,
    declaracion_id: uuid.UUID,
    producto_id: uuid.UUID,
    datos: RevisionProducto,
    contexto: Registro,
):
    servicio.revisar_producto(
        contexto, productor_id, declaracion_id, producto_id, datos.revision, datos.registro
    )
    return _salida(contexto, productor_id)


@router.put(
    "/productores/{productor_id}/declaraciones/{declaracion_id}/seguimiento",
    response_model=DeclaracionProductorSalida,
)
def nota_de_seguimiento(
    productor_id: uuid.UUID, declaracion_id: uuid.UUID, datos: NotaSeguimiento, contexto: Administrador
):
    servicio.escribir_seguimiento(contexto, productor_id, declaracion_id, datos.nota)
    return _salida(contexto, productor_id)

"""Productores, versión mínima. La Parte 3 amplía estos endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.auth_admin import ClienteAuthAdmin, obtener_auth_admin
from app.contexto import Contexto, requiere_rol
from app.schemas.comunes import ClaveTemporal, Pagina
from app.schemas.productores import ProductorNuevo, ProductorSalida
from app.services import productores as servicio
from app.services.paginacion import ParametrosPaginacion

router = APIRouter(prefix="/productores", tags=["productores"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
AuthAdmin = Annotated[ClienteAuthAdmin, Depends(obtener_auth_admin)]


@router.get("", response_model=Pagina[ProductorSalida])
def listar_productores(
    contexto: Lectura,
    paginacion: ParametrosPaginacion,
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    items, total = servicio.listar(contexto, q, paginacion)
    return Pagina(items=items, total=total, pagina=paginacion.pagina, por_pagina=paginacion.por_pagina)


@router.post("", response_model=ProductorSalida, status_code=201)
def crear_productor(datos: ProductorNuevo, contexto: Registro):
    return servicio.crear(contexto, datos)


@router.get("/{productor_id}", response_model=ProductorSalida)
def detalle_productor(productor_id: uuid.UUID, contexto: Lectura):
    return servicio.obtener(contexto, productor_id)


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

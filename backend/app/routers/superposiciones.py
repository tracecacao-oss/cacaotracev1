"""Superposiciones: las de la cooperativa y, para el superadmin, las que hay entre cooperativas."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from app.contexto import Contexto, cooperativa_del_contexto, requiere_rol
from app.schemas.superposiciones import Aceptacion, SuperposicionSalida
from app.services import superposiciones as servicio

router = APIRouter(tags=["superposiciones"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Superadmin = Annotated[Contexto, Depends(requiere_rol("superadmin"))]
Estado = Literal["abierta", "resuelta", "aceptada"]


@router.get("/superposiciones", response_model=list[SuperposicionSalida])
def listar(contexto: Lectura, estado: Estado | None = None):
    return servicio.listar(contexto.sesion, cooperativa_del_contexto(contexto), estado)


@router.post("/superposiciones/{superposicion_id}/aceptar", response_model=SuperposicionSalida)
def aceptar(superposicion_id: uuid.UUID, datos: Aceptacion, contexto: Administrador):
    return servicio.aceptar(contexto, superposicion_id, datos.nota, como_superadmin=False)


@router.get("/admin/superposiciones", response_model=list[SuperposicionSalida])
def listar_entre_cooperativas(contexto: Superadmin, estado: Estado | None = "abierta"):
    return servicio.listar_entre_cooperativas(contexto.sesion, estado)


@router.post("/admin/superposiciones/{superposicion_id}/aceptar", response_model=SuperposicionSalida)
def aceptar_entre_cooperativas(superposicion_id: uuid.UUID, datos: Aceptacion, contexto: Superadmin):
    return servicio.aceptar(contexto, superposicion_id, datos.nota, como_superadmin=True)

"""Plataforma: gestión de cooperativas. Solo superadmin."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth_admin import ClienteAuthAdmin, obtener_auth_admin
from app.contexto import Contexto, requiere_rol
from app.schemas.comunes import ClaveTemporal, Pagina
from app.schemas.plataforma import (
    CooperativaCambios,
    CooperativaCreada,
    CooperativaNueva,
    CooperativaSalida,
    UsoSalida,
)
from app.schemas.usuarios import AdministradorNuevo, CuentaCreada, UsuarioSalida
from app.services import plataforma as servicio
from app.services import uso as servicio_uso
from app.services.paginacion import ParametrosPaginacion

router = APIRouter(prefix="/admin", tags=["plataforma"])
Superadmin = Annotated[Contexto, Depends(requiere_rol("superadmin"))]
AuthAdmin = Annotated[ClienteAuthAdmin, Depends(obtener_auth_admin)]


@router.get("/cooperativas", response_model=Pagina[CooperativaSalida])
def listar_cooperativas(
    contexto: Superadmin,
    paginacion: ParametrosPaginacion,
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    items, total = servicio.listar(contexto, q, paginacion)
    return Pagina(items=items, total=total, pagina=paginacion.pagina, por_pagina=paginacion.por_pagina)


@router.post("/cooperativas", response_model=CooperativaCreada, status_code=201)
def crear_cooperativa(datos: CooperativaNueva, contexto: Superadmin, auth: AuthAdmin):
    cooperativa, administrador, clave = servicio.crear(contexto, auth, datos)
    return CooperativaCreada(
        cooperativa=cooperativa,
        administrador=UsuarioSalida.model_validate(administrador),
        clave_temporal=clave,
    )


@router.get("/cooperativas/{cooperativa_id}", response_model=CooperativaSalida)
def detalle_cooperativa(cooperativa_id: uuid.UUID, contexto: Superadmin):
    return servicio.obtener(contexto, cooperativa_id)


@router.patch("/cooperativas/{cooperativa_id}", response_model=CooperativaSalida)
def editar_cooperativa(cooperativa_id: uuid.UUID, datos: CooperativaCambios, contexto: Superadmin):
    return servicio.editar(contexto, cooperativa_id, datos)


@router.post("/cooperativas/{cooperativa_id}/administradores", response_model=CuentaCreada, status_code=201)
def crear_administrador(
    cooperativa_id: uuid.UUID, datos: AdministradorNuevo, contexto: Superadmin, auth: AuthAdmin
):
    perfil, clave = servicio.crear_administrador(contexto, auth, cooperativa_id, datos)
    return CuentaCreada(usuario=UsuarioSalida.model_validate(perfil), clave_temporal=clave)


@router.get("/uso", response_model=UsoSalida)
def uso(contexto: Superadmin):
    """Parte 10: espacio en archivos y en base de datos, en total y por cooperativa."""
    return servicio_uso.uso(contexto)


@router.post("/usuarios/{usuario_id}/restablecer-clave", response_model=ClaveTemporal)
def restablecer_clave_administrador(usuario_id: uuid.UUID, contexto: Superadmin, auth: AuthAdmin):
    return ClaveTemporal(clave_temporal=servicio.restablecer_clave_administrador(contexto, auth, usuario_id))

"""Personal de la cooperativa. Gestiona admin_cooperativa; superadmin consulta en solo lectura."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth_admin import ClienteAuthAdmin, obtener_auth_admin
from app.contexto import Contexto, requiere_rol
from app.schemas.comunes import ClaveTemporal, Pagina
from app.schemas.usuarios import CuentaCreada, UsuarioCambios, UsuarioNuevo, UsuarioSalida
from app.services import usuarios as servicio
from app.services.paginacion import ParametrosPaginacion

router = APIRouter(prefix="/usuarios", tags=["usuarios"])
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "superadmin"))]
AuthAdmin = Annotated[ClienteAuthAdmin, Depends(obtener_auth_admin)]


@router.get("", response_model=Pagina[UsuarioSalida])
def listar_usuarios(
    contexto: Lectura,
    paginacion: ParametrosPaginacion,
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    items, total = servicio.listar(contexto, q, paginacion)
    return Pagina(items=items, total=total, pagina=paginacion.pagina, por_pagina=paginacion.por_pagina)


@router.post("", response_model=CuentaCreada, status_code=201)
def crear_usuario(datos: UsuarioNuevo, contexto: Administrador, auth: AuthAdmin):
    perfil, clave = servicio.crear(contexto, auth, datos)
    return CuentaCreada(usuario=UsuarioSalida.model_validate(perfil), clave_temporal=clave)


@router.patch("/{usuario_id}", response_model=UsuarioSalida)
def editar_usuario(usuario_id: uuid.UUID, datos: UsuarioCambios, contexto: Administrador, auth: AuthAdmin):
    return servicio.editar(contexto, auth, usuario_id, datos)


@router.post("/{usuario_id}/restablecer-clave", response_model=ClaveTemporal)
def restablecer_clave(usuario_id: uuid.UUID, contexto: Administrador, auth: AuthAdmin):
    return ClaveTemporal(clave_temporal=servicio.restablecer_clave(contexto, auth, usuario_id))

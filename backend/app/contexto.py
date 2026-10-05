"""Contexto de cada petición protegida: quién es, qué rol tiene y a qué cooperativa pertenece.

La cooperativa sale siempre del perfil en la base de datos, nunca de un dato del navegador.
La única excepción es el superadministrador, que elige qué cooperativa consultar con la
cabecera X-Cooperativa-Id, solo en peticiones GET.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import UsuarioToken, usuario_actual
from app.db import obtener_sesion
from app.errores import error_api, no_encontrado, sin_permiso
from app.models import Auditoria, Cooperativa, Perfil

CABECERA_COOPERATIVA = "X-Cooperativa-Id"
# Mientras debe_cambiar_clave sea true, solo se permite esto.
RUTAS_CON_CAMBIO_PENDIENTE = {("GET", "/me"), ("POST", "/me/clave")}
# Una consulta de soporte se audita una vez por superadmin y cooperativa en esta ventana.
VENTANA_CONSULTA = timedelta(minutes=30)


@dataclass
class Contexto:
    sesion: Session
    perfil: Perfil
    usuario_id: uuid.UUID
    rol: str
    cooperativa_id: uuid.UUID | None
    productor_id: uuid.UUID | None
    ip: str | None

    @property
    def consultando(self) -> bool:
        """Superadministrador viendo una cooperativa en solo lectura."""
        return self.rol == "superadmin" and self.cooperativa_id is not None


def _ip(request: Request) -> str | None:
    # Render y Cloudflare ponen la IP del cliente en X-Forwarded-For.
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else None


def _cooperativa_consultada(request: Request, sesion: Session) -> uuid.UUID | None:
    valor = request.headers.get(CABECERA_COOPERATIVA)
    if not valor or request.method != "GET":
        return None
    try:
        cooperativa_id = uuid.UUID(valor)
    except ValueError as exc:
        raise error_api(400, "cabecera_invalida", "El identificador de cooperativa no es válido.") from exc
    if sesion.get(Cooperativa, cooperativa_id) is None:
        raise no_encontrado("La cooperativa no existe.")
    return cooperativa_id


def _auditar_consulta(sesion: Session, perfil: Perfil, cooperativa_id: uuid.UUID, ip: str | None) -> None:
    desde = datetime.now(UTC) - VENTANA_CONSULTA
    reciente = sesion.scalar(
        select(Auditoria.id).where(
            Auditoria.usuario_id == perfil.id,
            Auditoria.accion == "superadmin.consultar_cooperativa",
            Auditoria.cooperativa_id == cooperativa_id,
            Auditoria.ocurrido_en >= desde,
        )
    )
    if reciente is None:
        sesion.add(
            Auditoria(
                usuario_id=perfil.id,
                rol=perfil.rol,
                cooperativa_id=cooperativa_id,
                accion="superadmin.consultar_cooperativa",
                entidad="cooperativa",
                entidad_id=str(cooperativa_id),
                detalle={},
                ip=ip,
            )
        )
        sesion.commit()


def obtener_contexto(
    request: Request,
    usuario: Annotated[UsuarioToken, Depends(usuario_actual)],
    sesion: Annotated[Session, Depends(obtener_sesion)],
) -> Contexto:
    try:
        perfil = sesion.get(Perfil, uuid.UUID(usuario.id))
    except ValueError:
        perfil = None
    if perfil is None:
        raise error_api(403, "sin_perfil", "Tu cuenta no tiene acceso a CacaoTrace.")
    if not perfil.activo:
        raise error_api(403, "cuenta_desactivada", "Tu cuenta está desactivada. Consulta con tu cooperativa.")
    if perfil.cooperativa is not None and perfil.cooperativa.estado == "suspendida":
        raise error_api(
            403,
            "cooperativa_suspendida",
            "Tu cooperativa está suspendida. Consulta con el equipo CacaoTrace.",
        )
    if perfil.debe_cambiar_clave and (request.method, request.url.path) not in RUTAS_CON_CAMBIO_PENDIENTE:
        raise error_api(403, "cambio_clave_requerido", "Debes cambiar tu contraseña antes de continuar.")

    ip = _ip(request)
    cooperativa_id = perfil.cooperativa_id
    if perfil.rol == "superadmin":
        cooperativa_id = _cooperativa_consultada(request, sesion)
        if cooperativa_id is not None:
            _auditar_consulta(sesion, perfil, cooperativa_id, ip)

    return Contexto(
        sesion=sesion,
        perfil=perfil,
        usuario_id=perfil.id,
        rol=perfil.rol,
        cooperativa_id=cooperativa_id,
        productor_id=perfil.productor_id,
        ip=ip,
    )


def requiere_rol(*roles: str) -> Callable[..., Contexto]:
    """Dependencia reutilizable: requiere_rol("admin_cooperativa", "operador")."""

    def dependencia(contexto: Annotated[Contexto, Depends(obtener_contexto)]) -> Contexto:
        if contexto.rol not in roles:
            raise sin_permiso()
        return contexto

    return dependencia


def cooperativa_del_contexto(contexto: Contexto) -> uuid.UUID:
    """Cooperativa sobre la que opera la petición. El superadmin debe haber elegido una."""
    if contexto.cooperativa_id is None:
        raise error_api(400, "cooperativa_requerida", "Elige una cooperativa para consultar.")
    return contexto.cooperativa_id

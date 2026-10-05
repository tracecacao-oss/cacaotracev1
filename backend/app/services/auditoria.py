"""Registro de auditoría. Se escribe dentro de la misma transacción que el cambio."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import aliased

from app.contexto import Contexto
from app.models import Auditoria, Perfil

# Nunca se guardan contraseñas, tokens ni contenido de archivos.
CLAVES_PROHIBIDAS = ("clave", "password", "contrasena", "contraseña", "token", "secret", "secreto")
_DEL_CONTEXTO = object()


def _limpiar(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {
            str(k): _limpiar(v)
            for k, v in valor.items()
            if not any(p in str(k).lower() for p in CLAVES_PROHIBIDAS)
        }
    if isinstance(valor, list | tuple | set):
        return [_limpiar(v) for v in valor]
    if isinstance(valor, uuid.UUID | Decimal):
        return str(valor)
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    return valor


def registrar_auditoria(
    contexto: Contexto | None,
    accion: str,
    entidad: str,
    entidad_id: Any,
    detalle: dict[str, Any] | None = None,
    *,
    cooperativa_id: Any = _DEL_CONTEXTO,
    sesion=None,
) -> None:
    """Agrega la fila a la sesión; se confirma o revierte junto con el cambio auditado.

    contexto es None solo para los scripts de operación, que pasan su propia sesión.
    """
    if cooperativa_id is _DEL_CONTEXTO:
        cooperativa_id = contexto.cooperativa_id if contexto else None
    sesion = sesion or contexto.sesion
    sesion.add(
        Auditoria(
            usuario_id=contexto.usuario_id if contexto else None,
            rol=contexto.rol if contexto else None,
            cooperativa_id=cooperativa_id,
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id) if entidad_id is not None else None,
            detalle=_limpiar(detalle or {}),
            ip=contexto.ip if contexto else None,
        )
    )


def aplicar_cambios(objeto: Any, datos: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Asigna los campos que cambian y devuelve {campo: {"antes": ..., "despues": ...}}."""
    cambios = {}
    for campo, nuevo in datos.items():
        anterior = getattr(objeto, campo)
        if anterior != nuevo:
            setattr(objeto, campo, nuevo)
            cambios[campo] = {"antes": anterior, "despues": nuevo}
    return cambios


def consulta_auditoria(
    cooperativa_id: uuid.UUID | None,
    *,
    todas: bool = False,
    desde: date | None = None,
    hasta: date | None = None,
    usuario_id: uuid.UUID | None = None,
    accion: str | None = None,
) -> Select:
    autor = aliased(Perfil)
    nombre = func.concat(autor.nombres, " ", autor.apellidos).label("usuario_nombre")
    consulta = select(Auditoria, nombre).outerjoin(autor, autor.id == Auditoria.usuario_id)
    if not todas:
        consulta = consulta.where(Auditoria.cooperativa_id == cooperativa_id)
    if desde:
        consulta = consulta.where(func.date(func.timezone("America/Lima", Auditoria.ocurrido_en)) >= desde)
    if hasta:
        consulta = consulta.where(func.date(func.timezone("America/Lima", Auditoria.ocurrido_en)) <= hasta)
    if usuario_id:
        consulta = consulta.where(Auditoria.usuario_id == usuario_id)
    if accion:
        consulta = consulta.where(Auditoria.accion.startswith(accion, autoescape=True))
    return consulta.order_by(Auditoria.ocurrido_en.desc(), Auditoria.id.desc())

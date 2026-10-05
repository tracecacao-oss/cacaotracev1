"""Cuentas de acceso: creación en Supabase Auth + perfil, contraseñas temporales y bloqueos.

Ninguna cuenta nace por registro abierto. Quien la crea recibe la contraseña temporal una
sola vez; no se guarda ni se escribe en logs ni en auditoría.
"""

import logging
import re
import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_admin import ClienteAuthAdmin, CorreoEnUso, ErrorAuthAdmin
from app.config import get_settings
from app.contexto import Contexto
from app.errores import error_api
from app.models import Perfil
from app.services.auditoria import registrar_auditoria

log = logging.getLogger(__name__)

# Sin caracteres ambiguos: 0, O, 1, l e I.
ALFABETO_TEMPORAL = "".join(
    c for c in "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789" if c not in "0O1lI"
)
LARGO_TEMPORAL = 10
MINIMO_PERSONAL = 8
MINIMO_PRODUCTOR = 6


def generar_clave_temporal() -> str:
    while True:
        clave = "".join(secrets.choice(ALFABETO_TEMPORAL) for _ in range(LARGO_TEMPORAL))
        # Con letra y dígito, cumple también la regla de contraseñas del personal.
        if re.search(r"[A-Za-z]", clave) and re.search(r"[0-9]", clave):
            return clave


def validar_clave_nueva(rol: str, clave_nueva: str, clave_actual: str) -> None:
    if clave_nueva == clave_actual:
        raise error_api(400, "clave_repetida", "La nueva contraseña debe ser distinta de la actual.")
    if rol == "productor":
        if len(clave_nueva) < MINIMO_PRODUCTOR:
            raise error_api(400, "clave_debil", "La contraseña debe tener al menos 6 caracteres.")
        return
    if (
        len(clave_nueva) < MINIMO_PERSONAL
        or not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", clave_nueva)
        or not re.search(r"[0-9]", clave_nueva)
    ):
        raise error_api(
            400,
            "clave_debil",
            "La contraseña debe tener al menos 8 caracteres, con al menos una letra y un dígito.",
        )


def correo_tecnico(dni: str) -> str:
    """Correo con el que Supabase Auth identifica al productor. Nunca recibe mensajes."""
    return f"{dni}@{get_settings().productor_email_domain}"


def correo_de_acceso(perfil: Perfil) -> str:
    if perfil.rol == "productor":
        return correo_tecnico(perfil.productor.dni)
    return perfil.correo


def comprobar_correo_libre(sesion: Session, correo: str) -> None:
    if sesion.scalar(select(Perfil.id).where(func.lower(Perfil.correo) == correo.lower())) is not None:
        raise _correo_en_uso()


def _correo_en_uso():
    return error_api(409, "correo_en_uso", "Ese correo ya está en uso.")


def _servicio_no_disponible():
    return error_api(
        503, "autenticacion_no_disponible", "No se pudo completar la operación de acceso. Intenta de nuevo."
    )


def crear_cuenta(
    contexto: Contexto,
    auth: ClienteAuthAdmin,
    *,
    correo_auth: str,
    datos_perfil: dict,
    accion: str,
    cooperativa_id: uuid.UUID | None,
    detalle: dict | None = None,
) -> tuple[Perfil, str]:
    """Crea el usuario en Auth y su perfil, audita y confirma todo lo pendiente de la sesión.

    Si el perfil o la confirmación fallan, se borra el usuario de Auth: no quedan cuentas huérfanas.
    """
    sesion = contexto.sesion
    clave = generar_clave_temporal()
    try:
        auth_id = auth.crear_usuario(correo_auth, clave)
    except CorreoEnUso as exc:
        sesion.rollback()
        raise _correo_en_uso() from exc
    except ErrorAuthAdmin as exc:
        sesion.rollback()
        raise _servicio_no_disponible() from exc

    try:
        perfil = Perfil(
            id=auth_id,
            creado_por=contexto.usuario_id,
            cooperativa_id=cooperativa_id,
            debe_cambiar_clave=True,
            activo=True,
            **datos_perfil,
        )
        sesion.add(perfil)
        sesion.flush()
        registrar_auditoria(
            contexto,
            accion,
            "usuario",
            perfil.id,
            {"rol": perfil.rol, "nombres": perfil.nombres, "apellidos": perfil.apellidos, **(detalle or {})},
            cooperativa_id=cooperativa_id,
        )
        sesion.commit()
    except Exception as exc:
        sesion.rollback()
        try:
            auth.borrar_usuario(auth_id)
        except ErrorAuthAdmin:
            log.error("No se pudo borrar el usuario huérfano %s de Supabase Auth", auth_id)
        if isinstance(exc, IntegrityError):
            raise _correo_en_uso() from exc
        raise
    sesion.refresh(perfil)
    return perfil, clave


def restablecer_clave(contexto: Contexto, auth: ClienteAuthAdmin, perfil: Perfil) -> str:
    """Nueva contraseña temporal y cambio obligatorio.

    Fijar la contraseña desde la administración de Supabase cierra todas las sesiones abiertas.
    """
    clave = generar_clave_temporal()
    perfil.debe_cambiar_clave = True
    registrar_auditoria(
        contexto,
        "usuario.restablecer_clave",
        "usuario",
        perfil.id,
        {"rol": perfil.rol},
        cooperativa_id=perfil.cooperativa_id,
    )
    try:
        auth.cambiar_clave(perfil.id, clave)
    except ErrorAuthAdmin as exc:
        contexto.sesion.rollback()
        raise _servicio_no_disponible() from exc
    contexto.sesion.commit()
    return clave


def desactivar(
    contexto: Contexto, auth: ClienteAuthAdmin, perfil: Perfil, accion: str, detalle: dict
) -> None:
    """La cuenta no se borra (la auditoría la referencia): se desactiva y se bloquea en Auth."""
    perfil.activo = False
    registrar_auditoria(contexto, accion, "usuario", perfil.id, detalle, cooperativa_id=perfil.cooperativa_id)
    try:
        auth.bloquear(perfil.id)
    except ErrorAuthAdmin as exc:
        contexto.sesion.rollback()
        raise _servicio_no_disponible() from exc
    contexto.sesion.commit()


def reactivar(contexto: Contexto, auth: ClienteAuthAdmin, perfil: Perfil, accion: str, detalle: dict) -> None:
    perfil.activo = True
    registrar_auditoria(contexto, accion, "usuario", perfil.id, detalle, cooperativa_id=perfil.cooperativa_id)
    try:
        auth.desbloquear(perfil.id)
    except ErrorAuthAdmin as exc:
        contexto.sesion.rollback()
        raise _servicio_no_disponible() from exc
    contexto.sesion.commit()

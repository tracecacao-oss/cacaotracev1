"""Personal de la cooperativa: lo gestiona su administrador."""

import uuid

from sqlalchemy import func, or_, select

from app.auth_admin import ClienteAuthAdmin
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.models import ROLES_PERSONAL, Perfil
from app.schemas.usuarios import UsuarioCambios, UsuarioNuevo
from app.services import cuentas
from app.services.auditoria import aplicar_cambios, registrar_auditoria
from app.services.paginacion import Paginacion, paginar


def listar(contexto: Contexto, busqueda: str | None, paginacion: Paginacion):
    cooperativa_id = cooperativa_del_contexto(contexto)
    consulta = select(Perfil).where(Perfil.cooperativa_id == cooperativa_id, Perfil.rol.in_(ROLES_PERSONAL))
    if busqueda:
        patron = f"%{busqueda.strip()}%"
        consulta = consulta.where(
            or_(
                func.concat(Perfil.nombres, " ", Perfil.apellidos).ilike(patron),
                Perfil.correo.ilike(patron),
            )
        )
    filas, total = paginar(contexto.sesion, consulta.order_by(Perfil.apellidos, Perfil.nombres), paginacion)
    return [fila[0] for fila in filas], total


def _personal(contexto: Contexto, usuario_id: uuid.UUID) -> Perfil:
    """Solo personal de la propia cooperativa; cualquier otro caso es 404, como si no existiera."""
    perfil = contexto.sesion.get(Perfil, usuario_id)
    if perfil is None or perfil.cooperativa_id != contexto.cooperativa_id or perfil.rol not in ROLES_PERSONAL:
        raise no_encontrado("El usuario no existe.")
    return perfil


def crear(contexto: Contexto, auth: ClienteAuthAdmin, datos: UsuarioNuevo):
    cuentas.comprobar_correo_libre(contexto.sesion, datos.correo)
    return cuentas.crear_cuenta(
        contexto,
        auth,
        correo_auth=datos.correo,
        datos_perfil=datos.model_dump(),
        accion="usuario.crear",
        cooperativa_id=contexto.cooperativa_id,
    )


def _otros_administradores_activos(contexto: Contexto, perfil: Perfil) -> int:
    return contexto.sesion.scalar(
        select(func.count(Perfil.id)).where(
            Perfil.cooperativa_id == perfil.cooperativa_id,
            Perfil.rol == "admin_cooperativa",
            Perfil.activo.is_(True),
            Perfil.id != perfil.id,
        )
    )


def editar(
    contexto: Contexto, auth: ClienteAuthAdmin, usuario_id: uuid.UUID, datos: UsuarioCambios
) -> Perfil:
    perfil = _personal(contexto, usuario_id)
    valores = {k: v for k, v in datos.model_dump(exclude_unset=True).items() if v is not None}
    activo = valores.pop("activo", None)
    cambia_rol = "rol" in valores and valores["rol"] != perfil.rol
    desactiva = activo is False and perfil.activo

    deja_de_ser_admin = perfil.rol == "admin_cooperativa" and perfil.activo and (cambia_rol or desactiva)
    if deja_de_ser_admin and _otros_administradores_activos(contexto, perfil) == 0:
        raise error_api(
            400, "ultimo_administrador", "La cooperativa debe conservar al menos un administrador activo."
        )
    if perfil.id == contexto.usuario_id and (cambia_rol or desactiva):
        raise error_api(400, "accion_sobre_si_mismo", "No puedes desactivarte ni cambiar tu propio rol.")

    cambios = aplicar_cambios(perfil, valores)
    if cambios:
        registrar_auditoria(contexto, "usuario.editar", "usuario", perfil.id, cambios)

    if desactiva:
        cuentas.desactivar(contexto, auth, perfil, "usuario.desactivar", {"rol": perfil.rol})
    elif activo is True and not perfil.activo:
        cuentas.reactivar(contexto, auth, perfil, "usuario.reactivar", {"rol": perfil.rol})
    else:
        contexto.sesion.commit()
    contexto.sesion.refresh(perfil)
    return perfil


def restablecer_clave(contexto: Contexto, auth: ClienteAuthAdmin, usuario_id: uuid.UUID) -> str:
    return cuentas.restablecer_clave(contexto, auth, _personal(contexto, usuario_id))

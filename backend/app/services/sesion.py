"""Sesión del usuario: datos propios, cambio de contraseña y consentimiento del productor."""

from datetime import UTC, datetime

from app.auth_admin import ClaveRechazada, ClienteAuthAdmin, ErrorAuthAdmin
from app.contexto import Contexto
from app.errores import error_api, sin_permiso
from app.schemas.sesion import CooperativaDelUsuario, MeRespuesta
from app.services.auditoria import registrar_auditoria
from app.services.cuentas import correo_de_acceso, validar_clave_nueva


def datos_me(contexto: Contexto) -> MeRespuesta:
    perfil = contexto.perfil
    perfil.ultimo_acceso_en = datetime.now(UTC)
    contexto.sesion.commit()
    productor = perfil.productor
    return MeRespuesta(
        id=perfil.id,
        rol=perfil.rol,
        nombres=perfil.nombres,
        apellidos=perfil.apellidos,
        correo=perfil.correo,
        dni=productor.dni if productor else None,
        cooperativa=CooperativaDelUsuario.model_validate(perfil.cooperativa) if perfil.cooperativa else None,
        productor_id=perfil.productor_id,
        debe_cambiar_clave=perfil.debe_cambiar_clave,
        consentimiento_pendiente=bool(productor and productor.consentimiento_datos_en is None),
    )


def cambiar_clave(contexto: Contexto, auth: ClienteAuthAdmin, clave_actual: str, clave_nueva: str) -> None:
    """Cambia la contraseña propia. Supabase cierra todas las sesiones del usuario, incluida
    la actual: la interfaz vuelve a iniciar sesión con la contraseña nueva."""
    perfil = contexto.perfil
    validar_clave_nueva(perfil.rol, clave_nueva, clave_actual)
    try:
        if not auth.verificar_clave(correo_de_acceso(perfil), clave_actual, ip=contexto.ip):
            raise error_api(400, "clave_actual_incorrecta", "La contraseña actual no es correcta.")
        auth.cambiar_clave(perfil.id, clave_nueva)
    except ClaveRechazada as exc:
        raise error_api(
            400, "clave_debil", "La contraseña no cumple la política de seguridad. Prueba con una más larga."
        ) from exc
    except ErrorAuthAdmin as exc:
        raise error_api(
            503, "autenticacion_no_disponible", "No se pudo cambiar la contraseña. Intenta de nuevo."
        ) from exc
    perfil.debe_cambiar_clave = False
    registrar_auditoria(
        contexto, "usuario.cambiar_clave", "usuario", perfil.id, {}, cooperativa_id=perfil.cooperativa_id
    )
    contexto.sesion.commit()


def registrar_consentimiento(contexto: Contexto, version_texto: str) -> None:
    if contexto.rol != "productor":
        raise sin_permiso()
    productor = contexto.perfil.productor
    if productor.consentimiento_datos_en is not None:
        return  # ya registrado, por el productor o por la cooperativa
    productor.consentimiento_datos_en = datetime.now(UTC)
    productor.consentimiento_origen = "productor"
    registrar_auditoria(
        contexto,
        "productor.consentimiento",
        "productor",
        productor.id,
        {"origen": "productor", "version_texto": version_texto},
    )
    contexto.sesion.commit()

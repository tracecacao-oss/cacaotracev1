"""Cliente de la API de administración de Supabase Auth.

Solo lo usa la API, con la clave secreta, para crear, bloquear y borrar usuarios y fijar
contraseñas. Los usuarios se crean ya confirmados y nunca se les envía correo: el correo
técnico del productor (<dni>@productores.cacaotrace.local) no puede recibirlo.

Comportamiento verificado en el código de Supabase Auth (v2.197, sept. 2026):
- Fijar una contraseña desde la administración cierra todas las sesiones del usuario.
- Un bloqueo (ban) impide iniciar sesión y renovar el token, pero no borra las sesiones.
"""

import logging
import uuid

import httpx
from fastapi import Request

from app.config import Settings
from app.errores import error_api

log = logging.getLogger(__name__)

# Bloqueo "permanente" para cuentas desactivadas: ~100 años (Go time.ParseDuration, sin unidad "d").
DURACION_BLOQUEO = "876000h"
# Errores con la forma {"code": "email_exists", "message": ...}.
VERSION_API = "2024-01-01"
POR_PAGINA = 200


class ErrorAuthAdmin(Exception):
    pass


class CorreoEnUso(ErrorAuthAdmin):
    pass


class ClaveRechazada(ErrorAuthAdmin):
    """La política de contraseñas del proyecto de Supabase la rechazó (weak_password)."""


class ClienteAuthAdmin:
    def __init__(self, supabase_url: str, clave_secreta: str, http: httpx.Client | None = None):
        self._base = f"{supabase_url.rstrip('/')}/auth/v1"
        self._clave = clave_secreta
        self._http = http or httpx.Client(timeout=20)

    def _cabeceras(self) -> dict[str, str]:
        cabeceras = {"apikey": self._clave, "X-Supabase-Api-Version": VERSION_API}
        # Las claves nuevas (sb_secret_...) no son JWT: van solo en apikey.
        if not self._clave.startswith("sb_secret_"):
            cabeceras["Authorization"] = f"Bearer {self._clave}"
        return cabeceras

    def _pedir(self, metodo: str, ruta: str, cabeceras: dict | None = None, **kwargs) -> httpx.Response:
        try:
            return self._http.request(
                metodo, f"{self._base}{ruta}", headers=self._cabeceras() | (cabeceras or {}), **kwargs
            )
        except httpx.HTTPError as exc:
            raise ErrorAuthAdmin(f"Sin conexión con Supabase Auth ({type(exc).__name__})") from exc

    @staticmethod
    def _codigo(respuesta: httpx.Response) -> str | None:
        codigo = respuesta.headers.get("x-sb-error-code")
        if codigo:
            return codigo
        try:
            cuerpo = respuesta.json()
        except ValueError:
            return None
        if not isinstance(cuerpo, dict):
            return None
        return cuerpo.get("error_code") or (
            cuerpo.get("code") if isinstance(cuerpo.get("code"), str) else None
        )

    def _comprobar(self, respuesta: httpx.Response, accion: str) -> None:
        if not respuesta.is_error:
            return
        codigo = self._codigo(respuesta)
        if codigo == "weak_password":
            raise ClaveRechazada(accion)
        # Sin el cuerpo: podría repetir datos del usuario.
        raise ErrorAuthAdmin(f"Supabase Auth respondió {respuesta.status_code} al {accion} ({codigo})")

    def crear_usuario(self, correo: str, clave: str) -> uuid.UUID:
        respuesta = self._pedir(
            "POST", "/admin/users", json={"email": correo, "password": clave, "email_confirm": True}
        )
        if respuesta.status_code == 422 and self._codigo(respuesta) == "email_exists":
            raise CorreoEnUso(correo)
        self._comprobar(respuesta, "crear usuario")
        return uuid.UUID(respuesta.json()["id"])

    def listar_usuarios(self) -> list[dict]:
        """Todos los usuarios, como {"id", "email"}. GET /admin/users pagina con `page` y `per_page` y
        devuelve {"users": [...]} (supabase/auth, openapi.yaml)."""
        usuarios: list[dict] = []
        pagina = 1
        while True:
            respuesta = self._pedir("GET", "/admin/users", params={"page": pagina, "per_page": POR_PAGINA})
            self._comprobar(respuesta, "listar usuarios")
            lote = respuesta.json().get("users") or []
            usuarios += [{"id": uuid.UUID(u["id"]), "email": u.get("email")} for u in lote]
            if len(lote) < POR_PAGINA:
                return usuarios
            pagina += 1

    def borrar_usuario(self, usuario_id: uuid.UUID) -> None:
        respuesta = self._pedir("DELETE", f"/admin/users/{usuario_id}")
        if respuesta.status_code != 404:
            self._comprobar(respuesta, "borrar usuario")

    def _actualizar(self, usuario_id: uuid.UUID, datos: dict, accion: str) -> None:
        respuesta = self._pedir("PUT", f"/admin/users/{usuario_id}", json=datos)
        self._comprobar(respuesta, accion)

    def cambiar_clave(self, usuario_id: uuid.UUID, clave: str) -> None:
        """Fija la contraseña y, de paso, cierra todas las sesiones abiertas del usuario."""
        self._actualizar(usuario_id, {"password": clave}, "cambiar contraseña")

    def cambiar_correo(self, usuario_id: uuid.UUID, correo: str) -> None:
        """Se aplica al instante y sin enviar correo. Supabase no revisa duplicados al
        actualizar: quien llama debe garantizar que el correo está libre."""
        self._actualizar(usuario_id, {"email": correo, "email_confirm": True}, "cambiar correo")

    def bloquear(self, usuario_id: uuid.UUID) -> None:
        """Impide iniciar sesión y renovar el token."""
        self._actualizar(usuario_id, {"ban_duration": DURACION_BLOQUEO}, "bloquear")

    def desbloquear(self, usuario_id: uuid.UUID) -> None:
        self._actualizar(usuario_id, {"ban_duration": "none"}, "desbloquear")

    def verificar_clave(self, correo: str, clave: str, ip: str | None = None) -> bool:
        """Comprueba la contraseña actual con el flujo de inicio de sesión y cierra esa sesión.

        Con la clave secreta, Sb-Forwarded-For hace que el límite de intentos se cuente por
        usuario final y no por la IP del servidor.
        """
        respuesta = self._pedir(
            "POST",
            "/token",
            cabeceras={"Sb-Forwarded-For": ip} if ip else None,
            params={"grant_type": "password"},
            json={"email": correo, "password": clave},
        )
        if respuesta.status_code == 400 and self._codigo(respuesta) == "invalid_credentials":
            return False
        self._comprobar(respuesta, "verificar contraseña")
        token = respuesta.json().get("access_token")
        if token:
            try:
                self._pedir(
                    "POST",
                    "/logout",
                    cabeceras={"Authorization": f"Bearer {token}"},
                    params={"scope": "local"},
                )
            except ErrorAuthAdmin:
                log.warning("No se pudo cerrar la sesión de verificación")
        return True


def crear_auth_admin(settings: Settings) -> ClienteAuthAdmin | None:
    if settings.supabase_secret_key is None:
        return None
    return ClienteAuthAdmin(settings.supabase_url, settings.supabase_secret_key.get_secret_value())


def obtener_auth_admin(request: Request) -> ClienteAuthAdmin:
    """Dependencia de FastAPI; las pruebas la reemplazan por un cliente simulado."""
    cliente = request.app.state.auth_admin
    if cliente is None:
        log.error("Falta SUPABASE_SECRET_KEY: no se pueden administrar cuentas")
        raise error_api(
            503, "autenticacion_no_disponible", "La administración de cuentas no está disponible."
        )
    return cliente

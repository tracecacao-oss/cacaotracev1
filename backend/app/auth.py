"""Verificación del JWT que emite Supabase Auth y obtención del usuario actual.

La firma se verifica con las claves públicas del proyecto (JWKS, caché de 10 minutos).
Si el proyecto aún firma con secreto compartido HS256, se usa SUPABASE_JWT_SECRET.
Roles y cooperativa no salen del token: los define la Parte 2 en tablas propias.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

log = logging.getLogger(__name__)

AUDIENCIA = "authenticated"
ALGORITMOS_ASIMETRICOS = ("ES256", "RS256")
TTL_JWKS = 600
# Ante un kid desconocido se recargan las claves, pero no más de una vez por este intervalo.
ESPERA_RECARGA_KID = 30


class TokenInvalido(Exception):
    pass


class AutenticacionNoDisponible(Exception):
    """No se pudieron obtener las claves públicas del proyecto."""


@dataclass(frozen=True)
class UsuarioToken:
    id: str
    email: str | None


class VerificadorJWT:
    def __init__(
        self,
        supabase_url: str,
        jwt_secret: str | None = None,
        http: httpx.Client | None = None,
        ttl: int = TTL_JWKS,
    ) -> None:
        self._url_jwks = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        self._secreto = jwt_secret or None
        self._http = http or httpx.Client(timeout=10)
        self._ttl = ttl
        self._claves: dict[str, jwt.PyJWK] = {}
        self._cargado_en = 0.0
        self._candado = threading.Lock()

    def verificar(self, token: str) -> dict:
        try:
            cabecera = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenInvalido("Token mal formado") from exc

        alg = cabecera.get("alg")
        if alg == "HS256":
            if not self._secreto:
                raise TokenInvalido("El proyecto no firma con HS256")
            clave = self._secreto
        elif alg in ALGORITMOS_ASIMETRICOS:
            clave = self._clave_publica(cabecera.get("kid"), alg)
        else:
            raise TokenInvalido("Algoritmo no permitido")

        try:
            return jwt.decode(
                token,
                clave,
                algorithms=[alg],
                audience=AUDIENCIA,
                options={"require": ["exp", "sub", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenInvalido(str(exc)) from exc

    def _clave_publica(self, kid: str | None, alg: str):
        if not kid:
            raise TokenInvalido("Token sin kid")
        with self._candado:
            ahora = time.monotonic()
            vencido = ahora - self._cargado_en >= self._ttl
            desconocido = kid not in self._claves and ahora - self._cargado_en > ESPERA_RECARGA_KID
            if vencido or desconocido:
                self._recargar(ahora)
            jwk = self._claves.get(kid)
        if jwk is None or jwk.algorithm_name != alg:
            raise TokenInvalido("Clave de firma desconocida")
        return jwk.key

    def _recargar(self, ahora: float) -> None:
        try:
            respuesta = self._http.get(self._url_jwks)
            respuesta.raise_for_status()
            datos = respuesta.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.error("No se pudo leer el JWKS de Supabase: %s", type(exc).__name__)
            if self._claves:
                return  # se siguen usando las claves en caché
            raise AutenticacionNoDisponible from exc

        claves: dict[str, jwt.PyJWK] = {}
        for jwk in datos.get("keys", []):
            try:
                pyjwk = jwt.PyJWK.from_dict(jwk)
            except jwt.PyJWTError:
                continue
            if pyjwk.key_id and pyjwk.algorithm_name in ALGORITMOS_ASIMETRICOS:
                claves[pyjwk.key_id] = pyjwk
        self._claves = claves
        self._cargado_en = ahora


esquema_bearer = HTTPBearer(auto_error=False)


def _no_autorizado(mensaje: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"codigo": "no_autenticado", "mensaje": mensaje},
        headers={"WWW-Authenticate": "Bearer"},
    )


def obtener_verificador(request: Request) -> VerificadorJWT:
    return request.app.state.verificador


def usuario_actual(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
    verificador: Annotated[VerificadorJWT, Depends(obtener_verificador)],
) -> UsuarioToken:
    if credenciales is None:
        raise _no_autorizado("Inicia sesión para continuar.")
    try:
        claims = verificador.verificar(credenciales.credentials)
    except TokenInvalido as exc:
        raise _no_autorizado("La sesión no es válida o venció. Vuelve a iniciar sesión.") from exc
    except AutenticacionNoDisponible as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "codigo": "autenticacion_no_disponible",
                "mensaje": "No se pudo verificar la sesión. Intenta de nuevo en unos minutos.",
            },
        ) from exc
    return UsuarioToken(id=claims["sub"], email=claims.get("email"))

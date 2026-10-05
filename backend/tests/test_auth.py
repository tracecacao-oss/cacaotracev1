import time

import httpx
import jwt
import pytest

from app.auth import (
    AutenticacionNoDisponible,
    TokenInvalido,
    UsuarioToken,
    VerificadorJWT,
    usuario_actual,
)
from tests import factorias
from tests.conftest import ParDeClaves


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Endpoint /me ---


def test_me_sin_token_responde_401(cliente):
    respuesta = cliente.get("/me")
    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "no_autenticado"
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_me_con_token_valido(api, sesion, claves):
    # Token real firmado con el par de claves de la prueba: el verificador no se simula.
    api.app.dependency_overrides.pop(usuario_actual, None)
    coop = factorias.cooperativa(sesion)
    perfil = factorias.perfil(sesion, "operador", coop, correo="ana@prueba.test")
    token = claves.firmar(sub=str(perfil.id), email="ana@prueba.test")
    respuesta = api.get("/me", headers=_bearer(token))
    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == str(perfil.id)
    assert respuesta.json()["correo"] == "ana@prueba.test"


def test_me_con_token_valido_sin_perfil_responde_403(cliente, claves, base_disponible):
    respuesta = cliente.get("/me", headers=_bearer(claves.firmar()))
    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["codigo"] == "sin_perfil"


def test_me_con_token_vencido_responde_401(cliente, claves):
    ahora = int(time.time())
    token = claves.firmar(iat=ahora - 7200, exp=ahora - 3600)
    assert cliente.get("/me", headers=_bearer(token)).status_code == 401


def test_me_con_firma_alterada_responde_401(cliente, claves):
    cabecera, cuerpo, firma = claves.firmar().split(".")
    otro_cuerpo = ParDeClaves().firmar(email="intruso@ejemplo.pe").split(".")[1]
    assert cliente.get("/me", headers=_bearer(f"{cabecera}.{otro_cuerpo}.{firma}")).status_code == 401


def test_me_con_token_de_otra_clave_responde_401(cliente):
    intruso = ParDeClaves()  # mismo kid, distinta clave privada
    assert cliente.get("/me", headers=_bearer(intruso.firmar())).status_code == 401


def test_me_con_usuario_simulado(api, sesion):
    coop = factorias.cooperativa(sesion)
    perfil = factorias.perfil(sesion, "lector", coop)
    api.app.dependency_overrides[usuario_actual] = lambda: UsuarioToken(
        id=str(perfil.id), email=perfil.correo
    )
    respuesta = api.get("/me")
    assert respuesta.status_code == 200
    assert respuesta.json()["rol"] == "lector"


def test_me_con_cabecera_que_no_es_bearer_responde_401(cliente):
    assert cliente.get("/me", headers={"Authorization": "Basic dXN1YXJpbzpjbGF2ZQ=="}).status_code == 401


# --- Verificador ---


def test_rechaza_audiencia_distinta(verificador, claves):
    with pytest.raises(TokenInvalido):
        verificador.verificar(claves.firmar(aud="anon"))


def test_rechaza_token_sin_sub(verificador, claves):
    token = jwt.encode(
        {"aud": "authenticated", "exp": int(time.time()) + 60},
        claves.privada,
        algorithm="ES256",
        headers={"kid": claves.kid},
    )
    with pytest.raises(TokenInvalido):
        verificador.verificar(token)


def test_rechaza_algoritmo_none(verificador):
    token = jwt.encode(
        {"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 60}, None, algorithm="none"
    )
    with pytest.raises(TokenInvalido):
        verificador.verificar(token)


def test_rechaza_hs256_si_no_hay_secreto(verificador):
    token = jwt.encode(
        {"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 60},
        "un-secreto-cualquiera-de-al-menos-32-bytes",
        algorithm="HS256",
    )
    with pytest.raises(TokenInvalido):
        verificador.verificar(token)


def test_acepta_hs256_con_secreto_configurado():
    secreto = "secreto-compartido-de-prueba-con-32-bytes-o-mas"
    verificador = VerificadorJWT("https://proyecto-prueba.supabase.co", jwt_secret=secreto)
    token = jwt.encode(
        {"sub": "abc", "email": "a@b.pe", "aud": "authenticated", "exp": int(time.time()) + 60},
        secreto,
        algorithm="HS256",
    )
    assert verificador.verificar(token)["sub"] == "abc"


def test_rechaza_kid_desconocido(verificador):
    with pytest.raises(TokenInvalido):
        verificador.verificar(ParDeClaves(kid="otra").firmar())


def test_jwks_queda_en_cache(verificador, claves, llamadas_jwks):
    for _ in range(3):
        verificador.verificar(claves.firmar())
    assert len(llamadas_jwks) == 1


def test_jwks_se_recarga_al_vencer_la_cache(claves):
    llamadas = []

    def responder(peticion):
        llamadas.append(peticion)
        return httpx.Response(200, json={"keys": [claves.jwk_publica]})

    verificador = VerificadorJWT(
        "https://proyecto-prueba.supabase.co",
        http=httpx.Client(transport=httpx.MockTransport(responder)),
        ttl=0,
    )
    verificador.verificar(claves.firmar())
    verificador.verificar(claves.firmar())
    assert len(llamadas) == 2


def test_jwks_inaccesible_sin_cache(claves):
    def fallar(peticion):
        raise httpx.ConnectError("sin red", request=peticion)

    verificador = VerificadorJWT(
        "https://proyecto-prueba.supabase.co", http=httpx.Client(transport=httpx.MockTransport(fallar))
    )
    with pytest.raises(AutenticacionNoDisponible):
        verificador.verificar(claves.firmar())


def test_me_responde_503_si_no_hay_claves(claves):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import crear_app

    def fallar(peticion):
        raise httpx.ConnectError("sin red", request=peticion)

    verificador = VerificadorJWT(
        "https://proyecto-prueba.supabase.co", http=httpx.Client(transport=httpx.MockTransport(fallar))
    )
    with TestClient(crear_app(get_settings(), verificador=verificador)) as c:
        respuesta = c.get("/me", headers=_bearer(claves.firmar()))
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["codigo"] == "autenticacion_no_disponible"

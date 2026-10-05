"""Configuración común de las pruebas.

Las pruebas nunca tocan Supabase ni salen a internet: las variables se fijan aquí, antes de
importar la app, y la base es el Postgres local de Docker (o el servicio de CI).
"""

import os

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/cacaotrace"
)
os.environ["SUPABASE_URL"] = "https://proyecto-prueba.supabase.co"
os.environ["SUPABASE_SECRET_KEY"] = "sb_secret_prueba"
os.environ["CORS_ORIGINS"] = "https://cacaotrace.pages.dev,http://localhost:5500"
os.environ["GIT_SHA"] = "abc1234"
os.environ.pop("SUPABASE_JWT_SECRET", None)
os.environ.pop("RENDER_GIT_COMMIT", None)

import time  # noqa: E402
import uuid  # noqa: E402

import httpx  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.auth import VerificadorJWT  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import crear_app  # noqa: E402

KID = "clave-prueba"
URL_JWKS = "https://proyecto-prueba.supabase.co/auth/v1/.well-known/jwks.json"


class ParDeClaves:
    """Par de claves ES256 generado en la propia prueba, como las claves asimétricas de Supabase."""

    def __init__(self, kid: str = KID):
        self.kid = kid
        self.privada = ec.generate_private_key(ec.SECP256R1())
        jwk = jwt.algorithms.ECAlgorithm.to_jwk(self.privada.public_key(), as_dict=True)
        self.jwk_publica = jwk | {"kid": kid, "alg": "ES256", "use": "sig"}

    def firmar(self, **cambios) -> str:
        ahora = int(time.time())
        claims = {
            "sub": str(uuid.uuid4()),
            "email": "prueba@cacaotrace.pe",
            "aud": "authenticated",
            "role": "authenticated",
            "iat": ahora,
            "exp": ahora + 3600,
        } | cambios
        return jwt.encode(claims, self.privada, algorithm="ES256", headers={"kid": self.kid})


@pytest.fixture
def claves() -> ParDeClaves:
    return ParDeClaves()


@pytest.fixture
def llamadas_jwks() -> list:
    return []


@pytest.fixture
def verificador(claves, llamadas_jwks) -> VerificadorJWT:
    def responder(peticion: httpx.Request) -> httpx.Response:
        assert str(peticion.url) == URL_JWKS
        llamadas_jwks.append(peticion)
        return httpx.Response(200, json={"keys": [claves.jwk_publica]})

    http = httpx.Client(transport=httpx.MockTransport(responder))
    return VerificadorJWT("https://proyecto-prueba.supabase.co", http=http)


@pytest.fixture
def cliente(verificador) -> TestClient:
    app = crear_app(get_settings(), verificador=verificador)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def base_disponible() -> None:
    """Exige Postgres. En local se salta si Docker no está arriba; en CI falla."""
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
    except OperationalError:
        if os.environ.get("CI"):
            raise
        pytest.skip("Postgres local no disponible: levántalo con `docker compose up -d`")

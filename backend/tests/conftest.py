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
from sqlalchemy.orm import Session  # noqa: E402

from app.auth import UsuarioToken, VerificadorJWT, usuario_actual  # noqa: E402
from app.auth_admin import ClienteAuthAdmin, CorreoEnUso, ErrorAuthAdmin  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.contexto import CABECERA_COOPERATIVA  # noqa: E402
from app.db import engine, obtener_sesion  # noqa: E402
from app.main import crear_app  # noqa: E402
from app.storage import ClienteStorage  # noqa: E402

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


class AuthFalso(ClienteAuthAdmin):
    """Supabase Auth simulado: las pruebas nunca llaman a la API de administración real."""

    def __init__(self):
        self.usuarios: dict[uuid.UUID, dict] = {}
        self.llamadas: list[tuple] = []
        self.caido = False

    def _registrar(self, *llamada):
        if self.caido:
            raise ErrorAuthAdmin("Supabase Auth simulado no responde")
        self.llamadas.append(llamada)

    def correo_de(self, usuario_id) -> str:
        return self.usuarios[usuario_id]["correo"]

    def crear_usuario(self, correo, clave):
        self._registrar("crear", correo)
        if any(u["correo"] == correo for u in self.usuarios.values()):
            raise CorreoEnUso(correo)
        usuario_id = uuid.uuid4()
        self.usuarios[usuario_id] = {"correo": correo, "clave": clave, "bloqueado": False}
        return usuario_id

    def borrar_usuario(self, usuario_id):
        self._registrar("borrar", usuario_id)
        self.usuarios.pop(usuario_id, None)

    def cambiar_clave(self, usuario_id, clave):
        self._registrar("cambiar_clave", usuario_id)
        self.usuarios.setdefault(usuario_id, {"correo": None, "bloqueado": False})["clave"] = clave

    def cambiar_correo(self, usuario_id, correo):
        self._registrar("cambiar_correo", usuario_id, correo)
        self.usuarios[usuario_id]["correo"] = correo

    def bloquear(self, usuario_id):
        self._registrar("bloquear", usuario_id)
        self.usuarios.setdefault(usuario_id, {"correo": None})["bloqueado"] = True

    def desbloquear(self, usuario_id):
        self._registrar("desbloquear", usuario_id)
        self.usuarios.setdefault(usuario_id, {"correo": None})["bloqueado"] = False

    def verificar_clave(self, correo, clave, ip=None):
        self._registrar("verificar_clave", correo)
        return any(u["correo"] == correo and u.get("clave") == clave for u in self.usuarios.values())


@pytest.fixture
def auth_falso() -> AuthFalso:
    return AuthFalso()


class StorageFalso(ClienteStorage):
    """Supabase Storage simulado: guarda los archivos en memoria."""

    def __init__(self):
        self.archivos: dict[str, bytes] = {}
        self.borrados: list[str] = []
        self.bucket = "documentos"

    def subir(self, ruta, contenido, tipo_mime):
        self.archivos[ruta] = contenido

    def url_firmada(self, ruta, segundos=300):
        return f"https://storage.prueba/firmada/{ruta}?vence={segundos}"

    def borrar(self, ruta):
        self.borrados.append(ruta)
        self.archivos.pop(ruta, None)


@pytest.fixture
def storage_falso() -> StorageFalso:
    return StorageFalso()


@pytest.fixture
def cliente(verificador, auth_falso, storage_falso) -> TestClient:
    app = crear_app(get_settings(), verificador=verificador, auth_admin=auth_falso, storage=storage_falso)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def base_disponible() -> None:
    """Exige Postgres. En local se salta si no está arriba; en CI falla."""
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
    except OperationalError:
        if os.environ.get("CI"):
            raise
        pytest.skip("Postgres local no disponible: levántalo con `docker compose up -d`")


@pytest.fixture
def sesion(base_disponible) -> Session:
    """Sesión dentro de una transacción que se revierte al final: cada prueba parte de cero."""
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield sesion
    sesion.close()
    transaccion.rollback()
    conexion.close()


class ClienteAPI(TestClient):
    """Cliente de prueba con usuario simulado por sobreescritura de dependencias."""

    def como(self, perfil, cooperativa_id=None) -> "ClienteAPI":
        token = UsuarioToken(id=str(perfil.id), email=perfil.correo)
        self.app.dependency_overrides[usuario_actual] = lambda: token
        self.headers.pop(CABECERA_COOPERATIVA, None)
        if cooperativa_id is not None:
            self.headers[CABECERA_COOPERATIVA] = str(cooperativa_id)
        return self


@pytest.fixture
def api(sesion, verificador, auth_falso, storage_falso) -> ClienteAPI:
    app = crear_app(get_settings(), verificador=verificador, auth_admin=auth_falso, storage=storage_falso)
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    with ClienteAPI(app, raise_server_exceptions=False) as c:
        yield c

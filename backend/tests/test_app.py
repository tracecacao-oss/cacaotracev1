import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.main import crear_app


def _preflight(cliente, origen):
    return cliente.options(
        "/me",
        headers={
            "Origin": origen,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )


def test_cors_permite_origen_configurado(cliente):
    respuesta = _preflight(cliente, "https://cacaotrace.pages.dev")
    assert respuesta.headers.get("access-control-allow-origin") == "https://cacaotrace.pages.dev"


def test_cors_no_permite_origen_ajeno(cliente):
    respuesta = _preflight(cliente, "https://sitio-ajeno.com")
    assert "access-control-allow-origin" not in respuesta.headers

    respuesta = cliente.get("/health", headers={"Origin": "https://sitio-ajeno.com"})
    assert "access-control-allow-origin" not in respuesta.headers


def test_cors_rechaza_comodin():
    with pytest.raises(ValidationError):
        Settings(cors_origins="*", database_url="postgresql://x", supabase_url="https://x.supabase.co")


def test_database_url_usa_psycopg3():
    settings = Settings(
        database_url="postgresql://u:c@host:5432/postgres", supabase_url="https://x.supabase.co"
    )
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_secretos_vacios_cuentan_como_no_definidos():
    settings = Settings(
        database_url="postgresql://x",
        supabase_url="https://x.supabase.co",
        supabase_secret_key="",
        supabase_jwt_secret="",
    )
    assert settings.supabase_secret_key is None
    assert settings.supabase_jwt_secret is None


def test_git_sha_desde_render(monkeypatch):
    monkeypatch.delenv("GIT_SHA")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "def5678")
    assert Settings().git_sha == "def5678"


def test_docs_desactivadas_en_produccion():
    settings = get_settings().model_copy(update={"environment": "production"})
    with TestClient(crear_app(settings)) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404


def test_docs_activas_en_desarrollo(cliente):
    assert cliente.get("/docs").status_code == 200


def test_errores_con_formato_comun(cliente):
    respuesta = cliente.get("/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.json() == {"error": {"codigo": "no_encontrado", "mensaje": "No encontrado."}}


def test_error_inesperado_no_muestra_detalle_en_produccion():
    settings = get_settings().model_copy(update={"environment": "production"})
    app = crear_app(settings)

    @app.get("/explota")
    def explota():
        raise RuntimeError("clave=secreta")

    with TestClient(app, raise_server_exceptions=False) as c:
        respuesta = c.get("/explota")
    assert respuesta.status_code == 500
    assert respuesta.json() == {
        "error": {"codigo": "error_interno", "mensaje": "Ocurrió un error inesperado. Intenta de nuevo."}
    }

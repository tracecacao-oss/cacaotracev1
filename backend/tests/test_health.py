from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import obtener_sesion


def test_health_responde_estado_y_version(cliente):
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok", "version": "abc1234"}


def test_health_db_con_base_disponible(cliente, base_disponible):
    respuesta = cliente.get("/health/db")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["postgis"]


def test_health_db_con_base_caida(cliente):
    # Un puerto donde nada escucha: la conexión se rechaza al instante, sin salir a internet.
    engine_caido = create_engine(
        "postgresql+psycopg://nadie:nada@127.0.0.1:1/ninguna", connect_args={"connect_timeout": 2}
    )
    Sesion = sessionmaker(bind=engine_caido)

    def sesion_caida():
        with Sesion() as sesion:
            yield sesion

    cliente.app.dependency_overrides[obtener_sesion] = sesion_caida
    respuesta = cliente.get("/health/db")
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["codigo"] == "base_no_disponible"
    assert "nadie" not in respuesta.text  # no se filtran datos de conexión

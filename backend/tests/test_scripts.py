"""Scripts de operación, con Supabase Auth simulado y la base de prueba."""

import importlib.util
from pathlib import Path

import pytest

from app.models import Auditoria, Perfil

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "crear_superadmin.py"


@pytest.fixture
def script(sesion, auth_falso, monkeypatch):
    spec = importlib.util.spec_from_file_location("crear_superadmin", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    class SesionDePrueba:
        def __enter__(self):
            return sesion

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(modulo, "SesionLocal", SesionDePrueba)
    monkeypatch.setattr(modulo, "crear_auth_admin", lambda settings: auth_falso)
    return modulo


def test_crear_superadmin(script, sesion, auth_falso, capsys, monkeypatch):
    monkeypatch.setattr(
        "sys.argv", ["x", "--correo", "Super@Prueba.test", "--nombres", "Su", "--apellidos", "Per"]
    )
    assert script.main() == 0
    perfil = sesion.query(Perfil).filter_by(correo="super@prueba.test").one()
    assert perfil.rol == "superadmin" and perfil.cooperativa_id is None and perfil.debe_cambiar_clave
    clave = auth_falso.usuarios[perfil.id]["clave"]
    assert clave in capsys.readouterr().out
    fila = sesion.query(Auditoria).filter_by(accion="usuario.crear").one()
    assert fila.usuario_id is None and fila.detalle == {"rol": "superadmin", "origen": "script"}


def test_no_duplica_y_restablece(script, sesion, auth_falso, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["x", "--correo", "s@prueba.test", "--nombres", "S", "--apellidos", "A"])
    script.main()
    assert script.main() == 1  # ya existe

    perfil = sesion.query(Perfil).filter_by(correo="s@prueba.test").one()
    anterior = auth_falso.usuarios[perfil.id]["clave"]
    perfil.debe_cambiar_clave = False
    monkeypatch.setattr("sys.argv", ["x", "--restablecer", "--correo", "s@prueba.test"])
    assert script.main() == 0
    assert auth_falso.usuarios[perfil.id]["clave"] != anterior
    assert perfil.debe_cambiar_clave is True

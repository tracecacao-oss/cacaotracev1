"""Scripts de operación, con Supabase Auth simulado y la base de prueba."""

import contextlib
import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models import Auditoria, Correlativo, Perfil
from tests import factorias

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


# --- reiniciar_datos.py ---

REINICIAR = Path(__file__).resolve().parents[1] / "scripts" / "reiniciar_datos.py"


class MotorDePrueba:
    """El script usa engine.connect() y engine.begin(); aquí ambos dan la conexión de la prueba, que se
    revierte al terminar: el TRUNCATE nunca sale de la transacción de la prueba."""

    def __init__(self, conexion):
        self.conexion = conexion

    def connect(self):
        return contextlib.nullcontext(self.conexion)

    def begin(self):
        return contextlib.nullcontext(self.conexion)


@pytest.fixture
def reiniciar(sesion, auth_falso, storage_falso, monkeypatch):
    spec = importlib.util.spec_from_file_location("reiniciar_datos", REINICIAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    monkeypatch.setattr("app.db.engine", MotorDePrueba(sesion.connection()))
    monkeypatch.setattr(modulo, "crear_storage", lambda settings: storage_falso)
    monkeypatch.setattr(modulo, "crear_auth_admin", lambda settings: auth_falso)
    return modulo


@pytest.fixture
def datos(sesion, auth_falso, storage_falso):
    """Un superadministrador, una cooperativa con su administrador, un productor con parcela, auditoría,
    un correlativo, archivos en el bucket y un usuario de Auth sin perfil."""
    superadmin = factorias.perfil(sesion, "superadmin", correo="super@prueba.test", debe_cambiar_clave=False)
    coop = factorias.cooperativa(sesion, codigo="RST")
    admin = factorias.perfil(sesion, "admin_cooperativa", coop)
    productor = factorias.productor(sesion, coop)
    sesion.add(Correlativo(cooperativa_id=coop.id, tipo="tanda", anio=2026, ultimo=7))
    sesion.add(
        Auditoria(accion="prueba.reiniciar", entidad="cooperativa", entidad_id=str(coop.id), detalle={})
    )
    sesion.flush()
    for perfil in (superadmin, admin):
        auth_falso.usuarios[perfil.id] = {"correo": perfil.correo, "clave": "x", "bloqueado": False}
    auth_falso.usuarios[uuid.uuid4()] = {"correo": "huerfano@prueba.test", "clave": "x", "bloqueado": False}
    for ruta in (f"{coop.id}/parcela/a/1.pdf", f"{coop.id}/dop/b/2.pdf", "prueba/3.png"):
        storage_falso.archivos[ruta] = b"%PDF"
    return {"superadmin": superadmin, "coop": coop, "admin": admin, "productor": productor}


def test_reiniciar_simula_y_pide_la_palabra(
    reiniciar, sesion, datos, auth_falso, storage_falso, capsys, monkeypatch
):
    monkeypatch.setattr("sys.argv", ["x", "--simular"])
    assert reiniciar.main() == 0
    salida = capsys.readouterr().out
    assert "super@prueba.test" in salida and "Archivos del bucket que se borran: 3" in salida
    assert "Usuarios de Supabase Auth que se borran: 2" in salida and "no se borró nada" in salida
    monkeypatch.setattr("sys.argv", ["x"])
    monkeypatch.setattr("builtins.input", lambda _: "vaciar")
    assert reiniciar.main() == 1
    assert sesion.get(Perfil, datos["admin"].id) is not None
    assert len(storage_falso.archivos) == 3 and len(auth_falso.usuarios) == 3


def test_reiniciar_deja_todo_vacio_y_conserva_superadmins(
    reiniciar, sesion, datos, auth_falso, storage_falso, capsys, monkeypatch
):
    conexion = sesion.connection()
    _, triggers = reiniciar.protecciones(conexion)
    monkeypatch.setattr("sys.argv", ["x"])
    monkeypatch.setattr("builtins.input", lambda _: "VACIAR")
    assert reiniciar.main() == 0, capsys.readouterr().out
    sesion.expire_all()
    conteos = reiniciar.contar(conexion)
    assert conteos["perfiles"] == 1 and sum(conteos.values()) == 1
    superadmin = sesion.get(Perfil, datos["superadmin"].id)
    assert superadmin.rol == "superadmin" and superadmin.correo == "super@prueba.test"
    assert storage_falso.archivos == {}
    assert set(auth_falso.usuarios) == {datos["superadmin"].id}
    assert reiniciar.protecciones(conexion) == (0, triggers)
    # Las protecciones siguen activas: la auditoría vuelve a ser solo de inserción.
    sesion.add(Auditoria(accion="prueba.despues", entidad="cooperativa", entidad_id="x", detalle={}))
    sesion.flush()
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(text("UPDATE auditoria SET accion = 'otra'"))
    assert "Listo. El sistema está vacío." in capsys.readouterr().out

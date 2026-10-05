"""Personal de la cooperativa, gestionado por su administrador."""

import pytest

from app.models import Auditoria
from tests import factorias


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def admin(sesion, coop):
    return factorias.perfil(sesion, "admin_cooperativa", coop)


def _codigo(respuesta):
    return respuesta.json()["error"]["codigo"]


def test_crear_operador(api, sesion, coop, admin, auth_falso):
    respuesta = api.como(admin).post(
        "/usuarios",
        json={"nombres": "Op", "apellidos": "Uno", "correo": "OP.Uno@Prueba.test", "rol": "operador"},
    )
    assert respuesta.status_code == 201
    usuario = respuesta.json()["usuario"]
    assert usuario["correo"] == "op.uno@prueba.test"
    assert usuario["rol"] == "operador"
    assert usuario["debe_cambiar_clave"] is True
    assert ("crear", "op.uno@prueba.test") in auth_falso.llamadas


def test_solo_roles_de_personal(api, admin):
    for rol in ("superadmin", "productor"):
        respuesta = api.como(admin).post(
            "/usuarios", json={"nombres": "X", "apellidos": "Y", "correo": "x@prueba.test", "rol": rol}
        )
        assert respuesta.status_code == 422


def test_correo_ya_usado(api, sesion, coop, admin):
    otra = factorias.cooperativa(sesion)
    factorias.perfil(sesion, "lector", otra, correo="repetido@prueba.test")
    respuesta = api.como(admin).post(
        "/usuarios",
        json={"nombres": "X", "apellidos": "Y", "correo": "repetido@prueba.test", "rol": "lector"},
    )
    assert respuesta.status_code == 409
    assert _codigo(respuesta) == "correo_en_uso"


def test_correo_ya_usado_en_supabase_auth(api, admin, auth_falso):
    auth_falso.crear_usuario("solo.en.auth@prueba.test", "x")
    respuesta = api.como(admin).post(
        "/usuarios",
        json={"nombres": "X", "apellidos": "Y", "correo": "solo.en.auth@prueba.test", "rol": "lector"},
    )
    assert respuesta.status_code == 409
    assert _codigo(respuesta) == "correo_en_uso"


def test_operador_no_crea_usuarios(api, sesion, coop):
    operador = factorias.perfil(sesion, "operador", coop)
    respuesta = api.como(operador).post(
        "/usuarios", json={"nombres": "X", "apellidos": "Y", "correo": "x@prueba.test", "rol": "lector"}
    )
    assert respuesta.status_code == 403


def test_listar_solo_personal_de_la_cooperativa(api, sesion, coop, admin):
    factorias.perfil(sesion, "operador", coop, nombres="Busca", apellidos="Me")
    factorias.productor_con_acceso(sesion, coop)
    factorias.perfil(sesion, "operador", factorias.cooperativa(sesion))
    datos = api.como(admin).get("/usuarios").json()
    assert datos["total"] == 2
    assert {u["rol"] for u in datos["items"]} == {"admin_cooperativa", "operador"}
    assert api.get("/usuarios", params={"q": "busca"}).json()["total"] == 1


def test_cambiar_rol_y_nombres(api, sesion, coop, admin):
    lector = factorias.perfil(sesion, "lector", coop)
    respuesta = api.como(admin).patch(f"/usuarios/{lector.id}", json={"rol": "operador", "nombres": "Nuevo"})
    assert respuesta.status_code == 200
    assert respuesta.json()["rol"] == "operador"
    fila = sesion.query(Auditoria).filter_by(accion="usuario.editar").one()
    assert fila.detalle["rol"] == {"antes": "lector", "despues": "operador"}


def test_desactivar_y_reactivar(api, sesion, coop, admin, auth_falso):
    operador = factorias.perfil(sesion, "operador", coop)
    api.como(admin).patch(f"/usuarios/{operador.id}", json={"activo": False})
    assert operador.activo is False
    assert ("bloquear", operador.id) in auth_falso.llamadas
    assert api.como(operador).get("/me").json()["error"]["codigo"] == "cuenta_desactivada"

    api.como(admin).patch(f"/usuarios/{operador.id}", json={"activo": True})
    assert operador.activo is True
    assert ("desbloquear", operador.id) in auth_falso.llamadas
    acciones = [a.accion for a in sesion.query(Auditoria).order_by(Auditoria.id)]
    assert acciones == ["usuario.desactivar", "usuario.reactivar"]


def test_no_puede_desactivarse_ni_cambiarse_el_rol(api, sesion, coop, admin):
    factorias.perfil(sesion, "admin_cooperativa", coop)  # hay otro admin: no es la regla del último
    api.como(admin)
    for cambio in ({"activo": False}, {"rol": "lector"}):
        respuesta = api.patch(f"/usuarios/{admin.id}", json=cambio)
        assert respuesta.status_code == 400
        assert _codigo(respuesta) == "accion_sobre_si_mismo"


def test_un_admin_desactiva_a_otro(api, sesion, coop, admin):
    otro = factorias.perfil(sesion, "admin_cooperativa", coop)
    assert api.como(admin).patch(f"/usuarios/{otro.id}", json={"activo": False}).status_code == 200


def test_desactivar_al_ultimo_administrador_activo(api, sesion, coop, admin):
    factorias.perfil(sesion, "admin_cooperativa", coop, activo=False)  # inactivo: no cuenta
    api.como(admin)
    for cambio in ({"activo": False}, {"rol": "operador"}):
        respuesta = api.patch(f"/usuarios/{admin.id}", json=cambio)
        assert respuesta.status_code == 400
        assert _codigo(respuesta) == "ultimo_administrador"
    assert admin.activo is True
    assert admin.rol == "admin_cooperativa"


def test_restablecer_clave_de_personal(api, sesion, coop, admin, auth_falso):
    lector = factorias.perfil(sesion, "lector", coop)
    respuesta = api.como(admin).post(f"/usuarios/{lector.id}/restablecer-clave")
    assert respuesta.status_code == 200
    clave = respuesta.json()["clave_temporal"]
    assert auth_falso.usuarios[lector.id]["clave"] == clave
    assert lector.debe_cambiar_clave is True
    fila = sesion.query(Auditoria).filter_by(accion="usuario.restablecer_clave").one()
    assert clave not in str(fila.detalle)


def test_admin_restablece_a_otro_admin(api, sesion, coop, admin):
    otro = factorias.perfil(sesion, "admin_cooperativa", coop)
    assert api.como(admin).post(f"/usuarios/{otro.id}/restablecer-clave").status_code == 200


def test_productores_no_se_gestionan_como_personal(api, sesion, coop, admin):
    _, cuenta = factorias.productor_con_acceso(sesion, coop)
    assert api.como(admin).patch(f"/usuarios/{cuenta.id}", json={"nombres": "X"}).status_code == 404

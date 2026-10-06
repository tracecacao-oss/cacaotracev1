"""Plataforma: cooperativas y administradores, gestionados por el superadmin."""

import pytest

from app.models import Auditoria, Cooperativa, Perfil
from app.services import cuentas
from tests import factorias


def _nueva(ruc="20999999901", correo="admin.nueva@prueba.test", **cambios):
    return {
        "razon_social": "Coop Nueva Prueba",
        "codigo": "CNP",
        "tipo_organizacion": "cooperativa_agraria",
        "ruc": ruc,
        "departamento": "SAN MARTIN",
        "provincia": "PICOTA",
        "distrito": "PICOTA",
        "administrador": {"nombres": "Admin", "apellidos": "Prueba", "correo": correo},
        **cambios,
    }


@pytest.fixture
def superadmin(sesion):
    return factorias.perfil(sesion, "superadmin")


def test_crea_cooperativa_con_su_primer_administrador(api, sesion, superadmin, auth_falso):
    respuesta = api.como(superadmin).post("/admin/cooperativas", json=_nueva())
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["cooperativa"]["estado"] == "activa"
    assert datos["cooperativa"]["es_demo"] is False
    assert datos["cooperativa"]["usuarios"] == 1
    assert datos["administrador"]["rol"] == "admin_cooperativa"
    assert datos["administrador"]["debe_cambiar_clave"] is True

    clave = datos["clave_temporal"]
    assert len(clave) == 10
    assert not set(clave) & set("0O1lI")
    usuario_auth = auth_falso.usuarios[next(iter(auth_falso.usuarios))]
    assert usuario_auth == {"correo": "admin.nueva@prueba.test", "clave": clave, "bloqueado": False}

    acciones = [a.accion for a in sesion.query(Auditoria).order_by(Auditoria.id)]
    assert acciones == ["cooperativa.crear", "usuario.crear"]
    assert clave not in str([a.detalle for a in sesion.query(Auditoria)])


def test_ruc_duplicado(api, sesion, superadmin):
    factorias.cooperativa(sesion, ruc="20999999901")
    respuesta = api.como(superadmin).post("/admin/cooperativas", json=_nueva())
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "ruc_en_uso"


def test_ruc_mal_formado(api, superadmin):
    assert api.como(superadmin).post("/admin/cooperativas", json=_nueva(ruc="2099")).status_code == 422


def test_correo_del_administrador_en_uso_no_crea_la_cooperativa(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    factorias.perfil(sesion, "operador", coop, correo="admin.nueva@prueba.test")
    respuesta = api.como(superadmin).post("/admin/cooperativas", json=_nueva())
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "correo_en_uso"
    assert sesion.query(Cooperativa).filter_by(ruc="20999999901").count() == 0


def test_si_falla_el_perfil_se_borra_el_usuario_de_auth(api, sesion, superadmin, auth_falso, monkeypatch):
    def fallar(*args, **kwargs):
        raise RuntimeError("falla simulada al guardar el perfil")

    monkeypatch.setattr(cuentas, "registrar_auditoria", fallar)
    respuesta = api.como(superadmin).post("/admin/cooperativas", json=_nueva())
    assert respuesta.status_code == 500
    assert auth_falso.usuarios == {}
    assert [llamada[0] for llamada in auth_falso.llamadas] == ["crear", "borrar"]
    assert sesion.query(Cooperativa).filter_by(ruc="20999999901").count() == 0


def test_auth_caido_no_deja_cooperativa_a_medias(api, sesion, superadmin, auth_falso):
    auth_falso.caido = True
    respuesta = api.como(superadmin).post("/admin/cooperativas", json=_nueva())
    assert respuesta.status_code == 503
    assert sesion.query(Cooperativa).filter_by(ruc="20999999901").count() == 0


def test_cooperativa_demo(api, superadmin):
    respuesta = api.como(superadmin).post("/admin/cooperativas", json=_nueva(es_demo=True))
    assert respuesta.json()["cooperativa"]["es_demo"] is True


def test_listar_y_detalle(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    factorias.perfil(sesion, "admin_cooperativa", coop)
    factorias.productor(sesion, coop)
    api.como(superadmin)
    listado = api.get("/admin/cooperativas").json()
    assert listado["total"] == 1
    assert listado["items"][0]["usuarios"] == 1
    assert listado["items"][0]["productores"] == 1
    assert api.get(f"/admin/cooperativas/{coop.id}").json()["ruc"] == coop.ruc


def test_suspender_y_reactivar(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    operador = factorias.perfil(sesion, "operador", coop)

    api.como(superadmin).patch(f"/admin/cooperativas/{coop.id}", json={"estado": "suspendida"})
    assert api.como(operador).get("/productores").json()["error"]["codigo"] == "cooperativa_suspendida"

    api.como(superadmin).patch(f"/admin/cooperativas/{coop.id}", json={"estado": "activa"})
    assert api.como(operador).get("/productores").status_code == 200

    acciones = [a.accion for a in sesion.query(Auditoria).order_by(Auditoria.id)]
    assert acciones == ["cooperativa.suspender", "cooperativa.reactivar"]


def test_editar_guarda_antes_y_despues(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    anterior = coop.razon_social
    respuesta = api.como(superadmin).patch(
        f"/admin/cooperativas/{coop.id}", json={"razon_social": "Coop Renombrada"}
    )
    assert respuesta.json()["razon_social"] == "Coop Renombrada"
    fila = sesion.query(Auditoria).filter_by(accion="cooperativa.editar").one()
    assert fila.detalle == {"razon_social": {"antes": anterior, "despues": "Coop Renombrada"}}


def test_es_demo_no_se_puede_cambiar(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    respuesta = api.como(superadmin).patch(f"/admin/cooperativas/{coop.id}", json={"es_demo": True})
    assert respuesta.status_code == 422


def test_otro_administrador(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    respuesta = api.como(superadmin).post(
        f"/admin/cooperativas/{coop.id}/administradores",
        json={"nombres": "Otra", "apellidos": "Admin", "correo": "otra.admin@prueba.test"},
    )
    assert respuesta.status_code == 201
    perfil = sesion.get(Perfil, respuesta.json()["usuario"]["id"])
    assert perfil.cooperativa_id == coop.id
    assert perfil.creado_por == superadmin.id


def test_restablecer_clave_de_administrador(api, sesion, superadmin, auth_falso):
    coop = factorias.cooperativa(sesion)
    admin = factorias.perfil(sesion, "admin_cooperativa", coop)
    respuesta = api.como(superadmin).post(f"/admin/usuarios/{admin.id}/restablecer-clave")
    assert respuesta.status_code == 200
    assert auth_falso.usuarios[admin.id]["clave"] == respuesta.json()["clave_temporal"]
    assert admin.debe_cambiar_clave is True


def test_restablecer_desde_plataforma_solo_administradores(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    operador = factorias.perfil(sesion, "operador", coop)
    respuesta = api.como(superadmin).post(f"/admin/usuarios/{operador.id}/restablecer-clave")
    assert respuesta.status_code == 400


# --- Modo consulta del superadmin ---


def test_superadmin_consulta_una_cooperativa_en_solo_lectura(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    factorias.productor(sesion, coop)
    respuesta = api.como(superadmin, cooperativa_id=coop.id).get("/productores")
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1


def test_superadmin_sin_cooperativa_elegida(api, superadmin):
    respuesta = api.como(superadmin).get("/productores")
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "cooperativa_requerida"


def test_superadmin_no_escribe_datos_de_negocio(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    respuesta = api.como(superadmin, cooperativa_id=coop.id).post(
        "/productores",
        json={"dni": "90000001", "nombres": "Demo", "apellidos": "Uno", "direccion_postal": "Caserío Demo"},
    )
    assert respuesta.status_code == 403


def test_consulta_del_superadmin_se_audita_una_vez_por_ventana(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    api.como(superadmin, cooperativa_id=coop.id)
    api.get("/productores")
    api.get("/usuarios")
    filas = sesion.query(Auditoria).filter_by(accion="superadmin.consultar_cooperativa").all()
    assert len(filas) == 1
    assert filas[0].cooperativa_id == coop.id


def test_cabecera_de_cooperativa_inexistente(api, superadmin):
    respuesta = api.como(superadmin, cooperativa_id="00000000-0000-4000-8000-000000000000").get(
        "/productores"
    )
    assert respuesta.status_code == 404


def test_tipo_de_organizacion(api, sesion, superadmin):
    """Adenda 3 de la Parte 5: obligatorio al crear; el superadmin lo corrige después."""
    api.como(superadmin)
    sin_tipo = {k: v for k, v in _nueva().items() if k != "tipo_organizacion"}
    assert api.post("/admin/cooperativas", json=sin_tipo).status_code == 422
    creada = api.post("/admin/cooperativas", json=_nueva(tipo_organizacion="asociacion")).json()[
        "cooperativa"
    ]
    assert creada["tipo_organizacion"] == "asociacion"
    cambio = api.patch(f"/admin/cooperativas/{creada['id']}", json={"tipo_organizacion": "empresa"})
    assert cambio.json()["tipo_organizacion"] == "empresa"
    assert (
        api.patch(f"/admin/cooperativas/{creada['id']}", json={"tipo_organizacion": "otra"}).status_code
        == 422
    )

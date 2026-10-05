"""Productores, versión mínima: padrón, afiliación y acceso con DNI."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Afiliacion, Auditoria, Perfil, Productor
from tests import factorias


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


def _nuevo(dni="90000001", **cambios):
    return {
        "dni": dni,
        "nombres": "Demo",
        "apellidos": "Uno",
        "direccion_postal": "Caserío Demo s/n",
        **cambios,
    }


def _codigo(respuesta):
    return respuesta.json()["error"]["codigo"]


def test_registrar_productor(api, sesion, coop, operador):
    respuesta = api.como(operador).post(
        "/productores", json=_nuevo(codigo_socio="S-001", telefono="900000000")
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["dni"] == "90000001"
    assert datos["codigo_socio"] == "S-001"
    assert datos["acceso"]["existe"] is False
    assert datos["consentimiento_datos_en"] is None
    afiliacion = sesion.query(Afiliacion).filter_by(productor_id=datos["id"]).one()
    assert afiliacion.cooperativa_id == coop.id and afiliacion.estado == "activa"
    assert sesion.query(Auditoria).filter_by(accion="productor.crear").count() == 1


@pytest.mark.parametrize("dni", ["9000000", "9000000A", "abcdefgh", "900000011"])
def test_dni_invalido(api, operador, dni):
    respuesta = api.como(operador).post("/productores", json=_nuevo(dni=dni))
    assert respuesta.status_code == 422
    assert _codigo(respuesta) == "datos_invalidos"
    assert "dni" in respuesta.json()["error"]["campos"]


def test_dni_afiliado_a_otra_cooperativa(api, sesion, operador):
    otra = factorias.cooperativa(sesion, nombre="Coop Secreta")
    factorias.productor(sesion, otra, dni="90000001")
    respuesta = api.como(operador).post("/productores", json=_nuevo())
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["mensaje"] == "Este DNI ya está afiliado a otra cooperativa"
    assert otra.razon_social not in respuesta.text
    assert str(otra.id) not in respuesta.text


def test_dni_ya_registrado_en_la_misma_cooperativa(api, sesion, coop, operador):
    factorias.productor(sesion, coop, dni="90000001")
    respuesta = api.como(operador).post("/productores", json=_nuevo())
    assert respuesta.status_code == 409
    assert _codigo(respuesta) == "productor_ya_registrado"


def test_productor_sin_afiliacion_activa_se_reafilia(api, sesion, coop, operador):
    otra = factorias.cooperativa(sesion)
    productor = factorias.productor(sesion, otra, dni="90000001")
    afiliacion = sesion.query(Afiliacion).filter_by(productor_id=productor.id).one()
    afiliacion.estado, afiliacion.hasta = "inactiva", date(2026, 6, 30)
    sesion.flush()
    respuesta = api.como(operador).post("/productores", json=_nuevo())
    assert respuesta.status_code == 201
    assert respuesta.json()["id"] == str(productor.id)
    assert sesion.query(Productor).filter_by(dni="90000001").count() == 1


def test_segunda_afiliacion_activa_la_rechaza_el_indice(sesion, coop):
    productor = factorias.productor(sesion, coop)
    otra = factorias.cooperativa(sesion)
    sesion.add(
        Afiliacion(productor_id=productor.id, cooperativa_id=otra.id, estado="activa", desde=date.today())
    )
    with pytest.raises(IntegrityError, match="uq_afiliaciones_productor_activa"):
        sesion.flush()


def test_consentimiento_marcado_por_la_cooperativa(api, sesion, operador):
    respuesta = api.como(operador).post(
        "/productores", json=_nuevo(consentimiento_cooperativa=True, version_consentimiento="0")
    )
    assert respuesta.json()["consentimiento_origen"] == "cooperativa"
    fila = sesion.query(Auditoria).filter_by(accion="productor.consentimiento").one()
    assert fila.detalle == {"origen": "cooperativa", "version_texto": "0"}


def test_consentimiento_de_la_cooperativa_exige_version(api, operador):
    respuesta = api.como(operador).post("/productores", json=_nuevo(consentimiento_cooperativa=True))
    assert respuesta.status_code == 422


def test_productor_de_cooperativa_demo_nace_demo(api, sesion):
    demo = factorias.cooperativa(sesion, es_demo=True)
    operador = factorias.perfil(sesion, "operador", demo)
    assert api.como(operador).post("/productores", json=_nuevo()).json()["es_demo"] is True


def test_buscar_por_dni_o_nombre(api, sesion, coop, operador):
    factorias.productor(sesion, coop, dni="91112222", nombres="Demo Buscado")
    factorias.productor(sesion, coop, dni="93334444", nombres="Demo Otro")
    api.como(operador)
    assert api.get("/productores", params={"q": "9111"}).json()["total"] == 1
    assert api.get("/productores", params={"q": "buscado"}).json()["total"] == 1
    assert api.get("/productores").json()["total"] == 2


def test_paginacion(api, sesion, coop, operador):
    for _ in range(3):
        factorias.productor(sesion, coop)
    datos = api.como(operador).get("/productores", params={"pagina": 2, "por_pagina": 2}).json()
    assert datos == datos | {"total": 3, "pagina": 2, "por_pagina": 2}
    assert len(datos["items"]) == 1
    assert api.get("/productores", params={"por_pagina": 101}).status_code == 422


def test_lector_no_registra_productores(api, sesion, coop):
    lector = factorias.perfil(sesion, "lector", coop)
    api.como(lector)
    assert api.get("/productores").status_code == 200
    assert api.post("/productores", json=_nuevo()).status_code == 403


def test_productor_no_lista_productores(api, sesion, coop):
    _, cuenta = factorias.productor_con_acceso(sesion, coop)
    assert api.como(cuenta).get("/productores").status_code == 403


# --- Acceso del productor ---


def test_crear_acceso_con_correo_tecnico(api, sesion, coop, operador, auth_falso):
    productor = factorias.productor(sesion, coop, dni="90000007")
    respuesta = api.como(operador).post(f"/productores/{productor.id}/acceso")
    assert respuesta.status_code == 201
    clave = respuesta.json()["clave_temporal"]
    usuario_auth = next(iter(auth_falso.usuarios.values()))
    assert usuario_auth == {
        "correo": "90000007@productores.cacaotrace.local",
        "clave": clave,
        "bloqueado": False,
    }

    perfil = sesion.query(Perfil).filter_by(productor_id=productor.id).one()
    assert perfil.rol == "productor" and perfil.correo is None and perfil.cooperativa_id == coop.id
    assert perfil.debe_cambiar_clave is True
    detalle = api.get(f"/productores/{productor.id}").json()
    assert detalle["acceso"] == detalle["acceso"] | {
        "existe": True,
        "activo": True,
        "debe_cambiar_clave": True,
    }
    assert sesion.query(Auditoria).filter_by(accion="productor.acceso_crear").count() == 1


def test_no_duplica_un_acceso_activo(api, sesion, coop, operador):
    productor, _ = factorias.productor_con_acceso(sesion, coop)
    respuesta = api.como(operador).post(f"/productores/{productor.id}/acceso")
    assert respuesta.status_code == 409
    assert _codigo(respuesta) == "acceso_existente"


def test_desactivar_y_volver_a_crear_acceso(api, sesion, coop, operador, auth_falso):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    api.como(operador)
    assert api.delete(f"/productores/{productor.id}/acceso").status_code == 204
    assert cuenta.activo is False
    assert auth_falso.usuarios[cuenta.id]["bloqueado"] is True
    assert api.como(cuenta).get("/me").json()["error"]["codigo"] == "cuenta_desactivada"

    respuesta = api.como(operador).post(f"/productores/{productor.id}/acceso")
    assert respuesta.status_code == 201
    assert cuenta.activo is True and cuenta.debe_cambiar_clave is True
    assert auth_falso.usuarios[cuenta.id] == auth_falso.usuarios[cuenta.id] | {
        "bloqueado": False,
        "clave": respuesta.json()["clave_temporal"],
    }
    acciones = [a.accion for a in sesion.query(Auditoria).order_by(Auditoria.id)]
    assert acciones == ["productor.acceso_desactivar", "productor.acceso_crear"]


def test_restablecer_acceso_del_productor(api, sesion, coop, operador, auth_falso):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    respuesta = api.como(operador).post(f"/productores/{productor.id}/acceso/restablecer-clave")
    assert respuesta.status_code == 200
    assert auth_falso.usuarios[cuenta.id]["clave"] == respuesta.json()["clave_temporal"]
    assert cuenta.debe_cambiar_clave is True


def test_restablecer_sin_acceso(api, sesion, coop, operador):
    productor = factorias.productor(sesion, coop)
    assert api.como(operador).post(f"/productores/{productor.id}/acceso/restablecer-clave").status_code == 404


def test_lector_no_gestiona_accesos(api, sesion, coop):
    lector = factorias.perfil(sesion, "lector", coop)
    productor = factorias.productor(sesion, coop)
    assert api.como(lector).post(f"/productores/{productor.id}/acceso").status_code == 403

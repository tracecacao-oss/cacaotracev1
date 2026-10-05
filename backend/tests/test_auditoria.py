"""Auditoría: solo inserciones, sin contraseñas y consultable por admin y superadmin."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models import Auditoria
from app.services.auditoria import _limpiar
from tests import factorias


def _fila(sesion):
    coop = factorias.cooperativa(sesion)
    sesion.add(
        Auditoria(cooperativa_id=coop.id, accion="cooperativa.crear", entidad="cooperativa", detalle={})
    )
    sesion.flush()
    return coop


@pytest.mark.parametrize(
    "sentencia",
    ["UPDATE auditoria SET accion = 'otra'", "DELETE FROM auditoria"],
)
def test_trigger_rechaza_update_y_delete(sesion, sentencia):
    _fila(sesion)
    with pytest.raises(DBAPIError, match="solo admite inserciones"):
        with sesion.begin_nested():
            sesion.execute(text(sentencia))


def test_detalle_nunca_guarda_claves():
    limpio = _limpiar(
        {"rol": "lector", "clave_temporal": "x", "datos": {"password": "y", "token": "z", "ok": 1}}
    )
    assert limpio == {"rol": "lector", "datos": {"ok": 1}}


def test_cada_accion_auditable_crea_su_fila_sin_contrasenas(api, sesion, auth_falso):
    superadmin = factorias.perfil(sesion, "superadmin")
    api.como(superadmin)
    creada = api.post(
        "/admin/cooperativas",
        json={
            "razon_social": "Coop Auditada",
            "codigo": "CAU",
            "ruc": "20999999902",
            "departamento": "SAN MARTIN",
            "provincia": "PICOTA",
            "distrito": "PICOTA",
            "administrador": {"nombres": "A", "apellidos": "B", "correo": "aud.admin@prueba.test"},
        },
    ).json()
    coop_id = creada["cooperativa"]["id"]
    claves = [creada["clave_temporal"]]
    api.patch(f"/admin/cooperativas/{coop_id}", json={"razon_social": "Coop Auditada 2"})
    api.patch(f"/admin/cooperativas/{coop_id}", json={"estado": "suspendida"})
    api.patch(f"/admin/cooperativas/{coop_id}", json={"estado": "activa"})
    claves.append(
        api.post(f"/admin/usuarios/{creada['administrador']['id']}/restablecer-clave").json()[
            "clave_temporal"
        ]
    )

    from app.models import Perfil

    admin = sesion.get(Perfil, creada["administrador"]["id"])
    admin.debe_cambiar_clave = False
    sesion.flush()
    api.como(admin)
    usuario = api.post(
        "/usuarios",
        json={"nombres": "L", "apellidos": "C", "correo": "aud.lector@prueba.test", "rol": "lector"},
    ).json()
    claves.append(usuario["clave_temporal"])
    lector_id = usuario["usuario"]["id"]
    api.patch(f"/usuarios/{lector_id}", json={"nombres": "Lector"})
    api.patch(f"/usuarios/{lector_id}", json={"activo": False})
    api.patch(f"/usuarios/{lector_id}", json={"activo": True})
    claves.append(api.post(f"/usuarios/{lector_id}/restablecer-clave").json()["clave_temporal"])

    productor = api.post(
        "/productores",
        json={
            "dni": "90000009",
            "nombres": "Demo",
            "apellidos": "Nueve",
            "direccion_postal": "Caserío Demo",
            "consentimiento_cooperativa": True,
            "version_consentimiento": "0",
        },
    ).json()
    claves.append(api.post(f"/productores/{productor['id']}/acceso").json()["clave_temporal"])
    api.delete(f"/productores/{productor['id']}/acceso")

    auth_falso.usuarios[admin.id]["clave"] = "ClaveAdmin9"
    api.post("/me/clave", json={"clave_actual": "ClaveAdmin9", "clave_nueva": "ClaveAdmin10"})
    claves += ["ClaveAdmin9", "ClaveAdmin10"]

    api.como(superadmin, cooperativa_id=coop_id).get("/productores")

    filas = sesion.query(Auditoria).all()
    acciones = {f.accion for f in filas}
    assert acciones == {
        "cooperativa.crear", "cooperativa.editar", "cooperativa.suspender", "cooperativa.reactivar",
        "usuario.crear", "usuario.editar", "usuario.desactivar", "usuario.reactivar",
        "usuario.restablecer_clave", "usuario.cambiar_clave",
        "productor.crear", "productor.acceso_crear", "productor.acceso_desactivar",
        "productor.consentimiento", "superadmin.consultar_cooperativa",
    }  # fmt: skip
    for fila in filas:
        assert fila.cooperativa_id is not None
        for clave in claves:
            assert clave not in str(fila.detalle)


def test_listado_de_la_propia_cooperativa_con_filtros(api, sesion):
    coop = factorias.cooperativa(sesion)
    admin = factorias.perfil(sesion, "admin_cooperativa", coop)
    otra = _fila(sesion)
    sesion.add(
        Auditoria(cooperativa_id=coop.id, usuario_id=admin.id, accion="usuario.crear", entidad="usuario")
    )
    sesion.add(Auditoria(cooperativa_id=coop.id, accion="productor.crear", entidad="productor"))
    sesion.flush()

    api.como(admin)
    datos = api.get("/auditoria").json()
    assert datos["total"] == 2
    assert all(i["cooperativa_id"] == str(coop.id) for i in datos["items"])
    assert api.get("/auditoria", params={"accion": "usuario."}).json()["total"] == 1
    filtrado = api.get("/auditoria", params={"usuario_id": str(admin.id)}).json()
    assert filtrado["items"][0]["usuario_nombre"] == f"{admin.nombres} {admin.apellidos}"
    hoy = api.get("/auditoria", params={"desde": "2026-01-01", "hasta": "2099-12-31"}).json()
    assert hoy["total"] == 2
    assert str(otra.id) not in str(datos)


def test_superadmin_ve_toda_la_plataforma_o_una_cooperativa(api, sesion):
    superadmin = factorias.perfil(sesion, "superadmin")
    a = _fila(sesion)
    _fila(sesion)
    assert api.como(superadmin).get("/auditoria").json()["total"] == 2
    # Con cooperativa elegida: su fila y la de la consulta de soporte.
    datos = api.como(superadmin, cooperativa_id=a.id).get("/auditoria").json()
    assert {i["accion"] for i in datos["items"]} == {"cooperativa.crear", "superadmin.consultar_cooperativa"}


def test_operador_no_ve_la_auditoria(api, sesion):
    coop = factorias.cooperativa(sesion)
    operador = factorias.perfil(sesion, "operador", coop)
    assert api.como(operador).get("/auditoria").status_code == 403

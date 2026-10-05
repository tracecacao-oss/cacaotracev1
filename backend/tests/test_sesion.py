"""Contexto de cada petición, /me, cambio de contraseña y consentimiento."""

from app.models import Auditoria
from tests import factorias


def _codigo(respuesta) -> str:
    return respuesta.json()["error"]["codigo"]


# --- Contexto ---


def test_debe_cambiar_clave_solo_permite_me_y_cambio(api, sesion):
    coop = factorias.cooperativa(sesion)
    admin = factorias.perfil(sesion, "admin_cooperativa", coop, debe_cambiar_clave=True)
    api.como(admin)
    assert api.get("/me").status_code == 200
    respuesta = api.get("/usuarios")
    assert respuesta.status_code == 403
    assert _codigo(respuesta) == "cambio_clave_requerido"


def test_cuenta_desactivada(api, sesion):
    coop = factorias.cooperativa(sesion)
    operador = factorias.perfil(sesion, "operador", coop, activo=False)
    respuesta = api.como(operador).get("/me")
    assert respuesta.status_code == 403
    assert _codigo(respuesta) == "cuenta_desactivada"


def test_cooperativa_suspendida(api, sesion):
    coop = factorias.cooperativa(sesion, estado="suspendida")
    lector = factorias.perfil(sesion, "lector", coop)
    respuesta = api.como(lector).get("/productores")
    assert respuesta.status_code == 403
    assert _codigo(respuesta) == "cooperativa_suspendida"


def test_rol_sin_permiso_recibe_403(api, sesion):
    coop = factorias.cooperativa(sesion)
    operador = factorias.perfil(sesion, "operador", coop)
    respuesta = api.como(operador).get("/admin/cooperativas")
    assert respuesta.status_code == 403
    assert _codigo(respuesta) == "sin_permiso"


# --- /me ---


def test_me_del_personal(api, sesion):
    coop = factorias.cooperativa(sesion, nombre_comercial="Coop Comercial")
    admin = factorias.perfil(sesion, "admin_cooperativa", coop)
    datos = api.como(admin).get("/me").json()
    assert datos["rol"] == "admin_cooperativa"
    assert datos["cooperativa"]["id"] == str(coop.id)
    assert datos["cooperativa"]["nombre_comercial"] == "Coop Comercial"
    assert datos["dni"] is None
    assert datos["consentimiento_pendiente"] is False
    assert admin.ultimo_acceso_en is not None


def test_me_del_productor(api, sesion):
    coop = factorias.cooperativa(sesion)
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    datos = api.como(cuenta).get("/me").json()
    assert datos["rol"] == "productor"
    assert datos["dni"] == productor.dni
    assert datos["productor_id"] == str(productor.id)
    assert datos["correo"] is None
    assert datos["consentimiento_pendiente"] is True


def test_me_del_superadmin(api, sesion):
    superadmin = factorias.perfil(sesion, "superadmin")
    datos = api.como(superadmin).get("/me").json()
    assert datos["cooperativa"] is None


# --- Cambio de contraseña ---


def _con_clave(auth_falso, perfil, correo, clave):
    auth_falso.usuarios[perfil.id] = {"correo": correo, "clave": clave, "bloqueado": False}


def test_cambio_de_clave_del_personal(api, sesion, auth_falso):
    coop = factorias.cooperativa(sesion)
    admin = factorias.perfil(sesion, "admin_cooperativa", coop, debe_cambiar_clave=True)
    _con_clave(auth_falso, admin, admin.correo, "Temporal23")

    respuesta = api.como(admin).post(
        "/me/clave", json={"clave_actual": "Temporal23", "clave_nueva": "NuevaClave9"}
    )
    assert respuesta.status_code == 204
    assert auth_falso.usuarios[admin.id]["clave"] == "NuevaClave9"
    assert admin.debe_cambiar_clave is False
    assert api.get("/usuarios").status_code == 200  # ya puede operar
    fila = sesion.query(Auditoria).filter_by(accion="usuario.cambiar_clave").one()
    assert "NuevaClave9" not in str(fila.detalle)


def test_cambio_de_clave_con_clave_actual_incorrecta(api, sesion, auth_falso):
    coop = factorias.cooperativa(sesion)
    admin = factorias.perfil(sesion, "admin_cooperativa", coop, debe_cambiar_clave=True)
    _con_clave(auth_falso, admin, admin.correo, "Temporal23")
    respuesta = api.como(admin).post(
        "/me/clave", json={"clave_actual": "Otra12345", "clave_nueva": "NuevaClave9"}
    )
    assert respuesta.status_code == 400
    assert _codigo(respuesta) == "clave_actual_incorrecta"
    assert admin.debe_cambiar_clave is True


def test_reglas_de_clave_del_personal(api, sesion, auth_falso):
    coop = factorias.cooperativa(sesion)
    admin = factorias.perfil(sesion, "admin_cooperativa", coop, debe_cambiar_clave=True)
    _con_clave(auth_falso, admin, admin.correo, "Temporal23")
    api.como(admin)
    for nueva in ("corta1", "sinnumeros", "12345678"):
        respuesta = api.post("/me/clave", json={"clave_actual": "Temporal23", "clave_nueva": nueva})
        assert respuesta.status_code == 400, nueva
        assert _codigo(respuesta) == "clave_debil"
    respuesta = api.post("/me/clave", json={"clave_actual": "Temporal23", "clave_nueva": "Temporal23"})
    assert _codigo(respuesta) == "clave_repetida"


def test_productor_usa_su_correo_tecnico_y_minimo_de_6(api, sesion, auth_falso):
    coop = factorias.cooperativa(sesion)
    productor, cuenta = factorias.productor_con_acceso(sesion, coop, debe_cambiar_clave=True)
    correo = f"{productor.dni}@productores.cacaotrace.local"
    _con_clave(auth_falso, cuenta, correo, "Temporal23")
    respuesta = api.como(cuenta).post(
        "/me/clave", json={"clave_actual": "Temporal23", "clave_nueva": "cacao1"}
    )
    assert respuesta.status_code == 204
    assert ("verificar_clave", correo) in auth_falso.llamadas


# --- Consentimiento ---


def test_consentimiento_del_productor(api, sesion):
    coop = factorias.cooperativa(sesion)
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    respuesta = api.como(cuenta).post("/me/consentimiento", json={"version_texto": "0"})
    assert respuesta.status_code == 204
    assert productor.consentimiento_origen == "productor"
    assert productor.consentimiento_datos_en is not None
    fila = sesion.query(Auditoria).filter_by(accion="productor.consentimiento").one()
    assert fila.detalle == {"origen": "productor", "version_texto": "0"}
    assert fila.cooperativa_id == coop.id
    # Una segunda aceptación no duplica el registro.
    api.post("/me/consentimiento", json={"version_texto": "0"})
    assert sesion.query(Auditoria).filter_by(accion="productor.consentimiento").count() == 1


def test_consentimiento_solo_para_productor(api, sesion):
    coop = factorias.cooperativa(sesion)
    operador = factorias.perfil(sesion, "operador", coop)
    respuesta = api.como(operador).post("/me/consentimiento", json={"version_texto": "0"})
    assert respuesta.status_code == 403

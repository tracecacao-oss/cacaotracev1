"""Ficha del productor: niveles de verificación, pendientes, documentos y edición."""

import pytest

from app.models import Afiliacion, Auditoria, Documento
from tests import factorias
from tests.factorias import crear_parcela, rectangulo

PDF = b"%PDF-1.7\n% copia de DNI de prueba\n"
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
EJECUTABLE = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop, direccion_postal="Caserío Demo")


def _subir(api, productor_id, tipo="dni", contenido=PDF, nombre="dni.pdf"):
    return api.post(
        f"/productores/{productor_id}/documentos", data={"tipo": tipo}, files={"archivo": (nombre, contenido)}
    )


def test_pendientes_y_niveles_iniciales(api, operador, productor):
    ficha = api.como(operador).get(f"/productores/{productor.id}").json()
    assert ficha["nivel_identidad"] == "declarado"
    assert ficha["nivel_ppa"] == "no_registrado"
    assert ficha["pendientes"] == ["sin_documento_dni", "sin_consentimiento", "sin_parcelas"]


def test_documento_dni_eleva_la_identidad(api, operador, productor, storage_falso):
    respuesta = _subir(api.como(operador), productor.id)
    assert respuesta.status_code == 201
    assert respuesta.json()["tipo_mime"] == "application/pdf"
    ficha = api.get(f"/productores/{productor.id}").json()
    assert ficha["nivel_identidad"] == "documentado"
    assert "sin_documento_dni" not in ficha["pendientes"]
    assert len(storage_falso.archivos) == 1


def test_anular_el_unico_dni_vuelve_a_declarado(api, sesion, operador, productor):
    documento = _subir(api.como(operador), productor.id).json()
    respuesta = api.post(f"/documentos/{documento['id']}/anular", json={"motivo": "Foto ilegible"})
    assert respuesta.status_code == 200 and respuesta.json()["vigente"] is False
    assert api.get(f"/productores/{productor.id}").json()["nivel_identidad"] == "declarado"
    assert (
        sesion.query(Auditoria).filter_by(accion="documento.anular").one().detalle["motivo"]
        == "Foto ilegible"
    )


def test_ejecutable_con_extension_pdf(api, operador, productor):
    respuesta = _subir(api.como(operador), productor.id, contenido=EJECUTABLE, nombre="dni.pdf")
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "formato_no_admitido"


def test_mismo_documento_dos_veces(api, operador, productor):
    api.como(operador)
    assert _subir(api, productor.id).status_code == 201
    assert _subir(api, productor.id).status_code == 409
    # El mismo archivo con otro tipo sí se acepta.
    assert _subir(api, productor.id, tipo="constancia_ppa").status_code == 201


def test_tipo_de_documento_que_no_corresponde(api, operador, productor):
    respuesta = _subir(api.como(operador), productor.id, tipo="sustento_midagri")
    assert respuesta.status_code == 422


def test_archivo_mayor_a_10_mb(api, operador, productor):
    grande = PDF + b"0" * (10 * 1024 * 1024)
    respuesta = _subir(api.como(operador), productor.id, contenido=grande)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "archivo_muy_grande"


def test_url_firmada_de_5_minutos(api, operador, productor):
    documento = _subir(api.como(operador), productor.id, contenido=JPG, nombre="dni.jpg").json()
    respuesta = api.get(f"/documentos/{documento['id']}/url").json()
    assert respuesta["vence_en_segundos"] == 300
    assert "vence=300" in respuesta["url"]


def test_ppa_documentado(api, operador, productor):
    api.como(operador)
    api.patch(f"/productores/{productor.id}", json={"ppa_registrado": True, "ppa_codigo": "PPA-DEMO-1"})
    assert api.get(f"/productores/{productor.id}").json()["nivel_ppa"] == "declarado"
    _subir(api, productor.id, tipo="constancia_ppa")
    assert api.get(f"/productores/{productor.id}").json()["nivel_ppa"] == "documentado"
    ficha = api.patch(f"/productores/{productor.id}", json={"ppa_registrado": False}).json()
    assert ficha["nivel_ppa"] == "no_registrado" and ficha["ppa_codigo"] is None


def test_sin_parcelas_desaparece_al_registrar_una(api, operador, productor):
    crear_parcela(api.como(operador), productor.id, rectangulo(100, 100))
    ficha = api.get(f"/productores/{productor.id}").json()
    assert "sin_parcelas" not in ficha["pendientes"]
    assert ficha["parcelas"]["activas"] == 1
    listado = api.get("/productores").json()["items"][0]
    assert listado["parcelas"]["activas"] == 1 and "sin_parcelas" not in listado["pendientes"]


def test_editar_ficha(api, sesion, operador, productor):
    respuesta = api.como(operador).patch(
        f"/productores/{productor.id}",
        json={"ruc": "10900000017", "correo_contacto": "Demo@Prueba.test", "codigo_socio": "S-9"},
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ruc"] == "10900000017" and datos["correo_contacto"] == "demo@prueba.test"
    assert datos["codigo_socio"] == "S-9"
    fila = sesion.query(Auditoria).filter_by(accion="productor.editar").one()
    assert set(fila.detalle) == {"ruc", "correo_contacto", "codigo_socio"}


def test_corregir_dni_exige_motivo_y_actualiza_el_correo_tecnico(api, sesion, coop, operador, auth_falso):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    auth_falso.usuarios[cuenta.id] = {"correo": f"{productor.dni}@productores.cacaotrace.local", "clave": "x"}
    api.como(operador)
    respuesta = api.patch(f"/productores/{productor.id}", json={"dni": "91234567"})
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "motivo_requerido"

    anterior = productor.dni
    respuesta = api.patch(
        f"/productores/{productor.id}", json={"dni": "91234567", "motivo": "Error al digitar"}
    )
    assert respuesta.status_code == 200
    assert auth_falso.usuarios[cuenta.id]["correo"] == "91234567@productores.cacaotrace.local"
    fila = sesion.query(Auditoria).filter_by(accion="productor.editar").one()
    assert fila.detalle["dni"] == {"antes": anterior, "despues": "91234567"}
    assert fila.detalle["motivo"] == "Error al digitar"


def test_dni_ya_registrado(api, sesion, coop, operador, productor):
    otro = factorias.productor(sesion, factorias.cooperativa(sesion))
    respuesta = api.como(operador).patch(
        f"/productores/{productor.id}", json={"dni": otro.dni, "motivo": "x"}
    )
    assert respuesta.status_code == 409


def test_cerrar_afiliacion(api, sesion, coop, auth_falso):
    admin = factorias.perfil(sesion, "admin_cooperativa", coop)
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    respuesta = api.como(admin).post(
        f"/productores/{productor.id}/afiliacion/cerrar", json={"motivo": "Retiro"}
    )
    assert respuesta.status_code == 204
    afiliacion = sesion.query(Afiliacion).filter_by(productor_id=productor.id).one()
    assert afiliacion.estado == "inactiva" and afiliacion.hasta is not None
    assert cuenta.activo is False and ("bloquear", cuenta.id) in auth_falso.llamadas
    assert api.get(f"/productores/{productor.id}").status_code == 404


def test_operador_no_cierra_afiliaciones(api, operador, productor):
    respuesta = api.como(operador).post(f"/productores/{productor.id}/afiliacion/cerrar", json={})
    assert respuesta.status_code == 403


def test_alta_exige_direccion_postal(api, operador):
    respuesta = api.como(operador).post(
        "/productores", json={"dni": "91111111", "nombres": "Demo", "apellidos": "X"}
    )
    assert respuesta.status_code == 422
    assert "direccion_postal" in respuesta.json()["error"]["campos"]


def test_documentos_se_listan_en_la_ficha(api, sesion, operador, productor):
    api.como(operador)
    _subir(api, productor.id)
    documentos = api.get(f"/productores/{productor.id}").json()["documentos"]
    assert [d["tipo"] for d in documentos] == ["dni"]
    assert sesion.query(Documento).one().subido_por == operador.id

"""El productor sobre sus propios registros, y aislamiento de lo nuevo de la Parte 3."""

import pytest

from tests import factorias
from tests.factorias import crear_parcela, rectangulo

PDF = b"%PDF-1.7\n% prueba\n"


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor_con_acceso(sesion, coop)


def test_mi_ficha_con_pendientes(api, productor):
    prod, cuenta = productor
    ficha = api.como(cuenta).get("/mi/productor").json()
    assert ficha["id"] == str(prod.id)
    assert "sin_documento_dni" in ficha["pendientes"]


def test_solo_edita_su_telefono(api, productor):
    _, cuenta = productor
    api.como(cuenta)
    assert api.patch("/mi/productor", json={"telefono": "900000001"}).json()["telefono"] == "900000001"
    respuesta = api.patch("/mi/productor", json={"nombres": "Otro"})
    assert respuesta.status_code == 422


def test_carga_su_dni(api, productor):
    _, cuenta = productor
    api.como(cuenta)
    respuesta = api.post(
        "/mi/documentos", data={"tipo": "dni"}, files={"archivo": ("dni.jpg", b"\xff\xd8\xff" + b"0" * 50)}
    )
    assert respuesta.status_code == 201
    assert api.get("/mi/productor").json()["nivel_identidad"] == "documentado"
    url = api.get(f"/documentos/{respuesta.json()['id']}/url")
    assert url.status_code == 200


def test_crea_y_edita_su_parcela(api, productor):
    prod, cuenta = productor
    api.como(cuenta)
    parcela = crear_parcela(api, prod.id, rectangulo(100, 100), ruta="/mi/parcelas").json()
    assert parcela["productor"]["id"] == str(prod.id)
    assert [p["id"] for p in api.get("/mi/parcelas").json()] == [parcela["id"]]
    respuesta = api.patch(f"/mi/parcelas/{parcela['id']}", json={"nombre": "Mi chacra"})
    assert respuesta.json()["nombre"] == "Mi chacra"
    sustento = api.post(
        f"/mi/parcelas/{parcela['id']}/documentos",
        data={"tipo": "sustento_midagri"},
        files={"archivo": ("captura.pdf", PDF)},
    )
    assert sustento.status_code == 201


def test_productor_pide_una_parcela_ajena(api, sesion, coop, productor):
    _, cuenta = productor
    vecino = factorias.productor(sesion, coop)
    operador = factorias.perfil(sesion, "operador", coop)
    ajena = crear_parcela(api.como(operador), vecino.id, rectangulo(100, 100, este_m=500)).json()
    api.como(cuenta)
    assert api.get(f"/mi/parcelas/{ajena['id']}").status_code == 404
    assert api.patch(f"/mi/parcelas/{ajena['id']}", json={"nombre": "x"}).status_code == 404


def test_productor_ve_la_alerta_sin_datos_de_la_otra_parcela(api, sesion, coop, productor):
    prod, cuenta = productor
    operador = factorias.perfil(sesion, "operador", coop)
    crear_parcela(api.como(operador), factorias.productor(sesion, coop).id, rectangulo(100, 100))
    mia = crear_parcela(
        api.como(cuenta), prod.id, rectangulo(100, 100, este_m=70), ruta="/mi/parcelas"
    ).json()
    assert "superposicion" in mia["alertas"]
    assert mia["superposiciones"][0]["otra_parcela"] is None


def test_productor_no_usa_endpoints_del_personal(api, productor):
    prod, cuenta = productor
    api.como(cuenta)
    assert api.get("/parcelas").status_code == 403
    assert api.get(f"/productores/{prod.id}").status_code == 403
    assert api.get("/superposiciones").status_code == 403


def test_personal_no_usa_endpoints_del_productor(api, sesion, coop):
    operador = factorias.perfil(sesion, "operador", coop)
    assert api.como(operador).get("/mi/parcelas").status_code == 403


# --- Aislamiento A/B en los endpoints nuevos ---


@pytest.fixture
def mundo(api, sesion):
    a, b = factorias.cooperativa(sesion), factorias.cooperativa(sesion)
    operador_a, operador_b = factorias.perfil(sesion, "operador", a), factorias.perfil(sesion, "operador", b)
    productor_b = factorias.productor(sesion, b)
    parcela_b = crear_parcela(api.como(operador_b), productor_b.id, rectangulo(100, 100, este_m=2000)).json()
    documento_b = api.post(
        f"/productores/{productor_b.id}/documentos", data={"tipo": "dni"}, files={"archivo": ("dni.pdf", PDF)}
    ).json()
    return {
        "operador_a": operador_a,
        "productor_b": productor_b,
        "parcela_b": parcela_b,
        "documento_b": documento_b,
    }


def test_recursos_de_b_responden_404_a_un_usuario_de_a(api, mundo):
    api.como(mundo["operador_a"])
    pb, parcela, doc = mundo["productor_b"].id, mundo["parcela_b"]["id"], mundo["documento_b"]["id"]
    assert api.patch(f"/productores/{pb}", json={"telefono": "1"}).status_code == 404
    assert api.get(f"/productores/{pb}/parcelas").status_code == 404
    assert crear_parcela(api, pb, rectangulo(50, 50, este_m=5000)).status_code == 404
    assert (
        api.post(
            f"/productores/{pb}/documentos", data={"tipo": "dni"}, files={"archivo": ("x.pdf", PDF + b"1")}
        ).status_code
        == 404
    )
    assert api.get(f"/parcelas/{parcela}").status_code == 404
    assert api.patch(f"/parcelas/{parcela}", json={"nombre": "x"}).status_code == 404
    assert api.post(f"/parcelas/{parcela}/desactivar").status_code == 404
    assert api.get(f"/parcelas/{parcela}/geojson").status_code == 404
    assert (
        api.post(
            f"/parcelas/{parcela}/documentos",
            data={"tipo": "sustento_midagri"},
            files={"archivo": ("x.pdf", PDF)},
        ).status_code
        == 404
    )
    assert api.get(f"/documentos/{doc}/url").status_code == 404
    assert api.post(f"/documentos/{doc}/anular", json={"motivo": "x"}).status_code == 404
    assert api.get("/parcelas").json() == []
    assert api.get("/superposiciones").json() == []

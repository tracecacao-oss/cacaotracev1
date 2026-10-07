"""Parte 4: expediente legal de la parcela, exenciones y cotejo en fuente."""

import uuid
from datetime import timedelta

import pytest

from app.fechas import hoy_lima
from app.models import Auditoria, Parcela
from tests import factorias
from tests.factorias import crear_parcela, rectangulo
from tests.habilitacion_util import PDF, documento_legal, expediente_completo

MOTIVO = "La parcela es tierra privada titulada: no requiere contrato de cesión en uso."


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def admin(sesion, coop):
    return factorias.perfil(sesion, "admin_cooperativa", coop)


@pytest.fixture
def parcela(api, sesion, coop, operador):
    productor = factorias.productor(sesion, coop)
    datos = crear_parcela(api.como(operador), productor.id, rectangulo(100, 100)).json()
    return sesion.get(Parcela, uuid.UUID(datos["id"]))


def _expediente(api, parcela):
    return api.get(f"/parcelas/{parcela.id}/expediente").json()


def _casilla(expediente, codigo):
    return next(c for c in expediente["casillas"] if c["codigo"] == codigo)


def test_titulo_vigente_y_cinco_documentos_completan_el_expediente(api, sesion, operador, parcela):
    expediente_completo(sesion, parcela, operador)
    exp = _expediente(api.como(operador), parcela)
    assert exp["estado"] == "completo"
    assert exp["faltan"] == []
    assert [c["codigo"] for c in exp["casillas"]] == [
        "titulo_sunarp",
        "constancia_posesion",
        "cusaf",
        "autorizacion_serfor",
        "sunafil",
        "sunat",
        "zonificacion",
    ]
    assert _casilla(exp, "titulo_sunarp")["estado"] == "vigente"
    # Con el título vigente, la constancia no falta: no se requiere y dice qué la cubre.
    constancia = _casilla(exp, "constancia_posesion")
    assert constancia["estado"] == "no_requerida"
    assert constancia["cubierta_por"] == "titulo_sunarp"
    assert constancia["cubierta_por_nombre"] == "Título de propiedad inscrito en SUNARP"
    alertas = api.get(f"/parcelas/{parcela.id}").json()["alertas"]
    assert "expediente_incompleto" not in alertas


def test_solo_constancia_de_posesion(api, sesion, operador, parcela):
    for tipo in ("constancia_posesion", "cusaf", "autorizacion_serfor", "sunafil", "sunat", "zonificacion"):
        documento_legal(sesion, parcela, tipo, operador)
    exp = _expediente(api.como(operador), parcela)
    assert exp["estado"] == "completo"
    assert exp["tenencia_solo_posesion"] is True
    assert "tenencia_solo_posesion" in api.get(f"/parcelas/{parcela.id}").json()["alertas"]


def test_sin_titulo_ni_constancia(api, sesion, operador, parcela):
    for tipo in ("cusaf", "autorizacion_serfor", "sunafil", "sunat", "zonificacion"):
        documento_legal(sesion, parcela, tipo, operador)
    exp = _expediente(api.como(operador), parcela)
    assert exp["estado"] == "incompleto"
    assert exp["faltan"] == ["tenencia"]
    assert "expediente_incompleto" in api.get(f"/parcelas/{parcela.id}").json()["alertas"]


def test_vencido_y_por_vencer(api, sesion, operador, parcela):
    documento_legal(sesion, parcela, "titulo_sunarp", operador, vence=hoy_lima() - timedelta(days=1))
    documento_legal(sesion, parcela, "sunat", operador, vence=hoy_lima() + timedelta(days=10))
    exp = _expediente(api.como(operador), parcela)
    assert _casilla(exp, "titulo_sunarp")["estado"] == "vencido"
    assert _casilla(exp, "sunat")["estado"] == "por_vencer"
    assert _casilla(exp, "sunat")["vence_en"] == str(hoy_lima() + timedelta(days=10))
    alertas = api.get(f"/parcelas/{parcela.id}").json()["alertas"]
    assert {"documento_vencido", "documento_por_vencer", "expediente_incompleto"} <= set(alertas)


def test_cuenta_el_documento_con_vencimiento_mas_lejano(api, sesion, operador, parcela):
    documento_legal(sesion, parcela, "sunat", operador, vence=hoy_lima() - timedelta(days=5))
    documento_legal(sesion, parcela, "sunat", operador, vence=hoy_lima() + timedelta(days=400))
    assert _casilla(_expediente(api.como(operador), parcela), "sunat")["estado"] == "vigente"


# --- Exenciones ---


def test_exencion_cubre_la_casilla_y_se_retira(api, sesion, admin, parcela):
    api.como(admin)
    respuesta = api.post(f"/parcelas/{parcela.id}/exenciones", json={"tipo": "cusaf", "motivo": MOTIVO})
    assert respuesta.status_code == 201, respuesta.text
    casilla = _casilla(_expediente(api, parcela), "cusaf")
    assert casilla["estado"] == "no_aplica"
    assert casilla["exencion"]["motivo"] == MOTIVO
    assert (
        api.post(f"/parcelas/{parcela.id}/exenciones", json={"tipo": "cusaf", "motivo": MOTIVO}).status_code
        == 409
    )

    assert api.post(f"/exenciones/{respuesta.json()['id']}/retirar").status_code == 204
    assert _casilla(_expediente(api, parcela), "cusaf")["estado"] == "faltante"
    acciones = [
        a.accion
        for a in sesion.query(Auditoria).filter(Auditoria.accion.like("exencion.%")).order_by(Auditoria.id)
    ]
    assert acciones == ["exencion.declarar", "exencion.retirar"]


@pytest.mark.parametrize("tipo", ["titulo_sunarp", "constancia_posesion"])
def test_la_tenencia_no_admite_exencion(api, admin, parcela, tipo):
    respuesta = api.como(admin).post(
        f"/parcelas/{parcela.id}/exenciones", json={"tipo": tipo, "motivo": MOTIVO}
    )
    assert respuesta.status_code == 422


def test_exencion_sin_motivo_o_del_operador(api, admin, operador, parcela):
    corto = api.como(admin).post(
        f"/parcelas/{parcela.id}/exenciones", json={"tipo": "sunafil", "motivo": "no aplica"}
    )
    assert corto.status_code == 422
    del_operador = api.como(operador).post(
        f"/parcelas/{parcela.id}/exenciones", json={"tipo": "sunafil", "motivo": MOTIVO}
    )
    assert del_operador.status_code == 403


# --- Cotejo en fuente ---


def test_cotejo_de_constancia_de_posesion(api, sesion, operador, parcela):
    documento = documento_legal(sesion, parcela, "constancia_posesion", operador)
    respuesta = api.como(operador).post(
        f"/documentos/{documento.id}/cotejo", json={"nota": "Consulté el registro."}
    )
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "sin_registro_consultable"


def test_cotejo_de_titulo_sunarp(api, sesion, operador, parcela):
    documento = documento_legal(sesion, parcela, "titulo_sunarp", operador)
    assert _casilla(_expediente(api.como(operador), parcela), "titulo_sunarp")["nivel"] == "documentado"
    nota = "Consulté la partida en SUNARP en línea: titular y área coinciden."
    respuesta = api.post(f"/documentos/{documento.id}/cotejo", json={"nota": nota})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["cotejo_nota"] == nota
    assert _casilla(_expediente(api, parcela), "titulo_sunarp")["nivel"] == "verificado_en_fuente"
    assert api.post(f"/documentos/{documento.id}/cotejo", json={"nota": nota}).status_code == 400
    assert sesion.query(Auditoria).filter_by(accion="documento.cotejar").count() == 1


# --- Carga de documentos legales ---


def _subir(api, ruta, tipo="titulo_sunarp", **campos):
    datos = {
        "tipo": tipo,
        "numero": "P-0001",
        "entidad_emisora": "SUNARP",
        "fecha_emision": "2019-05-10",
        **campos,
    }
    datos = {k: v for k, v in datos.items() if v is not None}
    return api.post(ruta, data=datos, files={"archivo": ("titulo.pdf", PDF)})


def test_carga_de_documento_legal(api, operador, parcela):
    respuesta = _subir(
        api.como(operador), f"/parcelas/{parcela.id}/documentos", fecha_vencimiento="2031-05-10"
    )
    assert respuesta.status_code == 201, respuesta.text
    doc = respuesta.json()
    assert (doc["numero"], doc["entidad_emisora"], doc["fecha_emision"]) == ("P-0001", "SUNARP", "2019-05-10")
    assert _casilla(_expediente(api, parcela), "titulo_sunarp")["estado"] == "vigente"


@pytest.mark.parametrize(
    ("campos", "codigo"),
    [
        ({"numero": None}, "datos_legales_requeridos"),
        ({"fecha_emision": str(hoy_lima() + timedelta(days=1))}, "fecha_futura"),
        ({"fecha_vencimiento": "2019-01-01"}, "vencimiento_invalido"),
    ],
)
def test_documento_legal_con_datos_invalidos(api, operador, parcela, campos, codigo):
    respuesta = _subir(api.como(operador), f"/parcelas/{parcela.id}/documentos", **campos)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == codigo


def test_el_productor_carga_en_su_parcela(api, sesion, coop, operador):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    datos = crear_parcela(api.como(operador), productor.id, rectangulo(100, 100)).json()
    respuesta = _subir(api.como(cuenta), f"/mi/parcelas/{datos['id']}/documentos", tipo="constancia_posesion")
    assert respuesta.status_code == 201, respuesta.text
    exp = api.get(f"/mi/parcelas/{datos['id']}/expediente").json()
    assert _casilla(exp, "constancia_posesion")["estado"] == "vigente"


def test_otra_cooperativa_no_ve_ni_toca_el_expediente(api, sesion, parcela):
    otra = factorias.cooperativa(sesion, "Coop B")
    admin_b = factorias.perfil(sesion, "admin_cooperativa", otra)
    api.como(admin_b)
    assert api.get(f"/parcelas/{parcela.id}/expediente").status_code == 404
    assert (
        api.post(f"/parcelas/{parcela.id}/exenciones", json={"tipo": "cusaf", "motivo": MOTIVO}).status_code
        == 404
    )
    assert _subir(api, f"/parcelas/{parcela.id}/documentos").status_code == 404


def test_registros_consultables_confirmados():
    """Confirmados con fuentes oficiales el 2026-10-05 (especificación, "Los 7 documentos")."""
    from app.catalogos import documentos_legales as catalogo

    consultables = {t.codigo for t in catalogo.TIPOS if t.registro_consultable}
    assert consultables == {"titulo_sunarp", "cusaf", "sunafil", "sunat", "zonificacion"}


def test_la_constancia_cubre_la_tenencia_y_el_titulo_no_se_requiere(api, sesion, operador, parcela):
    documento_legal(sesion, parcela, "constancia_posesion", operador)
    titulo = _casilla(_expediente(api.como(operador), parcela), "titulo_sunarp")
    assert titulo["estado"] == "no_requerida"
    assert titulo["cubierta_por"] == "constancia_posesion"
    assert titulo["cubierta_por_nombre"].startswith("Constancia de posesión")


def test_sin_ningun_documento_de_tenencia_las_dos_casillas_faltan(api, operador, parcela):
    exp = _expediente(api.como(operador), parcela)
    for codigo in ("titulo_sunarp", "constancia_posesion"):
        casilla = _casilla(exp, codigo)
        assert casilla["estado"] == "faltante" and casilla["cubierta_por"] is None

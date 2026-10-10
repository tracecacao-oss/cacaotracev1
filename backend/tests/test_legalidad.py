"""Adenda 4: perfil legal de la parcela, requisitos por perfil, incidencias, plantillas y documentos.

Las pruebas de la sección 13 de la adenda que no tocan las capas oficiales; las del cruce están en
tests/test_cruce.py.
"""

import uuid
from datetime import date, timedelta

import pytest

from app.catalogos import documentos_legales
from app.fechas import hoy_lima
from app.models import Auditoria, Documento, Parcela, ParcelaVariable
from app.pdf import declaracion_tenencia
from app.services import legalidad
from tests import factorias
from tests.factorias import crear_parcela, rectangulo
from tests.habilitacion_util import (
    PDF,
    PERFIL_BASE,
    analisis_completado,
    cruce,
    declarar,
    documento_legal,
    fuentes_configuradas,
    incidencia,
    productor_listo,
)

NOTA = "Se habilita con la tenencia declarada por el productor y la nota del técnico que conoce la chacra."
HACE_13_MESES = hoy_lima() - timedelta(days=400)


@pytest.fixture
def fuentes():
    return fuentes_configuradas()


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
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


def _nueva(api, sesion, operador, productor, geometria=None, **datos) -> Parcela:
    respuesta = crear_parcela(api.como(operador), productor.id, geometria or rectangulo(100, 100), **datos)
    assert respuesta.status_code == 201, respuesta.text
    return sesion.get(Parcela, uuid.UUID(respuesta.json()["id"]))


@pytest.fixture
def parcela(api, sesion, operador, productor):
    return _nueva(api, sesion, operador, productor)


def _lista(sesion, parcela, operador, productor, **perfil):
    """Lo demás de la compuerta cumplido: análisis vigentes y productor listo. El perfil, a elección."""
    declarar(sesion, parcela, operador, **(PERFIL_BASE | perfil))
    productor_listo(sesion, productor, operador)
    analisis_completado(sesion, parcela, "whisp")
    analisis_completado(sesion, parcela, "gfw")


def _leg(api, parcela, ruta="/parcelas") -> dict:
    respuesta = api.get(f"{ruta}/{parcela.id}/legalidad")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _req(leg: dict, codigo: str) -> dict:
    return next(r for r in leg["requisitos"] if r["codigo"] == codigo)


def _variable(leg: dict, codigo: str) -> dict:
    return next(v for v in leg["perfil"] if v["codigo"] == codigo)


def _compuerta(leg: dict) -> dict[str, bool]:
    return {r["codigo"]: r["cumple"] for r in leg["compuerta"]}


def _habilitar(api, admin, parcela, nota=NOTA):
    return api.como(admin).post(f"/parcelas/{parcela.id}/habilitar", json={"nota": nota})


# ---------- Perfil y compuerta ----------


def test_parcela_sin_perfil_no_se_habilita(api, sesion, operador, admin, parcela):
    leg = _leg(api.como(operador), parcela)
    assert leg["perfil_completo"] is False
    assert _compuerta(leg)["perfil_legal_completo"] is False
    assert all(r["estado"] in ("sin_dato", "no_aplica") for r in leg["requisitos"])
    respuesta = _habilitar(api, admin, parcela)
    assert respuesta.status_code == 400
    assert "perfil_legal_completo" in respuesta.json()["error"]["faltan"]


def test_ninguna_parcela_recibe_un_perfil_por_defecto(api, sesion, operador, parcela):
    """Sección 9, regla 6: crear la parcela solo la pone en la cola del cruce."""
    assert sesion.query(ParcelaVariable).filter_by(parcela_id=parcela.id).count() == 0
    leg = _leg(api.como(operador), parcela)
    assert leg["cruce"]["en_cola"] is True
    assert {c["codigo"] for c in leg["cruce"]["capas"]} == {
        "sernanp_anp",
        "sernanp_amortiguamiento",
        "serfor_zonificacion",
        "idep_comunidades",
        "ign_hidrografia",
        "sigda_monumentos",
    }


def test_declarar_por_la_api_guarda_una_fila_y_conserva_la_anterior(api, sesion, operador, parcela):
    api.como(operador)
    r = api.post(f"/parcelas/{parcela.id}/perfil", json={"variable": "usa_riego", "valor": "si"})
    assert r.status_code == 200, r.text
    assert _variable(r.json(), "usa_riego")["valor"] == "si"
    r = api.post(f"/parcelas/{parcela.id}/perfil", json={"variable": "usa_riego", "valor": "no"})
    assert _variable(r.json(), "usa_riego")["valor"] == "no"
    filas = sesion.query(ParcelaVariable).filter_by(parcela_id=parcela.id, variable="usa_riego").all()
    assert sorted((f.valor, f.vigente) for f in filas) == [("no", True), ("si", False)]
    assert sesion.query(Auditoria).filter_by(accion="parcela.perfil_declarar").count() == 2


@pytest.mark.parametrize(
    ("variable", "valor"),
    [("usa_riego", "tal_vez"), ("anio_instalacion_cultivo", "15"), ("anio_instalacion_cultivo", "2999")],
)
def test_valores_invalidos(api, operador, parcela, variable, valor):
    r = api.como(operador).post(f"/parcelas/{parcela.id}/perfil", json={"variable": variable, "valor": valor})
    assert r.status_code == 422


def test_el_productor_ve_su_perfil_y_no_lo_edita(api, sesion, coop, operador):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    parcela = _nueva(api, sesion, operador, productor)
    declarar(sesion, parcela, operador, tenencia_tipo="poseedor")
    api.como(cuenta)
    assert _variable(_leg(api, parcela, "/mi/parcelas"), "tenencia_tipo")["valor"] == "poseedor"
    r = api.post(f"/parcelas/{parcela.id}/perfil", json={"variable": "usa_riego", "valor": "no"})
    assert r.status_code == 403


# ---------- Tenencia ----------


def test_poseedor_con_constancia_de_posesion(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **(PERFIL_BASE | {"tenencia_tipo": "poseedor"}))
    documento_legal(sesion, parcela, "constancia_posesion", operador)
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "tenencia")["estado"] == "sustentado"
    assert _req(leg, "tenencia")["sustento_nivel"] == "documentado"
    assert "tenencia_solo_posesion" in leg["alertas"]
    assert "tenencia_solo_posesion" in api.get(f"/parcelas/{parcela.id}").json()["alertas"]


def test_poseedor_solo_con_declaracion_jurada_se_habilita_con_nota(api, sesion, operador, admin, productor):
    parcela = _nueva(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor, tenencia_tipo="poseedor")
    documento_legal(
        sesion,
        parcela,
        "declaracion_jurada_tenencia",
        operador,
        emitido=hoy_lima() - timedelta(days=10),
        vence=legalidad.vencimiento_declaracion(hoy_lima() - timedelta(days=10)),
    )
    leg = _leg(api.como(operador), parcela)
    tenencia = _req(leg, "tenencia")
    assert (tenencia["estado"], tenencia["sustento_nivel"]) == ("sustentado", "declarado")
    assert "tenencia_sin_documento_formal" in leg["alertas"]
    assert tenencia["plantilla"] == "declaracion-jurada-tenencia"
    sin_nota = api.como(admin).post(f"/parcelas/{parcela.id}/habilitar", json={})
    assert sin_nota.status_code == 422 and sin_nota.json()["error"]["codigo"] == "nota_requerida"
    assert _habilitar(api, admin, parcela).json()["estado"] == "habilitada"


def test_poseedor_sin_sustento_no_se_habilita(api, sesion, operador, admin, productor):
    parcela = _nueva(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor, tenencia_tipo="poseedor")
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "tenencia")["estado"] == "sin_sustento"
    assert _compuerta(leg)["tenencia_sustentada"] is False
    assert _habilitar(api, admin, parcela).json()["error"]["faltan"] == ["tenencia_sustentada"]


def test_declaracion_jurada_de_hace_13_meses_vence_y_la_parcela_pasa_a_observada(
    api, sesion, operador, admin, productor
):
    parcela = _nueva(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor, tenencia_tipo="poseedor")
    dj = documento_legal(sesion, parcela, "declaracion_jurada_tenencia", operador, emitido=hoy_lima())
    dj.fecha_vencimiento = legalidad.vencimiento_declaracion(hoy_lima())
    sesion.flush()
    assert _habilitar(api, admin, parcela).json()["estado"] == "habilitada"
    # La misma declaración, firmada hace 13 meses: venció a los 12.
    dj.fecha_emision = HACE_13_MESES
    dj.fecha_vencimiento = legalidad.vencimiento_declaracion(HACE_13_MESES)
    sesion.flush()
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "tenencia")["estado"] == "vencido"
    assert api.get(f"/parcelas/{parcela.id}").json()["habilitacion_estado"] == "observada"


def test_comunal_tercero_con_declaracion_jurada_queda_sin_sustento(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **(PERFIL_BASE | {"tenencia_tipo": "comunal_tercero"}))
    documento_legal(sesion, parcela, "declaracion_jurada_tenencia", operador, emitido=hoy_lima())
    assert _req(_leg(api.como(operador), parcela), "tenencia")["estado"] == "sin_sustento"


def test_comunal_miembro_solo_con_declaracion_jurada(api, sesion, operador, admin, productor):
    parcela = _nueva(api, sesion, operador, productor)
    _lista(
        sesion,
        parcela,
        operador,
        productor,
        tenencia_tipo="comunal_miembro",
        en_tierra_comunal=("si", {"comunidad_nombre": "Comunidad de prueba", "inscrita": "si"}),
    )
    documento_legal(sesion, parcela, "declaracion_jurada_tenencia", operador, emitido=hoy_lima())
    leg = _leg(api.como(operador), parcela)
    # La misma declaración sustenta la tenencia y el acuerdo con la comunidad (el orientador no le exige
    # documento formal al miembro).
    assert _req(leg, "tenencia")["estado"] == "sustentado"
    assert _req(leg, "acuerdo_comunal")["estado"] == "sustentado"
    assert "tenencia_sin_documento_formal" in leg["alertas"]
    assert _habilitar(api, admin, parcela).json()["estado"] == "habilitada"


def test_comunal_tercero_sin_acta_contrato_ni_constancia(api, sesion, operador, admin, productor):
    parcela = _nueva(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor, tenencia_tipo="comunal_tercero", en_tierra_comunal="si")
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "tenencia")["estado"] == "sin_sustento"
    assert _req(leg, "acuerdo_comunal")["estado"] == "sin_sustento"
    assert _habilitar(api, admin, parcela).status_code == 400


def test_propietario_en_tierra_comunal_sin_constancia_de_la_comunidad(
    api, sesion, operador, admin, productor
):
    parcela = _nueva(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor, en_tierra_comunal="si")
    documento_legal(sesion, parcela, "titulo_sunarp", operador)
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "tenencia")["estado"] == "sustentado"
    assert _req(leg, "acuerdo_comunal")["estado"] == "sin_sustento"
    assert _req(leg, "acuerdo_comunal")["plantilla"] == "constancia-comunal"
    assert _habilitar(api, admin, parcela).json()["error"]["faltan"] == ["permisos_obligatorios"]
    documento_legal(sesion, parcela, "constancia_comunal", operador)
    assert _habilitar(api, admin, parcela).json()["estado"] == "habilitada"


# ---------- Áreas protegidas y tierra forestal ----------


def test_dentro_de_un_area_protegida_sin_acuerdo_no_se_habilita(api, sesion, operador, admin, productor):
    parcela = _nueva(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor, en_anp="dentro")
    documento_legal(sesion, parcela, "titulo_sunarp", operador)
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "area_protegida")["estado"] == "sin_sustento"
    # La interfaz avisa si la tenencia no es un título habilitante; no lo impide.
    assert _variable(leg, "tenencia_tipo")["aviso"]
    assert _habilitar(api, admin, parcela).status_code == 400
    documento_legal(sesion, parcela, "acuerdo_conservacion", operador)
    assert _habilitar(api, admin, parcela).json()["estado"] == "habilitada"


def test_zona_de_amortiguamiento_no_pide_documento(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **(PERFIL_BASE | {"en_anp": "zona_de_amortiguamiento"}))
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "area_protegida")["estado"] == "no_aplica"
    assert "en_zona_de_amortiguamiento" in leg["alertas"]
    habilitacion = api.get(f"/parcelas/{parcela.id}/habilitacion").json()
    [detalle] = [d for d in habilitacion["detalle_alertas"] if d["codigo"] == "en_zona_de_amortiguamiento"]
    assert detalle["pestana"] == "legalidad"
    assert detalle["lineas"] == [
        "La parcela está en la zona de amortiguamiento de un área protegida: no pide documento."
    ]


def test_tierra_forestal_con_ccusaf_vigente(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **(PERFIL_BASE | {"en_tierra_forestal": "si"}))
    documento_legal(sesion, parcela, "cusaf", operador, vence=hoy_lima() + timedelta(days=900))
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "tierra_forestal")["estado"] == "sustentado"
    assert _req(leg, "tierra_forestal")["por_excepcion"] is False


def test_tierra_forestal_con_constancia_de_2019_se_sustenta_por_la_excepcion(api, sesion, operador, parcela):
    declarar(
        sesion, parcela, operador, **(PERFIL_BASE | {"tenencia_tipo": "poseedor", "en_tierra_forestal": "si"})
    )
    documento_legal(sesion, parcela, "constancia_posesion", operador, emitido=date(2019, 3, 1))
    api.como(operador)
    leg = _leg(api, parcela)
    forestal = _req(leg, "tierra_forestal")
    assert (forestal["estado"], forestal["por_excepcion"]) == ("sustentado", True)
    assert "tierra_forestal_por_excepcion" in leg["alertas"]
    # Se pregunta la reserva de 30 % de bosque y el perfil no está completo sin ella.
    assert _variable(leg, "reserva_bosque_30")["se_pregunta"] is True
    assert leg["perfil_completo"] is False
    r = api.post(f"/parcelas/{parcela.id}/perfil", json={"variable": "reserva_bosque_30", "valor": "si"})
    assert r.json()["perfil_completo"] is True


@pytest.mark.parametrize(
    ("tipo", "emitido", "clase", "por_excepcion"),
    [
        ("constancia_posesion", date(2024, 1, 11), None, True),
        ("constancia_posesion", date(2024, 1, 12), None, False),
        ("titulo_no_inscrito", date(2019, 1, 1), "titulo_formalizacion", True),
        ("titulo_no_inscrito", date(2019, 1, 1), "minuta", False),
        ("constancia_saneamiento_31145", date(2025, 6, 1), None, True),
    ],
)
def test_la_excepcion_de_la_ley_31973(api, sesion, operador, parcela, tipo, emitido, clase, por_excepcion):
    """Decisiones del 2026-10-09: corte el 12/01/2024, solo el título de formalización y la Ley N.º 31145."""
    declarar(sesion, parcela, operador, **(PERFIL_BASE | {"en_tierra_forestal": "si"}))
    documento_legal(sesion, parcela, tipo, operador, emitido=emitido, clase=clase)
    assert _req(_leg(api.como(operador), parcela), "tierra_forestal")["por_excepcion"] is por_excepcion


def test_tierra_forestal_con_constancia_de_2025_sin_ccusaf_no_se_habilita(
    api, sesion, operador, admin, productor
):
    parcela = _nueva(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor, tenencia_tipo="poseedor", en_tierra_forestal="si")
    documento_legal(sesion, parcela, "constancia_posesion", operador, emitido=date(2025, 2, 1))
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "tierra_forestal")["estado"] == "sin_sustento"
    assert _habilitar(api, admin, parcela).json()["error"]["faltan"] == ["permisos_obligatorios"]


def test_fuera_de_tierra_forestal_no_se_pide_ccusaf(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **PERFIL_BASE)
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "tierra_forestal")["estado"] == "no_aplica"
    assert all(r["estado"] == "no_aplica" for r in leg["requisitos"] if r["codigo"] != "tenencia")


def test_sin_zonificacion_no_aplica_y_avisa(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **(PERFIL_BASE | {"en_tierra_forestal": "sin_zonificacion"}))
    leg = _leg(api.como(operador), parcela)
    assert _req(leg, "tierra_forestal")["estado"] == "no_aplica"
    assert "zonificacion_forestal_desconocida" in leg["alertas"]


# ---------- Requisitos que no bloquean ----------


def test_parcela_de_12_ha_sin_ficha_tecnica_se_habilita_con_nota(api, sesion, operador, admin, productor):
    parcela = _nueva(api, sesion, operador, productor, rectangulo(400, 300), area_cultivada_ha="5")
    _lista(sesion, parcela, operador, productor)
    documento_legal(sesion, parcela, "titulo_sunarp", operador)
    leg = _leg(api.como(operador), parcela)
    instrumento = _req(leg, "instrumento_ambiental")
    assert instrumento["estado"] == "sin_sustento"
    assert [a["codigo"] for a in instrumento["aceptados"]] == [
        "ficha_tecnica_ambiental",
        "instrumento_ambiental",
    ]
    assert "requisito_sin_sustento" in leg["alertas"]
    sin_nota = api.como(admin).post(f"/parcelas/{parcela.id}/habilitar", json={})
    assert sin_nota.json()["error"]["codigo"] == "nota_requerida"
    assert _habilitar(api, admin, parcela).json()["estado"] == "habilitada"


def test_sin_riego_no_se_pide_licencia_de_agua(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **PERFIL_BASE)
    assert _req(_leg(api.como(operador), parcela), "agua_de_riego")["estado"] == "no_aplica"
    declarar(sesion, parcela, operador, usa_riego="si")
    assert _req(_leg(api, parcela), "agua_de_riego")["estado"] == "sin_sustento"


def test_faja_marginal_se_sustenta_con_una_nota(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **(PERFIL_BASE | {"junto_a_cuerpo_de_agua": "si"}))
    api.como(operador)
    assert _req(_leg(api, parcela), "faja_marginal")["estado"] == "sin_sustento"
    nota = "El cacao empieza a unos 40 m de la quebrada; la orilla tiene bosque ribereño."
    r = api.post(f"/parcelas/{parcela.id}/requisitos/faja_marginal/nota", json={"nota": nota})
    assert r.status_code == 200, r.text
    faja = _req(r.json(), "faja_marginal")
    assert (faja["estado"], faja["nota"], faja["sustento_nivel"]) == ("sustentado", nota, "declarado")


# ---------- Incidencias ----------


def test_incidencia_de_tenencia_abierta_observa_y_al_cerrarla_se_habilita(
    api, sesion, operador, admin, productor
):
    parcela = _nueva(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor)
    documento_legal(sesion, parcela, "titulo_sunarp", operador)
    assert _habilitar(api, admin, parcela).json()["estado"] == "habilitada"
    descripcion = "Un vecino reclama ante el juez de paz una franja de 20 m del lindero norte de la parcela."
    api.como(operador)
    corta = api.post(
        f"/parcelas/{parcela.id}/incidencias",
        json={"tipo": "tenencia", "descripcion": "Reclamo", "fuente": "Vecino"},
    )
    assert corta.status_code == 422
    r = api.post(
        f"/parcelas/{parcela.id}/incidencias",
        json={"tipo": "tenencia", "descripcion": descripcion, "fuente": "Juez de paz del caserío"},
    )
    assert r.status_code == 201, r.text
    leg = r.json()
    assert _compuerta(leg)["sin_conflicto_de_tenencia"] is False
    assert "incidencia_abierta" in leg["alertas"]
    assert api.get(f"/parcelas/{parcela.id}").json()["habilitacion_estado"] == "observada"

    incidencia_id = leg["incidencias"][0]["id"]
    assert api.post(f"/incidencias/{incidencia_id}/cerrar", json={"nota": "Se resolvió."}).status_code == 403
    cierre = "El juez de paz levantó un acta de conciliación: el lindero queda como figura en el plano."
    r = api.como(admin).post(f"/incidencias/{incidencia_id}/cerrar", json={"nota": cierre})
    assert r.status_code == 200, r.text
    assert r.json()["incidencias"][0]["estado"] == "cerrada"
    assert _habilitar(api, admin, parcela).json()["estado"] == "habilitada"


def test_incidencia_ambiental_no_bloquea(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **PERFIL_BASE)
    documento_legal(sesion, parcela, "titulo_sunarp", operador)
    incidencia(sesion, parcela, operador, tipo="ambiental")
    leg = _leg(api.como(operador), parcela)
    assert all(r["cumple"] for r in leg["compuerta"])
    assert "incidencia_abierta" in leg["alertas"]


def test_las_incidencias_y_el_perfil_no_se_borran(sesion, operador, parcela):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    declarar(sesion, parcela, operador, usa_riego="no")
    incidencia(sesion, parcela, operador)
    for sql in (
        "DELETE FROM parcela_variables",
        "UPDATE parcela_variables SET valor = 'si'",
        "DELETE FROM parcela_incidencias",
        "UPDATE parcela_incidencias SET descripcion = 'x'",
    ):
        with pytest.raises(DBAPIError), sesion.begin_nested():
            sesion.execute(text(sql))


# ---------- Plantillas ----------


def test_plantilla_de_declaracion_jurada(api, sesion, operador, productor, parcela):
    declarar(sesion, parcela, operador, tenencia_tipo="poseedor")
    r = api.como(operador).get(f"/parcelas/{parcela.id}/plantillas/declaracion-jurada-tenencia")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert f"declaracion-jurada-tenencia-{parcela.codigo}.pdf" in r.headers["content-disposition"]

    datos = {
        "productor": f"{productor.nombres} {productor.apellidos}",
        "dni": productor.dni,
        "codigo": parcela.codigo,
    }
    pdf = declaracion_tenencia.documento("declaracion_jurada_tenencia", datos, "poseedor")
    texto = "".join(pdf.textos)
    assert f"{productor.nombres} {productor.apellidos}" in texto and productor.dni in texto
    assert parcela.codigo in texto
    assert texto.count(declaracion_tenencia.MARCADA) == 1
    marcada = texto.index(declaracion_tenencia.MARCADA)
    assert texto[marcada : marcada + 40].find("Posesión") > 0
    assert "Anexo A, versión 1" in texto


def test_plantilla_solo_para_los_tipos_que_la_admiten(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, tenencia_tipo="comunal_tercero", en_tierra_comunal="no")
    api.como(operador)
    assert api.get(f"/parcelas/{parcela.id}/plantillas/declaracion-jurada-tenencia").status_code == 400
    assert api.get(f"/parcelas/{parcela.id}/plantillas/constancia-comunal").status_code == 400
    declarar(sesion, parcela, operador, en_tierra_comunal="si")
    assert api.get(f"/parcelas/{parcela.id}/plantillas/constancia-comunal").status_code == 200


def test_el_productor_descarga_su_plantilla(api, sesion, coop, operador):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    parcela = _nueva(api, sesion, operador, productor)
    declarar(sesion, parcela, operador, tenencia_tipo="propietario")
    r = api.como(cuenta).get(f"/mi/parcelas/{parcela.id}/plantillas/declaracion-jurada-tenencia")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_plantilla_de_demostracion_lleva_la_marca_de_agua():
    from app.pdf.base import TEXTO_DEMO

    pdf = declaracion_tenencia.documento("constancia_comunal", {}, "comunal_miembro", es_demo=True)
    assert TEXTO_DEMO in pdf.textos
    assert TEXTO_DEMO not in declaracion_tenencia.documento("constancia_comunal", {}, None).textos


# ---------- Documentos ----------


def _subir(api, ruta, tipo="titulo_sunarp", **campos):
    datos = {
        "tipo": tipo,
        "numero": "P-0001",
        "entidad_emisora": "SUNARP",
        "fecha_emision": "2019-05-10",
        **campos,
    }
    datos = {k: v for k, v in datos.items() if v is not None}
    return api.post(ruta, data=datos, files={"archivo": ("documento.pdf", PDF)})


def test_carga_de_documento_legal(api, operador, parcela):
    r = _subir(api.como(operador), f"/parcelas/{parcela.id}/documentos", fecha_vencimiento="2031-05-10")
    assert r.status_code == 201, r.text
    doc = r.json()
    assert (doc["numero"], doc["entidad_emisora"], doc["fecha_emision"]) == ("P-0001", "SUNARP", "2019-05-10")


@pytest.mark.parametrize(
    ("campos", "codigo"),
    [
        ({"numero": None}, "datos_legales_requeridos"),
        ({"fecha_emision": str(hoy_lima() + timedelta(days=1))}, "fecha_futura"),
        ({"fecha_vencimiento": "2019-01-01"}, "vencimiento_invalido"),
        ({"tipo": "titulo_no_inscrito"}, "clase_requerida"),
        ({"clase": "minuta"}, "clase_invalida"),
    ],
)
def test_documento_legal_con_datos_invalidos(api, operador, parcela, campos, codigo):
    r = _subir(api.como(operador), f"/parcelas/{parcela.id}/documentos", **campos)
    assert r.status_code == 422
    assert r.json()["error"]["codigo"] == codigo


def test_la_declaracion_jurada_no_pide_numero_y_vence_sola(api, operador, parcela):
    firma = hoy_lima() - timedelta(days=30)
    r = _subir(
        api.como(operador),
        f"/parcelas/{parcela.id}/documentos",
        tipo="declaracion_jurada_tenencia",
        numero=None,
        entidad_emisora=None,
        fecha_emision=str(firma),
    )
    assert r.status_code == 201, r.text
    assert r.json()["fecha_vencimiento"] == str(legalidad.vencimiento_declaracion(firma))
    sin_fecha = _subir(
        api,
        f"/parcelas/{parcela.id}/documentos",
        tipo="acta_comunal",
        numero=None,
        entidad_emisora=None,
        fecha_emision=None,
    )
    assert sin_fecha.json()["error"]["codigo"] == "datos_legales_requeridos"


@pytest.mark.parametrize("tipo", ["sunafil", "sunat", "zonificacion", "autorizacion_serfor"])
def test_los_tipos_anteriores_no_se_cargan(api, operador, parcela, tipo):
    assert _subir(api.como(operador), f"/parcelas/{parcela.id}/documentos", tipo=tipo).status_code == 422


def test_los_documentos_anteriores_se_conservan_y_no_sustentan(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **PERFIL_BASE)
    documento_legal(sesion, parcela, "sunafil", operador)
    leg = _leg(api.como(operador), parcela)
    assert [d["tipo"] for d in leg["documentos_anteriores"]] == ["sunafil"]
    assert _req(leg, "tenencia")["estado"] == "sin_sustento"


def test_ya_no_se_declaran_exenciones(api, admin, parcela):
    r = api.como(admin).post(f"/parcelas/{parcela.id}/exenciones", json={"tipo": "cusaf", "motivo": "x" * 40})
    assert r.status_code == 422
    assert r.json()["error"]["codigo"] == "exenciones_sin_efecto"


def test_cotejo_de_titulo_sunarp(api, sesion, operador, parcela):
    declarar(sesion, parcela, operador, **PERFIL_BASE)
    documento = documento_legal(sesion, parcela, "titulo_sunarp", operador)
    api.como(operador)
    assert _req(_leg(api, parcela), "tenencia")["sustento_nivel"] == "documentado"
    nota = "Consulté la partida en SUNARP en línea: titular y área coinciden."
    r = api.post(f"/documentos/{documento.id}/cotejo", json={"nota": nota})
    assert r.status_code == 200, r.text
    assert _req(_leg(api, parcela), "tenencia")["sustento_nivel"] == "verificado_en_fuente"
    assert api.post(f"/documentos/{documento.id}/cotejo", json={"nota": nota}).status_code == 400


def test_cotejo_sin_registro_consultable(api, sesion, operador, parcela):
    documento = documento_legal(sesion, parcela, "constancia_posesion", operador)
    r = api.como(operador).post(f"/documentos/{documento.id}/cotejo", json={"nota": "Consulté el registro."})
    assert r.status_code == 400
    assert r.json()["error"]["codigo"] == "sin_registro_consultable"


def test_registros_consultables_confirmados():
    """Confirmados con fuentes oficiales el 2026-10-09 (adenda 4, sección 6)."""
    consultables = {t.codigo for t in documentos_legales.TIPOS if t.registro_consultable}
    assert consultables == {"titulo_sunarp", "cusaf"}


def test_autorizacion_serfor_se_renombro(sesion):
    """La migración 0016 renombró autorizacion_serfor a autorizacion_cambio_uso sin perder archivos."""
    assert "autorizacion_serfor" not in documentos_legales.TODOS
    assert sesion.query(Documento).filter_by(tipo="autorizacion_serfor").count() == 0


# ---------- Aislamiento ----------


def test_otra_cooperativa_recibe_404(api, sesion, operador, parcela):
    i = incidencia(sesion, parcela, operador)
    declarar(sesion, parcela, operador, tenencia_tipo="poseedor")
    otra = factorias.cooperativa(sesion, "Coop B")
    admin_b = factorias.perfil(sesion, "admin_cooperativa", otra)
    api.como(admin_b)
    assert api.get(f"/parcelas/{parcela.id}/legalidad").status_code == 404
    assert (
        api.post(f"/parcelas/{parcela.id}/perfil", json={"variable": "usa_riego", "valor": "no"}).status_code
        == 404
    )
    assert (
        api.post(
            f"/parcelas/{parcela.id}/incidencias",
            json={"tipo": "otra", "descripcion": "x" * 60, "fuente": "Prensa local"},
        ).status_code
        == 404
    )
    assert (
        api.post(f"/incidencias/{i.id}/cerrar", json={"nota": "Se resolvió el reclamo."}).status_code == 404
    )
    assert api.get(f"/parcelas/{parcela.id}/plantillas/declaracion-jurada-tenencia").status_code == 404
    assert api.post(f"/parcelas/{parcela.id}/cruce").status_code == 404


# ---------- Cruce y declaración ----------


def test_declarar_no_sobre_un_cruce_si_es_422(api, sesion, operador, parcela):
    cruce(sesion, parcela, "en_tierra_comunal", "si", {"capas": ["idep_comunidades"], "comunidades": []})
    r = api.como(operador).post(
        f"/parcelas/{parcela.id}/perfil", json={"variable": "en_tierra_comunal", "valor": "no"}
    )
    assert r.status_code == 422
    assert r.json()["error"]["codigo"] == "valor_bajo_el_cruce"


def test_cruce_no_y_declaracion_si_manda_si(api, sesion, operador, parcela):
    cruce(sesion, parcela, "en_patrimonio_cultural", "no", {"capas": ["sigda_monumentos"], "monumentos": []})
    api.como(operador)
    sin_nota = api.post(
        f"/parcelas/{parcela.id}/perfil", json={"variable": "en_patrimonio_cultural", "valor": "si"}
    )
    assert sin_nota.json()["error"]["codigo"] == "nota_requerida"
    r = api.post(
        f"/parcelas/{parcela.id}/perfil",
        json={
            "variable": "en_patrimonio_cultural",
            "valor": "si",
            "nota": "El técnico vio restos de cerámica y un muro de piedra en la ladera de la parcela.",
        },
    )
    variable = _variable(r.json(), "en_patrimonio_cultural")
    assert (variable["valor"], variable["origen"], variable["declarado_sin_cruce"]) == (
        "si",
        "declarado",
        True,
    )
    assert variable["cruce"]["valor"] == "no"


def test_reserva_de_bosque_solo_con_la_excepcion(api, sesion, operador, parcela):
    r = api.como(operador).post(
        f"/parcelas/{parcela.id}/perfil", json={"variable": "reserva_bosque_30", "valor": "si"}
    )
    assert r.json()["error"]["codigo"] == "reserva_no_aplica"


def test_volver_a_cruzar(api, sesion, operador, parcela):
    parcela.cruce_solicitado_en = None
    sesion.flush()
    r = api.como(operador).post(f"/parcelas/{parcela.id}/cruce")
    assert r.status_code == 202, r.text
    assert r.json()["cruce"]["en_cola"] is True

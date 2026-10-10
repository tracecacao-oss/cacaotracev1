"""Parte 5: configuración, lugares, tandas, compuerta de la tanda, DOP y verificación pública."""

import json
import re
import threading
import time
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.fechas import ahora, dia_lima
from app.models import (
    Auditoria,
    ConfiguracionCooperativa,
    Cooperativa,
    Correlativo,
    DecisionTanda,
    Documento,
    Dop,
    Lugar,
    Parcela,
    Tanda,
)
from app.services import correlativos, sello
from tests import factorias
from tests.factorias import crear_parcela, rectangulo
from tests.habilitacion_util import (
    PDF,
    documento_legal,
    fuentes_configuradas,
    legalidad_completa,
    productor_listo,
)
from tests.habilitacion_util import analisis_completado as analisis_hecho

NOTA = "Se valida: el técnico confirmó en cancha el peso y la procedencia de la parcela del productor."
NOTA_HABILITAR = "Se habilita: expediente completo y análisis de las dos fuentes sin cambios desde 2021."
RUC = "20123456789"


@pytest.fixture
def fuentes():
    return fuentes_configuradas()


@pytest.fixture
def coop(sesion):
    coop = factorias.cooperativa(sesion, "Coop Recepción", codigo="CRP")
    sesion.add(ConfiguracionCooperativa(cooperativa_id=coop.id, tope_kg_seco_ha_anio=Decimal("2000")))
    sesion.flush()
    return coop


@pytest.fixture
def admin(sesion, coop):
    return factorias.perfil(sesion, "admin_cooperativa", coop)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def cancha(sesion, coop):
    lugar = Lugar(
        cooperativa_id=coop.id,
        nombre="Cancha central",
        tipo="cancha_acopio",
        departamento="SAN MARTIN",
        provincia="PICOTA",
        distrito="PICOTA",
    )
    sesion.add(lugar)
    sesion.flush()
    return lugar


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


def _parcela(api, sesion, operador, productor, nombre="Parcela de Recepción", este=0) -> Parcela:
    respuesta = crear_parcela(
        api.como(operador), productor.id, rectangulo(100, 100, este_m=este), nombre=nombre
    )
    assert respuesta.status_code == 201, respuesta.text
    return sesion.get(Parcela, uuid.UUID(respuesta.json()["id"]))


def _habilitada(api, sesion, admin, operador, productor, **kw) -> Parcela:
    parcela = _parcela(api, sesion, operador, productor, **kw)
    legalidad_completa(sesion, parcela, operador)
    productor_listo(sesion, productor, operador)
    analisis_hecho(sesion, parcela, "whisp")
    analisis_hecho(sesion, parcela, "gfw")
    respuesta = api.como(admin).post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA_HABILITAR})
    assert respuesta.status_code == 200, respuesta.text
    sesion.refresh(parcela)
    assert parcela.habilitacion_estado == "habilitada"
    return parcela


@pytest.fixture
def parcela(api, sesion, admin, operador, productor):
    return _habilitada(api, sesion, admin, operador, productor)


def _datos(productor, parcela, lugar, **cambios) -> dict:
    recibida = ahora() - timedelta(hours=1)
    dia = dia_lima(recibida)
    return {
        "productor_id": str(productor.id),
        "parcela_id": str(parcela.id),
        "lugar_id": str(lugar.id),
        "recibida_en": recibida.isoformat(),
        "estado_producto": "seco",
        "peso_kg": "100.00",
        "variedad": "ccn_51",
        "cosecha_desde": str(dia - timedelta(days=10)),
        "cosecha_hasta": str(dia - timedelta(days=3)),
        "doc_entrega_tipo": "guia_remision",
        "doc_entrega_numero": "T001-123",
        "doc_entrega_fecha_emision": str(dia),
        "doc_entrega_ruc_emisor": RUC,
    } | cambios


def _tanda(api, operador, productor, parcela, lugar, *, guia=True, **cambios) -> dict:
    respuesta = api.como(operador).post("/tandas", json=_datos(productor, parcela, lugar, **cambios))
    assert respuesta.status_code == 201, respuesta.text
    tanda = respuesta.json()
    if guia:
        subida = api.post(
            f"/tandas/{tanda['id']}/documentos", files={"archivo": ("guia.pdf", PDF, "application/pdf")}
        )
        assert subida.status_code == 201, subida.text
        tanda = subida.json()
    return tanda


# ---------- Configuración y lugares ----------


def test_configuracion_inicial_y_cambio(api, sesion, admin, operador):
    otra = factorias.cooperativa(sesion, "Coop Sin Configurar", codigo="CSC")
    nuevo_admin = factorias.perfil(sesion, "admin_cooperativa", otra)
    inicial = api.como(nuevo_admin).get("/configuracion").json()
    assert inicial["tope_kg_seco_ha_anio"] is None and inicial["lista"] is False
    assert (inicial["factor_baba_a_seco"], inicial["rendimiento_min"], inicial["rendimiento_max"]) == (
        "0.390",
        "0.330",
        "0.450",
    )
    assert (inicial["dias_max_cosecha_entrega_baba"], inicial["dias_max_cosecha_entrega_seco"]) == (7, 90)
    assert inicial["tolerancia_peso_guia_pct"] == "5.0"
    assert inicial["dias_max_emision_doc_entrega"] == 7
    assert (inicial["ruc_cooperativa"], inicial["tipo_organizacion"]) == (otra.ruc, "cooperativa_agraria")
    cambio = inicial | {"tope_kg_seco_ha_anio": "1800.00"}
    for clave in ("lista", "codigo_cooperativa", "ruc_cooperativa", "tipo_organizacion"):
        cambio.pop(clave)
    operador_b = factorias.perfil(sesion, "operador", otra)
    assert api.como(operador_b).put("/configuracion", json=cambio).status_code == 403
    respuesta = api.como(nuevo_admin).put("/configuracion", json=cambio)
    assert respuesta.status_code == 200 and respuesta.json()["lista"] is True
    fila = sesion.query(Auditoria).filter_by(accion="configuracion.cambiar").one()
    assert fila.detalle["tope_kg_seco_ha_anio"] == {"antes": None, "despues": "1800.00"}
    banda = cambio | {"rendimiento_min": "0.500", "rendimiento_max": "0.400"}
    assert api.put("/configuracion", json=banda).status_code == 422


def test_lugares(api, sesion, admin, operador):
    nuevo = {
        "nombre": "Cancha Norte",
        "tipo": "cancha_acopio",
        "departamento": "SAN MARTIN",
        "provincia": "PICOTA",
        "distrito": "PICOTA",
    }
    assert api.como(operador).post("/lugares", json=nuevo).status_code == 403
    creado = api.como(admin).post("/lugares", json=nuevo)
    assert creado.status_code == 201, creado.text
    assert api.post("/lugares", json=nuevo | {"nombre": "cancha norte"}).status_code == 409
    editado = api.patch(f"/lugares/{creado.json()['id']}", json={"activo": False})
    assert editado.json()["activo"] is False
    assert [lugar["nombre"] for lugar in api.como(operador).get("/lugares").json()] == ["Cancha Norte"]
    assert {a.accion for a in sesion.query(Auditoria).filter(Auditoria.accion.like("lugar.%"))} == {
        "lugar.crear",
        "lugar.editar",
    }


# ---------- Registro de la tanda ----------


def test_cooperativa_sin_tope_no_registra(api, sesion, cancha, operador, productor, parcela, coop):
    sesion.get(ConfiguracionCooperativa, coop.id).tope_kg_seco_ha_anio = None
    sesion.flush()
    respuesta = api.como(operador).post("/tandas", json=_datos(productor, parcela, cancha))
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "configuracion_incompleta"


def test_cooperativa_sin_codigo_no_registra(api, sesion, cancha, operador, productor, parcela, coop):
    coop.codigo = None
    sesion.flush()
    respuesta = api.como(operador).post("/tandas", json=_datos(productor, parcela, cancha))
    assert respuesta.json()["error"]["codigo"] == "configuracion_incompleta"


def test_productor_sin_afiliacion_activa(api, sesion, cancha, operador, parcela):
    ajeno = factorias.productor(sesion, factorias.cooperativa(sesion, "Coop Ajena", codigo="CAJ"))
    respuesta = api.como(operador).post("/tandas", json=_datos(ajeno, parcela, cancha))
    assert respuesta.status_code == 404


def test_parcela_de_otro_productor(api, sesion, coop, cancha, operador, parcela):
    otro = factorias.productor(sesion, coop)
    respuesta = api.como(operador).post("/tandas", json=_datos(otro, parcela, cancha))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "parcela_de_otro_productor"


def test_fechas_de_cosecha_y_guia(api, cancha, operador, productor, parcela):
    base = _datos(productor, parcela, cancha)
    recibida = dia_lima(ahora() - timedelta(hours=1))
    api.como(operador)
    despues = base | {"cosecha_hasta": str(recibida + timedelta(days=1))}
    assert api.post("/tandas", json=despues).status_code == 422
    invertida = base | {
        "cosecha_desde": str(recibida - timedelta(days=2)),
        "cosecha_hasta": str(recibida - timedelta(days=5)),
    }
    assert api.post("/tandas", json=invertida).status_code == 422
    guia_futura = base | {"doc_entrega_fecha_emision": str(recibida + timedelta(days=1))}
    respuesta = api.post("/tandas", json=guia_futura)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] in ("documento_fecha_invalida", "fecha_futura")
    futura = base | {"recibida_en": (ahora() + timedelta(days=1)).isoformat()}
    assert api.post("/tandas", json=futura).status_code == 422


@pytest.mark.parametrize(
    ("escrito", "guardado"),
    [("T001-123", "T001-123"), ("eg07-00045", "EG07-45"), ("001-0000456", "0001-456"), ("V0A1-9", "V0A1-9")],
)
def test_numero_de_guia_valido(api, cancha, operador, productor, parcela, escrito, guardado):
    tanda = _tanda(api, operador, productor, parcela, cancha, guia=False, doc_entrega_numero=escrito)
    assert tanda["doc_entrega_numero"] == guardado


@pytest.mark.parametrize("escrito", ["ABC-1", "T001-0", "T001", "T001-123456789", "0000-5", "EG09-1"])
def test_numero_de_guia_invalido(api, cancha, operador, productor, parcela, escrito):
    respuesta = api.como(operador).post(
        "/tandas", json=_datos(productor, parcela, cancha, doc_entrega_numero=escrito)
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "documento_numero_invalido"


def test_codigo_de_tanda_y_peso_seco_equivalente(api, cancha, operador, productor, parcela):
    tanda = _tanda(
        api, operador, productor, parcela, cancha, guia=False, estado_producto="baba", peso_kg="1000.00"
    )
    assert re.fullmatch(r"TD-\d{4}-000001", tanda["codigo"])
    assert tanda["peso_seco_equivalente_kg"] == "390.00"
    assert tanda["estado"] == "registrada"
    segunda = _tanda(api, operador, productor, parcela, cancha, guia=False)
    assert segunda["codigo"].endswith("-000002")


# ---------- Requisitos y alertas ----------


def _requisitos(tanda: dict) -> dict:
    return {r["codigo"]: r["cumple"] for r in tanda["requisitos"]}


def test_parcela_no_habilitada_no_se_valida(api, sesion, admin, cancha, operador, productor):
    pendiente = _parcela(api, sesion, operador, productor, nombre="Parcela Pendiente")
    tanda = _tanda(api, operador, productor, pendiente, cancha)
    assert _requisitos(tanda)["parcela_habilitada"] is False
    respuesta = api.post(f"/tandas/{tanda['id']}/validar", json={"nota": NOTA})
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "requisitos_incompletos"
    assert "parcela_habilitada" in respuesta.json()["error"]["faltan"]


def test_validar_sin_archivo_de_guia(api, cancha, operador, productor, parcela):
    tanda = _tanda(api, operador, productor, parcela, cancha, guia=False)
    respuesta = api.post(f"/tandas/{tanda['id']}/validar", json={})
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["faltan"] == ["documento_entrega_completo"]


def test_volumen_acumulado_y_tanda_anulada(api, cancha, operador, productor, parcela):
    # Tope 2000 kg/ha y 0.5 ha con cacao: más de 1000 kg secos en 365 días.
    previa = _tanda(api, operador, productor, parcela, cancha, guia=False, peso_kg="600.00")
    tanda = _tanda(api, operador, productor, parcela, cancha, peso_kg="500.00")
    assert "volumen_acumulado_excede_tope" in tanda["alertas"]
    assert tanda["alertas_detalle"]["kg_seco_por_ha_365_dias"] == "2200.00"
    anulada = api.post(f"/tandas/{previa['id']}/anular", json={"motivo": "Registrada dos veces"})
    assert anulada.json()["estado"] == "anulada"
    assert "volumen_acumulado_excede_tope" not in api.get(f"/tandas/{tanda['id']}").json()["alertas"]


def test_dias_entre_cosecha_y_entrega(api, cancha, operador, productor, parcela):
    recibida = dia_lima(ahora() - timedelta(hours=1))
    tanda = _tanda(
        api,
        operador,
        productor,
        parcela,
        cancha,
        estado_producto="baba",
        cosecha_desde=str(recibida - timedelta(days=12)),
        cosecha_hasta=str(recibida - timedelta(days=8)),
    )
    assert "dias_cosecha_entrega_altos" in tanda["alertas"]
    assert tanda["alertas_detalle"]["dias_cosecha_entrega"] == 8


def test_peso_de_la_guia_distinto(api, cancha, operador, productor, parcela):
    tanda = _tanda(api, operador, productor, parcela, cancha, doc_entrega_peso_kg="110.00")
    assert "peso_difiere_del_documento" in tanda["alertas"]
    assert tanda["alertas_detalle"]["diferencia_peso_documento_pct"] == "10.0"


def test_parcela_habilitada_con_alertas(api, sesion, cancha, operador, productor, parcela):
    # El área declarada difiere más de 20 % de la calculada: la parcela sigue habilitada, con alerta.
    parcela.area_declarada_ha = Decimal("5.0000")
    sesion.flush()
    tanda = _tanda(api, operador, productor, parcela, cancha)
    assert "parcela_con_alertas" in tanda["alertas"]
    assert "area_discrepante" in tanda["alertas_detalle"]["alertas_parcela"]
    assert tanda["parcela"]["habilitacion_estado"] == "habilitada"


def test_misma_guia_en_otro_productor(api, sesion, admin, coop, cancha, operador, productor, parcela):
    _tanda(api, operador, productor, parcela, cancha, guia=False)
    otro = factorias.productor(sesion, coop)
    de_otro = _habilitada(api, sesion, admin, operador, otro, nombre="Parcela del Vecino", este=500)
    tanda = _tanda(api, operador, otro, de_otro, cancha, guia=False)
    assert "documento_usado_por_otro_productor" in tanda["alertas"]


# ---------- Decisiones y DOP ----------


def test_validar_con_alertas_exige_nota(api, cancha, operador, productor, parcela):
    tanda = _tanda(api, operador, productor, parcela, cancha, doc_entrega_peso_kg="150.00")
    assert tanda["nota_obligatoria"] is True
    respuesta = api.post(f"/tandas/{tanda['id']}/validar", json={"nota": "corta"})
    assert respuesta.status_code == 422 and respuesta.json()["error"]["codigo"] == "nota_requerida"
    assert api.post(f"/tandas/{tanda['id']}/validar", json={"nota": NOTA}).status_code == 200


def _validada(api, sesion, operador, productor, parcela, cancha) -> tuple[dict, Dop]:
    tanda = _tanda(api, operador, productor, parcela, cancha)
    assert tanda["alertas"] == [], tanda["alertas"]
    respuesta = api.post(f"/tandas/{tanda['id']}/validar", json={})
    assert respuesta.status_code == 200, respuesta.text
    dop = sesion.query(Dop).filter_by(tanda_id=uuid.UUID(tanda["id"])).one()
    return respuesta.json(), dop


def test_validar_emite_el_dop(api, sesion, coop, cancha, operador, productor, parcela, storage_falso):
    tanda, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    assert tanda["estado"] == "validada"
    assert tanda["dop"] == {"id": str(dop.id), "codigo": dop.codigo, "estado": "vigente"}
    assert re.fullmatch(r"DOP-CRP-\d{4}-000001", dop.codigo)
    assert dop.contenido_sha256 == sello.huella(dop.contenido)
    pdf = sesion.get(Documento, dop.pdf_documento_id)
    assert (pdf.tipo, pdf.entidad, pdf.entidad_id) == ("dop_pdf", "dop", dop.id)
    assert storage_falso.archivos[pdf.ruta].startswith(b"%PDF")
    bloques = {
        "identificacion",
        "productor",
        "parcela",
        "habilitacion",
        "cobertura",
        "convergencia",
        "legalidad",
        "tanda",
        "alertas",
        "no_verificado",
    }
    assert bloques <= dop.contenido.keys()
    # Adenda 4: el DOP versión 5 sella la legalidad por requisito en lugar del expediente.
    assert dop.contenido["version"] == 5 and "expediente" not in dop.contenido
    assert dop.contenido["tanda"]["codigo"] == tanda["codigo"]
    assert dop.contenido["identificacion"]["misma_persona"] is True
    assert dop.contenido["habilitacion"]["decision"]["nota"] == NOTA_HABILITAR
    legalidad = dop.contenido["legalidad"]
    por_codigo = {r["codigo"]: r for r in legalidad["requisitos"]}
    assert len(por_codigo) == 8
    tenencia = por_codigo["tenencia"]
    assert (tenencia["estado"], tenencia["documento"]["tipo"]) == ("sustentado", "titulo_sunarp")
    assert por_codigo["tierra_forestal"]["estado"] == "no_aplica"
    assert {v["codigo"] for v in legalidad["perfil"]} >= {"tenencia_tipo", "en_anp", "usa_riego"}
    assert len(legalidad["capas"]) == 6
    assert {c["fuente"] for c in dop.contenido["cobertura"]} == {"whisp", "gfw"}
    acciones = [
        a.accion
        for a in sesion.query(Auditoria).filter(Auditoria.accion.in_(("tanda.validar", "dop.emitir")))
    ]
    assert sorted(acciones) == ["dop.emitir", "tanda.validar"]
    # Tras emitir, la tanda ya no cambia.
    assert api.patch(f"/tandas/{tanda['id']}", json={"peso_kg": "99.00"}).status_code == 400
    assert api.post(f"/tandas/{tanda['id']}/anular", json={"motivo": "x"}).status_code == 400
    guia = next(d for d in tanda["documentos"] if d["tipo"] == "documento_entrega")
    assert api.post(f"/documentos/{guia['id']}/anular", json={"motivo": "x"}).status_code == 400


def test_el_dop_lleva_la_decision_de_habilitar_vigente(
    api, sesion, admin, cancha, operador, productor, parcela
):
    """Una parcela habilitada dos veces: el DOP copia la decisión más reciente, no la primera."""
    titulo = sesion.query(Documento).filter_by(entidad_id=parcela.id, tipo="titulo_sunarp").one()
    titulo.fecha_vencimiento = dia_lima(ahora()) - timedelta(days=1)
    sesion.flush()
    assert api.como(admin).get(f"/parcelas/{parcela.id}").json()["habilitacion_estado"] == "observada"
    documento_legal(sesion, parcela, "titulo_sunarp", operador, vence=dia_lima(ahora()) + timedelta(days=365))
    nueva = "Se habilita de nuevo: el título vencido se reemplazó por uno vigente de la misma partida."
    assert api.post(f"/parcelas/{parcela.id}/habilitar", json={"nota": nueva}).status_code == 200
    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    assert dop.contenido["habilitacion"]["decision"]["nota"] == nueva
    assert "evidencia_revision_id" not in dop.contenido["habilitacion"]["decision"]


def test_falla_el_pdf_y_nada_queda(api, sesion, cancha, operador, productor, parcela, monkeypatch):
    from app.pdf import dop as pdf_dop

    tanda = _tanda(api, operador, productor, parcela, cancha)

    def falla(*args, **kwargs):
        raise RuntimeError("fpdf2 no pudo generar el PDF")

    monkeypatch.setattr(pdf_dop, "generar", falla)
    assert api.post(f"/tandas/{tanda['id']}/validar", json={}).status_code == 500
    sesion.expire_all()
    assert sesion.get(Tanda, uuid.UUID(tanda["id"])).estado == "registrada"
    assert sesion.query(Dop).count() == 0
    assert sesion.query(DecisionTanda).filter_by(tanda_id=uuid.UUID(tanda["id"])).count() == 0


def test_misma_huella_al_canonizar_dos_veces(api, sesion, cancha, operador, productor, parcela):
    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    copia = json.loads(json.dumps(dop.contenido))
    assert sello.canonico(copia) == sello.canonico(dop.contenido)
    sesion.expire(dop)
    assert sello.huella(sesion.get(Dop, dop.id).contenido) == dop.contenido_sha256  # tras pasar por jsonb


def test_el_contenido_sellado_no_cambia(api, sesion, cancha, operador, productor, parcela):
    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(text("UPDATE dops SET contenido = '{}'::jsonb WHERE id = :i"), {"i": dop.id})
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(text("DELETE FROM dops WHERE id = :i"), {"i": dop.id})
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(
            text("UPDATE decisiones_tanda SET nota = 'x' WHERE tanda_id = :i"), {"i": dop.tanda_id}
        )


def test_editar_el_productor_no_altera_el_dop(api, sesion, cancha, operador, productor, parcela):
    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    antes = dict(dop.contenido)
    respuesta = api.patch(f"/productores/{productor.id}", json={"direccion_postal": "Jr. Nuevo 123"})
    assert respuesta.status_code == 200, respuesta.text
    sesion.expire(dop)
    assert sesion.get(Dop, dop.id).contenido == antes


def test_observar_corregir_y_validar(api, sesion, cancha, operador, productor, parcela):
    tanda = _tanda(api, operador, productor, parcela, cancha, peso_kg="80.00")
    observada = api.post(
        f"/tandas/{tanda['id']}/observar", json={"motivo": "El peso no coincide con la guía"}
    )
    assert observada.json()["estado"] == "observada"
    assert api.post(f"/tandas/{tanda['id']}/observar", json={"motivo": "otra vez"}).status_code == 400
    corregida = api.patch(f"/tandas/{tanda['id']}", json={"peso_kg": "100.00"})
    assert corregida.json()["peso_kg"] == "100.00"
    validada = api.post(f"/tandas/{tanda['id']}/validar", json={})
    assert validada.status_code == 200, validada.text
    assert [d["decision"] for d in validada.json()["decisiones"]] == ["observar", "validar"]
    edicion = sesion.query(Auditoria).filter_by(accion="tanda.editar").one()
    assert edicion.detalle["peso_kg"] == {"antes": "80.00", "despues": "100.00"}


def test_anular_el_dop(api, sesion, admin, cancha, operador, productor, parcela):
    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    assert (
        api.como(operador).post(f"/dops/{dop.id}/anular", json={"motivo": "Peso mal digitado"}).status_code
        == 403
    )
    anulado = api.como(admin).post(f"/dops/{dop.id}/anular", json={"motivo": "Peso mal digitado"})
    assert anulado.status_code == 200 and anulado.json()["estado"] == "anulado"
    assert api.post(f"/dops/{dop.id}/anular", json={"motivo": "otra"}).status_code == 400
    publico = api.get(f"/publico/dops/{dop.codigo}").json()
    assert publico["estado"] == "anulado"
    # La tanda sigue validada como registro, pero cuenta como anulada en el volumen acumulado.
    assert sesion.get(Tanda, dop.tanda_id).estado == "validada"
    nueva = _tanda(api, operador, productor, parcela, cancha, peso_kg="950.00", guia=False)
    assert nueva["alertas_detalle"]["volumen_acumulado_kg_seco"] == "950.00"


def test_detalle_y_pdf_del_dop(api, sesion, cancha, operador, productor, parcela):
    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    detalle = api.get(f"/dops/{dop.id}").json()
    assert detalle["url_verificacion"].endswith(f"/#/verificar/dop/{dop.codigo}")
    assert detalle["qr"] and set("".join(detalle["qr"])) <= {"0", "1"}
    assert detalle["contenido_sha256"] == dop.contenido_sha256
    url = api.get(f"/dops/{dop.id}/pdf").json()["url"]
    assert f"download={dop.codigo}.pdf" in url
    assert [d["codigo"] for d in api.get("/dops").json()] == [dop.codigo]


def test_el_croquis_de_una_parcela_punto():
    """fpdf2 2.8 llama radius al radio del círculo: el croquis de un punto no debe fallar."""
    from app.pdf.base import Documento

    pdf = Documento("DOP-PRUEBA")
    pdf.add_page()
    nota = pdf.croquis({"type": "Point", "coordinates": [-76.55, -6.95]}, 10, 10, 40)
    assert nota.startswith("Punto en") and bytes(pdf.output()).startswith(b"%PDF")


def test_el_pdf_no_usa_frases_prohibidas(api, sesion, cancha, operador, productor, parcela):
    from app.pdf import dop as pdf_dop
    from app.services.dops import LEYENDA, url_verificacion
    from tests.test_analisis import PROHIBIDAS

    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    documento = pdf_dop.documento(dop.contenido, dop.contenido_sha256, url_verificacion(dop.codigo))
    documento.output()
    escrito = "\n".join(documento.textos)
    assert dop.codigo in escrito and dop.contenido_sha256 in escrito and "Página 1 de" in escrito
    assert LEYENDA in escrito.replace("\n", " ")  # la leyenda obligatoria, la única excepción
    assert not PROHIBIDAS.search(escrito.replace(LEYENDA, ""))


def test_un_dop_anterior_a_la_adenda_4_se_lee_igual(api, sesion, cancha, operador, productor, parcela):
    """Adenda 4, sección 13: los DOP emitidos antes de la migración conservan su expediente y su huella, y su
    PDF se sigue armando con las siete casillas."""
    from app.pdf import dop as pdf_dop
    from app.services.dops import url_verificacion

    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    anterior = {k: v for k, v in dop.contenido.items() if k != "legalidad"} | {
        "version": 4,
        "expediente": {
            "estado": "completo",
            "faltan": [],
            "casillas": [
                {
                    "codigo": "titulo_sunarp",
                    "nombre": "Título de propiedad inscrito en SUNARP",
                    "estado": "vigente",
                    "cubierta_por": None,
                    "cubierta_por_nombre": None,
                    "nivel": "documentado",
                    "registro_consultable": True,
                    "documento": {
                        "numero": "P-1",
                        "entidad_emisora": "SUNARP",
                        "fecha_emision": "2019-01-01",
                        "fecha_vencimiento": None,
                        "cotejado_en": None,
                        "sha256": "ab" * 32,
                    },
                    "exencion": None,
                }
            ],
        },
    }
    huella = sello.huella(anterior)
    documento = pdf_dop.documento(anterior, huella, url_verificacion(dop.codigo))
    documento.output()
    escrito = "\n".join(documento.textos)
    assert "Expediente legal" in escrito and "Legalidad de la parcela" not in escrito
    assert sello.huella(anterior) == huella


def test_el_pdf_de_demostracion_lleva_la_marca(api, sesion, cancha, operador, productor, parcela):
    from app.pdf import dop as pdf_dop
    from app.pdf.base import TEXTO_DEMO
    from app.services.dops import url_verificacion

    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    assert dop.contenido["es_demo"] is False
    url = url_verificacion(dop.codigo)
    real = pdf_dop.documento(dop.contenido, dop.contenido_sha256, url)
    real.output()
    assert TEXTO_DEMO not in real.textos
    demo = pdf_dop.documento(dop.contenido | {"es_demo": True}, dop.contenido_sha256, url)
    demo.output()
    # Una vez por página (pasa dos veces por normalize_text: ancho y texto), más el aviso del encabezado.
    # Puede pasar más veces: antes de un salto de página, fpdf2 ensaya en borrador si una fila de tabla
    # cabe, y ese ensayo también pasa por el encabezado.
    assert demo.textos.count(TEXTO_DEMO) >= 2 * demo.pages_count + 1


# ---------- Adenda 3: documento de entrega ----------


def _liquidacion(productor, parcela, lugar, coop, *, dias_recepcion=0, dias_emision=0, **cambios) -> dict:
    """Tanda recibida hace `dias_recepcion` días; su liquidación, `dias_emision` días después."""
    recibida = ahora() - timedelta(days=dias_recepcion, hours=1)
    dia = dia_lima(recibida)
    return (
        _datos(
            productor,
            parcela,
            lugar,
            recibida_en=recibida.isoformat(),
            cosecha_desde=str(dia - timedelta(days=10)),
            cosecha_hasta=str(dia - timedelta(days=3)),
            doc_entrega_tipo="liquidacion_compra",
            doc_entrega_numero="L001-45",
            doc_entrega_fecha_emision=str(dia + timedelta(days=dias_emision)),
            doc_entrega_ruc_emisor=coop.ruc,
        )
        | cambios
    )


def _registrada(api, operador, datos, *, archivo=True) -> dict:
    respuesta = api.como(operador).post("/tandas", json=datos)
    assert respuesta.status_code == 201, respuesta.text
    tanda = respuesta.json()
    if archivo:
        subida = api.post(
            f"/tandas/{tanda['id']}/documentos",
            files={"archivo": ("liquidacion.pdf", PDF, "application/pdf")},
        )
        assert subida.status_code == 201, subida.text
        tanda = subida.json()
    return tanda


@pytest.mark.parametrize("tipo", ["guia_remision", "liquidacion_compra"])
def test_cada_tipo_de_documento_completo_se_valida(
    api, sesion, coop, cancha, operador, productor, parcela, storage_falso, tipo
):
    from app.pdf import dop as pdf_dop
    from app.services.dops import url_verificacion

    if tipo == "guia_remision":
        tanda = _tanda(api, operador, productor, parcela, cancha)
        numero = "T001-123"
    else:
        tanda = _registrada(api, operador, _liquidacion(productor, parcela, cancha, coop))
        numero = "L001-45"
    assert tanda["doc_entrega_tipo"] == tipo
    assert tanda["alertas"] == [], tanda["alertas"]
    respuesta = api.post(f"/tandas/{tanda['id']}/validar", json={})
    assert respuesta.status_code == 200, respuesta.text
    dop = sesion.query(Dop).filter_by(tanda_id=uuid.UUID(tanda["id"])).one()
    bloque = dop.contenido["tanda"]["documento_entrega"]
    nombre = "Guía de remisión" if tipo == "guia_remision" else "Liquidación de compra"
    assert (bloque["tipo"], bloque["nombre_tipo"], bloque["numero"]) == (tipo, nombre, numero)
    assert "guia_remision" not in dop.contenido["tanda"]
    documento = pdf_dop.documento(dop.contenido, dop.contenido_sha256, url_verificacion(dop.codigo))
    documento.output()
    assert f"{nombre}, {numero}" in "\n".join(documento.textos)


def test_sin_documento_de_entrega_se_guarda_y_no_se_valida(api, cancha, operador, productor, parcela):
    sin_documento = {
        k: v for k, v in _datos(productor, parcela, cancha).items() if not k.startswith("doc_entrega_")
    }
    tanda = _registrada(api, operador, sin_documento, archivo=False)
    requisito = next(r for r in tanda["requisitos"] if r["codigo"] == "documento_entrega_completo")
    assert requisito["cumple"] is False and "tipo" in requisito["detalle"]
    respuesta = api.post(f"/tandas/{tanda['id']}/validar", json={})
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["faltan"] == ["documento_entrega_completo"]
    # Un número sin tipo no se acepta.
    sin_tipo = sin_documento | {"doc_entrega_numero": "T001-9"}
    respuesta = api.post("/tandas", json=sin_tipo)
    assert respuesta.status_code == 422 and respuesta.json()["error"]["codigo"] == "documento_tipo_requerido"


def test_liquidacion_con_ruc_de_otro_emisor(api, coop, cancha, operador, productor, parcela):
    datos = _liquidacion(productor, parcela, cancha, coop, doc_entrega_ruc_emisor="20111111111")
    respuesta = api.como(operador).post("/tandas", json=datos)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "emisor_no_corresponde"
    # Sin RUC, se llena con el de la organización.
    datos = _liquidacion(productor, parcela, cancha, coop, doc_entrega_ruc_emisor=None)
    assert _registrada(api, operador, datos, archivo=False)["doc_entrega_ruc_emisor"] == coop.ruc


def test_el_comprobante_de_la_ley_29972_no_se_acepta(api, cancha, operador, productor, parcela):
    """La Ley N.° 29972 está derogada (adenda 3, sección 12): ese tipo no existe en CacaoTrace."""
    datos = _datos(productor, parcela, cancha, doc_entrega_tipo="comprobante_operaciones_29972")
    assert api.como(operador).post("/tandas", json=datos).status_code == 422


@pytest.mark.parametrize(
    ("dias_recepcion", "dias_emision", "estado"), [(5, 3, 201), (12, 10, 422), (3, -1, 422)]
)
def test_plazo_de_la_liquidacion(
    api, coop, cancha, operador, productor, parcela, dias_recepcion, dias_emision, estado
):
    datos = _liquidacion(
        productor, parcela, cancha, coop, dias_recepcion=dias_recepcion, dias_emision=dias_emision
    )
    respuesta = api.como(operador).post("/tandas", json=datos)
    assert respuesta.status_code == estado, respuesta.text
    if estado == 422:
        assert respuesta.json()["error"]["codigo"] == "documento_fecha_invalida"


def test_el_plazo_de_la_configuracion_se_revisa_al_validar(
    api, sesion, coop, cancha, operador, admin, productor, parcela
):
    tanda = _registrada(
        api, operador, _liquidacion(productor, parcela, cancha, coop, dias_recepcion=6, dias_emision=5)
    )
    conf = sesion.get(ConfiguracionCooperativa, coop.id)
    conf.dias_max_emision_doc_entrega = 3
    sesion.flush()
    requisito = next(
        r
        for r in api.get(f"/tandas/{tanda['id']}").json()["requisitos"]
        if r["codigo"] == "documento_entrega_completo"
    )
    assert requisito["cumple"] is False and "3 días" in requisito["detalle"]


def test_liquidacion_a_productor_con_ruc(api, sesion, coop, cancha, operador, productor, parcela):
    productor.ruc = "10456789012"
    sesion.flush()
    tanda = _registrada(api, operador, _liquidacion(productor, parcela, cancha, coop))
    assert "liquidacion_con_productor_con_ruc" in tanda["alertas"]
    assert tanda["nota_obligatoria"] is True
    sin_nota = api.post(f"/tandas/{tanda['id']}/validar", json={})
    assert sin_nota.status_code == 422 and sin_nota.json()["error"]["codigo"] == "nota_requerida"


def test_misma_liquidacion_en_otro_productor(api, sesion, admin, coop, cancha, operador, productor, parcela):
    _registrada(api, operador, _liquidacion(productor, parcela, cancha, coop), archivo=False)
    otro = factorias.productor(sesion, coop)
    de_otro = _habilitada(api, sesion, admin, operador, otro, nombre="Parcela del Vecino", este=500)
    tanda = _registrada(api, operador, _liquidacion(otro, de_otro, cancha, coop), archivo=False)
    assert "documento_usado_por_otro_productor" in tanda["alertas"]
    # Una guía con el mismo número no es el mismo documento.
    guia = _datos(otro, de_otro, cancha, doc_entrega_numero="L001-45", doc_entrega_ruc_emisor=coop.ruc)
    respuesta = api.post("/tandas", json=guia)
    assert respuesta.status_code == 422  # "L001" no es una serie de guía


def test_un_dop_de_antes_de_la_adenda_se_sigue_leyendo(api, sesion, cancha, operador, productor, parcela):
    """Los DOP emitidos antes guardan el bloque "guia_remision": la pantalla y el PDF lo siguen mostrando."""
    from app.pdf import dop as pdf_dop
    from app.services.dops import url_verificacion

    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    antes = json.loads(json.dumps(dop.contenido))
    bloque = antes["tanda"].pop("documento_entrega")
    antes["tanda"]["guia_remision"] = {
        k: bloque[k]
        for k in ("numero", "fecha_emision", "ruc_emisor", "peso_kg", "documento_sha256", "nivel")
    } | {"registro_consultable": False}
    huella = sello.huella(antes)
    documento = pdf_dop.documento(antes, huella, url_verificacion(dop.codigo))
    documento.output()
    assert "Guía de remisión" in "\n".join(documento.textos)
    assert sello.huella(antes) == huella


def test_las_pantallas_dicen_documento_de_entrega():
    """Adenda 3 (7.5): "guía" solo aparece cuando el tipo es una guía, no en las pantallas de la tanda."""
    raiz = Path(__file__).resolve().parents[2] / "frontend" / "js"
    pantallas = ("tanda-nueva.js", "tanda.js", "recepcion.js", "mis-entregas.js", "configuracion.js")
    con_guia = [
        n
        for n in pantallas
        if re.search(r"gu[ií]a", (raiz / "pantallas" / n).read_text(encoding="utf-8"), re.I)
    ]
    assert con_guia == []


# ---------- Verificación pública ----------


def test_verificacion_publica(api, sesion, cancha, operador, productor, parcela, coop):
    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    api.headers.pop("Authorization", None)
    respuesta = api.get(f"/publico/dops/{dop.codigo.lower()}")
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "codigo": dop.codigo,
        "estado": "vigente",
        "emitido_en": respuesta.json()["emitido_en"],
        "contenido_sha256": dop.contenido_sha256,
        "cooperativa": coop.razon_social,
        "es_demo": False,
    }
    assert api.get("/publico/dops/DOP-NOEXISTE-2026-000001").status_code == 404


def test_limite_de_30_por_minuto(api):
    respuestas = [api.get("/publico/dops/DOP-XYZ-2026-000001").status_code for _ in range(31)]
    assert respuestas[:30] == [404] * 30
    assert respuestas[30] == 429


def test_limite_no_se_esquiva_cambiando_x_forwarded_for(api):
    # Detrás de Cloudflare, el primer valor de X-Forwarded-For lo pone quien llama; CF-Connecting-IP no.
    respuestas = [
        api.get(
            "/publico/dops/DOP-XYZ-2026-000001",
            headers={"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": f"198.51.100.{n}, 203.0.113.7"},
        ).status_code
        for n in range(31)
    ]
    assert respuestas[30] == 429
    otra = api.get("/publico/dops/DOP-XYZ-2026-000001", headers={"CF-Connecting-IP": "203.0.113.8"})
    assert otra.status_code == 404


# ---------- Productor y otra cooperativa ----------


def test_el_productor_ve_solo_lo_suyo(api, sesion, coop, admin, cancha, operador):
    duenio, cuenta = factorias.productor_con_acceso(sesion, coop)
    parcela = _habilitada(api, sesion, admin, operador, duenio)
    _, dop = _validada(api, sesion, operador, duenio, parcela, cancha)
    api.como(cuenta)
    assert [t["codigo"] for t in api.get("/mi/tandas").json()] == [dop.contenido["tanda"]["codigo"]]
    assert [d["codigo"] for d in api.get("/mi/dops").json()] == [dop.codigo]
    assert api.get(f"/mi/dops/{dop.id}").status_code == 200
    assert "download=" in api.get(f"/mi/dops/{dop.id}/pdf").json()["url"]
    otro, cuenta_otra = factorias.productor_con_acceso(sesion, coop)
    api.como(cuenta_otra)
    assert api.get(f"/mi/dops/{dop.id}").status_code == 404
    assert api.get(f"/mi/dops/{dop.id}/pdf").status_code == 404
    assert api.get("/mi/tandas").json() == []
    assert api.como(cuenta).post("/tandas", json={}).status_code == 403


def test_otra_cooperativa_no_ve_nada(api, sesion, cancha, operador, productor, parcela):
    tanda, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    otra = factorias.cooperativa(sesion, "Coop Vecina", codigo="CVE")
    admin_b = factorias.perfil(sesion, "admin_cooperativa", otra)
    api.como(admin_b)
    for ruta in (f"/tandas/{tanda['id']}", f"/dops/{dop.id}", f"/dops/{dop.id}/pdf"):
        assert api.get(ruta).status_code == 404, ruta
    assert api.get("/tandas").json() == [] and api.get("/dops").json() == []
    assert api.patch(f"/tandas/{tanda['id']}", json={"peso_kg": "1.00"}).status_code == 404
    assert api.post(f"/tandas/{tanda['id']}/observar", json={"motivo": "x"}).status_code == 404
    assert api.post(f"/dops/{dop.id}/anular", json={"motivo": "x"}).status_code == 404
    assert api.patch(f"/lugares/{cancha.id}", json={"activo": False}).status_code == 404
    assert api.get("/lugares").json() == []


# ---------- Código de la cooperativa ----------


def test_codigo_de_cooperativa_se_fija_una_vez(api, sesion):
    superadmin = factorias.perfil(sesion, "superadmin")
    antigua = factorias.cooperativa(sesion, "Coop de antes de la Parte 5")
    api.como(superadmin)
    assert api.patch(f"/admin/cooperativas/{antigua.id}", json={"codigo": "ant"}).json()["codigo"] == "ANT"
    respuesta = api.patch(f"/admin/cooperativas/{antigua.id}", json={"codigo": "OTRA"})
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "codigo_inmutable"
    tercera = factorias.cooperativa(sesion, "Coop Tercera")
    assert api.patch(f"/admin/cooperativas/{tercera.id}", json={"codigo": "ANT"}).status_code == 409
    assert api.patch(f"/admin/cooperativas/{tercera.id}", json={"codigo": "AB"}).status_code == 422


# ---------- Correlativos simultáneos ----------


def test_correlativos_simultaneos_no_se_repiten(base_disponible):
    """Dos validaciones a la vez: cada una toma el siguiente número con la fila bloqueada."""
    from app.db import engine

    with Session(engine) as s:
        coop = Cooperativa(
            razon_social=f"Coop Concurrencia {uuid.uuid4().hex[:6]}",
            ruc=f"209{uuid.uuid4().int % 10**8:08d}",
            departamento="SAN MARTIN",
            provincia="PICOTA",
            distrito="PICOTA",
            tipo_organizacion="cooperativa_agraria",
        )
        s.add(coop)
        s.commit()
        coop_id = coop.id
    numeros: list[int] = []
    barrera = threading.Barrier(2)

    def tomar():
        with Session(engine) as s:
            barrera.wait()
            numero = correlativos.siguiente(s, coop_id, "dop", 2026)
            time.sleep(0.2)  # el otro espera el bloqueo de la fila
            s.commit()
            numeros.append(numero)

    hilos = [threading.Thread(target=tomar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    try:
        assert sorted(numeros) == [1, 2]
    finally:
        with Session(engine) as s:
            s.query(Correlativo).filter_by(cooperativa_id=coop_id).delete()
            s.query(Cooperativa).filter_by(id=coop_id).delete()
            s.commit()


# Historial de MapBiomas como lo sella el DOP en los indicadores de la fuente (pedido del 2026-10-08).
HISTORIAL_MAPBIOMAS = {
    "clase_predominante_2020": "Mosaico agropecuario",
    "pixeles": 3,
    "anios": {"2019": {"21": 0.18, "24": 0.09}, "2020": {"21": 0.27}, "2021": {"21": 0.27}},
    "clases": {"21": "Mosaico agropecuario", "24": "Infraestructura urbana"},
    "clases_bosque": [],
}


def test_el_pdf_del_dop_lleva_el_uso_del_suelo_por_anio(api, sesion, cancha, operador, productor, parcela):
    from app.pdf import dop as pdf_dop
    from app.services.dops import url_verificacion

    _, dop = _validada(api, sesion, operador, productor, parcela, cancha)
    mapbiomas = {"fuente": "mapbiomas", "nombre": "MapBiomas Perú", "indicadores": HISTORIAL_MAPBIOMAS}
    contenido = dop.contenido | {"cobertura": [*dop.contenido["cobertura"], mapbiomas]}
    documento = pdf_dop.documento(contenido, dop.contenido_sha256, url_verificacion(dop.codigo))
    documento.output()
    escrito = "\n".join(documento.textos)
    assert "Uso del suelo por año (ha)" in escrito and "Píxeles de 30 m en la parcela: 3" in escrito
    # Las clases van de la de más área en 2020 a la de menos, con una columna por año.
    assert escrito.index("Mosaico agropecuario") < escrito.index("Infraestructura urbana")
    assert "0.2700" in escrito and "0.0900" in escrito and "2019" in escrito
    # Sin la serie, no hay tabla.
    sin_serie = pdf_dop.documento(dop.contenido, dop.contenido_sha256, url_verificacion(dop.codigo))
    sin_serie.output()
    assert "Uso del suelo por año (ha)" not in "\n".join(sin_serie.textos)

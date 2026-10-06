"""Parte 6: corridas de proceso, las 23 etapas, consolidación, tanda final, DPP y stock."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.fechas import ahora
from app.models import (
    Auditoria,
    ConfiguracionCooperativa,
    Corrida,
    Documento,
    Dop,
    Dpp,
    Parcela,
    TandaFinal,
)
from app.services.corridas import proporciones
from tests import factorias
from tests.factorias import crear_parcela, rectangulo
from tests.proceso_util import calidad, datos_de_etapa, lugar, registrar_todas, tanda_validada


@pytest.fixture
def coop(sesion):
    coop = factorias.cooperativa(sesion, "Coop Proceso", codigo="CPR")
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
    return lugar(sesion, coop.id, "Cancha central")


@pytest.fixture
def planta(sesion, coop):
    return lugar(sesion, coop.id, "Planta de beneficio", tipo="planta")


@pytest.fixture
def almacen(sesion, coop):
    return lugar(sesion, coop.id, "Almacén central", tipo="almacen")


@pytest.fixture
def grado(sesion, coop):
    return calidad(sesion, coop.id, "Grado 1")


def _parcela(api, sesion, operador, productor, este=0, estado="habilitada") -> Parcela:
    respuesta = crear_parcela(
        api.como(operador), productor.id, rectangulo(100, 100, este_m=este), nombre=f"Parcela {este}"
    )
    assert respuesta.status_code == 201, respuesta.text
    parcela = sesion.get(Parcela, uuid.UUID(respuesta.json()["id"]))
    parcela.habilitacion_estado = estado
    sesion.flush()
    return parcela


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


@pytest.fixture
def parcela(api, sesion, operador, productor):
    return _parcela(api, sesion, operador, productor)


@pytest.fixture
def tanda(sesion, operador, productor, parcela, cancha):
    return tanda_validada(sesion, operador, productor, parcela, cancha)


def _corrida(api, ruta="completa", manejo="mezclado") -> dict:
    respuesta = api.post("/corridas", json={"ruta": ruta, "tipo_manejo": manejo})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _armada(api, operador, tandas, ruta="completa", manejo="mezclado") -> dict:
    corrida = _corrida(api.como(operador), ruta, manejo)
    for t in tandas:
        respuesta = api.post(f"/corridas/{corrida['id']}/tandas", json={"tanda_id": str(t.id)})
        assert respuesta.status_code == 201, respuesta.text
    respuesta = api.post(f"/corridas/{corrida['id']}/iniciar")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _consolidar(api, corrida, almacen, **cambios):
    return api.post(
        f"/corridas/{corrida['id']}/consolidar",
        json={"humedad_pct": "7.0", "lugar_id": str(almacen.id)} | cambios,
    )


def _lista(api, operador, tandas, planta, grado, *, peso_final="400.00", ruta="completa") -> dict:
    corrida = _armada(api, operador, tandas, ruta=ruta)
    return registrar_todas(api, corrida, planta.id, calidad_id=grado.id, peso_final=peso_final)


# ---------- Crear y armar ----------


def test_crear_corrida_con_sus_23_etapas_y_la_plantilla(api, sesion, admin, operador, planta):
    plantilla = {
        "filas": [
            {"numero": 6, "lugar_id": str(planta.id), "metodo": "En carretilla", "distancia_m": "35.0"},
            {
                "numero": 12,
                "lugar_id": str(planta.id),
                "metodo": "Tendales de madera",
                "duracion_horas": "96",
            },
        ]
    }
    assert api.como(operador).put("/proceso/plantilla", json=plantilla).status_code == 403
    assert api.como(admin).put("/proceso/plantilla", json=plantilla).status_code == 200
    assert sesion.query(Auditoria).filter_by(accion="plantilla.cambiar").count() == 1
    corrida = _corrida(api.como(operador))
    assert corrida["codigo"].startswith("CP-") and corrida["estado"] == "abierta"
    etapas = {e["numero"]: e for e in corrida["etapas"]}
    assert sorted(etapas) == list(range(1, 24))
    assert {e["situacion"] for e in etapas.values()} == {"pendiente"}
    assert (etapas[6]["lugar_id"], etapas[6]["metodo"], etapas[6]["distancia_m"]) == (
        str(planta.id),
        "En carretilla",
        "35.0",
    )
    assert etapas[12]["plantilla"]["duracion_horas"] == "96.00"
    assert etapas[5]["datos"] == {"tipo_manejo": "mezclado"}
    assert len(api.get("/proceso/etapas").json()) == 23


def test_ruta_seco_salta_fermentacion_y_secado(api, operador, planta):
    corrida = _corrida(api.como(operador), ruta="seco")
    no_aplica = sorted(e["numero"] for e in corrida["etapas"] if e["situacion"] == "no_aplica")
    assert no_aplica == list(range(6, 15))


def test_sin_lugares_no_se_crea(api, sesion):
    otra = factorias.cooperativa(sesion, "Coop Sin Lugares", codigo="CSL")
    respuesta = api.como(factorias.perfil(sesion, "operador", otra)).post(
        "/corridas", json={"ruta": "completa", "tipo_manejo": "mezclado"}
    )
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "sin_lugares"


def test_reglas_de_ingreso(api, sesion, coop, operador, productor, parcela, cancha, tanda):
    corrida = _corrida(api.como(operador))
    ruta = f"/corridas/{corrida['id']}/tandas"
    seca = tanda_validada(sesion, operador, productor, parcela, cancha, producto="seco")
    respuesta = api.post(ruta, json={"tanda_id": str(seca.id)})
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "ruta_no_coincide"

    anulada = tanda_validada(sesion, operador, productor, parcela, cancha)
    dop = sesion.query(Dop).filter_by(tanda_id=anulada.id).one()
    dop.estado, dop.anulado_en, dop.anulado_por, dop.motivo_anulacion = (
        "anulado",
        ahora(),
        operador.id,
        "Error",
    )
    sesion.flush()
    respuesta = api.post(ruta, json={"tanda_id": str(anulada.id)})
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "tanda_no_disponible"

    assert api.post(ruta, json={"tanda_id": str(tanda.id)}).status_code == 201
    otra = _corrida(api)
    respuesta = api.post(f"/corridas/{otra['id']}/tandas", json={"tanda_id": str(tanda.id)})
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "tanda_en_otra_corrida"
    disponibles = api.get("/corridas/tandas-disponibles", params={"ruta": "completa"}).json()
    assert str(tanda.id) not in {d["tanda_id"] for d in disponibles}


def test_segregada_lleva_un_solo_productor(api, sesion, coop, operador, productor, parcela, cancha, tanda):
    otro = factorias.productor(sesion, coop)
    de_otro = tanda_validada(sesion, operador, otro, _parcela(api, sesion, operador, otro, este=500), cancha)
    corrida = _corrida(api.como(operador), manejo="segregado")
    assert api.post(f"/corridas/{corrida['id']}/tandas", json={"tanda_id": str(tanda.id)}).status_code == 201
    respuesta = api.post(f"/corridas/{corrida['id']}/tandas", json={"tanda_id": str(de_otro.id)})
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "corrida_segregada"


def test_parcela_excluida_y_observada(api, sesion, operador, productor, cancha):
    excluida = _parcela(api, sesion, operador, productor, este=500, estado="excluida")
    observada = _parcela(api, sesion, operador, productor, este=1000, estado="observada")
    t_excluida = tanda_validada(sesion, operador, productor, excluida, cancha)
    t_observada = tanda_validada(sesion, operador, productor, observada, cancha)
    corrida = _corrida(api.como(operador))
    respuesta = api.post(f"/corridas/{corrida['id']}/tandas", json={"tanda_id": str(t_excluida.id)})
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "parcela_excluida"
    respuesta = api.post(f"/corridas/{corrida['id']}/tandas", json={"tanda_id": str(t_observada.id)})
    assert respuesta.status_code == 201
    assert "tanda_de_parcela_observada" in respuesta.json()["alertas"]


def test_iniciar_y_la_lista_de_tandas_no_cambia(api, sesion, operador, productor, parcela, cancha, tanda):
    corrida = _corrida(api.como(operador))
    respuesta = api.post(f"/corridas/{corrida['id']}/iniciar")
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "corrida_sin_tandas"
    api.post(f"/corridas/{corrida['id']}/tandas", json={"tanda_id": str(tanda.id)})
    iniciada = api.post(f"/corridas/{corrida['id']}/iniciar").json()
    assert iniciada["estado"] == "en_proceso"
    etapas = {e["numero"]: e for e in iniciada["etapas"]}
    assert {etapas[n]["situacion"] for n in (1, 3, 4)} == {"registrada"}
    assert etapas[1]["datos"]["tandas"][0]["codigo"] == tanda.codigo
    assert etapas[3]["datos"]["codigo_corrida"] == iniciada["codigo"]
    assert iniciada["fase"] == "ingreso" and iniciada["etapa_actual"] == 2
    otra = tanda_validada(sesion, operador, productor, parcela, cancha)
    respuesta = api.post(f"/corridas/{corrida['id']}/tandas", json={"tanda_id": str(otra.id)})
    assert respuesta.status_code == 400
    respuesta = api.patch(f"/corridas/{corrida['id']}/etapas/1", json={"metodo": "x"})
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "etapa_automatica"


# ---------- Etapas ----------


def test_reglas_de_las_etapas(api, operador, planta, tanda):
    corrida = _armada(api, operador, [tanda])
    ruta = f"/corridas/{corrida['id']}/etapas"
    momento = ahora() - timedelta(days=1)
    al_reves = datos_de_etapa(2, planta.id, momento) | {"fin": (momento - timedelta(hours=1)).isoformat()}
    respuesta = api.patch(f"{ruta}/2", json=al_reves)
    assert respuesta.status_code == 422 and respuesta.json()["error"]["codigo"] == "fin_antes_de_inicio"
    futura = datos_de_etapa(2, planta.id, ahora() + timedelta(days=1))
    assert api.patch(f"{ruta}/2", json=futura).json()["error"]["codigo"] == "fecha_futura"
    sin_distancia = datos_de_etapa(6, planta.id, momento)
    sin_distancia.pop("distancia_m")
    respuesta = api.patch(f"{ruta}/6", json=sin_distancia)
    assert respuesta.status_code == 422 and respuesta.json()["error"]["codigo"] == "distancia_requerida"
    respuesta = api.patch(f"{ruta}/9", json={"situacion": "no_ocurrio"})
    assert respuesta.status_code == 422 and respuesta.json()["error"]["codigo"] == "no_ocurrio_no_admitido"
    respuesta = api.patch(f"{ruta}/7", json={"situacion": "no_ocurrio"})
    assert respuesta.status_code == 200
    assert next(e for e in respuesta.json()["etapas"] if e["numero"] == 7)["situacion"] == "no_ocurrio"
    corrige = api.patch(f"{ruta}/2", json=datos_de_etapa(2, planta.id, momento))
    assert corrige.status_code == 200
    assert (
        api.patch(f"{ruta}/2", json=datos_de_etapa(2, planta.id, momento + timedelta(minutes=5))).status_code
        == 200
    )


def test_cada_correccion_se_audita(api, sesion, operador, planta, tanda):
    corrida = _armada(api, operador, [tanda])
    momento = ahora() - timedelta(days=1)
    api.patch(f"/corridas/{corrida['id']}/etapas/2", json=datos_de_etapa(2, planta.id, momento))
    api.patch(
        f"/corridas/{corrida['id']}/etapas/2", json=datos_de_etapa(2, planta.id, momento) | {"metodo": "Otro"}
    )
    filas = sesion.query(Auditoria).filter_by(accion="corrida.registrar_etapa").all()
    assert [f.detalle["correccion"] for f in filas] == [False, True]
    assert filas[1].detalle["cambios"]["metodo"] == {"antes": "Método de prueba", "despues": "Otro"}


def test_la_fase_avanza_sola(api, operador, planta, grado, tanda):
    corrida = _armada(api, operador, [tanda])
    assert corrida["fase"] == "ingreso"
    for numero in (2, 5):
        momento = ahora() - timedelta(days=3, hours=-numero)
        corrida = api.patch(
            f"/corridas/{corrida['id']}/etapas/{numero}", json=datos_de_etapa(numero, planta.id, momento)
        ).json()
    assert (corrida["fase"], corrida["etapa_actual"]) == ("fermentacion", 6)
    tablero = api.get("/corridas", params={"fase": "fermentacion"}).json()
    assert [c["codigo"] for c in tablero] == [corrida["codigo"]]


# ---------- Consolidación ----------


def test_consolidar_con_etapas_pendientes_o_fuera_de_orden(api, operador, planta, almacen, grado, tanda):
    corrida = registrar_todas(
        api, _armada(api, operador, [tanda]), planta.id, calidad_id=grado.id, salvo=(12,)
    )
    respuesta = _consolidar(api, corrida, almacen)
    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["codigo"] == "etapas_incompletas" and error["faltan"] == [
        "Etapa 12: Secado solar con volteos periódicos"
    ]
    temprano = ahora() - timedelta(days=4)
    api.patch(f"/corridas/{corrida['id']}/etapas/12", json=datos_de_etapa(12, planta.id, temprano))
    respuesta = _consolidar(api, corrida, almacen)
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "etapas_fuera_de_orden"


def test_consolidacion_dentro_de_la_banda(
    api, sesion, operador, planta, almacen, grado, tanda, storage_falso
):
    corrida = _lista(api, operador, [tanda], planta, grado, peso_final="400.00")
    assert corrida["rendimiento"]["rendimiento"] == "0.400" and corrida["rendimiento"]["alerta"] is None
    assert corrida["puede_consolidar"] is True
    respuesta = _consolidar(api, corrida, almacen)
    assert respuesta.status_code == 200, respuesta.text
    consolidada = respuesta.json()
    assert (consolidada["estado"], consolidada["fase"]) == ("consolidada", "stock")
    tf = sesion.get(TandaFinal, uuid.UUID(consolidada["tanda_final"]["id"]))
    assert (tf.estado, tf.peso_seco_kg, tf.saldo_kg, tf.calidad, tf.numero_sacos) == (
        "en_stock",
        Decimal("400.00"),
        Decimal("400.00"),
        "Grado 1",
        6,
    )
    dpp = sesion.query(Dpp).filter_by(corrida_id=uuid.UUID(corrida["id"])).one()
    assert dpp.estado == "vigente" and dpp.codigo.startswith("DPP-CPR-")
    pdf = sesion.get(Documento, dpp.pdf_documento_id)
    assert storage_falso.archivos[pdf.ruta].startswith(b"%PDF")
    assert {
        "identificacion",
        "entrada",
        "etapas",
        "salida",
        "rendimiento",
        "alertas",
        "no_verificado",
    } <= set(dpp.contenido)
    assert len(dpp.contenido["etapas"]) == 23
    acciones = {a.accion for a in sesion.query(Auditoria).all()}
    assert {
        "corrida.crear",
        "corrida.agregar_tanda",
        "corrida.iniciar",
        "corrida.registrar_etapa",
    } <= acciones
    assert {"corrida.consolidar", "dpp.emitir"} <= acciones
    stock = api.get("/tandas-finales").json()
    assert [(s["codigo"], s["saldo_kg"]) for s in stock] == [(tf.codigo, "400.00")]


@pytest.mark.parametrize(
    ("peso_final", "alerta"), [("500.00", "rendimiento_sobre_banda"), ("300.00", "rendimiento_bajo_banda")]
)
def test_rendimiento_fuera_de_banda_exige_explicacion(
    api, operador, planta, almacen, grado, tanda, peso_final, alerta
):
    corrida = _lista(api, operador, [tanda], planta, grado, peso_final=peso_final)
    assert corrida["rendimiento"]["alerta"] == alerta
    sin_explicacion = _consolidar(api, corrida, almacen)
    assert sin_explicacion.status_code == 422
    assert sin_explicacion.json()["error"]["codigo"] == "explicacion_requerida"
    explicacion = (
        "Se revisó la balanza y el registro de la baba: el peso final es el que se midió al envasar."
    )
    respuesta = _consolidar(api, corrida, almacen, explicacion=explicacion)
    assert respuesta.status_code == 200, respuesta.text
    dpp = api.get(f"/dpps/{respuesta.json()['dpp']['id']}").json()
    assert dpp["contenido"]["alertas"] == {"alertas": [alerta], "explicacion": explicacion}
    # La corrida consolidada sigue mostrando la alerta, tomada de su DPP sellado.
    assert respuesta.json()["alertas"] == [alerta]
    consolidadas = api.get("/corridas", params={"estado": "consolidada"}).json()
    assert consolidadas[0]["alertas"] == [alerta]


def test_ruta_seco_con_peso_final_mayor(
    api, sesion, operador, productor, parcela, cancha, planta, almacen, grado
):
    seca = tanda_validada(sesion, operador, productor, parcela, cancha, peso="500.00", producto="seco")
    corrida = _lista(api, operador, [seca], planta, grado, peso_final="520.00", ruta="seco")
    assert corrida["rendimiento"]["alerta"] == "peso_final_supera_entrada"
    assert _consolidar(api, corrida, almacen).status_code == 422
    explicacion = "El grano seco absorbió humedad en el almacén por la lluvia de la semana; se pesó de nuevo."
    assert _consolidar(api, corrida, almacen, explicacion=explicacion).status_code == 200


def test_proporciones_suman_exactamente_uno(
    api, sesion, operador, productor, parcela, cancha, planta, almacen, grado
):
    assert proporciones([Decimal("500"), Decimal("300"), Decimal("200")]) == [
        Decimal("0.500000"),
        Decimal("0.300000"),
        Decimal("0.200000"),
    ]
    raras = proporciones([Decimal("333.33"), Decimal("333.33"), Decimal("333.34")])
    assert sum(raras) == Decimal("1") and len(raras) == 3
    tandas = [
        tanda_validada(sesion, operador, productor, parcela, cancha, peso=p)
        for p in ("500.00", "300.00", "200.00")
    ]
    corrida = _lista(api, operador, tandas, planta, grado, peso_final="400.00")
    final = _consolidar(api, corrida, almacen).json()
    detalle = api.get(f"/tandas-finales/{final['tanda_final']['id']}").json()
    assert [c["proporcion"] for c in detalle["composicion"]] == ["0.500000", "0.300000", "0.200000"]
    assert [c["kg_atribuibles"] for c in detalle["composicion"]] == ["200.00", "120.00", "80.00"]


def test_falla_el_pdf_y_nada_cambia(api, sesion, operador, planta, almacen, grado, tanda, monkeypatch):
    from app.pdf import dpp as pdf_dpp

    corrida = _lista(api, operador, [tanda], planta, grado)

    def falla(*args, **kwargs):
        raise RuntimeError("fpdf2 no pudo generar el PDF")

    monkeypatch.setattr(pdf_dpp, "generar", falla)
    assert _consolidar(api, corrida, almacen).status_code == 500
    sesion.expire_all()
    assert sesion.get(Corrida, uuid.UUID(corrida["id"])).estado == "en_proceso"
    assert sesion.query(TandaFinal).count() == 0 and sesion.query(Dpp).count() == 0


def test_etapa_igual_a_la_plantilla_va_a_no_verificado(
    api, sesion, admin, operador, planta, almacen, grado, tanda
):
    api.como(admin).put(
        "/proceso/plantilla",
        json={"filas": [{"numero": 16, "lugar_id": str(planta.id), "metodo": "Método de prueba"}]},
    )
    corrida = _lista(api, operador, [tanda], planta, grado)
    assert next(e for e in corrida["etapas"] if e["numero"] == 16)["desde_plantilla"] is True
    assert next(e for e in corrida["etapas"] if e["numero"] == 15)["desde_plantilla"] is False
    dpp = (
        sesion.query(Dpp)
        .filter_by(id=uuid.UUID(_consolidar(api, corrida, almacen).json()["dpp"]["id"]))
        .one()
    )
    assert any(linea.startswith("Etapa 16 ") for linea in dpp.contenido["no_verificado"])
    assert not any(linea.startswith("Etapa 15 ") for linea in dpp.contenido["no_verificado"])


def test_peso_final_distinto_al_de_la_etapa_19(api, operador, planta, almacen, grado, tanda):
    corrida = _lista(api, operador, [tanda], planta, grado, peso_final="400.00")
    respuesta = _consolidar(api, corrida, almacen, peso_final_kg="410.00")
    assert respuesta.status_code == 422 and respuesta.json()["error"]["codigo"] == "peso_final_distinto"


# ---------- DPP ----------


def test_el_dpp_no_cambia_y_se_verifica_sin_token(api, sesion, operador, planta, almacen, grado, tanda):
    corrida = _lista(api, operador, [tanda], planta, grado)
    dpp_id = uuid.UUID(_consolidar(api, corrida, almacen).json()["dpp"]["id"])
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(text("UPDATE dpps SET contenido = '{}'::jsonb WHERE id = :i"), {"i": dpp_id})
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(text("DELETE FROM dpps WHERE id = :i"), {"i": dpp_id})
    dpp = sesion.get(Dpp, dpp_id)
    publico = api.get(f"/publico/dpps/{dpp.codigo.lower()}")
    assert publico.status_code == 200
    publicos = {"codigo", "estado", "emitido_en", "contenido_sha256", "cooperativa", "es_demo"}
    assert set(publico.json()) == publicos


def test_anular_el_dpp_y_consolidar_de_nuevo(api, sesion, admin, operador, planta, almacen, grado, tanda):
    corrida = _lista(api, operador, [tanda], planta, grado)
    primera = _consolidar(api, corrida, almacen).json()
    ruta = f"/dpps/{primera['dpp']['id']}/anular"
    assert api.post(ruta, json={"motivo": "Peso final mal digitado"}).status_code == 403
    anulado = api.como(admin).post(ruta, json={"motivo": "Peso final mal digitado"})
    assert anulado.json()["estado"] == "anulado"
    reabierta = api.get(f"/corridas/{corrida['id']}").json()
    assert reabierta["estado"] == "en_proceso"
    assert sesion.get(TandaFinal, uuid.UUID(primera["tanda_final"]["id"])).estado == "anulada"
    segunda = _consolidar(api, reabierta, almacen).json()
    assert segunda["dpp"]["codigo"] != primera["dpp"]["codigo"]
    assert segunda["tanda_final"]["codigo"] != primera["tanda_final"]["codigo"]
    assert [d["estado"] for d in segunda["dpps"]] == ["vigente", "anulado"]


def test_no_se_anula_un_dpp_con_saldo_usado(api, sesion, admin, operador, planta, almacen, grado, tanda):
    corrida = _lista(api, operador, [tanda], planta, grado)
    final = _consolidar(api, corrida, almacen).json()
    tf = sesion.get(TandaFinal, uuid.UUID(final["tanda_final"]["id"]))
    tf.saldo_kg = Decimal("150.00")
    sesion.flush()
    respuesta = api.como(admin).post(f"/dpps/{final['dpp']['id']}/anular", json={"motivo": "Prueba de saldo"})
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "tanda_final_usada"


def test_anular_una_corrida_libera_sus_tandas(api, sesion, operador, tanda):
    corrida = _armada(api, operador, [tanda])
    anulada = api.post(
        f"/corridas/{corrida['id']}/anular", json={"motivo": "Se armó con la tanda equivocada"}
    )
    assert anulada.json()["estado"] == "anulada"
    disponibles = api.get("/corridas/tandas-disponibles", params={"ruta": "completa"}).json()
    assert str(tanda.id) in {d["tanda_id"] for d in disponibles}
    otra = _corrida(api)
    assert api.post(f"/corridas/{otra['id']}/tandas", json={"tanda_id": str(tanda.id)}).status_code == 201


def test_el_dop_de_una_tanda_en_proceso_no_se_anula(api, sesion, admin, operador, tanda):
    _armada(api, operador, [tanda])
    dop = sesion.query(Dop).filter_by(tanda_id=tanda.id).one()
    respuesta = api.como(admin).post(f"/dops/{dop.id}/anular", json={"motivo": "Prueba"})
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "tanda_en_proceso"


def test_el_pdf_del_dpp_muestra_el_diagrama(api, sesion, operador, planta, almacen, grado, tanda):
    from app.pdf import dpp as pdf_dpp
    from app.services.dpps import LEYENDA, url_verificacion

    corrida = _lista(api, operador, [tanda], planta, grado)
    dpp = sesion.get(Dpp, uuid.UUID(_consolidar(api, corrida, almacen).json()["dpp"]["id"]))
    documento = pdf_dpp.documento(dpp.contenido, dpp.contenido_sha256, url_verificacion(dpp.codigo))
    documento.output()
    escrito = "\n".join(documento.textos)
    assert dpp.codigo in escrito and dpp.contenido_sha256 in escrito
    assert LEYENDA in escrito.replace("\n", " ")
    assert "Diagrama de análisis de proceso" in escrito
    for nombre in (
        "Recepción y pesaje en cancha de acopio",
        "Almacenamiento hasta consolidar el lote de exportación",
    ):
        assert nombre in escrito.replace("\n", " ")


def test_el_dpp_de_demostracion_lo_sella_y_lo_marca(api, sesion, operador, planta, almacen, grado, tanda):
    from app.pdf import dpp as pdf_dpp
    from app.pdf.base import TEXTO_DEMO
    from app.services.dpps import url_verificacion

    corrida = _lista(api, operador, [tanda], planta, grado)
    dpp = sesion.get(Dpp, uuid.UUID(_consolidar(api, corrida, almacen).json()["dpp"]["id"]))
    assert dpp.contenido["version"] == 2 and dpp.contenido["es_demo"] is False
    url = url_verificacion(dpp.codigo)
    demo = pdf_dpp.documento(dpp.contenido | {"es_demo": True}, dpp.contenido_sha256, url)
    demo.output()
    # Una vez por página; la marca pasa dos veces por normalize_text (su ancho y su texto).
    assert demo.textos.count(TEXTO_DEMO) == 2 * demo.pages_count >= 2
    real = pdf_dpp.documento(dpp.contenido, dpp.contenido_sha256, url)
    real.output()
    assert TEXTO_DEMO not in real.textos


# ---------- Calidades, productor y otra cooperativa ----------


def test_calidades(api, sesion, admin, operador):
    assert api.como(operador).post("/calidades", json={"nombre": "Grado 2"}).status_code == 403
    creada = api.como(admin).post("/calidades", json={"nombre": "Grado 2"})
    assert creada.status_code == 201
    assert api.post("/calidades", json={"nombre": "grado 2"}).status_code == 409
    desactivada = api.patch(f"/calidades/{creada.json()['id']}", json={"activo": False})
    assert desactivada.json()["activo"] is False


def test_sin_calidad_activa_no_se_consolida(api, sesion, operador, planta, almacen, grado, tanda):
    corrida = _lista(api, operador, [tanda], planta, grado)
    grado.activo = False
    sesion.flush()
    respuesta = _consolidar(api, corrida, almacen)
    assert respuesta.status_code == 400
    assert "calidad activa" in " ".join(respuesta.json()["error"]["faltan"])


def test_el_productor_ve_la_fase_de_su_cacao(api, sesion, coop, operador, cancha):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    parcela = _parcela(api, sesion, operador, productor, este=2000)
    tanda = tanda_validada(sesion, operador, productor, parcela, cancha)
    _armada(api, operador, [tanda])
    entregas = api.como(cuenta).get("/mi/tandas").json()
    assert entregas[0]["proceso"] == {"estado": "en_proceso", "fase": "ingreso", "fase_nombre": "Ingreso"}
    assert api.get("/corridas").status_code == 403
    assert api.get("/dpps").status_code == 403


def test_otra_cooperativa_no_ve_ni_opera(api, sesion, operador, planta, almacen, grado, tanda):
    corrida = _lista(api, operador, [tanda], planta, grado)
    final = _consolidar(api, corrida, almacen).json()
    otra = factorias.cooperativa(sesion, "Coop B", codigo="CBB")
    lugar(sesion, otra.id, "Cancha B")
    operador_b = factorias.perfil(sesion, "operador", otra)
    api.como(operador_b)
    assert api.get(f"/corridas/{corrida['id']}").status_code == 404
    assert api.post(f"/corridas/{corrida['id']}/anular", json={"motivo": "x"}).status_code == 404
    assert api.get(f"/dpps/{final['dpp']['id']}").status_code == 404
    assert api.get(f"/dpps/{final['dpp']['id']}/pdf").status_code == 404
    assert api.get(f"/tandas-finales/{final['tanda_final']['id']}").status_code == 404
    assert api.get("/corridas").json() == [] and api.get("/tandas-finales").json() == []
    propia = _corrida(api)
    respuesta = api.post(f"/corridas/{propia['id']}/tandas", json={"tanda_id": str(tanda.id)})
    assert respuesta.status_code == 404
    assert api.patch(f"/calidades/{grado.id}", json={"activo": False}).status_code == 403

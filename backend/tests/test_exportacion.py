"""Parte 7: importadores, órdenes de compra, lote de exportación con sugerencia FIFO, genealogía por parcela,
indicadores y trazabilidad en los dos sentidos."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.fechas import ahora
from app.models import Auditoria, Dop, Dpp, LoteGenealogia, Parcela, TandaFinal
from tests import factorias
from tests.exportacion_util import tanda_final
from tests.factorias import crear_parcela, rectangulo
from tests.proceso_util import calidad, lugar, tanda_validada

MOTIVO = "La tanda más antigua quedó reservada para un cliente nacional por acuerdo previo."


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion, "Coop Exporta", codigo="CEX")


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
def almacen(sesion, coop):
    return lugar(sesion, coop.id, "Almacén central", tipo="almacen")


@pytest.fixture
def grado(sesion, coop):
    return calidad(sesion, coop.id, "Grado 1")


@pytest.fixture
def grado2(sesion, coop):
    return calidad(sesion, coop.id, "Grado 2")


def _parcela(api, sesion, operador, productor, este) -> Parcela:
    respuesta = crear_parcela(
        api.como(operador), productor.id, rectangulo(100, 100, este_m=este), nombre=f"Parcela {este}"
    )
    assert respuesta.status_code == 201, respuesta.text
    return sesion.get(Parcela, uuid.UUID(respuesta.json()["id"]))


@pytest.fixture
def origen(api, sesion, coop, operador, cancha):
    """Dos productores y cuatro parcelas: P1 y P2 de uno, P3 y P4 del otro."""
    uno, dos = factorias.productor(sesion, coop), factorias.productor(sesion, coop)
    parcelas = {
        "P1": _parcela(api, sesion, operador, uno, 0),
        "P2": _parcela(api, sesion, operador, uno, 500),
        "P3": _parcela(api, sesion, operador, dos, 1000),
        "P4": _parcela(api, sesion, operador, dos, 1500),
    }
    duenos = {"P1": uno, "P2": uno, "P3": dos, "P4": dos}

    def tanda(nombre, peso):
        return tanda_validada(sesion, operador, duenos[nombre], parcelas[nombre], cancha, peso=peso)

    return {"parcelas": parcelas, "productores": (uno, dos), "tanda": tanda}


@pytest.fixture
def ejemplo(sesion, operador, grado, almacen, origen):
    """El ejemplo de la especificación: TF-A (1 de octubre) con P1 0.5, P2 0.3 y P3 0.2; TF-B (5 de octubre)
    con P1 0.6 y P4 0.4. Ambas de 400 kg y de la misma calidad."""
    t = origen["tanda"]
    hoy = ahora()
    tf_a = tanda_final(
        sesion,
        operador,
        grado,
        almacen,
        [t("P1", "500.00"), t("P2", "300.00"), t("P3", "200.00")],
        peso="400.00",
        ingreso=hoy - timedelta(days=10),
    )
    tf_b = tanda_final(
        sesion,
        operador,
        grado,
        almacen,
        [t("P1", "600.00"), t("P4", "400.00")],
        peso="400.00",
        ingreso=hoy - timedelta(days=6),
    )
    return {"tf_a": tf_a, "tf_b": tf_b, **origen}


def _importador(api, **cambios) -> dict:
    datos = {
        "razon_social": "Chocolates del Norte GmbH",
        "direccion": "Hafenstraße 12, 20457 Hamburgo",
        "pais": "Alemania",
        "correo": "compras@ejemplo.test",
    } | cambios
    respuesta = api.post("/importadores", json=datos)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _orden(api, calidad_, cantidad="500.00", tolerancia="0", importador=None) -> dict:
    importador = importador or _importador(api)
    respuesta = api.post(
        "/ordenes",
        json={
            "importador_id": importador["id"],
            "cantidad_kg": cantidad,
            "tolerancia_pct": tolerancia,
            "calidad_id": str(calidad_.id),
            "pais_destino": "Alemania",
            "lugar_destino": "Hamburgo",
            "fecha_entrega": "2026-12-15",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _lote(api, orden) -> dict:
    respuesta = api.post(f"/ordenes/{orden['id']}/lote")
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _seleccion(api, lote, pares) -> object:
    return api.put(
        f"/lotes/{lote['id']}/asignaciones",
        json={"asignaciones": [{"tanda_final_id": str(tf.id), "kg_asignados": kg} for tf, kg in pares]},
    )


def _confirmar(api, lote, motivo=None):
    return api.post(f"/lotes/{lote['id']}/confirmar", json={"motivo_desviacion": motivo} if motivo else {})


def _error(respuesta) -> str:
    return respuesta.json()["error"]["codigo"]


# ---------- Importadores y órdenes ----------


def test_importadores(api, sesion, coop, operador):
    api.como(operador)
    nuevo = _importador(api, eori="de123456789012345")
    assert nuevo["eori"] == "DE123456789012345" and nuevo["activo"] is True
    malo = api.post(
        "/importadores",
        json={"razon_social": "X", "direccion": "Y", "pais": "Z", "correo": "no-es-correo", "eori": "123"},
    )
    assert malo.status_code == 422
    editado = api.patch(f"/importadores/{nuevo['id']}", json={"activo": False, "eori": None})
    assert editado.json()["activo"] is False and editado.json()["eori"] is None
    respuesta = api.post(
        "/ordenes",
        json={
            "importador_id": nuevo["id"],
            "cantidad_kg": "100.00",
            "calidad_id": str(calidad(sesion, coop.id).id),
            "pais_destino": "Alemania",
            "lugar_destino": "Hamburgo",
            "fecha_entrega": "2026-12-15",
        },
    )
    assert respuesta.status_code == 422 and _error(respuesta) == "importador_inactivo"
    acciones = set(sesion.scalars(select(Auditoria.accion).where(Auditoria.entidad_id == nuevo["id"])))
    assert acciones == {"importador.crear", "importador.editar"}


def test_crear_editar_y_anular_una_orden(api, sesion, operador, grado, grado2):
    api.como(operador)
    orden = _orden(api, grado, cantidad="1000.00", tolerancia="2.5")
    assert orden["codigo"] == f"OC-{ahora().year}-000001"
    assert orden["partida_sa"] == "1801" and orden["estado"] == "abierta"
    assert Decimal(orden["minimo_kg"]) == Decimal("975.00") and Decimal(orden["maximo_kg"]) == Decimal(
        "1025.00"
    )
    editada = api.patch(
        f"/ordenes/{orden['id']}", json={"calidad_id": str(grado2.id), "referencia_importador": "PO-77"}
    )
    assert editada.json()["calidad"] == "Grado 2" and editada.json()["referencia_importador"] == "PO-77"
    lote = _lote(api, orden)
    assert lote["estado"] == "en_armado"
    anulada = api.post(f"/ordenes/{orden['id']}/anular", json={"motivo": "El importador canceló el pedido"})
    assert anulada.json()["estado"] == "anulada"
    # El lote en armado se anula con la orden.
    assert api.get(f"/lotes/{lote['id']}").json()["estado"] == "anulado"
    assert api.patch(f"/ordenes/{orden['id']}", json={"lugar_destino": "Bremen"}).status_code == 400


def test_el_lector_no_crea_ordenes(api, sesion, coop, admin, grado):
    importador = _importador(api.como(admin))
    lector = factorias.perfil(sesion, "lector", coop)
    respuesta = api.como(lector).post(
        "/ordenes",
        json={
            "importador_id": importador["id"],
            "cantidad_kg": "100.00",
            "calidad_id": str(grado.id),
            "pais_destino": "Alemania",
            "lugar_destino": "Hamburgo",
            "fecha_entrega": "2026-12-15",
        },
    )
    assert respuesta.status_code == 403
    assert api.get("/importadores").status_code == 200
    assert api.post("/importadores", json={}).status_code == 403


# ---------- El ejemplo y la sugerencia FIFO ----------


def test_el_ejemplo_de_la_genealogia(api, sesion, operador, grado, ejemplo):
    api.como(operador)
    orden = _orden(api, grado)
    lote = _lote(api, orden)
    assert lote["codigo"] == f"LE-{ahora().year}-000001"
    assert [(a["codigo"], Decimal(a["kg_asignados"])) for a in lote["asignaciones"]] == [
        (ejemplo["tf_a"].codigo, Decimal("400.00")),
        (ejemplo["tf_b"].codigo, Decimal("100.00")),
    ]
    confirmado = _confirmar(api, lote)
    assert confirmado.status_code == 200, confirmado.text
    datos = confirmado.json()
    assert datos["estado"] == "armado" and datos["desviacion_fifo"] is False
    assert Decimal(datos["masa_neta_kg"]) == Decimal("500.00") and datos["numero_parcelas"] == 4
    sesion.refresh(ejemplo["tf_a"])
    sesion.refresh(ejemplo["tf_b"])
    assert ejemplo["tf_a"].saldo_kg == 0 and ejemplo["tf_a"].estado == "agotada"
    assert ejemplo["tf_b"].saldo_kg == Decimal("300.00") and ejemplo["tf_b"].estado == "en_stock"
    assert api.get(f"/ordenes/{orden['id']}").json()["estado"] == "con_lote"

    genealogia = api.get(f"/lotes/{lote['id']}/genealogia").json()
    codigos = {p.codigo: n for n, p in ejemplo["parcelas"].items()}
    por_parcela = {
        codigos[p["codigo"]]: (Decimal(p["kg"]), Decimal(p["proporcion"])) for p in genealogia["por_parcela"]
    }
    assert por_parcela == {
        "P1": (Decimal("260"), Decimal("0.52")),
        "P2": (Decimal("120"), Decimal("0.24")),
        "P3": (Decimal("80"), Decimal("0.16")),
        "P4": (Decimal("40"), Decimal("0.08")),
    }
    assert [codigos[p["codigo"]] for p in genealogia["por_parcela"]] == ["P1", "P2", "P3", "P4"]
    assert genealogia["por_parcela"][0]["geometria"]["type"] == "Polygon"
    assert len(genealogia["filas"]) == 5 and len(genealogia["por_productor"]) == 2
    indicadores = {i["clave"]: i["valor"] for i in genealogia["indicadores"]}
    assert Decimal(indicadores["concentracion_mayor_parcela_pct"]) == Decimal("52")
    assert Decimal(indicadores["concentracion_tres_parcelas_pct"]) == Decimal("92")
    assert Decimal(indicadores["cobertura_genealogia_pct"]) == Decimal("100")
    assert Decimal(indicadores["balance_masa"]["diferencia_kg"]) == 0
    assert indicadores["numero_parcelas"] == 4 and indicadores["numero_productores"] == 2
    assert indicadores["numero_dops"] == 5
    assert indicadores["corridas_mezcladas"] == {"mezcladas": 2, "corridas": 2}
    assert indicadores["desviacion_fifo"] == {"desviacion": False, "motivo": None}

    # La genealogía no se edita ni se borra.
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(
            text("UPDATE lote_genealogia SET kg_atribuidos = 1 WHERE lote_id = :l"), {"l": lote["id"]}
        )
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(text("DELETE FROM lote_genealogia WHERE lote_id = :l"), {"l": lote["id"]})


def test_sugerencia_fifo_con_tres_tandas_finales(api, sesion, operador, grado, grado2, almacen, origen):
    t, hoy = origen["tanda"], ahora()
    tercera = tanda_final(
        sesion, operador, grado, almacen, [t("P3", "300.00")], peso="100.00", ingreso=hoy - timedelta(days=1)
    )
    primera = tanda_final(
        sesion, operador, grado, almacen, [t("P1", "300.00")], peso="100.00", ingreso=hoy - timedelta(days=9)
    )
    segunda = tanda_final(
        sesion, operador, grado, almacen, [t("P2", "300.00")], peso="100.00", ingreso=hoy - timedelta(days=5)
    )
    # Más antigua, pero de otra calidad: no entra.
    tanda_final(
        sesion,
        operador,
        grado2,
        almacen,
        [t("P4", "300.00")],
        peso="100.00",
        ingreso=hoy - timedelta(days=20),
    )
    api.como(operador)
    lote = _lote(api, _orden(api, grado, cantidad="250.00"))
    sugerencia = api.get(f"/lotes/{lote['id']}/sugerencia-fifo").json()
    assert [(a["tanda_final_id"], Decimal(a["kg_asignados"])) for a in sugerencia["asignaciones"]] == [
        (str(primera.id), Decimal("100.00")),
        (str(segunda.id), Decimal("100.00")),
        (str(tercera.id), Decimal("50.00")),
    ]
    assert [c["codigo"] for c in sugerencia["candidatas"]] == [primera.codigo, segunda.codigo, tercera.codigo]
    assert Decimal(sugerencia["faltan_kg"]) == 0 and sugerencia["alcanza"] is True
    assert Decimal(sugerencia["disponible_kg"]) == Decimal("300.00")


def test_stock_insuficiente(api, sesion, operador, grado, ejemplo):
    api.como(operador)
    lote = _lote(api, _orden(api, grado, cantidad="1000.00"))
    sugerencia = api.get(f"/lotes/{lote['id']}/sugerencia-fifo").json()
    assert Decimal(sugerencia["faltan_kg"]) == Decimal("200.00") and sugerencia["alcanza"] is False
    respuesta = _confirmar(api, lote)
    assert respuesta.status_code == 400 and _error(respuesta) == "masa_fuera_de_tolerancia"


# ---------- Cambiar la selección ----------


def test_desviacion_del_orden_fifo(api, sesion, operador, grado, ejemplo):
    api.como(operador)
    lote = _lote(api, _orden(api, grado, cantidad="300.00"))
    # Toma la más nueva y deja saldo en la más antigua.
    assert _seleccion(api, lote, [(ejemplo["tf_b"], "300.00")]).status_code == 200
    sin_motivo = _confirmar(api, lote)
    assert sin_motivo.status_code == 422 and _error(sin_motivo) == "motivo_desviacion_requerido"
    corto = _confirmar(api, lote, "Por un acuerdo.")
    assert corto.status_code == 422
    confirmado = _confirmar(api, lote, MOTIVO)
    assert confirmado.status_code == 200, confirmado.text
    assert confirmado.json()["desviacion_fifo"] is True and confirmado.json()["motivo_desviacion"] == MOTIVO
    indicadores = {i["clave"]: i["valor"] for i in confirmado.json()["indicadores"]}
    assert indicadores["desviacion_fifo"] == {"desviacion": True, "motivo": MOTIVO}
    detalle = sesion.scalar(select(Auditoria).where(Auditoria.accion == "lote.confirmar")).detalle
    assert detalle["desviacion_fifo"] is True and detalle["motivo_desviacion"] == MOTIVO


def test_reglas_de_la_seleccion(api, sesion, operador, grado, grado2, almacen, ejemplo):
    api.como(operador)
    lote = _lote(api, _orden(api, grado, cantidad="100.00"))
    otra = tanda_final(sesion, operador, grado2, almacen, [ejemplo["tanda"]("P2", "100.00")], peso="40.00")
    respuesta = _seleccion(api, lote, [(otra, "40.00")])
    assert respuesta.status_code == 400 and _error(respuesta) == "calidad_no_coincide"
    respuesta = _seleccion(api, lote, [(ejemplo["tf_a"], "400.01")])
    assert respuesta.status_code == 422 and _error(respuesta) == "kg_mayor_que_saldo"
    respuesta = _seleccion(api, lote, [(ejemplo["tf_a"], "50.00"), (ejemplo["tf_a"], "50.00")])
    assert respuesta.status_code == 422
    cambiada = _seleccion(api, lote, [(ejemplo["tf_a"], "60.00"), (ejemplo["tf_b"], "40.00")])
    assert Decimal(cambiada.json()["seleccionado_kg"]) == Decimal("100.00")
    assert sesion.scalar(select(Auditoria).where(Auditoria.accion == "lote.cambiar_seleccion")) is not None


def test_suma_fuera_de_la_tolerancia(api, sesion, operador, grado, ejemplo):
    api.como(operador)
    lote = _lote(api, _orden(api, grado, cantidad="500.00", tolerancia="2"))
    _seleccion(api, lote, [(ejemplo["tf_a"], "400.00"), (ejemplo["tf_b"], "120.00")])
    respuesta = _confirmar(api, lote, MOTIVO)
    assert respuesta.status_code == 400 and _error(respuesta) == "masa_fuera_de_tolerancia"
    _seleccion(api, lote, [(ejemplo["tf_a"], "400.00"), (ejemplo["tf_b"], "105.00")])
    respuesta = _confirmar(api, lote, MOTIVO)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["desviacion_fifo"] is True


def test_dos_lotes_sobre_la_misma_tanda_final(api, sesion, operador, grado, ejemplo):
    """Los dos lotes nacen con la misma sugerencia (no reserva nada). El primero que confirma descuenta el
    saldo; el segundo, que la API bloquea por fila y relee, recibe 409 y no guarda nada."""
    api.como(operador)
    primero = _lote(api, _orden(api, grado, cantidad="300.00"))
    segundo = _lote(api, _orden(api, grado, cantidad="300.00"))
    assert primero["asignaciones"][0]["tanda_final_id"] == segundo["asignaciones"][0]["tanda_final_id"]
    assert _confirmar(api, primero).status_code == 200
    respuesta = _confirmar(api, segundo)
    assert respuesta.status_code == 409 and _error(respuesta) == "saldo_insuficiente"
    assert api.get(f"/lotes/{segundo['id']}").json()["estado"] == "en_armado"
    assert (
        sesion.scalar(select(LoteGenealogia.id).where(LoteGenealogia.lote_id == uuid.UUID(segundo["id"])))
        is None
    )
    sesion.refresh(ejemplo["tf_a"])
    assert ejemplo["tf_a"].saldo_kg == Decimal("100.00")


def test_pesos_que_no_dividen_exacto(api, sesion, operador, grado, almacen, origen):
    t = origen["tanda"]
    tanda_final(
        sesion,
        operador,
        grado,
        almacen,
        [t("P1", "333.00"), t("P2", "333.00"), t("P3", "334.00"), t("P4", "17.00")],
        peso="391.37",
    )
    api.como(operador)
    lote = _lote(api, _orden(api, grado, cantidad="77.77"))
    assert _confirmar(api, lote).status_code == 200
    filas = list(
        sesion.scalars(select(LoteGenealogia).where(LoteGenealogia.lote_id == uuid.UUID(lote["id"])))
    )
    assert sum(f.kg_atribuidos for f in filas) == Decimal("77.77")
    assert sum(f.proporcion_lote for f in filas) == Decimal("1")


# ---------- Una orden, un lote; anular ----------


def test_una_orden_tiene_un_solo_lote(api, operador, grado, ejemplo):
    api.como(operador)
    orden = _orden(api, grado)
    lote = _lote(api, orden)
    respuesta = api.post(f"/ordenes/{orden['id']}/lote")
    assert respuesta.status_code == 409 and _error(respuesta) == "lote_existente"
    _confirmar(api, lote)
    assert api.patch(f"/ordenes/{orden['id']}", json={"lugar_destino": "Bremen"}).status_code == 400
    respuesta = api.post(f"/ordenes/{orden['id']}/anular", json={"motivo": "Cancelada"})
    assert respuesta.status_code == 400 and _error(respuesta) == "orden_con_lote"


def test_anular_un_lote_armado(api, sesion, operador, grado, ejemplo):
    api.como(operador)
    orden = _orden(api, grado)
    lote = _lote(api, orden)
    _confirmar(api, lote)
    anulado = api.post(f"/lotes/{lote['id']}/anular", json={"motivo": "El contenedor no se embarcó"})
    assert anulado.status_code == 200 and anulado.json()["estado"] == "anulado"
    sesion.refresh(ejemplo["tf_a"])
    sesion.refresh(ejemplo["tf_b"])
    assert ejemplo["tf_a"].saldo_kg == Decimal("400.00") and ejemplo["tf_a"].estado == "en_stock"
    assert ejemplo["tf_b"].saldo_kg == Decimal("400.00")
    assert api.get(f"/ordenes/{orden['id']}").json()["estado"] == "abierta"
    # La genealogía queda como historial, marcada como anulada.
    genealogia = api.get(f"/lotes/{lote['id']}/genealogia").json()
    assert genealogia["anulada"] is True and len(genealogia["filas"]) == 5
    recorrido = api.get(f"/trazabilidad/parcelas/{ejemplo['parcelas']['P1'].id}").json()
    assert recorrido["lotes"] == [] and recorrido["lotes_anulados"][0]["lote"]["codigo"] == lote["codigo"]
    # La orden recibe otro lote.
    assert _lote(api, orden)["estado"] == "en_armado"


def test_no_se_anula_el_dpp_de_una_tanda_final_en_un_lote(api, sesion, admin, operador, grado, ejemplo):
    api.como(operador)
    _confirmar(api, _lote(api, _orden(api, grado)))
    dpp = sesion.scalar(select(Dpp).where(Dpp.tanda_final_id == ejemplo["tf_b"].id))
    respuesta = api.como(admin).post(f"/dpps/{dpp.id}/anular", json={"motivo": "Error de prueba"})
    assert respuesta.status_code == 400 and _error(respuesta) == "tanda_final_usada"


# ---------- Trazabilidad y lo que ve el productor ----------


def test_rastreo_hacia_adelante(api, sesion, operador, grado, ejemplo):
    api.como(operador)
    lote = _lote(api, _orden(api, grado))
    _confirmar(api, lote)
    parcela = api.get(f"/trazabilidad/parcelas/{ejemplo['parcelas']['P1'].id}").json()
    assert [(lo["lote"]["codigo"], Decimal(lo["kg"])) for lo in parcela["lotes"]] == [
        (lote["codigo"], Decimal("260.00"))
    ]
    assert Decimal(parcela["kg_en_lotes"]) == Decimal("260.00")
    assert len(parcela["tandas"]) == 2
    assert {Decimal(t["kg_en_tanda_final"]) for t in parcela["tandas"]} == {
        Decimal("200.00"),
        Decimal("240.00"),
    }
    uno, dos = ejemplo["productores"]
    productor = api.get(f"/trazabilidad/productores/{dos.id}").json()
    assert Decimal(productor["kg_en_lotes"]) == Decimal("120.00")  # P3 80 + P4 40
    tanda_p4 = next(t for t in productor["tandas"] if t["parcela_codigo"] == ejemplo["parcelas"]["P4"].codigo)
    dop = api.get(f"/trazabilidad/dops/{tanda_p4['dop']['id']}").json()
    assert dop["tipo"] == "dop" and Decimal(dop["lotes"][0]["kg"]) == Decimal("40.00")
    assert dop["tandas"][0]["tanda_final"]["codigo"] == ejemplo["tf_b"].codigo


def test_el_productor_ve_que_su_cacao_entro_a_un_lote(api, sesion, coop, operador, cancha, grado, almacen):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    parcela = _parcela(api, sesion, operador, productor, 3000)
    tanda = tanda_validada(sesion, operador, productor, parcela, cancha, peso="500.00")
    tanda_final(sesion, operador, grado, almacen, [tanda], peso="200.00")
    entregas = api.como(cuenta).get("/mi/tandas").json()
    assert entregas[0]["proceso"]["estado"] == "consolidada"
    api.como(operador)
    _confirmar(api, _lote(api, _orden(api, grado, cantidad="150.00")))
    entregas = api.como(cuenta).get("/mi/tandas").json()
    assert entregas[0]["proceso"] == {
        "estado": "en_lote_de_exportacion",
        "fase": "exportacion",
        "fase_nombre": "En un lote de exportación",
    }
    texto = str(entregas)
    assert "Chocolates" not in texto and "OC-" not in texto and "LE-" not in texto
    assert api.get("/trazabilidad/parcelas/" + str(parcela.id)).status_code == 403


# ---------- Auditoría y dos cooperativas ----------


def test_las_acciones_se_auditan(api, sesion, operador, grado, ejemplo):
    api.como(operador)
    orden = _orden(api, grado)
    api.patch(f"/ordenes/{orden['id']}", json={"lugar_destino": "Bremen"})
    lote = _lote(api, orden)
    _seleccion(api, lote, [(ejemplo["tf_a"], "400.00"), (ejemplo["tf_b"], "100.00")])
    _seleccion(api, lote, [(ejemplo["tf_a"], "300.00"), (ejemplo["tf_b"], "200.00")])
    _confirmar(api, lote, MOTIVO)
    api.post(f"/lotes/{lote['id']}/anular", json={"motivo": "Prueba de anulación"})
    otra = _orden(api, grado)
    api.post(f"/ordenes/{otra['id']}/anular", json={"motivo": "Prueba de anulación"})
    acciones = set(sesion.scalars(select(Auditoria.accion)))
    assert {
        "importador.crear",
        "orden.crear",
        "orden.editar",
        "orden.anular",
        "lote.crear",
        "lote.cambiar_seleccion",
        "lote.confirmar",
        "lote.anular",
    } <= acciones


def test_otra_cooperativa_no_ve_ni_opera(api, sesion, operador, grado, ejemplo):
    api.como(operador)
    importador = _importador(api)
    orden = _orden(api, grado, importador=importador)
    lote = _lote(api, orden)
    otra = factorias.cooperativa(sesion, "Coop B", codigo="CBB")
    grado_b = calidad(sesion, otra.id, "Grado 1")
    operador_b = factorias.perfil(sesion, "operador", otra)
    api.como(operador_b)
    assert api.get("/importadores").json() == [] and api.get("/ordenes").json() == []
    assert api.get("/lotes").json() == []
    assert api.patch(f"/importadores/{importador['id']}", json={"activo": False}).status_code == 404
    assert api.get(f"/ordenes/{orden['id']}").status_code == 404
    assert api.patch(f"/ordenes/{orden['id']}", json={"lugar_destino": "X"}).status_code == 404
    assert api.post(f"/ordenes/{orden['id']}/anular", json={"motivo": "x"}).status_code == 404
    assert api.post(f"/ordenes/{orden['id']}/lote").status_code == 404
    assert api.get(f"/lotes/{lote['id']}").status_code == 404
    assert api.get(f"/lotes/{lote['id']}/sugerencia-fifo").status_code == 404
    assert _seleccion(api, lote, [(ejemplo["tf_a"], "10.00")]).status_code == 404
    assert _confirmar(api, lote).status_code == 404
    assert api.post(f"/lotes/{lote['id']}/anular", json={"motivo": "x"}).status_code == 404
    assert api.get(f"/lotes/{lote['id']}/genealogia").status_code == 404
    assert api.get(f"/trazabilidad/parcelas/{ejemplo['parcelas']['P1'].id}").status_code == 404
    assert api.get(f"/trazabilidad/productores/{ejemplo['productores'][0].id}").status_code == 404
    dop_id = sesion.scalar(select(Dop.id).where(Dop.cooperativa_id == operador.cooperativa_id).limit(1))
    assert api.get(f"/trazabilidad/dops/{dop_id}").status_code == 404
    # Con su propia orden, no puede tomar stock de la otra cooperativa.
    propia = _lote(api, _orden(api, grado_b))
    respuesta = _seleccion(api, propia, [(ejemplo["tf_a"], "10.00")])
    assert respuesta.status_code == 422 and _error(respuesta) == "tanda_final_invalida"
    assert api.post(f"/ordenes/{orden['id']}/lote").status_code == 404
    assert sesion.get(TandaFinal, ejemplo["tf_a"].id).saldo_kg == Decimal("400.00")

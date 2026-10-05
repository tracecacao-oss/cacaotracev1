"""Superposición entre parcelas: se detecta sola, en toda la plataforma."""

from decimal import Decimal

import pytest

from app.models import Auditoria, Superposicion
from tests import factorias
from tests.factorias import crear_parcela, punto, rectangulo


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def admin(sesion, coop):
    return factorias.perfil(sesion, "admin_cooperativa", coop)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


def _crear(api, actor, productor, geometria, **datos):
    respuesta = crear_parcela(api.como(actor), productor.id, geometria, **datos)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_dos_parcelas_del_mismo_productor_superpuestas(api, sesion, coop, operador):
    productor = factorias.productor(sesion, coop)
    primera = _crear(api, operador, productor, rectangulo(100, 100), nombre="Uno")
    respuesta = crear_parcela(api, productor.id, rectangulo(100, 100, este_m=50), nombre="Dos")
    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["codigo"] == "superposicion_propia"
    assert primera["codigo"] in error["mensaje"]


def test_solape_menor_al_umbral_no_se_registra(api, sesion, coop, operador):
    """1 % del área y 0.01 ha: imprecisión de linderos."""
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    otra = _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100, este_m=99))
    assert otra["alertas"] == []
    assert sesion.query(Superposicion).count() == 0


def test_dos_productores_de_la_misma_cooperativa_con_solape_de_30(api, sesion, coop, operador):
    a = _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    b = _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100, este_m=70))
    fila = sesion.query(Superposicion).one()
    assert fila.estado == "abierta" and fila.tipo == "poligono_poligono"
    assert abs(fila.porcentaje - Decimal("30")) < Decimal("0.5")
    assert abs(fila.area_ha - Decimal("0.3")) < Decimal("0.005")
    for parcela in (a, b):
        assert "superposicion" in api.get(f"/parcelas/{parcela['id']}").json()["alertas"]
    listado = api.get("/superposiciones").json()
    assert len(listado) == 1 and not listado[0]["entre_cooperativas"]
    assert {p["id"] for p in listado[0]["parcelas"]} == {a["id"], b["id"]}
    # En el detalle se ve cuál es la otra parcela, porque es de la misma cooperativa.
    detalle = api.get(f"/parcelas/{a['id']}").json()
    assert detalle["superposiciones"][0]["otra_parcela"]["codigo"] == b["codigo"]


def test_solape_entre_cooperativas(api, sesion, coop, operador):
    otra = factorias.cooperativa(sesion, nombre="Coop Vecina")
    operador_otra = factorias.perfil(sesion, "operador", otra)
    propia = _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    ajena = _crear(api, operador_otra, factorias.productor(sesion, otra), rectangulo(100, 100, este_m=50))

    for actor, mia, de_la_otra in ((operador, propia, ajena), (operador_otra, ajena, propia)):
        vista = api.como(actor).get("/superposiciones").json()
        assert len(vista) == 1
        s = vista[0]
        assert s["entre_cooperativas"] is True
        assert s["aviso"] == "Superposición con una parcela de otra cooperativa"
        assert [p["id"] for p in s["parcelas"]] == [mia["id"]]
        assert Decimal(s["area_ha"]) > 0 and s["interseccion"]["type"] == "Polygon"
        assert de_la_otra["id"] not in str(s)
        assert de_la_otra["productor"]["dni"] not in str(s)
        detalle = api.get(f"/parcelas/{mia['id']}").json()
        assert detalle["superposiciones"][0]["otra_parcela"] is None
        assert detalle["superposiciones"][0]["otra_cooperativa"] is True


def test_corregir_la_geometria_resuelve_la_superposicion(api, sesion, coop, operador):
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    b = _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100, este_m=70))
    respuesta = api.patch(
        f"/parcelas/{b['id']}",
        json={"geometria": rectangulo(100, 100, este_m=120), "motivo": "Se corrigió el lindero"},
    )
    assert respuesta.status_code == 200
    assert sesion.query(Superposicion).one().estado == "resuelta"
    assert "superposicion" not in respuesta.json()["alertas"]


def test_desactivar_una_parcela_cierra_su_superposicion(api, sesion, coop, operador):
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    b = _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100, este_m=70))
    api.post(f"/parcelas/{b['id']}/desactivar")
    assert sesion.query(Superposicion).one().estado == "resuelta"


def test_punto_dentro_de_un_poligono(api, sesion, coop, operador):
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    _crear(
        api,
        operador,
        factorias.productor(sesion, coop),
        punto(este_m=50, norte_m=50),
        area_declarada_ha="1",
        area_cultivada_ha="1",
    )
    fila = sesion.query(Superposicion).one()
    assert fila.tipo == "punto_en_poligono" and fila.area_ha is None


def test_operador_no_acepta_superposiciones(api, sesion, coop, operador):
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100, este_m=70))
    fila = sesion.query(Superposicion).one()
    assert api.post(f"/superposiciones/{fila.id}/aceptar", json={"nota": "x"}).status_code == 403


def test_admin_acepta_sin_nota(api, sesion, coop, operador, admin):
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100, este_m=70))
    fila = sesion.query(Superposicion).one()
    api.como(admin)
    assert api.post(f"/superposiciones/{fila.id}/aceptar", json={}).status_code == 422
    assert api.post(f"/superposiciones/{fila.id}/aceptar", json={"nota": ""}).status_code == 422


def test_admin_acepta_con_nota(api, sesion, coop, operador, admin):
    a = _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100, este_m=70))
    fila = sesion.query(Superposicion).one()
    respuesta = api.como(admin).post(
        f"/superposiciones/{fila.id}/aceptar", json={"nota": "Hermanos que comparten el lindero"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "aceptada"
    assert "superposicion" not in api.get(f"/parcelas/{a['id']}").json()["alertas"]
    assert sesion.query(Auditoria).filter_by(accion="superposicion.aceptar").count() == 1


def test_entre_cooperativas_solo_la_acepta_el_superadmin(api, sesion, coop, operador, admin):
    otra = factorias.cooperativa(sesion)
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    _crear(
        api,
        factorias.perfil(sesion, "operador", otra),
        factorias.productor(sesion, otra),
        rectangulo(100, 100, este_m=50),
    )
    fila = sesion.query(Superposicion).one()
    respuesta = api.como(admin).post(f"/superposiciones/{fila.id}/aceptar", json={"nota": "x"})
    assert respuesta.status_code == 403

    superadmin = factorias.perfil(sesion, "superadmin")
    api.como(superadmin)
    listado = api.get("/admin/superposiciones").json()
    assert len(listado) == 1 and len(listado[0]["parcelas"]) == 2
    assert all(p["cooperativa_nombre"] for p in listado[0]["parcelas"])
    respuesta = api.post(f"/admin/superposiciones/{fila.id}/aceptar", json={"nota": "Revisado con ambas"})
    assert respuesta.status_code == 200 and respuesta.json()["estado"] == "aceptada"
    # Queda en la auditoría de las dos cooperativas.
    assert sesion.query(Auditoria).filter_by(accion="superposicion.aceptar").count() == 2


def test_parcelas_de_demostracion_solo_se_comparan_entre_si(api, sesion, coop, operador):
    demo = factorias.cooperativa(sesion, es_demo=True)
    _crear(api, operador, factorias.productor(sesion, coop), rectangulo(100, 100))
    _crear(
        api,
        factorias.perfil(sesion, "operador", demo),
        factorias.productor(sesion, demo),
        rectangulo(100, 100),
    )
    assert sesion.query(Superposicion).count() == 0


def test_analizar_anticipa_superposiciones(api, sesion, coop, operador):
    import json

    vecino = factorias.productor(sesion, coop)
    existente = _crear(api, operador, vecino, rectangulo(100, 100))
    otra = factorias.cooperativa(sesion)
    _crear(
        api,
        factorias.perfil(sesion, "operador", otra),
        factorias.productor(sesion, otra),
        rectangulo(100, 100, norte_m=60),
    )
    nuevo = factorias.productor(sesion, coop)
    dibujo = json.dumps({"type": "Feature", "properties": {}, "geometry": rectangulo(100, 100, este_m=70)})
    respuesta = api.como(operador).post(
        "/parcelas/analizar-archivo",
        data={"productor_id": str(nuevo.id)},
        files={"archivo": ("dibujo.geojson", dibujo.encode())},
    )
    previstas = respuesta.json()["geometrias"][0]["superposiciones"]
    assert len(previstas) == 2
    misma = next(p for p in previstas if not p["otra_cooperativa"])
    assert misma["codigo"] == existente["codigo"] and misma["propia"] is False
    ajena = next(p for p in previstas if p["otra_cooperativa"])
    assert ajena["codigo"] is None and ajena["nombre"] is None
    assert sesion.query(Superposicion).count() == 1  # analizar no guarda nada

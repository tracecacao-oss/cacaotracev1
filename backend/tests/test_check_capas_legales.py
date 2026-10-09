"""Adenda 4, sección 10: check_capas_legales.py. Ninguna prueba sale a internet: el HTTP se simula."""

import importlib.util
from pathlib import Path
from urllib.parse import unquote

import httpx

from app.catalogos import capas_legales

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_capas_legales.py"
_spec = importlib.util.spec_from_file_location("check_capas_legales", SCRIPT)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

ABISEO = {"anp_nomb": "del Río Abiseo", "anp_cate": "Parque Nacional"}
SAN_MARTIN = {
    "NOMDEP": "22",
    "DOCLEG": "Resolución Ministerial Nº 039-2020-MINAM",
    "CATZFO": 603,
    "SCAZFO": 60302,
}
# Lo único que el script puede enviar: la geometría y cómo consultarla. Nunca nombres, DNI ni la organización.
PERMITIDOS = {
    "f",
    "geometry",
    "geometryType",
    "inSR",
    "spatialRel",
    "returnCountOnly",
    "outFields",
    "returnGeometry",
}


def servidor(caidos=(), respuestas=None):
    """Responde como los servicios reales. `caidos`: direcciones de servicio que devuelven 503."""
    pedidos = []
    respuestas = respuestas or {}

    def responder(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        url = unquote(str(request.url.copy_with(query=None)))
        servicio = next(
            c.servicio for c in (*capas_legales.CAPAS, *capas_legales.APOYO) if url.startswith(c.servicio)
        )
        if servicio in caidos:
            return httpx.Response(503)
        if url == servicio:
            numeros = {
                n
                for c in (*capas_legales.CAPAS, *capas_legales.APOYO)
                if c.servicio == servicio
                for n in c.capas
            }
            return httpx.Response(200, json={"layers": [{"id": n} for n in sorted(numeros)]})
        parametros = dict(request.url.params)
        if parametros.get("returnCountOnly") == "true":
            return httpx.Response(200, json={"count": 3})
        numero = int(url.rstrip("/").split("/")[-2])
        atributos = respuestas.get((servicio, numero), [])
        return httpx.Response(200, json={"features": [{"attributes": a} for a in atributos]})

    return httpx.Client(transport=httpx.MockTransport(responder)), pedidos


def _sin_esperas(_segundos):
    pass


BIEN = {(capas_legales.SERNANP, 1): [ABISEO], (capas_legales.SERFOR_ZONIFICACION, 0): [SAN_MARTIN]}


def test_responden_las_seis_capas_y_las_dos_geometrias():
    cliente, pedidos = servidor(respuestas=BIEN)
    todo_bien, lineas = check.comprobar(cliente, _sin_esperas)
    assert todo_bien
    assert lineas[-1] == "Responden las seis capas."
    assert sum(1 for linea in lineas if linea.startswith("  [OK]")) == len(capas_legales.CAPAS) + 2 + len(
        capas_legales.APOYO
    )
    # A cada servicio solo se le envía la geometría y cómo consultarla.
    assert all(set(p.url.params) <= PERMITIDOS for p in pedidos)


def test_un_servicio_caido_hace_fallar_la_comprobacion():
    cliente, _ = servidor(caidos={capas_legales.SIGDA}, respuestas=BIEN)
    todo_bien, lineas = check.comprobar(cliente, _sin_esperas)
    assert not todo_bien
    assert any("[FALLA] Monumentos arqueológicos" in linea and "503" in linea for linea in lineas)


def test_una_capa_de_apoyo_caida_no_cambia_el_resultado():
    cliente, _ = servidor(caidos={capas_legales.ANA_FAJA_MARGINAL}, respuestas=BIEN)
    todo_bien, lineas = check.comprobar(cliente, _sin_esperas)
    assert todo_bien
    assert any(linea.startswith("  [no responde] Fajas marginales") for linea in lineas)


def test_una_geometria_de_prueba_que_no_devuelve_lo_esperado_falla():
    otra = {**BIEN, (capas_legales.SERFOR_ZONIFICACION, 0): [{**SAN_MARTIN, "DOCLEG": "Otra resolución"}]}
    cliente, _ = servidor(respuestas=otra)
    todo_bien, lineas = check.comprobar(cliente, _sin_esperas)
    assert not todo_bien
    assert any("[FALLA] -76.75, -7.25" in linea for linea in lineas)


def test_reintenta_una_respuesta_vacia_antes_de_darla_por_caida():
    esperas = []
    llamadas = {"n": 0}
    cliente_bien, _ = servidor(respuestas=BIEN)

    def con_un_vacio(request: httpx.Request) -> httpx.Response:
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return httpx.Response(200, content=b"")  # como hace a veces el servidor de SERFOR
        return cliente_bien._transport.handle_request(request)

    cliente = httpx.Client(transport=httpx.MockTransport(con_un_vacio))
    todo_bien, _ = check.comprobar(cliente, esperas.append)
    assert todo_bien and esperas == [check.ESPERA_S]

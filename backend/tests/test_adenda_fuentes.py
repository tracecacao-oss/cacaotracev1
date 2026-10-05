"""Adenda de la Parte 4: detalle por capa de Whisp, MapBiomas Perú y tabla de convergencia.

Ninguna prueba sale a internet: Whisp y GFW se simulan con httpx.MockTransport y MapBiomas lee GeoTIFF
sintéticos, armados en la prueba, que un servidor simulado entrega por rangos.
"""

import json
import math
import re
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import numpy as np
import pytest

from app.catalogos import capas_whisp
from app.config import Settings
from app.fechas import ahora
from app.models import AnalisisCobertura, Documento, Parcela
from app.scripts import reprocesar_whisp
from app.services import analisis, convergencia
from app.services.fuentes import cog, registro
from app.services.fuentes.mapbiomas import URL, MapBiomas
from tests import factorias
from tests.factorias import crear_parcela
from tests.geotiff_util import D, geotiff, lzw_codificar, servidor_por_rangos
from tests.habilitacion_util import analisis_completado, fuentes_configuradas

DATOS = Path(__file__).parent / "datos"
WHISP_REAL = (DATOS / "whisp_respuesta_real.json").read_bytes()
PROPIEDADES = json.loads(WHISP_REAL)["data"]["features"][0]["properties"]

# Rejilla sintética de 48 x 48 píxeles de MapBiomas, en bloques de 16, cerca de la parcela ficticia.
X0, Y0 = -76.56, -6.94
LADO = 48


def _poligono(col0: int, col1: int, fila0: int, fila1: int) -> dict:
    """Polígono que contiene los centros de los píxeles [col0, col1] x [fila0, fila1] de la rejilla."""
    xa, xb = X0 + (col0 + 0.1) * D, X0 + (col1 + 0.9) * D
    ya, yb = Y0 - (fila0 + 0.1) * D, Y0 - (fila1 + 0.9) * D
    return {"type": "Polygon", "coordinates": [[[xa, ya], [xb, ya], [xb, yb], [xa, yb], [xa, ya]]]}


# 12 píxeles (4 columnas x 3 filas) que cruzan el borde entre bloques, en la fila y en la columna.
PARCELA = _poligono(14, 17, 14, 16)


def _mapas(por_anio: dict[int, np.ndarray], **opciones) -> dict[str, bytes]:
    return {URL.format(anio=a): geotiff(m, X0, Y0, **opciones) for a, m in por_anio.items()}


def _bosque_a_arroz() -> dict[int, np.ndarray]:
    """Bosque (3) en 2019 y 2020; en 2021 la mitad de la parcela pasó a arroz (40)."""
    base = np.full((LADO, LADO), 21, dtype=np.uint8)  # mosaico agropecuario alrededor
    base[14:17, 14:18] = 3
    despues = base.copy()
    despues[14:17, 14:16] = 40
    return {2019: base, 2020: base, 2021: despues}


def _area_pixel_ha(fila: int) -> float:
    """Área de un píxel de la fila, calculada aparte: franja esférica entre las dos latitudes."""
    r = 6_371_007.181
    lat_sup, lat_inf = math.radians(Y0 - fila * D), math.radians(Y0 - (fila + 1) * D)
    return r * r * math.radians(D) * (math.sin(lat_sup) - math.sin(lat_inf)) / 10_000


def _mapbiomas(archivos: dict[str, bytes]) -> MapBiomas:
    servidor = servidor_por_rangos(archivos)
    fuente = MapBiomas(True, 2019, 2021, httpx.Client(transport=httpx.MockTransport(servidor)))
    fuente.servidor = servidor
    return fuente


@pytest.fixture
def mapas():
    return _mapas(_bosque_a_arroz())


@pytest.fixture
def fuentes(mapas):
    return fuentes_configuradas() | {"mapbiomas": _mapbiomas(mapas)}


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion, "Coop Adenda")


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


def _parcela(api, sesion, operador, productor, geometria=PARCELA) -> Parcela:
    respuesta = crear_parcela(api.como(operador), productor.id, geometria)
    assert respuesta.status_code == 201, respuesta.text
    return sesion.get(Parcela, uuid.UUID(respuesta.json()["id"]))


def _procesar(sesion, fuentes, storage):
    ritmo = analisis.Ritmo(reloj=lambda: 0.0, dormir=lambda s: None)
    return analisis.procesar_siguiente(sesion, fuentes, storage, ritmo)


# --- Refuerzo A: detalle por capa de Whisp ---


def test_respuesta_real_de_whisp_trae_todas_sus_capas():
    _, indicadores, _ = fuentes_configuradas()["whisp"].interpretar(WHISP_REAL)
    capas = {c["nombre"]: c for c in indicadores["capas"]}
    # Todas las columnas que no son datos de la parcela ni la conclusión propia de Whisp.
    esperadas = [n for n in PROPIEDADES if capas_whisp.es_capa(n)]
    assert list(capas) == esperadas and len(esperadas) > 150
    assert all(c["pregunta"] in capas_whisp.PREGUNTAS for c in capas.values())
    assert {"Area", "Country", "Ind_01_treecover", "risk_pcrop", "whisp_processing_metadata"}.isdisjoint(
        capas
    )
    # Algunas, una por pregunta, con su conjunto de datos y su valor tal como vino.
    assert capas["EUFO_2020"] | {"valor": None} == {
        "nombre": "EUFO_2020",
        "pregunta": "estado_2020",
        "conjunto_de_datos": "jrc_gfc2020",
        "conjunto_nombre": "JRC Global Forest Cover 2020 (Bourgoin et al.)",
        "mide_bosque": True,
        "serie": False,
        "valor": None,
        "unidad": "ha",
    }
    assert capas["GFC_TC_2020"]["valor"] == PROPIEDADES["GFC_TC_2020"]
    assert (capas["GFC_loss_after_2020"]["pregunta"], capas["GFC_loss_after_2020"]["conjunto_de_datos"]) == (
        "cambio_posterior",
        "umd_gfc",
    )
    assert capas["TMF_def_2022"]["pregunta"] == "cambio_posterior" and capas["TMF_def_2022"]["serie"]
    assert capas["GFC_loss_year_2001"]["pregunta"] == "otra"
    assert capas["Cocoa_ETH"]["pregunta"] == "cultivo"
    assert (
        capas["SBTN_natural_2020"]["pregunta"] == "estado_2020"
        and not capas["SBTN_natural_2020"]["mide_bosque"]
    )
    assert [c["nombre"] for c in capas.values() if c["conjunto_de_datos"] is None] == []


def test_capa_que_no_esta_en_el_catalogo_se_guarda_como_otra():
    respuesta = json.loads(WHISP_REAL)
    respuesta["data"]["features"][0]["properties"]["Capa_Nueva_De_Whisp_2027"] = 0.25
    _, indicadores, _ = fuentes_configuradas()["whisp"].interpretar(json.dumps(respuesta).encode())
    nueva = next(c for c in indicadores["capas"] if c["nombre"] == "Capa_Nueva_De_Whisp_2027")
    assert nueva == {
        "nombre": "Capa_Nueva_De_Whisp_2027",
        "pregunta": "otra",
        "conjunto_de_datos": None,
        "conjunto_nombre": None,
        "mide_bosque": False,
        "serie": False,
        "valor": 0.25,
        "unidad": "ha",
    }


def test_reprocesar_un_analisis_de_whisp_sin_llamar_a_whisp(api, sesion, operador, productor, storage_falso):
    parcela = _parcela(api, sesion, operador, productor)
    fila = analisis_completado(sesion, parcela, "whisp")
    assert "capas" not in fila.indicadores
    ruta = f"{parcela.cooperativa_registro_id}/analisis/{fila.id}/respuesta.json"
    storage_falso.subir(ruta, WHISP_REAL, "application/json")
    documento = Documento(
        cooperativa_id=parcela.cooperativa_registro_id,
        entidad="analisis",
        entidad_id=fila.id,
        tipo="respuesta_analisis",
        ruta=ruta,
        nombre_original="whisp.json",
        tipo_mime="application/json",
        tamano_bytes=len(WHISP_REAL),
        sha256="0" * 64,
    )
    sesion.add(documento)
    sesion.flush()
    fila.respuesta_documento_id = documento.id
    sesion.flush()

    # Whisp sin clave ni transporte: si el reproceso intentara consultarlo, fallaría.
    assert reprocesar_whisp.reprocesar(sesion, storage_falso) == 1
    sesion.refresh(fila)
    assert len(fila.indicadores["capas"]) > 150
    assert fila.indicadores["risk_pcrop"] == "low"  # lo demás queda como estaba
    assert reprocesar_whisp.reprocesar(sesion, storage_falso) == 0  # una sola vez


# --- Refuerzo C: MapBiomas Perú, con GeoTIFF sintéticos ---


def test_lzw_de_ida_y_vuelta_con_cambio_de_ancho():
    rng = np.random.default_rng(7)
    datos = rng.integers(0, 40, size=64 * 64, dtype=np.uint8).tobytes()  # pasa de 9 a 12 bits
    assert cog.lzw(lzw_codificar(datos), len(datos)) == datos
    assert cog.lzw(lzw_codificar(bytes(70_000))) == bytes(70_000)  # una sola clase, códigos largos


def test_hectareas_por_clase_coinciden_con_las_esperadas(mapas):
    fuente = _mapbiomas(mapas)
    _, indicadores, version = fuente.interpretar(fuente.consultar(PARCELA, "x"))
    filas = (14, 15, 16)
    bosque_esperado = sum(4 * _area_pixel_ha(f) for f in filas)
    arroz_2021 = sum(2 * _area_pixel_ha(f) for f in filas)
    assert indicadores["anios"]["2020"] == {"3": pytest.approx(bosque_esperado, abs=1e-4)}
    assert indicadores["anios"]["2021"]["40"] == pytest.approx(arroz_2021, abs=1e-4)
    assert indicadores["anios"]["2021"]["3"] == pytest.approx(bosque_esperado - arroz_2021, abs=1e-4)
    assert indicadores["bosque_2020_ha"] == pytest.approx(bosque_esperado, abs=1e-4)
    # Un píxel de 30 m mide unas 0.09 ha: 12 píxeles, cerca de 1.08 ha.
    assert 1.0 < indicadores["bosque_2020_ha"] < 1.2
    assert indicadores["clase_predominante_2020"] == "Bosque"
    assert indicadores["clases"] == {"3": "Bosque", "40": "Arroz"}
    assert (indicadores["pixeles"], indicadores["pocos_pixeles"], indicadores["ultimo_anio"]) == (
        12,
        False,
        2021,
    )
    assert version == "MapBiomas Perú, Colección 3 · hasta 2021"
    # Solo rangos: la cabecera (16 KiB como máximo), las entradas de la tabla y los bloques.
    assert all(b - a + 1 <= 16 * 1024 for _, a, b in fuente.servidor.pedidos)


def test_georreferencia_lejos_de_la_cabecera_como_en_los_archivos_reales():
    mapas = _mapas(_bosque_a_arroz(), relleno=500_000)
    fuente = _mapbiomas(mapas)
    _, indicadores, _ = fuente.interpretar(fuente.consultar(PARCELA, "x"))
    assert indicadores["pixeles"] == 12
    # Nunca se bajó un archivo completo, ni sumando los rangos pedidos a cada uno.
    for url, contenido in mapas.items():
        pedido = sum(b - a + 1 for u, a, b in fuente.servidor.pedidos if u == url)
        assert pedido < len(contenido) / 5


def test_parcela_con_6_pixeles_lleva_la_marca(mapas):
    fuente = _mapbiomas(mapas)
    _, indicadores, _ = fuente.interpretar(fuente.consultar(_poligono(14, 15, 14, 16), "x"))
    assert (indicadores["pixeles"], indicadores["pocos_pixeles"]) == (6, True)


def test_bosque_en_2020_y_arroz_despues_pide_revision(
    api, sesion, operador, productor, fuentes, storage_falso
):
    parcela = _parcela(api, sesion, operador, productor)
    sesion.query(AnalisisCobertura).filter(AnalisisCobertura.fuente != "mapbiomas").delete()
    assert _procesar(sesion, fuentes, storage_falso)
    fila = sesion.query(AnalisisCobertura).filter_by(parcela_id=parcela.id, fuente="mapbiomas").one()
    assert fila.estado == "completado" and fila.resultado_fuente is None and fila.es_aproximacion is False
    assert fila.indicadores["cambio_bosque_a_no_bosque_ha"] > 0
    evidencia = json.loads(storage_falso.archivos[sesion.get(Documento, fila.respuesta_documento_id).ruta])
    assert evidencia["anios"]["2020"]["pixeles"] == {"3": 12}
    assert evidencia["anios"]["2020"]["url"] == URL.format(anio=2020)
    assert evidencia["anios"]["2020"]["cabeceras"] == {"etag": '"prueba"', "x-goog-generation": "1"}
    assert evidencia["transicion"]["pixeles"] == {"3->3": 6, "3->40": 6}

    detalle = api.get(f"/parcelas/{parcela.id}").json()
    assert "analisis_requiere_revision" in detalle["alertas"]
    tarjeta = next(
        a for a in api.get(f"/parcelas/{parcela.id}/analisis").json() if a["fuente"] == "mapbiomas"
    )
    ha_bosque = fila.indicadores["bosque_2020_ha"]
    ha_cambio = fila.indicadores["cambio_bosque_a_no_bosque_ha"]
    assert tarjeta["resultado_texto"] == (
        f"MapBiomas Perú: en 2020, clase predominante Bosque; {ha_bosque:g} ha de bosque en 2020; "
        f"{ha_cambio:g} ha pasaron de bosque a otra clase entre 2020 y 2021"
    )


def test_mapbiomas_inactivo_no_crea_analisis_ni_aparece_en_la_tabla(
    api, sesion, operador, productor, fuentes
):
    base = {"database_url": "postgresql+psycopg://x@localhost/x", "supabase_url": "https://x.invalid"}
    assert "mapbiomas" not in registro.construir(Settings(**base, mapbiomas_activo=False))
    assert "mapbiomas" in registro.construir(Settings(**base, mapbiomas_activo=True))

    registro.fijar(fuentes_configuradas())  # como en producción con MAPBIOMAS_ACTIVO en false
    parcela = _parcela(api, sesion, operador, productor)
    assert {a.fuente for a in sesion.query(AnalisisCobertura).filter_by(parcela_id=parcela.id)} == {
        "whisp",
        "gfw",
    }
    # Un análisis de MapBiomas de antes, si lo hubiera, tampoco entra en la tabla.
    analisis_completado(
        sesion,
        parcela,
        "mapbiomas",
        resultado=None,
        indicadores={"bosque_2020_ha": 5.0, "cambio_bosque_a_no_bosque_ha": 1.0},
    )
    filas = api.get(f"/parcelas/{parcela.id}/convergencia").json()["filas"]
    assert "MapBiomas" not in {v for f in filas for v in f["vias"]}
    assert "analisis_requiere_revision" not in api.get(f"/parcelas/{parcela.id}").json()["alertas"]


# --- Refuerzo D: tabla de convergencia ---


def _analisis(fuente: str, indicadores: dict, *, aproximacion=False) -> SimpleNamespace:
    return SimpleNamespace(
        fuente=fuente,
        indicadores=indicadores,
        completado_en=ahora() - timedelta(hours=1),
        es_aproximacion=aproximacion,
    )


def _whisp(**valores) -> SimpleNamespace:
    propiedades = {"Unit": "ha"} | valores
    return _analisis("whisp", {"capas": capas_whisp.capas(propiedades)})


def _gfw(**indicadores) -> SimpleNamespace:
    base = {
        "alertas_desde_2021": 0,
        "perdida_ha_total": 0,
        "bosque_natural_2020_ha": 0,
        "alertas_dist_desde_2021": 0,
    }
    return _analisis("gfw", base | indicadores)


def test_el_mismo_conjunto_por_whisp_y_por_gfw_se_cuenta_una_vez():
    c = convergencia.calcular(
        [_whisp(GFC_TC_2020=0.0, GFC_loss_after_2020=0.0), _gfw(perdida_ha_total=0.3)], 4.0, 10
    )
    hansen = [f for f in c.filas if f.conjunto == "umd_gfc"]
    assert len(hansen) == 1
    assert hansen[0].vias == ["Whisp", "GFW"]
    assert [m.nombre for m in hansen[0].despues_2020] == ["GFC_loss_after_2020", "perdida_ha_total"]
    assert hansen[0].registra_cambio is True  # GFW vio pérdida aunque Whisp no
    assert c.conteos["consultados"] == len(c.filas) == len({f.conjunto for f in c.filas})


def test_dos_conjuntos_que_discrepan_sobre_2020_muestran_sus_valores():
    # Parcela de 4.525 ha: 1.546 ha de cobertura arbórea según UMD (34 %) y 0 según JRC.
    c = convergencia.calcular([_whisp(GFC_TC_2020=1.546, EUFO_2020=0.0)], 4.525, 10)
    por_conjunto = {f.conjunto: f for f in c.filas}
    assert [(m.nombre, m.valor) for m in por_conjunto["umd_gfc"].al_2020] == [("GFC_TC_2020", 1.546)]
    assert [(m.nombre, m.valor) for m in por_conjunto["jrc_gfc2020"].al_2020] == [("EUFO_2020", 0.0)]
    assert por_conjunto["umd_gfc"].registra_bosque_2020 is True
    assert por_conjunto["jrc_gfc2020"].registra_bosque_2020 is False
    assert c.discrepan == {"estado_2020": True, "cambio_posterior": False}
    assert c.registran_bosque_2020 == ["UMD Global Forest Change (Hansen et al.)"]


def test_umbral_de_bosque_en_2020():
    # 10 % de 4 ha son 0.4 ha: 0.39 no alcanza y 0.4 sí.
    assert convergencia.calcular([_whisp(EUFO_2020=0.39)], 4.0, 10).filas[0].registra_bosque_2020 is False
    assert convergencia.calcular([_whisp(EUFO_2020=0.4)], 4.0, 10).filas[0].registra_bosque_2020 is True
    # En un punto, Whisp analiza el punto tal cual: cualquier valor distinto de cero cuenta.
    assert (
        convergencia.calcular([_whisp(EUFO_2020=0.01)], 4.0, 10, es_punto=True).filas[0].registra_bosque_2020
    )


PROHIBIDAS = re.compile(
    r"no deforestad|sin deforestaci|libre de deforestaci|cumple|bajo riesgo|alto riesgo|seguro|confiable",
    re.IGNORECASE,
)


def test_frase_de_conteo_coincide_con_los_datos_y_solo_cuenta():
    c = convergencia.calcular(
        [
            _whisp(
                GFC_TC_2020=1.546, EUFO_2020=0.0, TMF_undist=0.0, GFC_loss_after_2020=0.0, RADD_after_2020=0.2
            ),
            _gfw(alertas_desde_2021=3, bosque_natural_2020_ha=0.1),
        ],
        4.525,
        10,
    )
    assert c.conteos == {
        "consultados": 7,  # JRC GFC2020, TMF, UMD GFC, RADD, alertas integradas, SBTN y DIST
        "bosque_registran": 1,  # UMD GFC: 1.546 ha de 4.525 (34 %)
        "bosque_miden": 4,  # JRC GFC2020, TMF, UMD GFC y SBTN (0.1 ha, menos del 10 %)
        "cambio_registran": 2,  # RADD y alertas integradas
        "cambio_miden": 4,  # UMD GFC, RADD, alertas integradas y DIST
    }
    assert c.frase == (
        "Conjuntos de datos consultados: 7. Registran bosque en 2020: 1 de 4 que lo miden. "
        "Registran cambios después de 2020: 2 de 4 que lo miden."
    )
    assert not PROHIBIDAS.search(c.frase)


def test_tabla_de_convergencia_por_la_api(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    sesion.query(AnalisisCobertura).delete()
    fila = analisis_completado(sesion, parcela, "whisp")
    fila.indicadores = {"risk_pcrop": "low", "capas": capas_whisp.capas({"Unit": "ha", "EUFO_2020": 0.9})}
    sesion.flush()
    tabla = api.get(f"/parcelas/{parcela.id}/convergencia").json()
    assert tabla["frase"].startswith("Conjuntos de datos consultados: 1. Registran bosque en 2020: 1 de 1")
    assert tabla["filas"][0]["al_2020"][0] | {"valor": 0} == {
        "via": "Whisp",
        "nombre": "EUFO_2020",
        "valor": 0,
        "unidad": "ha",
        "mide_bosque": True,
        "serie": False,
    }
    assert tabla["filas"][0]["despues_2020"] is None  # no mide esa pregunta: celda vacía
    # Regla 3 de la sección 7.2, con la decisión del equipo del 2026-10-05: un solo conjunto que registra
    # bosque en 2020 se muestra, pero no pide revisión; hacen falta 3.
    assert tabla["mapas_minimos_bosque_2020"] == 3 and tabla["hubo_bosque_2020"] is False
    assert "analisis_requiere_revision" not in api.get(f"/parcelas/{parcela.id}").json()["alertas"]

    fila.indicadores = {
        "risk_pcrop": "low",
        "capas": capas_whisp.capas({"Unit": "ha", "EUFO_2020": 0.9, "TMF_undist": 0.9, "GLAD_Primary": 0.9}),
    }
    sesion.flush()
    tabla = api.get(f"/parcelas/{parcela.id}/convergencia").json()
    assert tabla["frase"].startswith("Conjuntos de datos consultados: 3. Registran bosque en 2020: 3 de 3")
    assert tabla["hubo_bosque_2020"] is True
    assert "analisis_requiere_revision" in api.get(f"/parcelas/{parcela.id}").json()["alertas"]


# --- Respuestas reales de las tres fuentes (PA-00002, producción, 2026-10-05) ---

MAPBIOMAS_REAL = (DATOS / "mapbiomas_respuesta_real.json").read_bytes()
WHISP_REAL_2 = (DATOS / "whisp_respuesta_real_2.json").read_bytes()
GFW_REAL_ADENDA = (DATOS / "gfw_respuesta_real_adenda.json").read_bytes()


def test_mapbiomas_respuesta_real():
    fuente = MapBiomas(True, 2015, 2024)
    resultado, indicadores, version = fuente.interpretar(MAPBIOMAS_REAL)
    assert resultado is None
    assert version == "MapBiomas Perú, Colección 3 · hasta 2024"
    assert indicadores["clase_predominante_2020"] == "Arroz"
    assert (indicadores["bosque_2020_ha"], indicadores["cambio_bosque_a_no_bosque_ha"]) == (0, 0)
    assert (indicadores["pixeles"], indicadores["pocos_pixeles"]) == (74, False)
    assert indicadores["clases"] == {"33": "Río, lago u océano", "40": "Arroz"}
    assert indicadores["anios"]["2021"] == {"33": 4.3669, "40": 2.228}
    assert not fuente.requiere_revision(resultado, indicadores)
    evidencia = json.loads(MAPBIOMAS_REAL)
    assert all(
        set(a["cabeceras"]) == {"etag", "last-modified", "x-goog-generation"}
        for a in evidencia["anios"].values()
    )


def test_convergencia_con_las_tres_respuestas_reales():
    """PA-00002: UMD GFC registra cobertura arbórea en 2020 (3.906 de 6.527 ha) y pérdida en 2022, por Whisp
    y por GFW; MapBiomas la ve como arroz desde 2015."""
    fuentes = fuentes_configuradas()
    analisis_reales = [
        _analisis("whisp", fuentes["whisp"].interpretar(WHISP_REAL_2)[1]),
        _analisis("gfw", fuentes["gfw"].interpretar(GFW_REAL_ADENDA)[1]),
        _analisis("mapbiomas", MapBiomas(True, 2015, 2024).interpretar(MAPBIOMAS_REAL)[1]),
    ]
    c = convergencia.calcular(analisis_reales, 6.527, 10)
    por_conjunto = {f.conjunto: f for f in c.filas}
    hansen = por_conjunto["umd_gfc"]
    assert hansen.vias == ["Whisp", "GFW"]
    assert (hansen.registra_bosque_2020, hansen.registra_cambio) == (True, True)
    assert [(m.nombre, m.valor) for m in hansen.despues_2020 if not m.serie] == [
        ("GFC_loss_after_2020", 0.21699999272823334),
        ("perdida_ha_total", 0.2292),
    ]
    assert (
        por_conjunto["mapbiomas_peru_c3"].registra_bosque_2020,
        por_conjunto["mapbiomas_peru_c3"].registra_cambio,
    ) == (
        False,
        False,
    )
    assert por_conjunto["esa_worldcover"].registra_bosque_2020 is False  # 0.002 ha, menos del 10 %
    assert (c.conteos["bosque_registran"], c.conteos["cambio_registran"]) == (1, 1)
    assert c.frase.startswith(
        f"Conjuntos de datos consultados: {len(c.filas)}. Registran bosque en 2020: 1 de "
    )
    assert c.discrepan == {"estado_2020": True, "cambio_posterior": True}

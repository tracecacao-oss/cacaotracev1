"""Adenda 4, sección 10: cruce de la parcela con las capas oficiales, con los servicios simulados."""

import json
import uuid
from urllib.parse import parse_qs

import httpx
import pytest

from app.catalogos import capas_legales
from app.config import get_settings
from app.models import Parcela, ParcelaVariable
from app.services import cruce
from app.services.capas_legales import registro
from tests import factorias
from tests.factorias import crear_parcela, punto, rectangulo

PARAMETROS_PERMITIDOS = {
    "geometry",
    "geometryType",
    "inSR",
    "spatialRel",
    "where",
    "outFields",
    "returnGeometry",
    "f",
    "outSR",
    "maxAllowableOffset",
    "geometryPrecision",
    "returnCountOnly",
}
METADATO_ZONIFICACION = {
    "types": [
        {
            "id": 601,
            "name": "Zonas de Producción Permanente",
            "domains": {"SCAZFO": {"codedValues": [{"code": 60101, "name": "Bosques de categoría I"}]}},
        },
        {
            "id": 605,
            "name": "Otras categorías",
            "domains": {"SCAZFO": {"codedValues": [{"code": 60501, "name": "Área agropecuaria"}]}},
        },
    ]
}


class Servicios:
    """Los servicios ArcGIS simulados: por (servidor, capa), los elementos que devuelven."""

    def __init__(self):
        self.elementos: dict[tuple[str, int], list[dict]] = {}
        self.caidos: set[str] = set()
        self.zonificados: set[str] = {"22"}
        self.peticiones: list[tuple[str, dict]] = []

    def poner(self, codigo: str, numero: int, geometria: dict, **atributos) -> None:
        servicio = capas_legales.POR_CODIGO[codigo].servicio
        self.elementos.setdefault((servicio, numero), []).append(
            {"type": "Feature", "properties": atributos, "geometry": geometria}
        )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        datos = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        url = str(request.url)
        self.peticiones.append((url, datos))
        if any(url.startswith(s) for s in self.caidos):
            return httpx.Response(500, text="")
        base, _, resto = url.rpartition("/MapServer/")
        servicio = f"{base}/MapServer"
        partes = resto.split("/")
        numero = int(partes[0])
        if len(partes) == 1:
            return httpx.Response(200, json=METADATO_ZONIFICACION)
        if datos.get("returnCountOnly") == "true":
            codigo = datos["where"].split("'")[1]
            return httpx.Response(200, json={"count": 7 if codigo in self.zonificados else 0})
        elementos = self.elementos.get((servicio, numero), [])
        donde = datos.get("where", "")
        if "CATZFO IN" in donde:
            forestal = not donde.startswith("NOT")
            elementos = [
                e for e in elementos if (e["properties"].get("CATZFO") in (601, 602, 603, 604)) == forestal
            ]
        if datos.get("returnGeometry") == "false":
            elementos = [
                {"type": "Feature", "properties": e["properties"], "geometry": None} for e in elementos
            ]
        return httpx.Response(200, json={"type": "FeatureCollection", "features": elementos})


@pytest.fixture
def servicios():
    return Servicios()


@pytest.fixture
def capas(servicios):
    return registro.construir(
        get_settings(), cliente=httpx.Client(transport=httpx.MockTransport(servicios)), dormir=lambda _s: None
    )


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


def _parcela(api, sesion, operador, productor, geometria=None, **datos) -> Parcela:
    r = crear_parcela(api.como(operador), productor.id, geometria or rectangulo(100, 100), **datos)
    assert r.status_code == 201, r.text
    return sesion.get(Parcela, uuid.UUID(r.json()["id"]))


def _cruzar(sesion, capas) -> None:
    assert cruce.procesar_siguiente(sesion, capas) is True


def _fila(sesion, parcela, variable) -> ParcelaVariable | None:
    return (
        sesion.query(ParcelaVariable)
        .filter_by(parcela_id=parcela.id, variable=variable, origen="cruce", vigente=True)
        .one_or_none()
    )


def test_cruce_sin_nada_en_las_capas(api, sesion, operador, productor, servicios, capas):
    parcela = _parcela(api, sesion, operador, productor)
    _cruzar(sesion, capas)
    valores = {
        v: _fila(sesion, parcela, v).valor for v in ("en_anp", "en_tierra_forestal", "en_tierra_comunal")
    }
    # San Martín (22) tiene zonificación en la capa: sin superposición, no es tierra forestal.
    assert valores == {"en_anp": "no", "en_tierra_forestal": "no", "en_tierra_comunal": "no"}
    assert _fila(sesion, parcela, "junto_a_cuerpo_de_agua").valor == "no"
    assert _fila(sesion, parcela, "en_patrimonio_cultural").valor == "no"
    sesion.refresh(parcela)
    assert parcela.cruce_solicitado_en is None
    assert {c["estado"] for c in parcela.cruce_estado["capas"].values()} == {"hecho"}
    fila = _fila(sesion, parcela, "en_anp")
    assert "Consultada el" in fila.fuente and "SERNANP" in fila.fuente
    # La interfaz lo muestra con su capa y su fecha, y el sistema nunca dice "no está": no figura.
    leg = api.get(f"/parcelas/{parcela.id}/legalidad").json()
    anp = next(v for v in leg["perfil"] if v["codigo"] == "en_anp")
    assert (anp["origen"], anp["nivel"]) == ("cruce", "verificado_en_fuente")


def test_cruce_que_devuelve_un_area_protegida(api, sesion, operador, productor, servicios, capas):
    servicios.poner(
        "sernanp_anp",
        1,
        rectangulo(1000, 1000, este_m=-500, norte_m=-500),
        anp_nomb="Parque Nacional de Prueba",
        anp_cate="Parque Nacional",
    )
    parcela = _parcela(api, sesion, operador, productor)
    _cruzar(sesion, capas)
    fila = _fila(sesion, parcela, "en_anp")
    assert fila.valor == "dentro"
    area = fila.detalle["areas"][0]
    assert (area["nombre"], area["categoria"]) == ("Parque Nacional de Prueba", "Parque Nacional")
    assert area["area_comun_ha"] == pytest.approx(1, rel=0.02)


def test_sin_resultado_en_un_departamento_sin_zonificacion(
    api, sesion, operador, productor, servicios, capas
):
    servicios.zonificados = set()
    parcela = _parcela(api, sesion, operador, productor)
    _cruzar(sesion, capas)
    fila = _fila(sesion, parcela, "en_tierra_forestal")
    assert fila.valor == "sin_zonificacion"
    assert fila.detalle["departamentos"] == ["22"] and fila.detalle["zonificados"] == []


def test_zonificacion_forestal_con_su_categoria(api, sesion, operador, productor, servicios, capas):
    servicios.poner(
        "serfor_zonificacion",
        0,
        rectangulo(1000, 1000, este_m=-500, norte_m=-500),
        CATZFO=601,
        SCAZFO=60101,
        DOCLEG="RM N° 039-2020-MINAM",
        NOMDEP="22",
    )
    parcela = _parcela(api, sesion, operador, productor)
    _cruzar(sesion, capas)
    fila = _fila(sesion, parcela, "en_tierra_forestal")
    assert fila.valor == "si"
    zona = fila.detalle["zonas"][0]
    # El significado sale del metadato de la capa, no de una lista propia.
    assert (zona["categoria_nombre"], zona["subcategoria_nombre"]) == (
        "Zonas de Producción Permanente",
        "Bosques de categoría I",
    )


def test_solo_area_agropecuaria_es_no(api, sesion, operador, productor, servicios, capas):
    servicios.zonificados = set()
    servicios.poner(
        "serfor_zonificacion", 0, rectangulo(1000, 1000, este_m=-500, norte_m=-500), CATZFO=605, SCAZFO=60501
    )
    parcela = _parcela(api, sesion, operador, productor)
    _cruzar(sesion, capas)
    fila = _fila(sesion, parcela, "en_tierra_forestal")
    assert fila.valor == "no"
    assert fila.detalle["otras"][0]["subcategoria_nombre"] == "Área agropecuaria"


def test_superposicion_de_001_ha_con_una_comunidad_es_un_roce(
    api, sesion, operador, productor, servicios, capas
):
    servicios.poner(
        "idep_comunidades", 1, rectangulo(20, 20, este_m=90, norte_m=90), nom_comuni="Comunidad X"
    )
    parcela = _parcela(api, sesion, operador, productor)
    _cruzar(sesion, capas)
    fila = _fila(sesion, parcela, "en_tierra_comunal")
    assert fila.valor == "no"
    assert fila.detalle["comunidades"] == []
    roce = fila.detalle["roces"][0]
    assert roce["nombre"] == "Comunidad X" and roce["area_comun_ha"] == pytest.approx(0.01, abs=0.002)


def test_comunidad_que_se_superpone(api, sesion, operador, productor, servicios, capas):
    servicios.poner("idep_comunidades", 0, rectangulo(100, 50), nom_comuni="Nativa Y", etnia="Awajún")
    parcela = _parcela(api, sesion, operador, productor)
    _cruzar(sesion, capas)
    fila = _fila(sesion, parcela, "en_tierra_comunal")
    assert fila.valor == "si"
    assert (fila.detalle["comunidad_nombre"], fila.detalle["comunidad_tipo"]) == ("Nativa Y", "nativa")


def test_rio_a_60_m_del_lindero(api, sesion, operador, productor, servicios, capas):
    servicios.poner(
        "ign_hidrografia", 2, rectangulo(5, 300, este_m=160, norte_m=-100), NOMBRE="Río de Prueba"
    )
    parcela = _parcela(api, sesion, operador, productor)
    _cruzar(sesion, capas)
    fila = _fila(sesion, parcela, "junto_a_cuerpo_de_agua")
    assert fila.valor == "si"
    assert fila.detalle["nombre"] == "Río de Prueba"
    assert fila.detalle["distancia_m"] == pytest.approx(60, abs=1.5)
    assert fila.detalle["distancia_maxima_m"] == 100


def test_parcela_punto_se_cruza_como_circulo_y_queda_marcada(
    api, sesion, operador, productor, servicios, capas
):
    parcela = _parcela(api, sesion, operador, productor, punto(), area_declarada_ha="1.0")
    _cruzar(sesion, capas)
    fila = _fila(sesion, parcela, "en_anp")
    assert fila.detalle["aproximacion"] is True
    sesion.refresh(parcela)
    assert parcela.cruce_estado["aproximacion"] is True
    geometria = json.loads(servicios.peticiones[0][1]["geometry"])
    assert len(geometria["rings"][0]) > 10  # un círculo, no un punto


def test_servicio_caido_deja_la_variable_sin_cruce_y_se_reintenta(
    api, sesion, operador, productor, servicios, capas
):
    servicios.caidos = {capas_legales.SERFOR_ZONIFICACION}
    parcela = _parcela(api, sesion, operador, productor)
    _cruzar(sesion, capas)
    assert _fila(sesion, parcela, "en_tierra_forestal") is None
    assert _fila(sesion, parcela, "en_anp").valor == "no"
    sesion.refresh(parcela)
    assert parcela.cruce_estado["capas"]["serfor_zonificacion"]["estado"] == "fallo"
    assert parcela.cruce_solicitado_en is not None  # se repite pronto
    # Una persona la puede declarar para no detener el trabajo.
    r = api.como(operador).post(
        f"/parcelas/{parcela.id}/perfil", json={"variable": "en_tierra_forestal", "valor": "no"}
    )
    assert r.status_code == 200, r.text
    capa = next(c for c in r.json()["cruce"]["capas"] if c["codigo"] == "serfor_zonificacion")
    assert capa["estado"] == "fallo"
    # Agotados los reintentos rápidos, la tarea diaria lo vuelve a la cola.
    parcela.cruce_solicitado_en = None
    sesion.flush()
    assert cruce.tarea_diaria(sesion) == 1
    sesion.refresh(parcela)
    assert parcela.cruce_solicitado_en is not None


def test_cambiar_la_geometria_vuelve_a_cruzar(api, sesion, operador, productor, servicios, capas):
    parcela = _parcela(api, sesion, operador, productor)
    _cruzar(sesion, capas)
    assert _fila(sesion, parcela, "en_anp") is not None
    r = api.patch(
        f"/parcelas/{parcela.id}",
        json={"geometria": rectangulo(100, 120), "motivo": "Se corrigió el lindero."},
    )
    assert r.status_code == 200, r.text
    # Los cruces de la geometría anterior dejan de valer y la parcela vuelve a la cola.
    assert _fila(sesion, parcela, "en_anp") is None
    sesion.refresh(parcela)
    assert parcela.cruce_solicitado_en is not None


def test_a_los_servicios_solo_se_envia_la_geometria(api, sesion, operador, productor, servicios, capas):
    parcela = _parcela(api, sesion, operador, productor, nombre="Chacra de Juana")
    _cruzar(sesion, capas)
    assert servicios.peticiones
    for url, datos in servicios.peticiones:
        assert set(datos) <= PARAMETROS_PERMITIDOS, (url, datos)
        texto = json.dumps(datos)
        for dato in (productor.dni, productor.nombres, productor.apellidos, parcela.nombre, parcela.codigo):
            assert dato not in texto


def test_sin_capas_configuradas_no_cruza(sesion):
    assert cruce.procesar_siguiente(sesion, None) is False

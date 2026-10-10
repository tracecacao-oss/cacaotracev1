"""Parcelas: geometría validada por dibujo o archivo, alertas, edición y exportación."""

import json
import math
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import Auditoria, Documento, Parcela
from tests import factorias
from tests.factorias import crear_parcela, punto, rectangulo

DATOS = Path(__file__).parent / "datos"


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


def _archivo(nombre: str) -> tuple[str, bytes]:
    return (nombre, (DATOS / nombre).read_bytes())


def _codigo(respuesta) -> str:
    return respuesta.json()["error"]["codigo"]


# --- Casos de la especificación ---


def test_poligono_valido_de_area_conocida(api, operador, productor):
    respuesta = crear_parcela(api.como(operador), productor.id, rectangulo(100, 100))
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    assert datos["tipo_geometria"] == "poligono"
    assert abs(Decimal(datos["area_calculada_ha"]) - 1) / 1 < Decimal("0.01")
    assert datos["codigo"] == "PA-00001"
    assert datos["origen_geometria"] == "dibujada"


def test_punto_con_area_declarada_de_3_ha(api, operador, productor):
    respuesta = crear_parcela(
        api.como(operador), productor.id, punto(), area_declarada_ha="3", area_cultivada_ha="2"
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["area_total_ha"] == "3.0000"


def test_punto_con_area_declarada_de_5_ha(api, operador, productor):
    respuesta = crear_parcela(
        api.como(operador), productor.id, punto(), area_declarada_ha="5", area_cultivada_ha="2"
    )
    assert respuesta.status_code == 400
    assert _codigo(respuesta) == "poligono_requerido"


@pytest.mark.parametrize(
    ("archivo", "codigo"),
    [
        ("lados_cruzados.geojson", "geometria_invalida"),
        ("utm.geojson", "coordenadas_invalidas"),
        ("invertidas.geojson", "coordenadas_invertidas"),
        ("otro_pais.geojson", "fuera_de_peru"),
        ("multipoligono_dos_partes.geojson", "varias_partes"),
        ("poligono_con_hueco.geojson", "poligono_con_huecos"),
    ],
)
def test_geometrias_rechazadas(api, operador, productor, archivo, codigo):
    respuesta = crear_parcela(api.como(operador), productor.id, archivo=_archivo(archivo), indice=0)
    assert respuesta.status_code == 400
    assert _codigo(respuesta) == codigo
    assert respuesta.json()["error"]["mensaje"]  # dice qué hacer, en español


def test_kml_y_geojson_de_la_misma_parcela_dan_la_misma_geometria(api, operador):
    api.como(operador)
    kml = api.post("/parcelas/analizar-archivo", files={"archivo": _archivo("cuadrado_1ha.kml")}).json()
    geojson = api.post(
        "/parcelas/analizar-archivo", files={"archivo": _archivo("cuadrado_1ha.geojson")}
    ).json()
    a, b = kml["geometrias"][0], geojson["geometrias"][0]
    assert a["area_ha"] == b["area_ha"]
    for p, q in zip(a["geometria"]["coordinates"][0], b["geometria"]["coordinates"][0], strict=True):
        assert math.isclose(p[0], q[0], abs_tol=1e-9) and math.isclose(p[1], q[1], abs_tol=1e-9)


def _analizar(api, geometria) -> dict:
    archivo = ("dibujo.geojson", json.dumps({"type": "Feature", "properties": {}, "geometry": geometria}))
    respuesta = api.post("/parcelas/analizar-archivo", files={"archivo": archivo})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["geometrias"][0]


def test_la_ubicacion_sale_de_las_coordenadas(api, operador):
    """Decisión del 2026-10-06: el distrito sale de los límites del INEI y la persona lo confirma."""
    api.como(operador)
    poligono = _analizar(api, rectangulo(100, 100))
    u = poligono["ubicacion"]
    assert (u["ubigeo"], u["departamento"], u["provincia"], u["distrito"]) == (
        "220201",
        "SAN MARTIN",
        "BELLAVISTA",
        "BELLAVISTA",
    )
    assert "INEI" in u["fuente"]
    assert _analizar(api, punto())["ubicacion"]["ubigeo"] == "220201"
    # En el mar, frente a La Libertad: dentro del recuadro del Perú, pero en ningún distrito.
    mar = _analizar(api, {"type": "Point", "coordinates": [-81.2, -8.0]})
    assert mar["valida"] and mar["ubicacion"] is None


def test_kml_con_entidad_externa_se_rechaza(api, operador):
    respuesta = api.como(operador).post("/parcelas/analizar-archivo", files={"archivo": _archivo("xxe.kml")})
    assert respuesta.status_code == 422
    assert _codigo(respuesta) == "archivo_invalido"
    assert "root" not in respuesta.text


def test_archivo_con_tres_geometrias_indice_1(api, sesion, operador, productor, storage_falso):
    api.como(operador)
    analisis = api.post(
        "/parcelas/analizar-archivo", files={"archivo": _archivo("tres_parcelas.geojson")}
    ).json()
    assert len(analisis["geometrias"]) == 3
    assert [g["nombre"] for g in analisis["geometrias"]] == [
        "Parcela Demo A",
        "Parcela Demo B",
        "Parcela Demo C",
    ]
    assert sesion.query(Parcela).count() == 0  # analizar no guarda nada

    respuesta = crear_parcela(api, productor.id, archivo=_archivo("tres_parcelas.geojson"), indice=1)
    assert respuesta.status_code == 201, respuesta.text
    creada = respuesta.json()
    assert creada["geometria"] == analisis["geometrias"][1]["geometria"]
    assert creada["origen_geometria"] == "archivo"
    documento = sesion.query(Documento).filter_by(tipo="archivo_geometria").one()
    assert documento.entidad_id == Parcela.id.type.python_type(creada["id"])
    assert storage_falso.archivos[documento.ruta] == (DATOS / "tres_parcelas.geojson").read_bytes()


def test_alerta_area_discrepante(api, operador, productor):
    lado = math.sqrt(12000)  # 1.2 ha
    respuesta = crear_parcela(
        api.como(operador), productor.id, rectangulo(lado, lado), area_declarada_ha="2", area_cultivada_ha="1"
    )
    assert "area_discrepante" in respuesta.json()["alertas"]


def test_alerta_diez_hectareas(api, operador, productor):
    lado = math.sqrt(120000)  # 12 ha
    respuesta = crear_parcela(api.como(operador), productor.id, rectangulo(lado, lado), area_cultivada_ha="5")
    assert respuesta.status_code == 201
    assert "diez_hectareas_o_mas" in respuesta.json()["alertas"]


def test_cambio_de_geometria_sin_motivo(api, operador, productor):
    parcela = crear_parcela(api.como(operador), productor.id, rectangulo(100, 100)).json()
    respuesta = api.patch(f"/parcelas/{parcela['id']}", json={"geometria": rectangulo(90, 90)})
    assert respuesta.status_code == 422


def test_cambio_de_geometria_con_motivo_guarda_wkt_anterior(api, sesion, operador, productor):
    parcela = crear_parcela(api.como(operador), productor.id, rectangulo(100, 100)).json()
    respuesta = api.patch(
        f"/parcelas/{parcela['id']}",
        json={"geometria": rectangulo(90, 90), "motivo": "Lindero corregido en campo"},
    )
    assert respuesta.status_code == 200
    assert Decimal(respuesta.json()["area_calculada_ha"]) < Decimal("0.82")
    fila = sesion.query(Auditoria).filter_by(accion="parcela.editar_geometria").one()
    assert fila.detalle["geometria_anterior"].startswith("POLYGON ((")
    assert fila.detalle["motivo"] == "Lindero corregido en campo"


# --- Reglas adicionales ---


def test_codigo_correlativo_por_cooperativa(api, sesion, coop, operador, productor):
    api.como(operador)
    a = crear_parcela(api, productor.id, rectangulo(80, 80), nombre="Uno").json()
    b = crear_parcela(api, productor.id, rectangulo(80, 80, este_m=200), nombre="Dos").json()
    assert (a["codigo"], b["codigo"]) == ("PA-00001", "PA-00002")
    otra = factorias.cooperativa(sesion)
    otro_operador = factorias.perfil(sesion, "operador", otra)
    otro_productor = factorias.productor(sesion, otra)
    c = crear_parcela(api.como(otro_operador), otro_productor.id, rectangulo(80, 80, este_m=1000)).json()
    assert c["codigo"] == "PA-00001"


def test_nombre_unico_por_productor(api, operador, productor):
    api.como(operador)
    crear_parcela(api, productor.id, rectangulo(80, 80), nombre="La Loma")
    respuesta = crear_parcela(api, productor.id, rectangulo(80, 80, este_m=300), nombre="la loma")
    assert respuesta.status_code == 409


def test_area_cultivada_no_supera_la_total(api, operador, productor):
    respuesta = crear_parcela(api.como(operador), productor.id, rectangulo(100, 100), area_cultivada_ha="1.5")
    assert respuesta.status_code == 400
    assert _codigo(respuesta) == "area_cultivada_excede"


def test_punto_sin_area_declarada(api, operador, productor):
    respuesta = crear_parcela(api.como(operador), productor.id, punto())
    assert respuesta.status_code == 422


def test_sin_geometria(api, operador, productor):
    respuesta = crear_parcela(api.como(operador), productor.id)
    assert respuesta.status_code == 422
    assert _codigo(respuesta) == "geometria_requerida"


def test_anillo_sin_cerrar_se_cierra(api, operador, productor):
    abierto = rectangulo(100, 100)
    abierto["coordinates"][0].pop()
    respuesta = crear_parcela(api.como(operador), productor.id, abierto)
    assert respuesta.status_code == 201
    anillo = respuesta.json()["geometria"]["coordinates"][0]
    assert anillo[0] == anillo[-1]


def test_coordenadas_sin_perder_precision(api, operador, productor):
    """Se guardan sin redondear y se entregan con al menos 6 decimales (8 en la API)."""
    dibujada = rectangulo(100, 100, este_m=12.3456789)
    respuesta = crear_parcela(api.como(operador), productor.id, dibujada)
    for p, q in zip(dibujada["coordinates"][0], respuesta.json()["geometria"]["coordinates"][0], strict=True):
        assert abs(p[0] - q[0]) < 1e-8 and abs(p[1] - q[1]) < 1e-8


def test_exportar_geojson_sin_datos_personales(api, operador, productor):
    parcela = crear_parcela(api.como(operador), productor.id, rectangulo(100, 100)).json()
    respuesta = api.get(f"/parcelas/{parcela['id']}/geojson")
    assert respuesta.headers["content-type"].startswith("application/geo+json")
    feature = respuesta.json()
    assert set(feature["properties"]) == {"parcela_id", "nombre", "tipo_geometria", "area_ha"}
    assert productor.dni not in respuesta.text
    anillo = feature["geometry"]["coordinates"][0]
    # Sentido antihorario: área con signo (fórmula del cordón) positiva.
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(anillo, anillo[1:], strict=False))
    assert area > 0


def test_mapa_en_geojson(api, operador, productor):
    api.como(operador)
    crear_parcela(api, productor.id, rectangulo(100, 100))
    crear_parcela(
        api, productor.id, rectangulo(100, 100, norte_m=500), nombre="Otra", midagri_estado="validado"
    )
    coleccion = api.get("/parcelas", params={"formato": "geojson"}).json()
    assert coleccion["type"] == "FeatureCollection"
    propiedades = {f["properties"]["nombre"]: f["properties"] for f in coleccion["features"]}
    # Adenda 4: el perfil legal sin completar no es una alerta (lo dice la compuerta); sin sustento de
    # MIDAGRI, sí.
    assert propiedades["Parcela Demo"]["estado_mapa"] == "sin_alertas"
    assert propiedades["Otra"]["estado_mapa"] == "con_alertas"
    assert "superposicion" not in propiedades["Otra"]["alertas"]


def test_desactivar(api, sesion, operador, productor):
    parcela = crear_parcela(api.como(operador), productor.id, rectangulo(100, 100)).json()
    respuesta = api.post(f"/parcelas/{parcela['id']}/desactivar")
    assert respuesta.json()["estado"] == "inactiva"
    assert sesion.query(Auditoria).filter_by(accion="parcela.desactivar").count() == 1
    assert api.patch(f"/parcelas/{parcela['id']}", json={"nombre": "Otra"}).status_code == 400


def test_lector_no_crea_parcelas(api, sesion, coop, productor):
    lector = factorias.perfil(sesion, "lector", coop)
    assert crear_parcela(api.como(lector), productor.id, rectangulo(100, 100)).status_code == 403


def test_estado_midagri_y_nivel(api, operador, productor):
    api.como(operador)
    parcela = crear_parcela(api, productor.id, rectangulo(100, 100), midagri_estado="validado").json()
    assert parcela["nivel_midagri"] == "declarado"
    assert "sin_sustento_midagri" in parcela["alertas"]
    api.post(
        f"/parcelas/{parcela['id']}/documentos",
        data={"tipo": "sustento_midagri"},
        files={"archivo": ("constancia.pdf", b"%PDF-1.7 sustento demo")},
    )
    detalle = api.get(f"/parcelas/{parcela['id']}").json()
    assert detalle["nivel_midagri"] == "documentado"
    assert "sin_sustento_midagri" not in detalle["alertas"]
    assert [d["tipo"] for d in detalle["documentos"]] == ["sustento_midagri"]
    assert {h["accion"] for h in detalle["historial"]} == {"parcela.crear", "documento.cargar"}

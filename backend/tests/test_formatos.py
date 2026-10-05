"""Formatos de archivo de la parcela: KMZ, Shapefile en .zip y listas de coordenadas.

Todos deben dar la misma geometría que el GeoJSON de referencia (cuadrado de 1 ha).
"""

import io
import json
import math
import zipfile
from pathlib import Path

import openpyxl
import pytest
import shapefile

from app.models import Documento
from tests import factorias
from tests.factorias import crear_parcela

DATOS = Path(__file__).parent / "datos"
REFERENCIA = json.loads((DATOS / "cuadrado_1ha.geojson").read_text())["geometry"]["coordinates"][0]
# (lat, lon) de los vértices de referencia, sin repetir el primero.
VERTICES = [(lat, lon) for lon, lat in REFERENCIA[:-1]]
WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)
UTM_PRJ = (
    'PROJCS["WGS_1984_UTM_Zone_18S",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]]],PROJECTION["Transverse_Mercator"]]'
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


def _analizar(api, nombre: str, contenido: bytes):
    return api.post("/parcelas/analizar-archivo", files={"archivo": (nombre, contenido)})


def _igual_a_la_referencia(geometria: dict) -> None:
    anillo = geometria["coordinates"][0]
    assert len(anillo) == len(REFERENCIA)
    # Mismos vértices, aunque el anillo empiece en otro o vaya en otro sentido.
    for lon, lat in REFERENCIA:
        assert any(
            math.isclose(lon, p[0], abs_tol=1e-7) and math.isclose(lat, p[1], abs_tol=1e-7) for p in anillo
        )


def _zip(archivos: dict[str, bytes]) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
    return salida.getvalue()


def _shapefile(prj: str | None = WGS84_PRJ, anillo=None) -> bytes:
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    escritor = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    escritor.field("NOMBRE", "C")
    # En Shapefile el anillo exterior va en sentido horario.
    escritor.poly([anillo or list(reversed(REFERENCIA))])
    escritor.record("Parcela Shape")
    escritor.close()
    archivos = {
        "capa/parcela.shp": shp.getvalue(),
        "capa/parcela.shx": shx.getvalue(),
        "capa/parcela.dbf": dbf.getvalue(),
    }
    if prj:
        archivos["capa/parcela.prj"] = prj.encode()
    return _zip(archivos)


# --- KMZ y Shapefile ---


def test_kmz_da_la_misma_geometria_que_el_geojson(api, operador):
    kmz = _zip({"doc.kml": (DATOS / "cuadrado_1ha.kml").read_bytes(), "files/icono.png": b"\x89PNG"})
    respuesta = _analizar(api.como(operador), "parcela.kmz", kmz)
    assert respuesta.status_code == 200, respuesta.text
    geometria = respuesta.json()["geometrias"][0]
    assert geometria["errores"] == []
    _igual_a_la_referencia(geometria["geometria"])


def test_kmz_sin_kml(api, operador):
    respuesta = _analizar(api.como(operador), "parcela.kmz", _zip({"leeme.txt": b"hola"}))
    assert respuesta.status_code == 422
    assert "KML" in respuesta.json()["error"]["mensaje"]


def test_shapefile_en_zip_con_nombre_del_dbf(api, operador):
    respuesta = _analizar(api.como(operador), "parcelas.zip", _shapefile())
    assert respuesta.status_code == 200, respuesta.text
    geometria = respuesta.json()["geometrias"][0]
    assert geometria["nombre"] == "Parcela Shape"
    assert geometria["errores"] == []
    _igual_a_la_referencia(geometria["geometria"])


def test_shapefile_sin_prj_se_valida_por_rangos(api, operador):
    respuesta = _analizar(api.como(operador), "parcelas.zip", _shapefile(prj=None))
    assert respuesta.json()["geometrias"][0]["errores"] == []


def test_shapefile_en_utm_se_rechaza(api, operador):
    respuesta = _analizar(api.como(operador), "parcelas.zip", _shapefile(prj=UTM_PRJ))
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "coordenadas_invalidas"


def test_zip_sin_shapefile(api, operador):
    respuesta = _analizar(api.como(operador), "parcelas.zip", _zip({"foto.jpg": b"\xff\xd8"}))
    assert respuesta.status_code == 422
    assert ".shp" in respuesta.json()["error"]["mensaje"]


def test_zip_bomba_se_rechaza(api, operador):
    respuesta = _analizar(api.como(operador), "parcela.kmz", _zip({"doc.kml": b"0" * (60 * 1024 * 1024)}))
    assert respuesta.status_code == 422
    assert "demasiado grande" in respuesta.json()["error"]["mensaje"]


@pytest.mark.parametrize("nombre", ["parcela.shp", "parcela.dbf"])
def test_partes_sueltas_del_shapefile(api, operador, nombre):
    respuesta = _analizar(api.como(operador), nombre, b"\x00\x00\x27\x0a")
    assert respuesta.status_code == 422
    assert ".zip" in respuesta.json()["error"]["mensaje"]


@pytest.mark.parametrize("nombre", ["ruta.gpx", "parcela.xls", "plano.dwg"])
def test_formatos_no_admitidos(api, operador, nombre):
    respuesta = _analizar(api.como(operador), nombre, b"datos")
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "formato_no_admitido"


# --- Listas de coordenadas ---


def _texto(lineas: list[str]) -> bytes:
    return "\n".join(lineas).encode()


@pytest.mark.parametrize(
    "lineas",
    [
        [f"{lat}, {lon}" for lat, lon in VERTICES],  # como se copia de Google Maps
        [f"{lon} {lat}" for lat, lon in VERTICES],  # longitud primero
        [f"{lat:.10f};{lon:.10f}".replace(".", ",") for lat, lon in VERTICES],  # coma decimal
        ["vertice, latitud, longitud", *(f"{i}, {lat}, {lon}" for i, (lat, lon) in enumerate(VERTICES, 1))],
        [f"{abs(lat)} {abs(lon)}" for lat, lon in VERTICES],  # sin signo: sur y oeste
    ],
    ids=["google_maps", "lon_lat", "coma_decimal", "numerado", "sin_signo"],
)
def test_lista_de_coordenadas_en_texto(api, operador, lineas):
    respuesta = _analizar(api.como(operador), "coordenadas.txt", _texto(lineas))
    assert respuesta.status_code == 200, respuesta.text
    geometria = respuesta.json()["geometrias"][0]
    assert geometria["errores"] == []
    _igual_a_la_referencia(geometria["geometria"])


def _gms(valor: float, positivo: str, negativo: str) -> str:
    hemisferio = negativo if valor < 0 else positivo
    valor = abs(valor)
    grados = int(valor)
    minutos = int((valor - grados) * 60)
    segundos = (valor - grados - minutos / 60) * 3600
    return f"{grados}°{minutos}'{segundos:.4f}\"{hemisferio}"


def test_grados_minutos_y_segundos(api, operador):
    lineas = [f"{_gms(lat, 'N', 'S')} {_gms(lon, 'E', 'W')}" for lat, lon in VERTICES]
    respuesta = _analizar(api.como(operador), "coordenadas.txt", _texto(lineas))
    _igual_a_la_referencia(respuesta.json()["geometrias"][0]["geometria"])


def test_varias_parcelas_separadas_por_nombre(api, operador):
    lineas = ["Parcela Norte", *(f"{lat}, {lon}" for lat, lon in VERTICES), "", "Pozo", "-6.96, -76.56"]
    geometrias = _analizar(api.como(operador), "coordenadas.txt", _texto(lineas)).json()["geometrias"]
    assert [(g["nombre"], g["tipo"]) for g in geometrias] == [
        ("Parcela Norte", "poligono"),
        ("Pozo", "punto"),
    ]


def test_csv_de_excel_con_columnas(api, operador):
    filas = ["Nombre;Latitud;Longitud", *(f"Lote A;{lat};{lon}".replace(".", ",") for lat, lon in VERTICES)]
    respuesta = _analizar(api.como(operador), "lote.csv", "\r\n".join(filas).encode("cp1252"))
    geometria = respuesta.json()["geometrias"][0]
    assert geometria["nombre"] == "Lote A"
    _igual_a_la_referencia(geometria["geometria"])


def test_excel_con_columnas(api, operador):
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(["Longitud", "Latitud"])
    for lat, lon in VERTICES:
        hoja.append([lon, lat])
    salida = io.BytesIO()
    libro.save(salida)
    respuesta = _analizar(api.como(operador), "vertices.xlsx", salida.getvalue())
    assert respuesta.status_code == 200, respuesta.text
    _igual_a_la_referencia(respuesta.json()["geometrias"][0]["geometria"])


@pytest.mark.parametrize(
    ("contenido", "codigo", "texto"),
    [
        (b"Este,Norte\n383210,9231456\n383310,9231456\n383310,9231556", "coordenadas_invalidas", "UTM"),
        (b"383210 9231456\n383310 9231456\n383310 9231556", "coordenadas_invalidas", "UTM"),
        (b"-6.95, -76.55\n-6.95, -76.549", "archivo_invalido", "2 vértices"),
        (b"-6.95, -76.55\n-6.95, -76.549, -6.94", "archivo_invalido", "línea 2"),
        (b"-7 -77\n-7 -76\n-6 -76", "archivo_invalido", "línea 1"),
        (b"\n\n", "sin_geometrias", "ninguna coordenada"),
    ],
    ids=["utm_con_titulos", "utm_sin_titulos", "dos_vertices", "linea_rara", "enteros", "vacia"],
)
def test_listas_que_no_se_entienden(api, operador, contenido, codigo, texto):
    respuesta = _analizar(api.como(operador), "coordenadas.txt", contenido)
    assert respuesta.status_code in (400, 422)
    error = respuesta.json()["error"]
    assert error["codigo"] == codigo
    assert texto in error["mensaje"]


def test_coordenadas_pegadas_crean_la_parcela_y_guardan_el_texto(
    api, sesion, operador, productor, storage_falso
):
    texto = _texto([f"{lat}, {lon}" for lat, lon in VERTICES])
    respuesta = crear_parcela(api.como(operador), productor.id, archivo=("coordenadas.txt", texto), indice=0)
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["origen_geometria"] == "archivo"
    documento = sesion.query(Documento).filter_by(tipo="archivo_geometria").one()
    assert documento.tipo_mime == "text/plain"
    assert storage_falso.archivos[documento.ruta] == texto

"""Esri World Imagery Wayback (adenda 2 de la Parte 4): versiones de alta resolución de un lugar con su
fecha de captura real, el proveedor y la resolución.

La fecha de publicación de una versión no es la de captura: la captura se lee de la capa de metadatos de
cada versión (`SRC_DATE2`). Qué versiones cambiaron la imagen en un punto sale del servicio "tilemap", con
la misma lógica que el código de Esri (github.com/Esri/wayback-core). Todo es público y no pide clave,
pero el servicio rechaza (403) el identificador por defecto de httpx: las peticiones se identifican como
CacaoTrace. Comprobado con backend/scripts/check_imagenes.py el 2026-10-05.

Por los términos de Esri (Master Agreement, 3.2) no se guardan sus imágenes: se guardan solo los datos de
cada versión y la interfaz muestra las teselas desde Esri.
"""

import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx

CONFIG = "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json"
TILEMAP = (
    "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tilemap/"
    "{version}/{z}/{fila}/{columna}"
)
# Lo que usa la interfaz (Leaflet): {s} es uno de los subdominios de Esri.
TESELAS = (
    "https://{s}.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/"
    "tile/{version}/{z}/{y}/{x}"
)
SUBDOMINIOS = ("wayback", "wayback-a", "wayback-b")
ZOOM = 17  # capa de metadatos 23 - 17 = 6 ("1.2m"), como en wayback-core
ATRIBUCION = "Esri, Vantor, Earthstar Geographics, and the GIS User Community"
AGENTE = "CacaoTrace/1.0 (+https://cacaotrace.pages.dev)"


class ErrorWayback(Exception):
    def __init__(self, detalle: str):
        super().__init__(detalle)
        self.detalle = detalle


@dataclass
class Captura:
    version: int  # número de la versión de Wayback
    publicada: date
    fecha_captura: date
    proveedor: str | None
    sensor: str | None
    resolucion_m: float | None


def _tesela(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2**z
    columna = int((lon + 180) / 360 * n)
    fila = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return columna, fila


class Wayback:
    def __init__(self, http: httpx.Client | None = None):
        self.http = http or httpx.Client(
            timeout=httpx.Timeout(60, connect=20), headers={"User-Agent": AGENTE}, follow_redirects=True
        )

    def _json(self, url: str, **params) -> dict:
        try:
            r = self.http.get(url, params=params or None)
        except httpx.HTTPError as exc:
            raise ErrorWayback(f"No se pudo conectar con Esri Wayback: {type(exc).__name__}") from exc
        if r.status_code != 200:
            raise ErrorWayback(f"Esri Wayback respondió HTTP {r.status_code}.")
        try:
            return r.json()
        except ValueError as exc:
            raise ErrorWayback("Esri Wayback respondió algo que no es JSON.") from exc

    def capturas(self, lat: float, lon: float) -> list[Captura]:
        """Una por cada imagen distinta en el punto (misma fecha de captura y proveedor = misma imagen)."""
        config = self._json(CONFIG)
        versiones = sorted(
            ((int(numero), datos) for numero, datos in config.items()),
            key=lambda par: _fecha_publicacion(par[1]),
            reverse=True,
        )
        orden = [numero for numero, _ in versiones]
        por_numero = dict(versiones)
        columna, fila = _tesela(lat, lon, ZOOM)
        cambios: list[int] = []
        actual: int | None = orden[0] if orden else None
        while actual is not None and len(cambios) < 60:
            datos = self._json(TILEMAP.format(version=actual, z=ZOOM, fila=fila, columna=columna))
            if not datos.get("data") or not datos["data"][0]:
                break
            elegida = datos["select"][0]
            if elegida in cambios or elegida not in por_numero:
                break
            cambios.append(elegida)
            posicion = orden.index(elegida)
            actual = orden[posicion + 1] if posicion + 1 < len(orden) else None

        capturas: dict[tuple, Captura] = {}
        for numero in cambios:
            datos = por_numero[numero]
            consulta = self._json(
                f"{datos['metadataLayerUrl']}/{23 - ZOOM}/query",
                f="json",
                where="1=1",
                outFields="SRC_DATE2,NICE_DESC,SRC_DESC,SRC_RES",
                geometry=json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
                geometryType="esriGeometryPoint",
                spatialRel="esriSpatialRelIntersects",
                returnGeometry="false",
            )
            atributos = (consulta.get("features") or [{}])[0].get("attributes") or {}
            if not atributos.get("SRC_DATE2"):
                continue  # sin fecha de captura no se muestra (9.2, regla 1)
            captura = Captura(
                version=numero,
                publicada=_fecha_publicacion(datos),
                fecha_captura=datetime.fromtimestamp(atributos["SRC_DATE2"] / 1000, UTC).date(),
                proveedor=atributos.get("NICE_DESC"),
                sensor=atributos.get("SRC_DESC"),
                resolucion_m=atributos.get("SRC_RES"),
            )
            clave = (captura.fecha_captura, captura.sensor)
            # De las versiones con la misma imagen se conserva la más reciente (la primera recorrida).
            capturas.setdefault(clave, captura)
        return sorted(capturas.values(), key=lambda c: c.fecha_captura)


def _fecha_publicacion(datos: dict) -> date:
    texto = datos.get("itemTitle", "").split("Wayback ")[-1].rstrip(")")
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return date.min

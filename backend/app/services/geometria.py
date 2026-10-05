"""Geometría de la parcela: lectura de GeoJSON y KML y validaciones automáticas.

Las validaciones se ejecutan en el orden de la especificación y se detienen en la primera que
falla. Una geometría que falla se rechaza: el sistema nunca la corrige por su cuenta. La única
modificación es cerrar un anillo que no repite su primer vértice.
"""

import json
import math
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import PurePath
from typing import Any

from defusedxml import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden
from defusedxml import ElementTree as XML
from shapely.geometry import Point, Polygon, mapping
from shapely.geometry.base import BaseGeometry
from sqlalchemy import text
from sqlalchemy.orm import Session

TAMANO_MAXIMO_ARCHIVO = 2 * 1024 * 1024
MAXIMO_VERTICES = 2000
AREA_MINIMA_HA = Decimal("0.01")
AREA_MAXIMA_HA = Decimal("100")
AREA_POLIGONO_OBLIGATORIO_HA = Decimal("4")
# Rectángulo que contiene al Perú.
PERU_LATITUD = (-18.5, 0.1)
PERU_LONGITUD = (-81.5, -68.5)

MENSAJES = {
    "coordenadas_invalidas": (
        "Las coordenadas no son latitud y longitud válidas. Si el archivo está en UTM u otra proyección, "
        "expórtalo en WGS 84 (EPSG:4326)."
    ),
    "coordenadas_invertidas": (
        "La latitud y la longitud parecen estar invertidas. "
        "En GeoJSON va primero la longitud y luego la latitud."
    ),
    "fuera_de_peru": "La parcela queda fuera del Perú. Revisa su ubicación.",
    "demasiados_vertices": "El polígono tiene más de 2,000 vértices. Simplifícalo antes de cargarlo.",
    "geometria_invalida": (
        "El polígono no es válido: sus lados se cruzan o le faltan vértices. Corrige el dibujo."
    ),
    "area_demasiado_pequena": "El polígono mide menos de 0.01 ha. Revisa que esté completo.",
    "area_excesiva": (
        "El polígono mide más de 100 ha. Revisa el dibujo o registra la tierra en varias parcelas."
    ),
    "poligono_requerido": "Una parcela de 4 ha o más debe registrarse como polígono, no como punto.",
    "varias_partes": "El polígono tiene varias partes. Registra cada parte como una parcela distinta.",
    "poligono_con_huecos": "El polígono tiene huecos. Registra la parcela sin huecos.",
    "tipo_no_admitido": (
        "Solo se aceptan polígonos o puntos. Las líneas y otras geometrías no sirven para una parcela."
    ),
}


class ErrorArchivo(Exception):
    """El archivo no se puede leer: formato, tamaño o contenido no permitido."""

    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


@dataclass
class Resultado:
    indice: int
    nombre: str | None
    tipo: str | None = None  # "poligono" o "punto"
    geometria: BaseGeometry | None = None
    area_ha: Decimal | None = None
    errores: list[dict] = field(default_factory=list)

    @property
    def valida(self) -> bool:
        return not self.errores

    @property
    def error(self) -> dict | None:
        return self.errores[0] if self.errores else None

    def fallar(self, codigo: str) -> "Resultado":
        self.errores.append({"codigo": codigo, "mensaje": MENSAJES[codigo]})
        return self


def a_geojson(geometria: BaseGeometry, decimales: int = 8) -> dict:
    """GeoJSON con al menos 6 decimales (8 por defecto)."""

    def redondear(valor):
        if isinstance(valor, list | tuple):
            return [redondear(v) for v in valor]
        return round(valor, decimales)

    datos = mapping(geometria)
    return {"type": datos["type"], "coordinates": redondear(datos["coordinates"])}


# ---------- Lectura de archivos ----------


def leer_archivo(nombre: str, contenido: bytes) -> list[tuple[str | None, dict]]:
    """Devuelve (nombre, geometría GeoJSON) por cada entidad del archivo. No valida."""
    extension = PurePath(nombre or "").suffix.lower()
    if extension in (".kmz", ".shp", ".shx", ".dbf", ".prj", ".zip", ".gpx", ".csv"):
        raise ErrorArchivo(
            "formato_no_admitido",
            "Ese formato no se acepta. Exporta la parcela como KML o GeoJSON y vuelve a cargarla.",
        )
    if extension not in (".geojson", ".json", ".kml"):
        raise ErrorArchivo(
            "formato_no_admitido", "Solo se aceptan archivos GeoJSON (.geojson, .json) o KML (.kml)."
        )
    if not contenido:
        raise ErrorArchivo("archivo_vacio", "El archivo está vacío.")
    if len(contenido) > TAMANO_MAXIMO_ARCHIVO:
        raise ErrorArchivo("archivo_muy_grande", "El archivo supera el máximo de 2 MB.")
    if extension == ".kml":
        return _leer_kml(contenido)
    return _leer_geojson(contenido)


def tipo_mime_de(nombre: str) -> str:
    if PurePath(nombre).suffix.lower() == ".kml":
        return "application/vnd.google-earth.kml+xml"
    return "application/geo+json"


def _leer_geojson(contenido: bytes) -> list[tuple[str | None, dict]]:
    try:
        datos = json.loads(contenido.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ErrorArchivo("archivo_invalido", "El archivo no es un GeoJSON válido.") from exc
    if not isinstance(datos, dict):
        raise ErrorArchivo("archivo_invalido", "El archivo no es un GeoJSON válido.")

    if datos.get("type") == "FeatureCollection":
        entidades = datos.get("features") or []
    elif datos.get("type") == "Feature":
        entidades = [datos]
    else:
        entidades = [{"type": "Feature", "geometry": datos, "properties": {}}]

    resultado = []
    for entidad in entidades:
        if not isinstance(entidad, dict):
            continue
        propiedades = entidad.get("properties") or {}
        nombre = next(
            (str(propiedades[k]) for k in ("nombre", "name", "Name", "NOMBRE") if propiedades.get(k)), None
        )
        resultado.append((nombre, entidad.get("geometry") or {}))
    if not resultado:
        raise ErrorArchivo("sin_geometrias", "El archivo no contiene ninguna geometría.")
    return resultado


def _local(etiqueta: str) -> str:
    return etiqueta.rsplit("}", 1)[-1]


def _hijos(elemento, nombre: str):
    return [e for e in elemento.iter() if _local(e.tag) == nombre]


def _coordenadas_kml(elemento) -> list[list[Any]]:
    """'lon,lat[,alt] lon,lat …' → [[lon, lat], …]. Se ignora la altitud."""
    nodo = next(iter(_hijos(elemento, "coordinates")), None)
    if nodo is None or not (nodo.text or "").strip():
        return []
    puntos = []
    for tupla in nodo.text.split():
        partes = tupla.split(",")
        puntos.append([_numero(p) for p in partes[:2]])
    return puntos


def _numero(texto: str):
    try:
        return float(texto)
    except ValueError:
        return texto  # la validación de coordenadas lo rechazará


def _poligono_kml(elemento) -> list:
    exterior = [_coordenadas_kml(b) for b in _hijos(elemento, "outerBoundaryIs")]
    interiores = [_coordenadas_kml(b) for b in _hijos(elemento, "innerBoundaryIs")]
    return [*exterior[:1], *interiores]


def _leer_kml(contenido: bytes) -> list[tuple[str | None, dict]]:
    try:
        raiz = XML.fromstring(contenido, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden) as exc:
        raise ErrorArchivo(
            "archivo_invalido",
            "El KML contiene entidades o referencias externas no permitidas y no se procesó.",
        ) from exc
    except XML.ParseError as exc:
        raise ErrorArchivo("archivo_invalido", "El archivo no es un KML válido.") from exc

    resultado = []
    for marca in _hijos(raiz, "Placemark"):
        nombre_nodo = next((e for e in marca if _local(e.tag) == "name"), None)
        nombre = (nombre_nodo.text or "").strip() or None if nombre_nodo is not None else None
        poligonos = _hijos(marca, "Polygon")
        puntos = _hijos(marca, "Point")
        if len(poligonos) > 1:
            geometria = {"type": "MultiPolygon", "coordinates": [_poligono_kml(p) for p in poligonos]}
        elif poligonos:
            geometria = {"type": "Polygon", "coordinates": _poligono_kml(poligonos[0])}
        elif puntos:
            coordenadas = _coordenadas_kml(puntos[0])
            geometria = {"type": "Point", "coordinates": coordenadas[0] if coordenadas else []}
        else:
            # Líneas u otros elementos: se informan como tipo no admitido.
            geometria = {"type": "LineString", "coordinates": []}
        resultado.append((nombre, geometria))
    if not resultado:
        raise ErrorArchivo("sin_geometrias", "El KML no contiene ninguna parcela (Placemark).")
    return resultado


# ---------- Validación ----------


def _posiciones(tipo: str, coordenadas) -> list:
    if tipo == "Point":
        return [coordenadas]
    return [p for anillo in coordenadas for p in anillo]


def _coordenada_valida(posicion) -> bool:
    if not isinstance(posicion, list | tuple) or len(posicion) < 2:
        return False
    lon, lat = posicion[0], posicion[1]
    numeros = all(
        isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v) for v in (lon, lat)
    )
    return numeros and -180 <= lon <= 180 and -90 <= lat <= 90


def _en_peru(lon: float, lat: float) -> bool:
    return PERU_LATITUD[0] <= lat <= PERU_LATITUD[1] and PERU_LONGITUD[0] <= lon <= PERU_LONGITUD[1]


def _normalizar_tipo(resultado: Resultado, geometria: dict) -> tuple[str, Any] | None:
    tipo = geometria.get("type") if isinstance(geometria, dict) else None
    coordenadas = geometria.get("coordinates") if isinstance(geometria, dict) else None
    if tipo == "MultiPolygon" and isinstance(coordenadas, list):
        if len(coordenadas) != 1:
            resultado.fallar("varias_partes")
            return None
        tipo, coordenadas = "Polygon", coordenadas[0]
    if tipo == "Polygon":
        if not isinstance(coordenadas, list) or not coordenadas:
            resultado.fallar("geometria_invalida")
            return None
        if len(coordenadas) > 1:
            resultado.fallar("poligono_con_huecos")
            return None
        return tipo, coordenadas
    if tipo == "Point":
        return tipo, coordenadas
    resultado.fallar("tipo_no_admitido")
    return None


def validar(
    sesion: Session,
    geometria: dict,
    *,
    indice: int = 0,
    nombre: str | None = None,
    area_declarada_ha: Decimal | None = None,
) -> Resultado:
    resultado = Resultado(indice=indice, nombre=nombre)
    normalizada = _normalizar_tipo(resultado, geometria)
    if normalizada is None:
        return resultado
    tipo, coordenadas = normalizada

    # 1. Latitud y longitud con valores posibles.
    try:
        posiciones = _posiciones(tipo, coordenadas)
    except TypeError:
        return resultado.fallar("coordenadas_invalidas")
    if not posiciones or not all(_coordenada_valida(p) for p in posiciones):
        return resultado.fallar("coordenadas_invalidas")
    pares = [(float(p[0]), float(p[1])) for p in posiciones]  # se ignora la altitud

    # 2 y 3. Dentro del Perú, o invertidas.
    if not all(_en_peru(lon, lat) for lon, lat in pares):
        if all(_en_peru(lat, lon) for lon, lat in pares):
            return resultado.fallar("coordenadas_invertidas")
        return resultado.fallar("fuera_de_peru")

    if tipo == "Point":
        resultado.tipo, resultado.geometria = "punto", Point(pares[0])
        # 8. Un punto solo con área declarada menor que 4 ha.
        if area_declarada_ha is not None and area_declarada_ha >= AREA_POLIGONO_OBLIGATORIO_HA:
            return resultado.fallar("poligono_requerido")
        return resultado

    # 4. Máximo de vértices (sin contar el que cierra el anillo).
    anillo = pares[:-1] if len(pares) > 1 and pares[0] == pares[-1] else pares
    if len(anillo) > MAXIMO_VERTICES:
        return resultado.fallar("demasiados_vertices")
    if len(anillo) < 3:
        return resultado.fallar("geometria_invalida")
    poligono = Polygon(anillo)  # Shapely cierra el anillo: única modificación permitida
    resultado.tipo, resultado.geometria = "poligono", poligono

    # 5 a 7. Validez y área según PostGIS.
    fila = sesion.execute(
        text(
            "SELECT ST_IsValid(g) AS valida, ST_Area(g::geography) / 10000 AS area "
            "FROM (SELECT ST_GeomFromText(:wkt, 4326) AS g) AS s"
        ),
        {"wkt": poligono.wkt},
    ).one()
    if not fila.valida:
        return resultado.fallar("geometria_invalida")
    resultado.area_ha = Decimal(str(fila.area)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    if resultado.area_ha < AREA_MINIMA_HA:
        return resultado.fallar("area_demasiado_pequena")
    if resultado.area_ha > AREA_MAXIMA_HA:
        return resultado.fallar("area_excesiva")
    return resultado

"""Capas oficiales que responden el perfil legal de la parcela (adenda 4, sección 10).

Cada capa vive en su módulo con la misma interfaz: `cruzar(consulta) -> dict` devuelve lo que la capa
encontró para esta parcela. `Consulta` hace las peticiones a los servicios ArcGIS REST y mide en PostGIS el
área común y la distancia, con las mismas reglas que la superposición entre parcelas.

A cada servicio se le envía solo la geometría de la parcela (o, para medir la distancia a ríos y lagos, esa
geometría ensanchada): nunca nombres, DNI ni datos de la organización.
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

import httpx
from shapely.geometry import mapping, shape
from shapely.geometry.polygon import orient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.catalogos.capas_legales import Capa

AGENTE = "CacaoTrace/1.0 (cruce de capas legales)"
TIEMPO_MAXIMO = 60  # segundos por petición
INTENTOS = 3
ESPERA_S = 3  # el servidor de SERFOR a veces responde vacío si se le pregunta seguido
# Las geometrías se piden simplificadas a ~1 m: muy por debajo de la precisión de las capas.
DESVIO_MAXIMO_GRADOS = 0.00001
DECIMALES = 7
# Las mismas reglas que la superposición entre parcelas (app/services/superposiciones.py).
UMBRAL_AREA_HA = Decimal("0.05")
UMBRAL_PORCENTAJE = Decimal("5")


class ErrorCapa(Exception):
    """El servicio no respondió o respondió con un error: la variable queda sin cruce."""

    def __init__(self, detalle: str):
        super().__init__(detalle)
        self.detalle = detalle


class CapaLegal(Protocol):
    capa: Capa

    def cruzar(self, consulta: "Consulta") -> dict[str, Any]:
        """Lo que la capa encontró para la parcela. Lanza ErrorCapa si el servicio falla."""


@dataclass
class Elemento:
    """Un elemento de la capa que toca la parcela (o, en la hidrografía, que está cerca)."""

    atributos: dict[str, Any]
    numero: int  # la capa dentro del servicio
    area_comun_ha: float | None = None
    porcentaje: float | None = None
    distancia_m: float | None = None

    @property
    def superpone(self) -> bool:
        """Al menos 0,05 ha o 5 % de la parcela; menos que eso es un roce de lindero."""
        if self.area_comun_ha is None:
            return False
        return (
            Decimal(str(self.area_comun_ha)) >= UMBRAL_AREA_HA
            or Decimal(str(self.porcentaje or 0)) >= UMBRAL_PORCENTAJE
        )

    def medidas(self) -> dict[str, Any]:
        datos = {}
        if self.area_comun_ha is not None:
            datos["area_comun_ha"] = round(self.area_comun_ha, 4)
            datos["porcentaje"] = round(self.porcentaje or 0, 2)
        if self.distancia_m is not None:
            datos["distancia_m"] = round(self.distancia_m, 1)
        return datos


def a_esri(geojson: dict) -> tuple[str, dict]:
    """Un polígono GeoJSON como geometría de ArcGIS: anillo exterior en sentido horario, huecos al revés."""
    forma = shape(geojson)
    if forma.geom_type == "Polygon":
        partes = [forma]
    elif forma.geom_type == "MultiPolygon":
        partes = list(forma.geoms)
    else:
        raise ValueError(f"Solo se cruzan polígonos, no {forma.geom_type}")
    anillos = []
    for parte in partes:
        orientado = mapping(orient(parte, sign=-1.0))
        anillos.extend([[list(p[:2]) for p in anillo] for anillo in orientado["coordinates"]])
    return "esriGeometryPolygon", {"rings": anillos, "spatialReference": {"wkid": 4326}}


def limpiar(valor: Any) -> Any:
    if isinstance(valor, str):
        return " ".join(valor.split()) or None
    return valor


@dataclass
class Consulta:
    """Una parcela que se cruza: su geometría (un punto llega como círculo), su área y su departamento."""

    cliente: httpx.Client
    sesion: Session
    geometria: dict  # GeoJSON del polígono que se cruza
    area_ha: float
    departamento: str | None = None  # código del INEI ("22"), para la zonificación forestal
    distancia_agua_m: int = 100
    dormir: Callable[[float], None] = time.sleep
    # Lo que se envió a cada servicio, para las pruebas: solo geometrías y parámetros de consulta.
    enviado: list[dict] = field(default_factory=list)
    _metadatos: dict[str, dict] = field(default_factory=dict)

    # --- peticiones ---

    def pedir(self, url: str, datos: dict) -> dict:
        """POST con reintentos: el servidor de SERFOR a veces responde vacío."""
        self.enviado.append({"url": url, **datos})
        ultimo = "sin respuesta"
        for intento in range(INTENTOS):
            try:
                respuesta = self.cliente.post(url, data=datos, headers={"User-Agent": AGENTE})
                respuesta.raise_for_status()
                if not respuesta.content.strip():
                    raise ValueError("respuesta vacía")
                cuerpo = respuesta.json()
                if isinstance(cuerpo, dict) and "error" in cuerpo:
                    error = cuerpo["error"] or {}
                    raise ValueError(f"error {error.get('code')}: {error.get('message')}")
                return cuerpo
            except (httpx.HTTPError, ValueError) as exc:
                ultimo = str(exc) or type(exc).__name__
            if intento < INTENTOS - 1:
                self.dormir(ESPERA_S)
        raise ErrorCapa(f"El servicio no respondió tras {INTENTOS} intentos: {ultimo}")

    def metadato(self, capa: Capa, numero: int) -> dict:
        """El metadato de la capa (`?f=pjson`), una vez por cruce."""
        url = f"{capa.servicio}/{numero}"
        if url not in self._metadatos:
            self._metadatos[url] = self.pedir(url, {"f": "json"})
        return self._metadatos[url]

    def _consultar(
        self, capa: Capa, numero: int, geometria: dict, campos: str, donde: str, con_geometria: bool
    ) -> list[dict]:
        tipo, esri = a_esri(geometria)
        datos = {
            "geometry": json.dumps(esri, separators=(",", ":")),
            "geometryType": tipo,
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "where": donde,
            "outFields": campos,
            "returnGeometry": "true" if con_geometria else "false",
            "f": "geojson",
        }
        if con_geometria:
            datos |= {
                "outSR": "4326",
                "maxAllowableOffset": str(DESVIO_MAXIMO_GRADOS),
                "geometryPrecision": str(DECIMALES),
            }
        cuerpo = self.pedir(f"{capa.servicio}/{numero}/query", datos)
        elementos = cuerpo.get("features")
        if not isinstance(elementos, list):
            raise ErrorCapa("La respuesta no trae elementos.")
        return elementos

    def contar(self, capa: Capa, numero: int, donde: str) -> int:
        cuerpo = self.pedir(
            f"{capa.servicio}/{numero}/query", {"where": donde, "returnCountOnly": "true", "f": "json"}
        )
        if "count" not in cuerpo:
            raise ErrorCapa("La respuesta no trae el conteo.")
        return int(cuerpo["count"])

    # --- medidas ---

    def tocan(self, capa: Capa, numero: int, campos: str, donde: str = "1=1") -> list[dict]:
        """Solo los atributos de los elementos que tocan la parcela, sin su geometría ni su área común."""
        return [
            {k: limpiar(v) for k, v in (e.get("properties") or {}).items()}
            for e in self._consultar(capa, numero, self.geometria, campos, donde, False)
        ]

    def intersectan(self, capa: Capa, numero: int, campos: str, donde: str = "1=1") -> list[Elemento]:
        """Los elementos que tocan la parcela, cada uno con su área común y su porcentaje."""
        resultado = []
        for e in self._consultar(capa, numero, self.geometria, campos, donde, True):
            if not e.get("geometry"):
                continue
            area = self.sesion.execute(
                text(
                    "SELECT ST_Area(ST_Intersection(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(:p), 4326)), "
                    "ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(:e), 4326)))::geography) / 10000"
                ),
                {"p": json.dumps(self.geometria), "e": json.dumps(e["geometry"])},
            ).scalar_one()
            area = float(area or 0)
            atributos = {k: limpiar(v) for k, v in (e.get("properties") or {}).items()}
            porcentaje = area / self.area_ha * 100 if self.area_ha else 0
            resultado.append(Elemento(atributos, numero, area, porcentaje))
        return resultado

    def cercanos(self, capa: Capa, numero: int, campos: str, distancia_m: int) -> list[Elemento]:
        """Los elementos a `distancia_m` metros o menos del lindero, con su distancia."""
        ancho = json.loads(
            self.sesion.execute(
                text(
                    "SELECT ST_AsGeoJSON(ST_Buffer(ST_SetSRID(ST_GeomFromGeoJSON(:p), 4326)::geography, "
                    ":d, 4)::geometry, 7)"
                ),
                {"p": json.dumps(self.geometria), "d": distancia_m},
            ).scalar_one()
        )
        resultado = []
        for e in self._consultar(capa, numero, ancho, campos, "1=1", True):
            if not e.get("geometry"):
                continue
            distancia = self.sesion.execute(
                text(
                    "SELECT ST_Distance(ST_SetSRID(ST_GeomFromGeoJSON(:p), 4326)::geography, "
                    "ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(:e), 4326))::geography)"
                ),
                {"p": json.dumps(self.geometria), "e": json.dumps(e["geometry"])},
            ).scalar_one()
            if distancia is not None and float(distancia) <= distancia_m:
                atributos = {k: limpiar(v) for k, v in (e.get("properties") or {}).items()}
                resultado.append(Elemento(atributos, numero, distancia_m=float(distancia)))
        return resultado


def separar(elementos: list[dict]) -> dict[str, list[dict]]:
    """Los que se superponen y los roces de lindero, que se guardan pero no cambian la variable."""
    resultado: dict[str, list[dict]] = {"elementos": [], "roces": []}
    for e in elementos:
        resultado["elementos" if e.pop("_superpone") else "roces"].append(e)
    return resultado


def fila(elemento: Elemento, **datos) -> dict:
    """Lo que se guarda de un elemento: sus datos, la capa y su medida."""
    return {**{k: v for k, v in datos.items() if v not in (None, "")}, "capa": elemento.numero} | (
        elemento.medidas() | {"_superpone": elemento.superpone}
    )

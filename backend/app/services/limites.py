"""Ubicación sugerida de una parcela desde sus coordenadas (decisión del equipo del 2026-10-06).

Con los límites distritales del INEI (2023) cargados en `limites_distritales`, devuelve el departamento,
la provincia y el distrito donde cae la geometría, con los nombres del catálogo `ubigeo_inei.csv`. Un
polígono que cruza un límite toma el distrito donde tiene más área. Si la geometría cae justo fuera de todo
límite (los límites están simplificados a unos 20 m), toma el distrito más cercano a menos de 1 km.

El INEI advierte que sus límites son referenciales: la interfaz llena la ubicación y la persona la confirma.
"""

import csv
from functools import cache

from shapely.geometry.base import BaseGeometry
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import ubigeo
from app.schemas.parcelas import UbicacionSugerida

FUENTE = "Límites distritales del INEI (2023), referenciales"
# Unos 1,100 m en grados, para lo que cae en el borde de un límite simplificado.
CERCANIA_GRADOS = 0.01

CONSULTA = text(
    """
    WITH g AS (SELECT ST_SetSRID(ST_GeomFromText(:wkt), 4326) AS geom)
    SELECT l.ubigeo
    FROM limites_distritales l, g
    WHERE ST_DWithin(l.geometria, g.geom, :cercania)
    ORDER BY ST_Intersects(l.geometria, g.geom) DESC,
             ST_Area(ST_Intersection(l.geometria, g.geom)) DESC,
             ST_Distance(l.geometria, g.geom)
    LIMIT 1
    """
)


@cache
def _por_codigo() -> dict[str, tuple[str, str, str]]:
    with ubigeo.ARCHIVO.open(encoding="utf-8", newline="") as archivo:
        filas = csv.DictReader(archivo)
        return {f["ubigeo"]: (f["departamento"], f["provincia"], f["distrito"]) for f in filas}


def ubicar(sesion: Session, geometria: BaseGeometry) -> UbicacionSugerida | None:
    """El distrito donde cae la geometría, o None si no cae en ninguno o su código no está en el catálogo."""
    codigo = sesion.scalar(CONSULTA, {"wkt": geometria.wkt, "cercania": CERCANIA_GRADOS})
    nombres = _por_codigo().get(codigo) if codigo else None
    if nombres is None:
        return None
    departamento, provincia, distrito = nombres
    return UbicacionSugerida(
        ubigeo=codigo, departamento=departamento, provincia=provincia, distrito=distrito, fuente=FUENTE
    )

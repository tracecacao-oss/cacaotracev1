"""Prepara `app/datos/limites_distritales_inei.json.gz` desde el GeoPackage de límites distritales del INEI.

Fuente: INEI, Infraestructura de Datos Espaciales (https://ide.inei.gob.pe), capa "Distrital", versión 2023
(archivo Distrito.rar, actualizado el 06/03/2026). El INEI advierte que sus límites son referenciales.

Guarda solo el ubigeo y el polígono de cada distrito: los nombres salen del catálogo `ubigeo_inei.csv` por
el código. Simplifica cada polígono con una tolerancia de 0.0002 grados (unos 20 m) y deja 5 decimales en
las coordenadas, para que el archivo pese unos 4 MB. La migración 0015 lo carga en `limites_distritales`.

    python scripts/preparar_limites_distritales.py RUTA/DISTRITO.gpkg
"""

import argparse
import gzip
import json
import re
import sqlite3
import sys
from pathlib import Path

from shapely import wkb
from shapely.geometry import mapping

DESTINO = Path(__file__).resolve().parents[1] / "app" / "datos" / "limites_distritales_inei.json.gz"
TOLERANCIA = 0.0002
FUENTE = "INEI, IDE (ide.inei.gob.pe), capa Distrital, versión 2023, actualizada el 06/03/2026"
# Bytes del sobre según el indicador de la cabecera de la geometría GeoPackage.
SOBRE = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def _geometria(blob: bytes):
    """Una geometría GeoPackage es una cabecera de 8 bytes, un sobre opcional y el WKB."""
    sobre = SOBRE[(blob[3] >> 1) & 7]
    return wkb.loads(bytes(blob[8 + sobre :]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("gpkg", type=Path)
    args = parser.parse_args()
    conexion = sqlite3.connect(args.gpkg)
    srs = conexion.execute("SELECT srs_id FROM gpkg_contents WHERE table_name = 'DISTRITO'").fetchone()
    if srs is None or srs[0] != 4326:
        print("Se esperaba la capa DISTRITO en EPSG:4326.")
        return 1
    distritos = {}
    for ubigeo, blob in conexion.execute("SELECT ubigeo, geom FROM DISTRITO ORDER BY ubigeo"):
        simple = _geometria(blob).simplify(TOLERANCIA, preserve_topology=True)
        distritos[ubigeo] = mapping(simple)
    texto = json.dumps(
        {"fuente": FUENTE, "tolerancia_grados": TOLERANCIA, "distritos": distritos},
        separators=(",", ":"),
    )
    texto = re.sub(r"(-?\d+\.\d{5})\d+", r"\1", texto)
    DESTINO.write_bytes(gzip.compress(texto.encode("utf-8"), mtime=0))
    print(f"{len(distritos)} distritos en {DESTINO} ({DESTINO.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

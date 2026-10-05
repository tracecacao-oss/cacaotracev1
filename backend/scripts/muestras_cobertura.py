"""Guarda respuestas reales de Whisp y GFW para las pruebas automáticas (Parte 4).

La especificación pide que las pruebas se escriban contra respuestas reales, no contra formatos
inventados. Este script consulta las dos fuentes con parcelas ficticias en San Martín (sin ningún
dato personal) y guarda lo que responden en backend/tests/datos/, exactamente como lo guardaría el
sistema. Se corre una vez, con las claves reales:

    cd backend
    .venv\\Scripts\\python scripts\\muestras_cobertura.py

Las claves se leen de WHISP_API_KEY y GFW_API_KEY o, si faltan, se piden por teclado sin mostrarse.
Nunca se escriben en ningún archivo.
"""

import getpass
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.fuentes import ErrorFuente  # noqa: E402
from app.services.fuentes.gfw import GFW  # noqa: E402
from app.services.fuentes.whisp import Whisp  # noqa: E402

DATOS = Path(__file__).resolve().parent.parent / "tests" / "datos"
# Parcelas ficticias de 1 ha y un punto en San Martín, las mismas de las pruebas.
LAT, LON = -6.95, -76.55


def _cuadrado(lat: float, lon: float, lado_m: float) -> dict:
    dlat = lado_m / 111_320
    dlon = lado_m / (111_320 * math.cos(math.radians(lat)))
    anillo = [[lon, lat], [lon + dlon, lat], [lon + dlon, lat + dlat], [lon, lat + dlat], [lon, lat]]
    return {"type": "Polygon", "coordinates": [[[round(x, 8), round(y, 8)] for x, y in anillo]]}


def _circulo(lat: float, lon: float, area_ha: float, lados: int = 32) -> dict:
    radio = math.sqrt(area_ha * 10_000 / math.pi)
    anillo = []
    for i in range(lados + 1):
        angulo = 2 * math.pi * (i % lados) / lados
        anillo.append(
            [
                round(lon + radio * math.cos(angulo) / (111_320 * math.cos(math.radians(lat))), 8),
                round(lat + radio * math.sin(angulo) / 111_320, 8),
            ]
        )
    return {"type": "Polygon", "coordinates": [anillo]}


def _clave(variable: str, nombre: str) -> str | None:
    valor = os.environ.get(variable)
    if not valor:
        valor = getpass.getpass(f"Pega la clave de {nombre} (no se mostrará; Enter para saltar): ").strip()
    return valor or None


def _guardar(fuente, nombre_archivo: str, geometria: dict) -> None:
    try:
        contenido = fuente.consultar(geometria, "muestra-cacaotrace")
    except ErrorFuente as exc:
        print(f"  {nombre_archivo}: la fuente falló: {exc.detalle}")
        return
    ruta = DATOS / nombre_archivo
    ruta.write_bytes(contenido)
    resultado, indicadores, version = fuente.interpretar(contenido)
    print(f"  {nombre_archivo}: guardado ({len(contenido)} bytes)")
    print(f"    {fuente.texto(resultado, indicadores)} · versión {version}")
    print(f"    indicadores: {json.dumps(indicadores, ensure_ascii=False)}")


def main() -> None:
    whisp_clave = _clave("WHISP_API_KEY", "Whisp")
    gfw_clave = _clave("GFW_API_KEY", "GFW")
    if whisp_clave:
        print("Whisp:")
        whisp = Whisp(whisp_clave)
        _guardar(whisp, "whisp_poligono.json", _cuadrado(LAT, LON, 100))
        _guardar(whisp, "whisp_punto.json", {"type": "Point", "coordinates": [LON, LAT]})
    if gfw_clave:
        print("GFW:")
        gfw = GFW(gfw_clave)
        _guardar(gfw, "gfw_poligono.json", _cuadrado(LAT, LON, 100))
        _guardar(gfw, "gfw_circulo.json", _circulo(LAT, LON, 3))
    print("Listo. Los archivos están en backend/tests/datos/.")


if __name__ == "__main__":
    main()

"""Comprobación de las capas oficiales del perfil legal de la parcela (adenda 4, sección 10).

Consulta cada capa y dice cuáles responden:
1. Lee el metadato de cada servicio y confirma que sus capas existen.
2. Pregunta a cada capa cuántos elementos tiene en un recuadro de San Martín: solo prueba que responde.
3. Consulta las dos geometrías de prueba de la adenda y confirma lo que deben devolver.

No usa claves ni escribe en disco. A cada servicio le envía solo la geometría. Lo corre una persona del
equipo, desde backend/, en su máquina y en el servidor de producción:

    python scripts/check_capas_legales.py

Pasa (código de salida 0) si responden las seis capas que deciden variables del perfil y las dos geometrías
devuelven lo esperado. Las capas de apoyo se informan, pero no cambian el resultado.
"""

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.catalogos import capas_legales  # noqa: E402

AGENTE = "CacaoTrace/1.0 (check_capas_legales)"
TIEMPO_MAXIMO_S = 60
INTENTOS = 3
ESPERA_S = 3  # el servidor de SERFOR a veces responde vacío si se le pregunta seguido
RECUADRO_SAN_MARTIN = "-77.5,-8.0,-76.0,-5.5"


@dataclass(frozen=True)
class Prueba:
    capa: str
    numero: int
    punto: tuple[float, float]  # longitud, latitud
    campos: str
    espera: str
    cumple: Callable[[dict[str, Any]], bool]


PRUEBAS = (
    Prueba(
        "sernanp_anp",
        1,
        (-77.35, -7.75),
        "anp_nomb,anp_cate",
        "el Parque Nacional del Río Abiseo",
        lambda a: "abiseo" in (a.get("anp_nomb") or "").lower(),
    ),
    Prueba(
        "serfor_zonificacion",
        0,
        (-76.75, -7.25),
        "NOMDEP,DOCLEG,CATZFO,SCAZFO",
        "un polígono de zonificación de San Martín aprobado por la RM N.º 039-2020-MINAM",
        lambda a: a.get("NOMDEP") == "22" and "039-2020-MINAM" in (a.get("DOCLEG") or ""),
    ),
)


class SinRespuesta(Exception):
    pass


def _pedir(cliente: httpx.Client, url: str, parametros: dict, dormir: Callable[[float], None]) -> dict:
    ultimo = "sin respuesta"
    for intento in range(INTENTOS):
        try:
            respuesta = cliente.get(url, params=parametros)
            respuesta.raise_for_status()
            datos = respuesta.json()
            if "error" not in datos:
                return datos
            ultimo = f"el servicio respondió con un error: {datos['error'].get('message') or datos['error']}"
        except (httpx.HTTPError, ValueError) as error:
            ultimo = f"{type(error).__name__}: {error}"
        if intento + 1 < INTENTOS:
            dormir(ESPERA_S)
    raise SinRespuesta(ultimo)


def comprobar_capa(capa: capas_legales.Capa, cliente: httpx.Client, dormir) -> tuple[bool, str]:
    """La capa responde si su servicio la lista y cada uno de sus números acepta una consulta espacial."""
    try:
        metadato = _pedir(cliente, capa.servicio, {"f": "json"}, dormir)
        listadas = {c["id"] for c in metadato.get("layers", [])}
        faltan = [n for n in capa.capas if n not in listadas]
        if faltan:
            return False, f"el servicio no lista la capa {', '.join(map(str, faltan))}"
        cuentas = []
        for numero in capa.capas:
            datos = _pedir(
                cliente,
                f"{capa.servicio}/{numero}/query",
                {
                    "geometry": RECUADRO_SAN_MARTIN,
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                    "returnCountOnly": "true",
                    "f": "json",
                },
                dormir,
            )
            if "count" not in datos:
                return False, f"la capa {numero} no devolvió un conteo"
            cuentas.append(f"capa {numero}: {datos['count']}")
        return True, "; ".join(cuentas)
    except SinRespuesta as error:
        return False, str(error)


def comprobar_prueba(prueba: Prueba, cliente: httpx.Client, dormir) -> tuple[bool, str]:
    capa = capas_legales.POR_CODIGO[prueba.capa]
    try:
        datos = _pedir(
            cliente,
            f"{capa.servicio}/{prueba.numero}/query",
            {
                "geometry": f"{prueba.punto[0]},{prueba.punto[1]}",
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": prueba.campos,
                "returnGeometry": "false",
                "f": "json",
            },
            dormir,
        )
    except SinRespuesta as error:
        return False, str(error)
    atributos = [f.get("attributes") or {} for f in datos.get("features", [])]
    if any(prueba.cumple(a) for a in atributos):
        return True, f"devolvió {prueba.espera}"
    return False, f"debía devolver {prueba.espera}; devolvió {atributos or 'nada'}"


def comprobar(cliente: httpx.Client, dormir: Callable[[float], None] = time.sleep) -> tuple[bool, list[str]]:
    lineas = ["Capas que deciden el perfil legal:"]
    todo_bien = True
    for capa in capas_legales.CAPAS:
        ok, detalle = comprobar_capa(capa, cliente, dormir)
        todo_bien &= ok
        lineas.append(f"  [{'OK' if ok else 'FALLA'}] {capa.nombre} ({capa.entidad}): {detalle}")
    lineas.append("Geometrías de prueba:")
    for prueba in PRUEBAS:
        ok, detalle = comprobar_prueba(prueba, cliente, dormir)
        todo_bien &= ok
        lineas.append(
            f"  [{'OK' if ok else 'FALLA'}] {prueba.punto[0]}, {prueba.punto[1]} en {prueba.capa}: {detalle}"
        )
    lineas.append("Capas de apoyo (no cambian el resultado):")
    for capa in capas_legales.APOYO:
        ok, detalle = comprobar_capa(capa, cliente, dormir)
        lineas.append(f"  [{'OK' if ok else 'no responde'}] {capa.nombre} ({capa.entidad}): {detalle}")
    lineas.append(
        "Responden las seis capas."
        if todo_bien
        else "Al menos una capa no responde o no devolvió lo esperado."
    )
    return todo_bien, lineas


def main() -> int:
    with httpx.Client(
        timeout=TIEMPO_MAXIMO_S, headers={"User-Agent": AGENTE}, follow_redirects=True
    ) as cliente:
        todo_bien, lineas = comprobar(cliente)
    print("\n".join(lineas))
    return 0 if todo_bien else 1


if __name__ == "__main__":
    sys.exit(main())

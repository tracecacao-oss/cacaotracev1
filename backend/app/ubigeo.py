"""Catálogo oficial de departamentos, provincias y distritos del Perú.

Fuente: INEI, "UBIGEO 2022_1891 distritos.xlsx", publicado en la Plataforma Nacional de Datos
Abiertos (datosabiertos.gob.pe, conjunto "Ubigeos - Instituto Nacional de Estadística e
Informática", actualizado el 2023-09-07). Se usa el código del INEI, no el del RENIEC.
`datos/ubigeo_inei.csv` es esa hoja sin cambios: código y los tres nombres, en mayúsculas.

Se guardan los nombres tal como los escribe el INEI. Al comparar se ignoran mayúsculas, tildes,
la eñe y los espacios repetidos, así que "San Martín" se acepta y se guarda "SAN MARTIN".
"""

import csv
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from app.errores import error_api

ARCHIVO = Path(__file__).parent / "datos" / "ubigeo_inei.csv"
FUENTE = "INEI, UBIGEO 2022 (1891 distritos)"
CAMPOS = ("departamento", "provincia", "distrito")


def _clave(texto: str) -> str:
    sin_marcas = unicodedata.normalize("NFD", texto.strip().upper())
    return " ".join("".join(c for c in sin_marcas if not unicodedata.combining(c)).split())


@dataclass(frozen=True)
class Catalogo:
    # clave -> nombre oficial, en cada nivel
    departamentos: dict[str, str]
    provincias: dict[tuple[str, str], str]
    distritos: dict[tuple[str, str, str], str]
    # Árbol con los nombres oficiales, en el orden del código del INEI.
    arbol: dict[str, dict[str, list[str]]]


@cache
def catalogo() -> Catalogo:
    departamentos, provincias, distritos = {}, {}, {}
    arbol: dict[str, dict[str, list[str]]] = {}
    with ARCHIVO.open(encoding="utf-8", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            dep, prov, dist = fila["departamento"], fila["provincia"], fila["distrito"]
            kd, kp, kt = _clave(dep), _clave(prov), _clave(dist)
            departamentos[kd] = dep
            provincias[(kd, kp)] = prov
            distritos[(kd, kp, kt)] = dist
            arbol.setdefault(dep, {}).setdefault(prov, []).append(dist)
    return Catalogo(departamentos, provincias, distritos, arbol)


def oficial(departamento: str, provincia: str, distrito: str) -> tuple[str, str, str]:
    """Devuelve los nombres oficiales o responde 422 diciendo cuál no está en el catálogo."""
    c = catalogo()
    kd, kp, kt = _clave(departamento), _clave(provincia), _clave(distrito)
    if kd not in c.departamentos:
        raise error_api(
            422, "ubigeo_invalido", f"El departamento «{departamento}» no existe en el catálogo del INEI."
        )
    dep = c.departamentos[kd]
    if (kd, kp) not in c.provincias:
        raise error_api(422, "ubigeo_invalido", f"La provincia «{provincia}» no pertenece a {dep}.")
    prov = c.provincias[(kd, kp)]
    if (kd, kp, kt) not in c.distritos:
        raise error_api(422, "ubigeo_invalido", f"El distrito «{distrito}» no pertenece a {prov}, {dep}.")
    return dep, prov, c.distritos[(kd, kp, kt)]


def normalizar(valores: dict, actual: object | None = None) -> None:
    """Si `valores` trae alguno de los tres campos, valida la terna y la deja con los nombres oficiales.

    En una edición, los campos que no llegan se toman de `actual`, porque la combinación se valida
    completa. Un registro previo al catálogo no se toca mientras no se cambie su ubicación.
    """
    if not any(valores.get(campo) for campo in CAMPOS):
        return
    terna = [valores.get(campo) or getattr(actual, campo) for campo in CAMPOS]
    valores.update(zip(CAMPOS, oficial(*terna), strict=True))


# Los 25 departamentos con su ortografía (pedido del equipo del 2026-10-07). El catálogo oficial del INEI los
# trae en mayúsculas y sin tildes, igual que a las provincias y los distritos.
DEPARTAMENTOS_ESCRITOS = {
    "AMAZONAS": "Amazonas",
    "ANCASH": "Áncash",
    "APURIMAC": "Apurímac",
    "AREQUIPA": "Arequipa",
    "AYACUCHO": "Ayacucho",
    "CAJAMARCA": "Cajamarca",
    "CALLAO": "Callao",
    "CUSCO": "Cusco",
    "HUANCAVELICA": "Huancavelica",
    "HUANUCO": "Huánuco",
    "ICA": "Ica",
    "JUNIN": "Junín",
    "LA LIBERTAD": "La Libertad",
    "LAMBAYEQUE": "Lambayeque",
    "LIMA": "Lima",
    "LORETO": "Loreto",
    "MADRE DE DIOS": "Madre de Dios",
    "MOQUEGUA": "Moquegua",
    "PASCO": "Pasco",
    "PIURA": "Piura",
    "PUNO": "Puno",
    "SAN MARTIN": "San Martín",
    "TACNA": "Tacna",
    "TUMBES": "Tumbes",
    "UCAYALI": "Ucayali",
}
MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y", "en"}


def mostrar(nombre: str | None) -> str:
    """Un nombre del catálogo para leerlo: "SAN MARTIN" → "San Martín" y "MARISCAL CACERES" →
    "Mariscal Caceres".

    Un nombre igual al de un departamento lleva sus tildes, sea departamento, provincia o distrito. A los
    demás no se les agregan tildes, porque el catálogo oficial no las trae: solo pasan a mayúsculas y
    minúsculas.
    """
    if not nombre:
        return nombre or ""
    escrito = DEPARTAMENTOS_ESCRITOS.get(_clave(nombre))
    if escrito:
        return escrito
    palabras = nombre.strip().lower().split()
    return " ".join(
        p if i and p in MINUSCULAS else p[:1].upper() + p[1:] for i, p in enumerate(palabras)
    )


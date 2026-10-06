"""Textos fijos del informe de hallazgos y del DEX (Parte 9), en español y en inglés.

Viven en es.json y en.json, con las mismas claves (una prueba lo comprueba). Los textos del informe salen
solo de estas plantillas: los mismos datos producen siempre el mismo texto. Lo que escribieron las
personas (notas, motivos, explicaciones) no pasa por aquí: no se traduce.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

from app.fechas import LIMA

IDIOMAS = ("es", "en")
CARPETA = Path(__file__).resolve().parent


@cache
def cargar(idioma: str) -> dict[str, Any]:
    return json.loads((CARPETA / f"{idioma}.json").read_text(encoding="utf-8"))


def obtener(idioma: str, ruta: str) -> Any:
    """`ruta` con puntos: "hallazgo.diez_hectareas_o_mas"."""
    valor: Any = cargar(idioma)
    for parte in ruta.split("."):
        valor = valor[parte]
    return valor


def en_idioma(idioma: str, valor: Any) -> Any:
    """Un valor que depende del idioma viaja como {"es": ..., "en": ...}; cualquier otro, tal cual."""
    if isinstance(valor, dict) and set(valor) == set(IDIOMAS):
        return valor[idioma]
    return valor


def t(idioma: str, ruta: str, **valores: Any) -> str:
    plantilla = obtener(idioma, ruta)
    return plantilla.format(**{k: en_idioma(idioma, v) for k, v in valores.items()})


def ambos(ruta: str, **valores: Any) -> dict[str, str]:
    return {idioma: t(idioma, ruta, **valores) for idioma in IDIOMAS}


def numero(valor: Any, decimales: int = 2) -> str:
    """Con coma de miles y punto decimal, igual en los dos idiomas: 1,500.00."""
    return f"{Decimal(str(valor)):,.{decimales}f}"


def hectareas(valor: Any) -> str:
    texto = f"{Decimal(str(valor)):,.4f}".rstrip("0").rstrip(".")
    return texto


def fecha(idioma: str, valor: date | datetime | str | None) -> str:
    """Fecha completa: "14 de agosto de 2026" o "14 August 2026"."""
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor) if len(valor) > 10 else date.fromisoformat(valor)
    if isinstance(valor, datetime):
        valor = valor.astimezone(LIMA).date()
    meses = obtener(idioma, "comun.meses")
    return t(idioma, "comun.fecha", dia=valor.day, mes=meses[valor.month - 1], anio=valor.year)


def fechas(valor: date | datetime | str | None) -> dict[str, str]:
    return {idioma: fecha(idioma, valor) for idioma in IDIOMAS}


def lista(idioma: str, elementos: list[str]) -> str:
    """Une con comas y la conjunción del idioma: A, B y C; A, B and C."""
    elementos = [e for e in elementos if e]
    if len(elementos) <= 1:
        return "".join(elementos)
    return f"{', '.join(elementos[:-1])} {obtener(idioma, 'comun.y')} {elementos[-1]}"

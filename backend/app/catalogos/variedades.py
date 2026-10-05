"""Variedades de cacao que se registran en una tanda (Parte 5).

Lista inicial de la especificación, por confirmar con el equipo. Con "otra", el usuario escribe el nombre.
"""

VARIEDADES: dict[str, str] = {
    "ccn_51": "CCN-51",
    "ics_95": "ICS-95",
    "imc_67": "IMC-67",
    "tsh_565": "TSH-565",
    "trinitario": "Trinitario",
    "chuncho": "Chuncho",
    "sin_variedad": "Sin variedad específica",
    "otra": "Otra",
}
CODIGOS = tuple(VARIEDADES)


def nombre(codigo: str, otra: str | None = None) -> str:
    if codigo == "otra" and otra:
        return otra
    return VARIEDADES.get(codigo, codigo)

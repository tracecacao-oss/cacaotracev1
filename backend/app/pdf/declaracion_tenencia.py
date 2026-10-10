"""Plantillas para firmar (adenda 4, sección 7): la declaración jurada de tenencia (Anexo A) y la constancia
de uso de tierra comunal (Anexo B).

El texto vive en app/textos/plantillas_legales.json con su número de versión, que el PDF imprime al pie. Lo
que el sistema sabe va escrito; lo que no, queda como línea en blanco. La plantilla no se guarda como
documento: la que cuenta es la firmada, que se carga como `declaracion_jurada_tenencia` (o
`constancia_comunal`).
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from app.pdf.base import TEXTO_DEMO, TINTA, TINTA_2, TINTA_3, Documento

TEXTOS = Path(__file__).resolve().parents[1] / "textos" / "plantillas_legales.json"
EN_BLANCO = "______________________"
NEGRITA = re.compile(r"\*\*(.+?)\*\*")
MARCADA, SIN_MARCAR = "( X )", "(    )"
TITULOS = {
    "declaracion_jurada_tenencia": "Declaración jurada de tenencia",
    "constancia_comunal": "Constancia de uso de tierra comunal",
}


@cache
def textos() -> dict[str, Any]:
    return json.loads(TEXTOS.read_text(encoding="utf-8"))


def llenar(texto: str, datos: dict[str, Any]) -> str:
    """Las llaves con un dato se llenan; las que no tienen dato quedan como línea en blanco."""
    return re.sub(r"\{(\w+)\}", lambda m: str(datos.get(m.group(1)) or EN_BLANCO), texto)


def _escribir(pdf: Documento, texto: str, *, tamano: float = 9.5, alto: float = 5) -> None:
    """Un párrafo con sus partes en negrita (**así**), que fluye como texto corrido."""
    pdf.set_text_color(*TINTA)
    for i, parte in enumerate(NEGRITA.split(texto)):
        if not parte:
            continue
        pdf.set_font("Jakarta", "B" if i % 2 else "", tamano)
        pdf.write(alto, parte)
    pdf.ln(alto)


def documento(clave: str, datos: dict[str, Any], opcion: str | None, *, es_demo: bool = False) -> Documento:
    """`datos`: lo que el sistema sabe (productor, DNI, parcela, área, organización, RUC). `opcion`: la opción
    que se marca (el tipo de tenencia)."""
    plantilla = textos()[clave]
    pie = f"{plantilla['anexo']}, versión {plantilla['version']} · Página {{n}} de {{total}}"
    pdf = Documento(
        f"{TITULOS[clave]} · {datos.get('codigo') or ''}".strip(" ·"),
        pie=pie,
        marca_agua=TEXTO_DEMO if es_demo else None,
    )
    pdf.add_page()
    pdf.set_font("Jakarta", "", 7.5)
    pdf.set_text_color(*TINTA_3)
    pdf.multi_cell(0, 4, plantilla["nota"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    for bloque in plantilla["bloques"]:
        texto = llenar(bloque["texto"], datos)
        if bloque["tipo"] == "titulo":
            pdf.set_font("Jakarta", "B", 12)
            pdf.set_text_color(*TINTA)
            pdf.multi_cell(0, 6, texto, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
        elif bloque["tipo"] == "opcion":
            marca = MARCADA if bloque["clave"] == opcion else SIN_MARCAR
            pdf.set_x(pdf.l_margin + 4)
            _escribir(pdf, f"{marca}  {texto}")
            pdf.ln(1.5)
        elif bloque["tipo"] == "firma":
            if pdf.get_y() > pdf.page_break_trigger - 18:
                pdf.add_page()
            pdf.ln(3)
            for linea in texto.split("\n"):
                _escribir(pdf, linea, tamano=9)
            pdf.ln(1)
        elif bloque["tipo"] == "referencias":
            pdf.ln(3)
            pdf.set_font("Jakarta", "", 7.5)
            pdf.set_text_color(*TINTA_2)
            pdf.multi_cell(0, 4, texto, new_x="LMARGIN", new_y="NEXT")
        else:
            _escribir(pdf, texto)
            pdf.ln(2)
    return pdf


def generar(clave: str, datos: dict[str, Any], opcion: str | None, *, es_demo: bool = False) -> bytes:
    return bytes(documento(clave, datos, opcion, es_demo=es_demo).output())

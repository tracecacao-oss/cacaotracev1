"""Hoja de la declaración anual del productor (adenda 5, sección 5.4, y Anexo A).

El texto vive en app/textos/plantillas_legales.json (clave `declaracion_productor`) con su número de versión,
que el PDF imprime al pie, junto a la versión del cuestionario. La hoja para firmar trae los datos del
productor y de la organización, cada pregunta mostrada con su respuesta y el texto del Anexo A; la firmada se
carga como `hoja_declaracion_productor`. De una declaración ya declarada, la misma hoja sale como copia: dice
quién la declaró y cuándo, sin las líneas para firmar.
"""

from typing import Any

from app.pdf.base import TEXTO_DEMO, TINTA, TINTA_2, TINTA_3, Documento
from app.pdf.declaracion_tenencia import _escribir, llenar, textos

TITULO = "Declaración jurada anual del productor"


def documento(
    datos: dict[str, Any],
    respuestas: list[dict[str, Any]],
    *,
    copia: str | None = None,
    version_cuestionario: int,
    es_demo: bool = False,
) -> Documento:
    """`datos`: lo que el sistema sabe del productor y la organización. `respuestas`: cada pregunta mostrada
    con su etiqueta. `copia`: el texto que dice quién declaró y cuándo, si ya se declaró."""
    plantilla = textos()["declaracion_productor"]
    pie = (
        f"{plantilla['anexo']}, versión {plantilla['version']} · Cuestionario, versión {version_cuestionario}"
        " · Página {n} de {total}"
    )
    pdf = Documento(TITULO, pie=pie, marca_agua=TEXTO_DEMO if es_demo else None)
    pdf.add_page()
    pdf.set_font("Jakarta", "", 7.5)
    pdf.set_text_color(*TINTA_3)
    pdf.multi_cell(0, 4, plantilla["nota"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    if copia:
        pdf.recuadro(copia)
    for bloque in plantilla["bloques"]:
        texto = llenar(bloque["texto"], datos)
        tipo = bloque["tipo"]
        if tipo == "titulo":
            pdf.set_font("Jakarta", "B", 12)
            pdf.set_text_color(*TINTA)
            pdf.multi_cell(0, 6, texto, align="C", new_x="LMARGIN", new_y="NEXT")
        elif tipo == "subtitulo":
            pdf.set_font("Jakarta", "B", 9.5)
            pdf.set_text_color(*TINTA_2)
            pdf.multi_cell(0, 5, texto, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
        elif tipo == "respuestas":
            pdf.tabla(
                ["Pregunta", "Respuesta"],
                [[r["pregunta"], r["etiqueta"]] for r in respuestas],
                [110, pdf.ancho - 110],
                tamano=8,
            )
            pdf.ln(1)
        elif tipo == "literal":
            pdf.set_x(pdf.l_margin + 4)
            _escribir(pdf, texto)
            pdf.ln(1)
        elif tipo in ("fecha", "firma"):
            # La copia de una declaración ya hecha no lleva líneas para firmar.
            if copia:
                continue
            if tipo == "firma" and pdf.get_y() > pdf.page_break_trigger - 18:
                pdf.add_page()
            pdf.ln(3)
            for linea in texto.split("\n"):
                _escribir(pdf, linea, tamano=9)
            pdf.ln(1)
        elif tipo == "referencias":
            pdf.ln(3)
            pdf.set_font("Jakarta", "", 7.5)
            pdf.set_text_color(*TINTA_2)
            pdf.multi_cell(0, 4, texto, new_x="LMARGIN", new_y="NEXT")
        else:
            _escribir(pdf, texto)
            pdf.ln(2)
    return pdf


def generar(
    datos: dict[str, Any],
    respuestas: list[dict[str, Any]],
    *,
    copia: str | None = None,
    version_cuestionario: int,
    es_demo: bool = False,
) -> bytes:
    return bytes(
        documento(
            datos, respuestas, copia=copia, version_cuestionario=version_cuestionario, es_demo=es_demo
        ).output()
    )

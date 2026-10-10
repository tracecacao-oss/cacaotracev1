"""Política de la organización para firmar (adenda 6, sección 5 y Anexo A) y lista de productos buscados en
el registro del SENASA (sección 6.6).

El texto de la política vive en app/textos/plantillas_legales.json (clave `politica_organizacion`) con su
número de versión, que el PDF imprime al pie. Trae ya escritos la razón social, el RUC, el tipo de
organización, el órgano de dirección que se sugiere según el tipo y el contacto del canal de quejas y
denuncias; lo que no se sabe queda como línea en blanco. La plantilla no se guarda como documento: la que
cuenta es la firmada, que se carga como `politica_organizacion`.
"""

from datetime import date
from typing import Any

from app.pdf.base import TEXTO_DEMO, TINTA, TINTA_2, TINTA_3, Documento
from app.pdf.declaracion_tenencia import _escribir, llenar, textos

TITULO = "Política de integridad, trabajo digno y diligencia debida"
TITULO_PRODUCTOS = "Productos buscados en el registro del SENASA"
LEYENDA_PRODUCTOS = "Esta lista no reemplaza la consulta del registro."


def version() -> int:
    return textos()["politica_organizacion"]["version"]


def documento(datos: dict[str, Any], *, es_demo: bool = False) -> Documento:
    """`datos`: organizacion, ruc, tipo_organizacion, organo y canal."""
    plantilla = textos()["politica_organizacion"]
    pie = f"{plantilla['anexo']}, versión {plantilla['version']} · Página {{n}} de {{total}}"
    pdf = Documento(TITULO, pie=pie, marca_agua=TEXTO_DEMO if es_demo else None)
    pdf.add_page()
    pdf.set_font("Jakarta", "", 7.5)
    pdf.set_text_color(*TINTA_3)
    pdf.multi_cell(0, 4, plantilla["nota"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
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
        elif tipo == "firma":
            if pdf.get_y() > pdf.page_break_trigger - 14:
                pdf.add_page()
            pdf.ln(4)
            _escribir(pdf, texto, tamano=9)
        elif tipo == "referencias":
            pdf.ln(3)
            pdf.set_font("Jakarta", "", 7.5)
            pdf.set_text_color(*TINTA_2)
            pdf.multi_cell(0, 4, texto, new_x="LMARGIN", new_y="NEXT")
        else:
            _escribir(pdf, texto)
            pdf.ln(2)
    return pdf


def generar(datos: dict[str, Any], *, es_demo: bool = False) -> bytes:
    return bytes(documento(datos, es_demo=es_demo).output())


def documento_productos(
    organizacion: str,
    fecha: date,
    figuran: list[dict[str, Any]],
    no_figuran: list[dict[str, Any]],
    consultas: tuple[tuple[str, str], ...],
    *,
    es_demo: bool = False,
) -> Documento:
    """Sección 6.6: los productos declarados que el personal buscó en el registro del SENASA, en dos grupos.
    No dice "autorizado" ni "prohibido": dice si el producto figura en el registro."""
    pdf = Documento(TITULO_PRODUCTOS, marca_agua=TEXTO_DEMO if es_demo else None)
    pdf.add_page()
    pdf.set_font("Jakarta", "B", 12)
    pdf.set_text_color(*TINTA)
    pdf.multi_cell(0, 6, TITULO_PRODUCTOS, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Jakarta", "", 9)
    pdf.set_text_color(*TINTA_2)
    pdf.multi_cell(0, 5, f"{organizacion} · {fecha.strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.recuadro(f"{LEYENDA_PRODUCTOS} Cada producto se buscó por su nombre comercial; la fecha dice cuándo.")
    pdf.set_font("Jakarta", "B", 8.5)
    pdf.set_text_color(*TINTA_2)
    pdf.cell(0, 5, "Consultas del SENASA", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Jakarta", "", 8)
    for url, nombre in consultas:
        pdf.multi_cell(0, 4.5, f"{nombre}: {url}", align="L", new_x="LMARGIN", new_y="NEXT")
    for titulo, filas in (
        ("Figuran en el registro del SENASA", figuran),
        ("No figuran en el registro del SENASA", no_figuran),
    ):
        pdf.seccion(titulo, f"{len(filas)} producto(s)")
        if not filas:
            pdf.parrafo("Ninguno.")
            continue
        pdf.tabla(
            ["Producto", "Tipo", "N.º de registro", "Buscado el", "Productores"],
            [[f["nombre"], f["tipo"], f.get("registro"), f.get("fecha"), f["productores"]] for f in filas],
            [60, 28, 36, 28, pdf.ancho - 152],
        )
    return pdf


def generar_productos(*args, **kwargs) -> bytes:
    return bytes(documento_productos(*args, **kwargs).output())

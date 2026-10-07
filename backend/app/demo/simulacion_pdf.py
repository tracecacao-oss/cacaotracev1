"""PDF de muestra del paquete de simulación (app/demo/simulacion.py).

Cada documento lleva los campos y el orden de su documento real, pero es ficticio y lo dice en cada página:
la marca "MUESTRA - SIN VALOR LEGAL" va en diagonal, arriba y en el pie. No lleva logos, sellos, firmas ni
elementos de seguridad de ninguna entidad. Se arma con la tipografía del diseño sin fijar su peso, para que
cada archivo tarde milisegundos.
"""

from datetime import UTC, datetime

from fpdf import FPDF

from app.pdf.base import FUENTES

MARCA = "MUESTRA - SIN VALOR LEGAL"
# Fecha fija en los metadatos: el mismo escenario da siempre los mismos archivos.
CREACION = datetime(2026, 10, 6, tzinfo=UTC)
GRIS_MARCA = (226, 226, 226)
ROJO = (176, 40, 40)
TINTA = (31, 41, 55)
TINTA_SUAVE = (100, 110, 125)
LINEA = (220, 223, 228)


class _Muestra(FPDF):
    def header(self) -> None:
        with self.local_context():
            self.set_font("Jakarta", "", 46)
            self.set_text_color(*GRIS_MARCA)
            ancho = self.get_string_width(MARCA)
            centro_x, centro_y = self.w / 2, self.h / 2
            with self.rotation(angle=40, x=centro_x, y=centro_y):
                self.text(centro_x - ancho / 2, centro_y, MARCA)
        with self.local_context():
            self.set_font("Jakarta", "", 9)
            self.set_text_color(*ROJO)
            self.set_xy(self.l_margin, 7)
            self.cell(self.w - self.l_margin - self.r_margin, 5, MARCA, align="C")
        self.set_y(18)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_font("Jakarta", "", 7.5)
        self.set_text_color(*ROJO)
        texto = (
            f"{MARCA} · Documento ficticio generado para pruebas de CacaoTrace · "
            f"Página {self.page_no()}/{{nb}}"
        )
        self.cell(0, 5, texto, align="C")


def documento(
    titulo: str,
    secciones: list[tuple[str, list[tuple[str, str]]]],
    *,
    subtitulo: str | None = None,
    texto: str | None = None,
) -> bytes:
    """Un documento de muestra: título, secciones de campos (etiqueta y valor) y un texto final opcional."""
    pdf = _Muestra(orientation="P", unit="mm", format="A4")
    pdf.set_creator("CacaoTrace - paquete de simulación")
    pdf.set_title(f"{titulo} ({MARCA})")
    pdf.set_creation_date(CREACION)
    pdf.add_font("Jakarta", "", str(FUENTES / "PlusJakartaSans-Variable.ttf"))
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    ancho = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font("Jakarta", "", 17)
    pdf.set_text_color(*TINTA)
    pdf.multi_cell(ancho, 8, titulo, new_x="LMARGIN", new_y="NEXT")
    if subtitulo:
        pdf.set_font("Jakarta", "", 10)
        pdf.set_text_color(*TINTA_SUAVE)
        pdf.multi_cell(ancho, 5, subtitulo, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    etiqueta_ancho = 62
    for nombre, campos in secciones:
        pdf.set_font("Jakarta", "", 11)
        pdf.set_text_color(*TINTA)
        pdf.set_draw_color(*LINEA)
        pdf.cell(ancho, 7, nombre, border="B", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        for etiqueta, valor in campos:
            pdf.set_font("Jakarta", "", 9)
            y = pdf.get_y()
            pdf.set_text_color(*TINTA_SUAVE)
            pdf.multi_cell(etiqueta_ancho, 5, etiqueta)
            alto_etiqueta = pdf.get_y() - y
            pdf.set_xy(pdf.l_margin + etiqueta_ancho, y)
            pdf.set_text_color(*TINTA)
            pdf.multi_cell(ancho - etiqueta_ancho, 5, valor or "—")
            pdf.set_y(max(pdf.get_y(), y + alto_etiqueta) + 1)
        pdf.ln(3)
    if texto:
        pdf.set_font("Jakarta", "", 9)
        pdf.set_text_color(*TINTA)
        pdf.multi_cell(ancho, 5, texto, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())

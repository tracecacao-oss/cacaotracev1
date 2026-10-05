"""Base de los PDF de CacaoTrace (DOP en la Parte 5; DPP y DEX después).

fpdf2 está escrito solo en Python y no necesita nada instalado en el sistema, así que funciona en Render.
Usa las tipografías del diseño (Plus Jakarta Sans y JetBrains Mono, licencia OFL) incluidas en
app/recursos/fuentes. Todo texto entra como texto, nunca como HTML.
"""

import math
from pathlib import Path
from typing import Any

import segno
from fpdf import FPDF
from fpdf.fonts import FontFace

FUENTES = Path(__file__).resolve().parents[1] / "recursos" / "fuentes"
TINTA = (17, 24, 39)
TINTA_2 = (75, 85, 99)
TINTA_3 = (107, 114, 128)
LINEA = (229, 231, 235)
FONDO = (246, 247, 249)
ESMERALDA = (5, 150, 105)
AMBAR = (180, 83, 9)


class Documento(FPDF):
    """Página A4 con pie de código y número de página."""

    def __init__(self, codigo: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.codigo = codigo
        self.set_margins(16, 16, 16)
        self.set_auto_page_break(auto=True, margin=18)
        variable = str(FUENTES / "PlusJakartaSans-Variable.ttf")
        self.add_font("Jakarta", "", variable, variations={"wght": 400})
        self.add_font("Jakarta", "B", variable, variations={"wght": 700})
        self.add_font("Mono", "", str(FUENTES / "JetBrainsMono-Variable.ttf"), variations={"wght": 400})
        self.set_creator("CacaoTrace")
        self.set_title(codigo)
        self.alias_nb_pages()
        # Todo texto escrito en el documento, para revisarlo en las pruebas (frases que no se usan).
        self.textos: list[str] = []

    def normalize_text(self, text):
        self.textos.append(text)
        return super().normalize_text(text)

    # ---------- Pie ----------

    def footer(self) -> None:
        self.set_y(-12)
        self.set_draw_color(*LINEA)
        self.line(self.l_margin, self.get_y() - 1.5, self.w - self.r_margin, self.get_y() - 1.5)
        self.set_font("Mono", "", 7.5)
        self.set_text_color(*TINTA_3)
        self.cell(0, 5, self.codigo, align="L")
        self.set_x(self.l_margin)
        self.set_font("Jakarta", "", 7.5)
        self.cell(0, 5, f"Página {self.page_no()} de {{nb}}", align="R")

    # ---------- Piezas ----------

    @property
    def ancho(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def seccion(self, titulo: str, subtitulo: str | None = None) -> None:
        if self.get_y() > self.h - 50:
            self.add_page()
        self.ln(3)
        self.set_fill_color(*ESMERALDA)
        self.rect(self.l_margin, self.get_y() + 0.6, 1.2, 5, style="F")
        self.set_x(self.l_margin + 3)
        self.set_font("Jakarta", "B", 11.5)
        self.set_text_color(*TINTA)
        self.cell(0, 6, titulo, new_x="LMARGIN", new_y="NEXT")
        if subtitulo:
            self.set_font("Jakarta", "", 8)
            self.set_text_color(*TINTA_3)
            self.multi_cell(0, 4, subtitulo, new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)

    def dato(self, etiqueta: str, valor: Any, *, nivel: str | None = None, mono: bool = False) -> None:
        """Una fila etiqueta / valor, con el nivel de verificación a la derecha si lo hay."""
        texto = "—" if valor in (None, "") else str(valor)
        ancho_etiqueta = 52
        ancho_nivel = 30 if nivel else 0
        ancho_valor = self.ancho - ancho_etiqueta - ancho_nivel
        # La fila entera va en una sola página: si no cabe, empieza en la siguiente.
        self.set_font("Jakarta", "", 8)
        lineas_etiqueta = len(self.multi_cell(ancho_etiqueta, 4.6, etiqueta, dry_run=True, output="LINES"))
        self.set_font("Mono" if mono else "Jakarta", "", 8.5 if mono else 9)
        lineas_valor = len(self.multi_cell(ancho_valor, 4.6, texto, dry_run=True, output="LINES"))
        alto = max(lineas_etiqueta, lineas_valor, 1) * 4.6
        if self.get_y() + alto + 1 > self.page_break_trigger:
            self.add_page()
        y = self.get_y()
        self.set_font("Jakarta", "", 8)
        self.set_text_color(*TINTA_3)
        self.multi_cell(ancho_etiqueta, 4.6, etiqueta, new_x="RIGHT", new_y="TOP")
        self.set_xy(self.l_margin + ancho_etiqueta, y)
        self.set_font("Mono" if mono else "Jakarta", "", 8.5 if mono else 9)
        self.set_text_color(*TINTA)
        self.multi_cell(ancho_valor, 4.6, texto, new_x="RIGHT", new_y="TOP")
        fin = y + alto
        if nivel:
            self.set_xy(self.w - self.r_margin - ancho_nivel, y)
            self.set_font("Jakarta", "", 7.5)
            verificado = nivel in ("Documentado", "Verificado en fuente")
            self.set_text_color(*(ESMERALDA if verificado else TINTA_3))
            self.cell(ancho_nivel, 4.6, nivel, align="R")
        self.set_xy(self.l_margin, max(fin, y + 4.6) + 0.6)
        self.set_draw_color(*LINEA)
        self.line(self.l_margin, self.get_y() - 0.3, self.w - self.r_margin, self.get_y() - 0.3)

    def parrafo(self, texto: str, *, tamano: float = 9, color=TINTA_2) -> None:
        self.set_font("Jakarta", "", tamano)
        self.set_text_color(*color)
        self.multi_cell(0, tamano * 0.5, texto, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def recuadro(self, texto: str) -> None:
        """Texto en un recuadro con fondo, para la leyenda de la primera página."""
        self.set_font("Jakarta", "", 8.5)
        self.set_text_color(*TINTA_2)
        self.set_fill_color(*FONDO)
        self.set_draw_color(*LINEA)
        self.multi_cell(0, 4.6, texto, border=1, fill=True, padding=3, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def tabla(
        self, encabezados: list[str], filas: list[list[Any]], anchos: list[float], *, tamano: float = 7.5
    ):
        with self.table(
            col_widths=anchos,
            text_align="LEFT",
            line_height=tamano * 0.55,
            borders_layout="HORIZONTAL_LINES",
            headings_style=FontFace(family="Jakarta", emphasis="BOLD", color=TINTA_2, fill_color=FONDO),
            first_row_as_headings=True,
            cell_fill_mode="NONE",
            width=self.ancho,
        ) as tabla:
            # La tabla toma el estilo vigente al crear su primera fila, incluido el color de relleno.
            self.set_font("Jakarta", "", tamano)
            self.set_text_color(*TINTA)
            self.set_fill_color(255, 255, 255)
            fila = tabla.row()
            for e in encabezados:
                fila.cell(e)
            for valores in filas:
                fila = tabla.row()
                for v in valores:
                    fila.cell("—" if v in (None, "") else str(v))
        self.ln(2)

    # ---------- Código QR y croquis ----------

    def qr(self, contenido: str, x: float, y: float, lado: float) -> None:
        """Dibuja el código QR con rectángulos, sin imágenes."""
        matriz = [list(fila) for fila in segno.make(contenido, error="m", micro=False).matrix_iter(border=2)]
        modulo = lado / len(matriz)
        self.set_fill_color(255, 255, 255)
        self.rect(x, y, lado, lado, style="F")
        self.set_fill_color(*TINTA)
        for i, fila in enumerate(matriz):
            j = 0
            while j < len(fila):
                if fila[j]:
                    inicio = j
                    while j < len(fila) and fila[j]:
                        j += 1
                    self.rect(
                        x + inicio * modulo,
                        y + i * modulo,
                        (j - inicio) * modulo + 0.01,
                        modulo + 0.01,
                        style="F",
                    )
                else:
                    j += 1

    def croquis(self, geometria: dict[str, Any], x: float, y: float, lado: float) -> str:
        """Dibuja la parcela desde su geometría, sin mapa de fondo, con el norte arriba. Devuelve una nota
        con su tamaño aproximado."""
        self.set_draw_color(*LINEA)
        self.set_fill_color(*FONDO)
        self.rect(x, y, lado, lado, style="DF")
        if geometria.get("type") == "Point":
            lon, lat = geometria["coordinates"][:2]
            cx, cy = x + lado / 2, y + lado / 2
            self.set_draw_color(*ESMERALDA)
            self.set_line_width(0.6)
            self.circle(x=cx - 3, y=cy - 3, r=3, style="D")
            self.line(cx - 5, cy, cx + 5, cy)
            self.line(cx, cy - 5, cx, cy + 5)
            self.set_line_width(0.2)
            return f"Punto en {lat:.6f}, {lon:.6f}"
        anillos = (
            [geometria["coordinates"][0]]
            if geometria["type"] == "Polygon"
            else [p[0] for p in geometria["coordinates"]]
        )
        puntos = [pt for anillo in anillos for pt in anillo]
        lat_media = sum(p[1] for p in puntos) / len(puntos)
        escala_x = math.cos(math.radians(lat_media))
        xs = [p[0] * escala_x for p in puntos]
        ys = [p[1] for p in puntos]
        ancho_g, alto_g = max(xs) - min(xs), max(ys) - min(ys)
        tam = max(ancho_g, alto_g) or 1e-9
        margen = lado * 0.1
        factor = (lado - 2 * margen) / tam
        ox = x + margen + ((lado - 2 * margen) - ancho_g * factor) / 2
        oy = y + margen + ((lado - 2 * margen) - alto_g * factor) / 2
        self.set_draw_color(*ESMERALDA)
        self.set_fill_color(209, 250, 229)
        self.set_line_width(0.5)
        for anillo in anillos:
            trazo = [
                (ox + (p[0] * escala_x - min(xs)) * factor, oy + (max(ys) - p[1]) * factor) for p in anillo
            ]
            self.polygon(trazo, style="DF")
        self.set_line_width(0.2)
        # Flecha del norte
        self.set_font("Jakarta", "B", 7)
        self.set_text_color(*TINTA_3)
        self.text(x + lado - 5, y + 5, "N")
        self.line(x + lado - 4.2, y + 6, x + lado - 4.2, y + 11)
        metros = f"{max(ancho_g, alto_g) * 111_320:,.0f}".replace(",", " ")
        return f"Croquis sin mapa de fondo, con el norte arriba. Lado mayor: unos {metros} m."

"""PDF del DEX (Parte 9), en español y en inglés, desde el mismo contenido sellado.

Los dos tienen la misma estructura y las mismas cifras. Los textos fijos salen de app/textos; lo que
escribieron las personas (notas, motivos, explicaciones) no se traduce: en el PDF en inglés aparece en
español, bajo "Original text in Spanish". Orden de las secciones: leyenda y mensaje final; identificación,
exportador, importador y orden, y producto; genealogía con el croquis; respaldo por parcela; proceso y
embarque; recomprobación; informe de hallazgos completo; documentos de evidencia.
"""

import io
import math
from datetime import datetime
from functools import partial
from typing import Any

from app import textos, ubigeo
from app.catalogos import mapbiomas_peru_c3 as leyenda
from app.fechas import LIMA
from app.pdf.base import AMBAR, ESMERALDA, FONDO, LINEA, TINTA, TINTA_3, Documento
from app.services.hallazgos.catalogo import GRUPOS
from app.services.hallazgos.parcela import texto_fuente


class Pdf(Documento):
    def __init__(self, codigo: str, idioma: str, demo: bool = False):
        marca = textos.obtener(idioma, "pdf.demo") if demo else None
        super().__init__(codigo, pie=textos.obtener(idioma, "pdf.pagina"), marca_agua=marca)
        self.idioma = idioma

    # ---------- Textos ----------

    def L(self, clave: str, **valores) -> str:
        """Etiqueta del PDF en el idioma del documento."""
        return (
            textos.t(self.idioma, f"pdf.{clave}", **valores)
            if valores
            else textos.obtener(self.idioma, f"pdf.{clave}")
        )

    def de(self, valor: Any) -> Any:
        return textos.en_idioma(self.idioma, valor)

    def fecha(self, valor: str | None, *, hora: bool = False) -> str:
        if not valor:
            return "—"
        texto = textos.fecha(self.idioma, valor)
        if hora and len(valor) > 10:
            momento = datetime.fromisoformat(valor).astimezone(LIMA)
            texto += f", {momento:%H:%M} {self.L('hora_lima')}"
        return texto

    def original(self, texto: str | None) -> str | None:
        """Lo que escribió una persona: en el PDF en inglés va en español, con su etiqueta."""
        if not texto:
            return texto
        if self.idioma == "es":
            return texto
        return f"{textos.obtener('en', 'comun.texto_original')}: {texto}"

    def estado(self, valor: str | None) -> str:
        return textos.obtener(self.idioma, "estados").get(valor or "", valor or "—")

    def nivel(self, valor: str | None) -> str:
        return textos.obtener(self.idioma, "niveles").get(valor or "", "—")

    def documento(self, codigo: str) -> str:
        return textos.obtener(self.idioma, "documentos").get(codigo, codigo)

    def subtitulo(self, texto: str) -> None:
        if self.get_y() > self.page_break_trigger - 20:
            self.add_page()
        self.ln(1)
        self.set_font("Jakarta", "B", 9.5)
        self.set_text_color(*TINTA)
        self.multi_cell(0, 5.5, texto, new_x="LMARGIN", new_y="NEXT")


def _kg(valor: Any) -> str:
    return "—" if valor in (None, "") else f"{textos.numero(valor)} kg"


def _ha(valor: Any) -> str:
    return "—" if valor in (None, "") else f"{textos.hectareas(valor)} ha"


def _pct(valor: Any) -> str:
    return "—" if valor in (None, "") else f"{textos.numero(valor)} %"


# ---------- Encabezado y mensaje final ----------


def _encabezado(pdf: Pdf, c: dict[str, Any], huella: str, url: str) -> None:
    ident = c["identificacion"]
    lado_qr = 34
    x_qr = pdf.w - pdf.r_margin - lado_qr
    y0 = pdf.get_y()
    pdf.qr(url, x_qr, y0, lado_qr)
    ancho = pdf.ancho - lado_qr - 6
    pdf.set_font("Jakarta", "B", 8)
    pdf.set_text_color(*TINTA_3)
    pdf.cell(ancho, 5, pdf.L("marca"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Mono", "", 15)
    pdf.set_text_color(*TINTA)
    pdf.cell(ancho, 8, ident["codigo"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Jakarta", "", 8.5)
    pdf.multi_cell(
        ancho,
        4.4,
        f"{ident['cooperativa']['razon_social']} · RUC {ident['cooperativa']['ruc']}\n"
        f"{pdf.L('titulo')} · {pdf.L('lote')} {ident['lote']['codigo']}\n"
        + pdf.L("emitido_el", fecha=pdf.fecha(ident["emitido_en"], hora=True)),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(1)
    pdf.set_font("Jakarta", "", 7.5)
    pdf.set_text_color(*TINTA_3)
    pdf.multi_cell(ancho, 4, pdf.L("huella"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Mono", "", 7.5)
    pdf.set_text_color(*TINTA)
    pdf.multi_cell(ancho, 3.8, huella, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Jakarta", "", 6.5)
    pdf.set_text_color(*TINTA_3)
    pdf.set_xy(x_qr - 4, y0 + lado_qr + 0.5)
    enlace = url.replace("#/", "\n#/", 1).replace("/dex/", "/dex/\n", 1)
    pdf.multi_cell(lado_qr + 4, 3, f"{pdf.L('verificacion')}\n{enlace}", align="C")
    pdf.set_y(max(pdf.get_y(), y0 + lado_qr + 12))
    pdf.ln(1)


def _mensaje(pdf: Pdf, informe: dict[str, Any]) -> None:
    """Encabezado, los grupos con su número de hallazgos (una frase por código), contexto y cierre."""
    pdf.seccion(textos.obtener(pdf.idioma, "secciones.mensaje"))
    for bloque in informe["mensaje"][pdf.idioma]:
        if bloque["titulo"]:
            if pdf.get_y() > pdf.page_break_trigger - 14:
                pdf.add_page()
            pdf.set_font("Jakarta", "B", 9)
            pdf.set_text_color(*TINTA)
            pdf.multi_cell(0, 5, bloque["titulo"], new_x="LMARGIN", new_y="NEXT")
        vinetas = bloque["grupo"] is not None
        for frase in bloque["frases"]:
            pdf.parrafo(f"• {frase}" if vinetas else frase, tamano=8.5 if vinetas else 9, color=TINTA)


# ---------- Identificación, exportador, importador, producto ----------


def _detalle_documento(pdf: Pdf, doc: dict[str, Any]) -> str:
    """Número, emisor y fechas de un documento, en una línea."""
    detalle = " · ".join(
        [doc.get("numero") or "—", doc.get("entidad_emisora") or "—", pdf.fecha(doc.get("fecha_emision"))]
    )
    if doc.get("fecha_vencimiento"):
        detalle += f" → {pdf.fecha(doc['fecha_vencimiento'])}"
    return detalle


def _identificacion(pdf: Pdf, c: dict[str, Any]) -> None:
    ident = c["identificacion"]
    pdf.seccion(pdf.L("identificacion"))
    pdf.dato(pdf.L("codigo"), ident["codigo"], mono=True)
    pdf.dato(pdf.L("lote"), ident["lote"]["codigo"], mono=True)
    pdf.dato(pdf.L("emitido"), pdf.fecha(ident["emitido_en"], hora=True))
    pdf.dato(pdf.L("emitido_por"), ident["emitido_por"])

    e = c["exportador"]
    pdf.seccion(pdf.L("exportador"))
    pdf.dato(pdf.L("razon_social"), e["razon_social"])
    pdf.dato(pdf.L("ruc"), e["ruc"], mono=True)
    pdf.dato(pdf.L("direccion"), e["direccion_postal"])
    pdf.dato(pdf.L("correo"), e["correo"])
    pdf.dato(pdf.L("representante"), e["representante"]["nombre"])
    pdf.dato(pdf.L("dni_representante"), e["representante"]["dni"], mono=True)
    pdf.subtitulo(pdf.L("documentos_legales"))
    filas = []
    for x in e["documentos"]:
        doc = x["documento"] or {}
        detalle = ""
        if doc:
            detalle = _detalle_documento(pdf, doc)
        filas.append([pdf.documento(x["codigo"]), pdf.estado(x["estado"]), pdf.nivel(x["nivel"]), detalle])
    pdf.tabla(
        [
            pdf.L("documento"),
            pdf.L("estado"),
            pdf.L("nivel"),
            f"{pdf.L('numero')} · {pdf.L('emisor')} · {pdf.L('emision')}",
        ],
        filas,
        [56, 20, 26, pdf.ancho - 102],
        tamano=7,
    )

    i, o = c["importador"], c["orden"]
    pdf.seccion(pdf.L("importador_orden"))
    pdf.dato(pdf.L("importador"), i["razon_social"])
    pdf.dato(pdf.L("direccion_importador"), i["direccion"])
    pdf.dato(pdf.L("pais"), i["pais"])
    pdf.dato(pdf.L("correo"), i["correo"])
    pdf.dato(pdf.L("eori"), i["eori"], mono=True)
    pdf.dato(pdf.L("orden"), o["codigo"], mono=True)
    pdf.dato(pdf.L("referencia"), o["referencia_importador"])
    pdf.dato(pdf.L("cantidad"), _kg(o["cantidad_kg"]))
    pdf.dato(pdf.L("tolerancia"), _pct(o["tolerancia_pct"]))
    pdf.dato(pdf.L("calidad"), o["calidad"])
    pdf.dato(pdf.L("destino"), f"{o['lugar_destino']}, {o['pais_destino']}")
    pdf.dato(pdf.L("entrega"), pdf.fecha(o["fecha_entrega"]))

    p = c["producto"]
    pdf.seccion(pdf.L("producto"))
    pdf.dato(pdf.L("partida"), p["partida_sa"], mono=True)
    pdf.dato(pdf.L("descripcion"), pdf.de(p["descripcion"]))
    pdf.dato(pdf.L("nombre_cientifico"), p["nombre_cientifico"])
    pdf.dato(pdf.L("masa_neta"), _kg(p["masa_neta_kg"]))
    pdf.dato(pdf.L("pais_produccion"), f"{pdf.L('pais_produccion_valor')} ({p['pais_produccion']})")


# ---------- Genealogía y croquis ----------


def _croquis_lote(
    pdf: Pdf, parcelas: list[dict[str, Any]], x: float, y: float, ancho: float, alto: float
) -> None:
    """Todas las parcelas del lote en un mismo marco, con el norte arriba y sin mapa de fondo."""
    pdf.set_draw_color(*LINEA)
    pdf.set_fill_color(*FONDO)
    pdf.rect(x, y, ancho, alto, style="DF")
    puntos = []
    for p in parcelas:
        g = p["geometria"]
        if g["type"] == "Point":
            puntos.append(g["coordinates"][:2])
        else:
            anillos = [g["coordinates"][0]] if g["type"] == "Polygon" else [q[0] for q in g["coordinates"]]
            puntos += [pt[:2] for anillo in anillos for pt in anillo]
    if not puntos:
        return
    lat_media = sum(pt[1] for pt in puntos) / len(puntos)
    escala_x = math.cos(math.radians(lat_media))
    xs = [pt[0] * escala_x for pt in puntos]
    ys = [pt[1] for pt in puntos]
    ancho_g, alto_g = (max(xs) - min(xs)) or 1e-6, (max(ys) - min(ys)) or 1e-6
    margen = 8
    factor = min((ancho - 2 * margen) / ancho_g, (alto - 2 * margen) / alto_g)
    ox = x + margen + ((ancho - 2 * margen) - ancho_g * factor) / 2
    oy = y + margen + ((alto - 2 * margen) - alto_g * factor) / 2

    def punto(lon: float, lat: float) -> tuple[float, float]:
        return ox + (lon * escala_x - min(xs)) * factor, oy + (max(ys) - lat) * factor

    pdf.set_font("Jakarta", "B", 6.5)
    for p in parcelas:
        g = p["geometria"]
        pdf.set_draw_color(*ESMERALDA)
        pdf.set_line_width(0.4)
        if g["type"] == "Point":
            cx, cy = punto(*g["coordinates"][:2])
            pdf.set_fill_color(*ESMERALDA)
            pdf.circle(x=cx - 1.2, y=cy - 1.2, radius=1.2, style="F")
            etiqueta = (cx + 2, cy + 1)
        else:
            anillos = [g["coordinates"][0]] if g["type"] == "Polygon" else [q[0] for q in g["coordinates"]]
            pdf.set_fill_color(209, 250, 229)
            for anillo in anillos:
                pdf.polygon([punto(*pt[:2]) for pt in anillo], style="DF")
            vertices = [punto(*pt[:2]) for pt in anillos[0]]
            etiqueta = (
                sum(v[0] for v in vertices) / len(vertices),
                sum(v[1] for v in vertices) / len(vertices),
            )
        pdf.set_text_color(*TINTA)
        pdf.text(etiqueta[0], etiqueta[1], p["codigo"])
    pdf.set_line_width(0.2)
    pdf.set_font("Jakarta", "B", 7)
    pdf.set_text_color(*TINTA_3)
    pdf.set_draw_color(*TINTA_3)
    pdf.text(x + ancho - 5, y + 5, "N")
    pdf.line(x + ancho - 4.2, y + 6, x + ancho - 4.2, y + 11)


def _genealogia(pdf: Pdf, c: dict[str, Any]) -> None:
    g = c["genealogia"]
    pdf.seccion(pdf.L("genealogia"), pdf.L("genealogia_sub"))
    filas = []
    for p in g["parcelas"]:
        u = p["ubicacion"]
        filas.append(
            [
                f"{p['codigo']}\n{p['nombre']}",
                p["productor"],
                ", ".join(ubigeo.mostrar(v) for v in (u["distrito"], u["provincia"], u["departamento"]) if v),
                _ha(p["area_ha"]),
                pdf.L("poligono") if p["tipo_geometria"] == "poligono" else pdf.L("punto"),
                _kg(p["kg"]),
                _pct(p["proporcion_pct"]),
                pdf.L(
                    "cosecha_valor",
                    desde=pdf.fecha(p["cosecha"]["desde"]),
                    hasta=pdf.fecha(p["cosecha"]["hasta"]),
                ),
            ]
        )
    pdf.tabla(
        [
            pdf.L("parcela"),
            pdf.L("productor"),
            pdf.L("ubicacion"),
            pdf.L("area"),
            pdf.L("geometria"),
            pdf.L("kilos"),
            pdf.L("proporcion"),
            pdf.L("cosecha"),
        ],
        filas,
        [24, 28, 30, 16, 16, 20, 16, pdf.ancho - 150],
        tamano=6.5,
    )
    alto = 90
    if pdf.get_y() + alto + 10 > pdf.page_break_trigger:
        pdf.add_page()
    y = pdf.get_y()
    _croquis_lote(pdf, g["parcelas"], pdf.l_margin, y, pdf.ancho, alto)
    pdf.set_y(y + alto + 1)
    pdf.parrafo(pdf.L("croquis"), tamano=7.5, color=TINTA_3)


# ---------- Respaldo por parcela ----------


def _uso_suelo(pdf: Pdf, cobertura: list[dict[str, Any]]) -> None:
    """Historial de uso del suelo de MapBiomas (pedido del equipo del 2026-10-08), con los nombres de la
    leyenda oficial en el idioma del documento."""
    indicadores = next((f.get("indicadores") or {} for f in cobertura if f["fuente"] == "mapbiomas"), {})
    if not indicadores.get("anios"):
        return
    pdf.subtitulo(pdf.L("uso_suelo"))
    pdf.parrafo(pdf.L("uso_suelo_nota", pixeles=indicadores.get("pixeles", "—")), tamano=7.5)
    nombre = partial(leyenda.nombre_sellado, indicadores.get("clases") or {}, idioma=pdf.idioma)
    pdf.uso_suelo(indicadores, pdf.L("clase"), nombre)


def _imagenes(pdf: Pdf, bloque: dict[str, Any], png: dict[str, bytes]) -> None:
    papeles = [p for p in ("anterior_al_corte", "reciente") if bloque.get(p)]
    ancho = (pdf.ancho - 6) / 2
    alto_max = ancho * 1.15
    if papeles and pdf.get_y() + 12 + alto_max + 20 > pdf.page_break_trigger:
        pdf.add_page()
    pdf.subtitulo(pdf.L("imagenes"))
    if papeles:
        y = pdf.get_y()
        fines = []
        for i, papel in enumerate(papeles):
            dato = bloque[papel]
            x = pdf.l_margin + i * (ancho + 6)
            alto = alto_max
            if png.get(papel):
                imagen = pdf.image(io.BytesIO(png[papel]), x=x, y=y, w=ancho)
                alto = imagen.rendered_height
            pdf.set_xy(x, y + alto + 1)
            pdf.set_font("Jakarta", "B", 8.5)
            pdf.set_text_color(*TINTA)
            dias = pdf.L("dias_corte", dias=f"{dato['dias_respecto_al_corte']:+d}")
            pdf.multi_cell(
                ancho,
                4.2,
                f"{pdf.L(papel)}: {pdf.fecha(dato['fecha_captura'])} ({dias})",
                new_x="RIGHT",
                new_y="NEXT",
            )
            pdf.set_x(x)
            pdf.set_font("Mono", "", 6)
            pdf.set_text_color(*TINTA_3)
            pdf.multi_cell(
                ancho, 3, f"SHA-256 {dato['sha256']}\n{dato['atribucion']}", new_x="RIGHT", new_y="NEXT"
            )
            fines.append(pdf.get_y())
        pdf.set_xy(pdf.l_margin, max(fines) + 2)
    revision = bloque.get("revision")
    if revision:
        pdf.dato(pdf.L("revisada_por"), revision.get("revisada_por"))
        pdf.dato(pdf.L("fecha"), pdf.fecha(revision.get("revisada_en"), hora=True))
        pdf.dato(
            pdf.L("obs_2020"), textos.obtener(pdf.idioma, "observaciones").get(revision["observacion_2020"])
        )
        pdf.dato(
            pdf.L("obs_cambio"),
            textos.obtener(pdf.idioma, "observaciones").get(revision["observacion_cambio"]),
        )
        pdf.dato(pdf.L("lo_observado"), pdf.original(revision.get("descripcion")))
    else:
        pdf.dato(pdf.L("revision"), pdf.L("sin_revision"))
    altas = bloque.get("alta_resolucion") or []
    if altas:
        pdf.dato(
            pdf.L("alta_resolucion"),
            "; ".join(
                f"{pdf.fecha(a['fecha_captura'])}, {a.get('proveedor') or '—'}"
                + (f", {a['resolucion_m']:g} m" if a.get("resolucion_m") is not None else "")
                for a in altas
            ),
        )


def _respaldo(pdf: Pdf, c: dict[str, Any], png: dict[str, dict[str, bytes]]) -> None:
    pdf.seccion(pdf.L("respaldo"), pdf.L("respaldo_sub"))
    for r in c["respaldo"]:
        if pdf.get_y() > pdf.page_break_trigger - 60:
            pdf.add_page()
        pdf.set_font("Mono", "", 10.5)
        pdf.set_text_color(*TINTA)
        pdf.cell(0, 7, f"{pdf.L('parcela')} {r['parcela']}", new_x="LMARGIN", new_y="NEXT")
        pdf.dato(pdf.L("dops"), "; ".join(f"{d['codigo']} ({d['tanda']})" for d in r["dops"]), mono=True)
        for d in r["dops"]:
            pdf.dato(f"{pdf.L('huella_corta')} {d['codigo']}", d["sha256"], mono=True)
        h = r["habilitacion"]
        pdf.dato(pdf.L("habilitacion"), pdf.estado(h["estado"]))
        if h.get("decidida_en"):
            pdf.dato(
                pdf.L("decidio"), f"{h.get('decidida_por') or '—'} · {pdf.fecha(h['decidida_en'], hora=True)}"
            )
        if h.get("nota"):
            pdf.dato(pdf.L("nota"), pdf.original(h["nota"]))
        pdf.subtitulo(pdf.L("fuentes"))
        pdf.tabla(
            [
                pdf.L("fuente"),
                pdf.L("resultado"),
                pdf.L("fecha"),
                pdf.L("version"),
                pdf.L("huella_respuesta"),
            ],
            [
                [
                    f["nombre"],
                    texto_fuente(pdf.idioma, f["fuente"], f.get("resultado_fuente"), f.get("indicadores")),
                    pdf.fecha(f.get("completado_en")),
                    f.get("version"),
                    f.get("respuesta_sha256"),
                ]
                for f in r["cobertura"]
            ],
            [26, 56, 22, 22, pdf.ancho - 126],
            tamano=6.5,
        )
        conteos = (r.get("convergencia") or {}).get("conteos")
        if conteos and "perdida_registran" in conteos:
            pdf.parrafo(
                pdf.L(
                    "convergencia_frase",
                    n=conteos["consultados"],
                    a=conteos["bosque_registran"],
                    b=conteos["bosque_miden"],
                    c=conteos["perdida_registran"],
                    d=conteos["perdida_miden"],
                    e=conteos["alteracion_registran"],
                    f=conteos["alteracion_miden"],
                ),
                tamano=8,
            )
        _uso_suelo(pdf, r["cobertura"])
        if r.get("imagenes"):
            _imagenes(pdf, r["imagenes"], png.get(r["parcela"], {}))
        pdf.subtitulo(pdf.L("casillas"))
        filas = []
        for casilla in r["expediente"]["casillas"]:
            doc, exencion = casilla.get("documento"), casilla.get("exencion")
            if doc:
                detalle = _detalle_documento(pdf, doc)
            elif exencion:
                detalle = pdf.L("exencion", motivo=pdf.original(exencion["motivo"]))
            elif casilla.get("cubierta_por"):
                detalle = pdf.L("tenencia_cubierta", documento=pdf.documento(casilla["cubierta_por"]))
            else:
                detalle = ""
            filas.append(
                [
                    pdf.documento(casilla["codigo"]),
                    pdf.estado(casilla["estado"]),
                    pdf.nivel(casilla.get("nivel")),
                    detalle,
                ]
            )
        pdf.tabla(
            [pdf.L("casilla"), pdf.L("estado"), pdf.L("nivel"), pdf.L("documento")],
            filas,
            [56, 20, 26, pdf.ancho - 102],
            tamano=6.5,
        )


# ---------- Proceso, embarque y recomprobación ----------


def _proceso_y_embarque(pdf: Pdf, c: dict[str, Any]) -> None:
    pdf.seccion(pdf.L("proceso"))
    filas = []
    for x in c["proceso"]:
        r = x.get("rendimiento") or {}
        filas.append(
            [
                x["dpp"],
                x["corrida"],
                pdf.L(x["ruta"]) if x.get("ruta") in ("completa", "seco") else x.get("ruta"),
                pdf.L(x["tipo_manejo"])
                if x.get("tipo_manejo") in ("segregado", "mezclado")
                else x.get("tipo_manejo"),
                x.get("tanda_final"),
                f"{_kg(r.get('entrada_kg'))} → {_kg(r.get('peso_final_kg'))}" if r else "—",
                r.get("rendimiento") or "—",
            ]
        )
    pdf.tabla(
        [
            pdf.L("dpp"),
            pdf.L("corrida"),
            pdf.L("ruta"),
            pdf.L("manejo"),
            "TF",
            f"{pdf.L('entrada')} → {pdf.L('salida')}",
            pdf.L("rendimiento"),
        ],
        filas,
        [30, 24, 30, 20, 22, 34, pdf.ancho - 160],
        tamano=6.5,
    )
    for x in c["proceso"]:
        pdf.dato(f"{pdf.L('huella_corta')} {x['dpp']}", x["sha256"], mono=True)

    pdf.seccion(pdf.L("embarque"))
    pdf.tabla(
        [pdf.L("documento"), pdf.L("numero"), pdf.L("emisor"), pdf.L("emision"), pdf.L("huella_corta")],
        [
            [
                pdf.documento(x["tipo"]),
                x.get("numero"),
                x.get("entidad_emisora"),
                pdf.fecha(x.get("fecha_emision")),
                x.get("sha256"),
            ]
            for x in c["embarque"]
        ],
        [36, 24, 30, 22, pdf.ancho - 112],
        tamano=6.5,
    )


def _recomprobacion(pdf: Pdf, c: dict[str, Any]) -> None:
    r = c["recomprobacion"]
    pdf.seccion(pdf.L("recomprobacion"), pdf.L("recomprobacion_sub"))
    pdf.dato(pdf.L("fecha"), pdf.fecha(r["ejecutada_en"], hora=True))
    pdf.tabla(
        [pdf.L("comprobacion"), pdf.L("resultado")],
        [
            [
                textos.obtener(pdf.idioma, "comprobaciones").get(x["codigo"], x["nombre"]),
                pdf.L("sin_observaciones")
                if x["resultado"] == "sin_observaciones"
                else pdf.L("con_observaciones"),
            ]
            for x in r["comprobaciones"]
        ],
        [pdf.ancho - 50, 50],
        tamano=7.5,
    )


# ---------- Informe completo ----------


def _informe(pdf: Pdf, informe: dict[str, Any]) -> None:
    idioma = pdf.idioma
    pdf.seccion(pdf.L("informe"))
    pdf.subtitulo(textos.obtener(idioma, "secciones.datos_lote"))
    for fila in informe["datos_lote"]:
        pdf.dato(fila["etiqueta"][idioma], fila["valor"][idioma])
    pdf.subtitulo(textos.obtener(idioma, "secciones.hallazgos"))
    for grupo in GRUPOS:
        del_grupo = [h for h in informe["hallazgos"] if h["grupo"] == grupo]
        if grupo == "impide_cierre" and not informe["preliminar"]:
            continue
        pdf.set_font("Jakarta", "B", 8.5)
        pdf.set_text_color(*TINTA)
        pdf.cell(
            0,
            6,
            f"{textos.obtener(idioma, f'grupos.{grupo}')} — {len(del_grupo)}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        if not del_grupo:
            pdf.parrafo(textos.obtener(idioma, "comun.vacio"), tamano=8, color=TINTA_3)
            continue
        filas = []
        for h in del_grupo:
            hecho = h["hecho"][idioma]
            if h.get("explicacion"):
                hecho += f"\n{pdf.L('explicacion')}: {pdf.original(h['explicacion'])}"
            filas.append(
                [
                    h["sujeto"].get("codigo") or "—",
                    str(h["criterio"]),
                    _pct(h["peso_en_lote_pct"]),
                    hecho,
                ]
            )
        pdf.tabla(
            [pdf.L("sujeto"), pdf.L("criterio"), pdf.L("peso"), pdf.L("hecho")],
            filas,
            [24, 14, 18, pdf.ancho - 56],
            tamano=6.8,
        )
    pdf.subtitulo(textos.obtener(idioma, "secciones.no_verificado"))
    for frase in informe["no_verificado"][idioma]:
        pdf.parrafo(f"• {frase}", tamano=8)
    pdf.subtitulo(textos.obtener(idioma, "secciones.contexto"))
    pdf.parrafo(informe["contexto"]["texto"][idioma], tamano=8.5)
    pdf.subtitulo(pdf.L("criterios_titulo"))
    for numero, nombres in informe["criterios"].items():
        pdf.parrafo(f"{numero}. {nombres[idioma]}", tamano=7.5)


def _evidencia(pdf: Pdf, c: dict[str, Any]) -> None:
    pdf.seccion(pdf.L("evidencia"), pdf.L("evidencia_sub"))
    pdf.tabla(
        [pdf.L("documento"), pdf.L("de"), pdf.L("numero"), pdf.L("fecha"), pdf.L("huella_corta")],
        [
            [
                pdf.documento(x["tipo"]),
                x.get("de"),
                x.get("numero"),
                pdf.fecha(x.get("fecha")),
                x.get("sha256"),
            ]
            for x in c["evidencia"]
        ],
        [42, 24, 24, 24, pdf.ancho - 114],
        tamano=6.3,
    )


def documento(
    contenido: dict[str, Any],
    huella: str,
    url: str,
    idioma: str,
    imagenes: dict[str, dict[str, bytes]] | None = None,
) -> Pdf:
    c = contenido
    pdf = Pdf(c["identificacion"]["codigo"], idioma, demo=bool(c.get("es_demo")))
    pdf.set_title(f"{c['identificacion']['codigo']} ({idioma})")
    pdf.add_page()
    _encabezado(pdf, c, huella, url)
    pdf.recuadro(c["leyenda"][idioma] + ".")
    if c.get("es_demo"):
        pdf.parrafo(pdf.L("demo"), tamano=9, color=AMBAR)
    _mensaje(pdf, c["informe"])
    _identificacion(pdf, c)
    _genealogia(pdf, c)
    _respaldo(pdf, c, imagenes or {})
    _proceso_y_embarque(pdf, c)
    _recomprobacion(pdf, c)
    _informe(pdf, c["informe"])
    _evidencia(pdf, c)
    return pdf


def generar(
    contenido: dict[str, Any],
    huella: str,
    url: str,
    idioma: str,
    imagenes: dict[str, dict[str, bytes]] | None = None,
) -> bytes:
    return bytes(documento(contenido, huella, url, idioma, imagenes).output())

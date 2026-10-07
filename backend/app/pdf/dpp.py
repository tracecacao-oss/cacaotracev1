"""PDF del DPP (Parte 6): se genera una sola vez, al consolidar, a partir del contenido sellado.

Mismo encabezado que el DOP (código, fecha, huella y código QR). Las 23 etapas van como diagrama de análisis
de proceso: una fila por etapa, con el símbolo de su tipo, su lugar, su tiempo y su distancia.
"""

from datetime import datetime
from typing import Any

from app.catalogos import etapas_proceso as catalogo
from app.fechas import LIMA
from app.pdf.base import AMBAR, ESMERALDA, FONDO, LINEA, TEXTO_DEMO, TINTA, TINTA_2, TINTA_3, Documento
from app.pdf.dop import _fecha, _kg

ALERTAS = {
    "rendimiento_sobre_banda": (
        "Salió más grano del que explica la baba registrada: pudo entrar cacao sin registro"
    ),
    "rendimiento_bajo_banda": "Merma inusual, o salió grano que no se registró",
    "peso_final_supera_entrada": "El peso final supera en más de 1 % el peso seco que entró",
    "tanda_de_parcela_observada": "Entró una tanda de una parcela que pasó a observada después de su DOP",
}
RUTA = {"completa": "Completa (cacao en baba)", "seco": "Seco (grano entregado seco)"}
MANEJO = {"segregado": "Segregado (un solo productor)", "mezclado": "Mezclado (varios productores)"}
SITUACION = {
    "no_aplica": "No aplica en la ruta seco",
    "no_usada": "La cooperativa no usa esta etapa",
    "no_ocurrio": "No ocurrió",
    "pendiente": "Sin registrar",
}
SIMBOLOS = (
    "Operación (círculo) · Inspección (cuadrado) · Transporte (flecha) · Espera (D) · "
    "Almacenamiento (triángulo)"
)


def _encabezado(pdf: Documento, c: dict[str, Any], huella: str, url: str) -> None:
    ident = c["identificacion"]
    lado_qr = 34
    x_qr = pdf.w - pdf.r_margin - lado_qr
    y0 = pdf.get_y()
    pdf.qr(url, x_qr, y0, lado_qr)
    ancho = pdf.ancho - lado_qr - 6
    pdf.set_font("Jakarta", "B", 8)
    pdf.set_text_color(*TINTA_3)
    pdf.cell(ancho, 5, "CacaoTrace · DPP", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Mono", "", 15)
    pdf.set_text_color(*TINTA)
    pdf.cell(ancho, 8, ident["codigo"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Jakarta", "", 8.5)
    pdf.multi_cell(
        ancho,
        4.4,
        f"{ident['cooperativa']['razon_social']} · RUC {ident['cooperativa']['ruc']}\n"
        f"Emitido el {_fecha(ident['emitido_en'], hora=True)}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(1)
    pdf.set_font("Jakarta", "", 7.5)
    pdf.set_text_color(*TINTA_3)
    pdf.cell(
        ancho,
        4,
        "Huella SHA-256 del contenido (JSON con claves ordenadas, UTF-8, sin espacios):",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("Mono", "", 7.5)
    pdf.set_text_color(*TINTA)
    pdf.multi_cell(ancho, 3.8, huella, new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(x_qr - 4, y0 + lado_qr + 1)
    pdf.set_font("Jakarta", "", 6.5)
    pdf.set_text_color(*TINTA_3)
    pdf.multi_cell(lado_qr + 4, 3, f"Verificación pública:\n{url}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(max(pdf.get_y(), y0 + lado_qr + 12))
    pdf.ln(2)


def _simbolo(pdf: Documento, tipo: str, cx: float, cy: float, activo: bool) -> None:
    """Símbolos del diagrama de análisis de proceso, dibujados con líneas."""
    r = 2.1
    pdf.set_draw_color(*(ESMERALDA if activo else LINEA))
    pdf.set_fill_color(*((209, 250, 229) if activo else FONDO))
    pdf.set_line_width(0.35)
    if tipo == "operacion":
        pdf.circle(x=cx - r, y=cy - r, radius=r, style="DF")
    elif tipo == "inspeccion":
        pdf.rect(cx - r, cy - r, 2 * r, 2 * r, style="DF")
    elif tipo == "transporte":
        pdf.polygon(
            [
                (cx - r, cy - 0.8),
                (cx + 0.4, cy - 0.8),
                (cx + 0.4, cy - r),
                (cx + r + 0.6, cy),
                (cx + 0.4, cy + r),
                (cx + 0.4, cy + 0.8),
                (cx - r, cy + 0.8),
            ],
            style="DF",
        )
    elif tipo == "espera":
        pdf.line(cx - r, cy - r, cx - r, cy + r)
        pdf.line(cx - r, cy - r, cx, cy - r)
        pdf.line(cx - r, cy + r, cx, cy + r)
        pdf.arc(x=cx - r, y=cy - r, a=2 * r, b=2 * r, start_angle=-90, end_angle=90, style="D")
    else:  # almacenamiento
        pdf.polygon([(cx - r, cy - r), (cx + r, cy - r), (cx, cy + r)], style="DF")
    pdf.set_line_width(0.2)


def _cuantos(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _dato_propio(e: dict[str, Any]) -> str:
    datos = e.get("datos") or {}
    numero = e["numero"]
    if numero == 1 and datos.get("tandas"):
        return f"{_cuantos(len(datos['tandas']), 'tanda', 'tandas')} · {_kg(datos.get('peso_total_kg'))}"
    if numero == 3 and datos.get("dops"):
        return f"{datos.get('codigo_corrida')} · {len(datos['dops'])} DOP"
    if numero == 4 and datos.get("tandas"):
        return "; ".join(
            f"{t['codigo']}: {t['dop_estado']}, parcela {t['habilitacion_estado']}" for t in datos["tandas"]
        )
    if numero == 5:
        return MANEJO.get(datos.get("tipo_manejo"), "—")
    if numero == 17:
        return datos.get("calidad") or "—"
    if numero == 21 and datos.get("numero_sacos") is not None:
        return _cuantos(int(datos["numero_sacos"]), "saco", "sacos")
    partes = []
    for dato in catalogo.POR_NUMERO[numero].datos:
        valor = datos.get(dato.clave)
        if valor in (None, "", []):
            continue
        if dato.tipo == "fechas":
            partes.append(_cuantos(len(valor), "volteo", "volteos"))
        elif dato.unidad:
            partes.append(f"{valor} {dato.unidad}")
        else:
            partes.append(str(valor))
    return " · ".join(partes) or "—"


def _lima(valor: str) -> str:
    return datetime.fromisoformat(valor).astimezone(LIMA).strftime("%d/%m/%Y %H:%M")


def _situacion(e: dict[str, Any], ruta: str) -> str:
    """Una etapa que no aplica: o no es de la ruta seco, o la cooperativa la desactivó en su plantilla."""
    if e["situacion"] == "no_aplica" and (ruta != "seco" or catalogo.POR_NUMERO[e["numero"]].en_ruta_seco):
        return SITUACION["no_usada"]
    return SITUACION.get(e["situacion"], "—")


def _tiempo(e: dict[str, Any], ruta: str) -> str:
    if not e.get("inicio"):
        return _situacion(e, ruta)
    horas = e.get("duracion_horas")
    duracion = f" ({float(horas):g} h)" if horas not in (None, "") else ""
    return f"{_lima(e['inicio'])} a {_lima(e['fin'])}{duracion}"


def _diagrama(pdf: Documento, etapas: list[dict[str, Any]], ruta: str) -> None:
    """Una fila por etapa: número, símbolo, etapa, lugar, tiempo, distancia y dato propio."""
    anchos = [7, 8, 50, 30, 40, 14, pdf.ancho - 149]
    encabezados = ["N.º", "", "Etapa", "Lugar", "Tiempo", "Dist. (m)", "Dato propio"]
    pdf.set_font("Jakarta", "B", 6.8)
    pdf.set_text_color(*TINTA_2)
    pdf.set_fill_color(*FONDO)
    x0 = pdf.l_margin
    for ancho, texto in zip(anchos, encabezados, strict=True):
        pdf.cell(ancho, 5, texto, fill=True)
    pdf.ln(5)
    fase_actual = None
    for e in etapas:
        if e["fase"] != fase_actual:
            fase_actual = e["fase"]
            if pdf.get_y() + 12 > pdf.page_break_trigger:
                pdf.add_page()
            pdf.set_font("Jakarta", "B", 7)
            pdf.set_text_color(*ESMERALDA)
            pdf.cell(0, 5, catalogo.NOMBRE_FASE[fase_actual], new_x="LMARGIN", new_y="NEXT")
        activa = e["situacion"] == "registrada"
        textos = [
            str(e["numero"]),
            "",
            e["nombre"],
            e.get("lugar") or "—",
            _tiempo(e, ruta),
            str(e["distancia_m"]) if e.get("distancia_m") not in (None, "") else "",
            _dato_propio(e) if activa else _situacion(e, ruta),
        ]
        pdf.set_font("Jakarta", "", 6.6)
        lineas = max(
            len(pdf.multi_cell(ancho, 3.2, texto or " ", dry_run=True, output="LINES"))
            for ancho, texto in zip(anchos, textos, strict=True)
        )
        alto = max(lineas * 3.2, 6) + 1
        if pdf.get_y() + alto > pdf.page_break_trigger:
            pdf.add_page()
        y = pdf.get_y()
        x = x0
        pdf.set_text_color(*(TINTA if activa else TINTA_3))
        for i, (ancho, texto) in enumerate(zip(anchos, textos, strict=True)):
            if i == 1:
                _simbolo(pdf, e["tipo"], x + ancho / 2, y + 3.2, activa)
            else:
                pdf.set_xy(x, y + 0.5)
                pdf.set_font("Mono" if i in (0, 5) else "Jakarta", "", 6.6)
                pdf.multi_cell(ancho, 3.2, texto, align="L", new_x="RIGHT", new_y="TOP")
            x += ancho
        pdf.set_xy(x0, y + alto)
        pdf.set_draw_color(*LINEA)
        pdf.line(x0, y + alto, x0 + pdf.ancho, y + alto)
    pdf.ln(1.5)
    pdf.parrafo(SIMBOLOS + ".", tamano=7, color=TINTA_3)


def generar(contenido: dict[str, Any], huella: str, url: str) -> bytes:
    return bytes(documento(contenido, huella, url).output())


def documento(contenido: dict[str, Any], huella: str, url: str) -> Documento:
    c = contenido
    ident = c["identificacion"]
    pdf = Documento(ident["codigo"], marca_agua=TEXTO_DEMO if c.get("es_demo") else None)
    pdf.add_page()
    _encabezado(pdf, c, huella, url)
    pdf.recuadro(c["leyenda"] + ".")

    pdf.seccion("Identificación")
    pdf.dato("Código", ident["codigo"], mono=True)
    pdf.dato("Cooperativa", f"{ident['cooperativa']['razon_social']} ({ident['cooperativa']['codigo']})")
    pdf.dato("RUC de la cooperativa", ident["cooperativa"]["ruc"], mono=True)
    pdf.dato("Fecha de emisión", _fecha(ident["emitido_en"], hora=True))
    pdf.dato("Corrida", ident["corrida"], mono=True)
    pdf.dato("Ruta", RUTA.get(ident["ruta"], ident["ruta"]))
    pdf.dato("Tipo de manejo", MANEJO.get(ident["tipo_manejo"], ident["tipo_manejo"]))
    pdf.dato("Consolidó", ident["consolidada_por"])

    entrada = c["entrada"]
    pdf.seccion(
        "Entrada", "Cada tanda con su DOP, su peso al entrar y su proporción sobre la masa de entrada."
    )
    pdf.tabla(
        ["Tanda", "DOP y huella", "Productor", "Parcela", "Peso", "Proporción"],
        [
            [
                t["tanda"],
                f"{t['dop']}\n{t['dop_sha256'][:16]}…",
                f"{t['productor']['nombres']}\nDNI {t['productor']['dni']}",
                f"{t['parcela']['codigo']} · {t['parcela']['nombre']}",
                _kg(t["peso_kg"]),
                t["proporcion"],
            ]
            for t in entrada["tandas"]
        ],
        [28, 40, 36, 34, 20, pdf.ancho - 158],
    )
    pdf.dato("Peso total de entrada", _kg(entrada["peso_total_kg"]))

    pdf.seccion(
        "Diagrama de análisis de proceso",
        "Las 23 etapas del catálogo, con el símbolo de su tipo, su lugar, su tiempo y su distancia.",
    )
    _diagrama(pdf, c["etapas"], c["identificacion"]["ruta"])

    s = c["salida"]
    pdf.seccion("Salida", "La tanda final que entró al stock.")
    pdf.dato("Tanda final", s["tanda_final"], mono=True)
    pdf.dato("Peso final", _kg(s["peso_final_kg"]))
    pdf.dato("Humedad", f"{s['humedad_pct']} %" if s.get("humedad_pct") not in (None, "") else None)
    pdf.dato("Calidad", s["calidad"])
    pdf.dato("Sacos", s["numero_sacos"])
    pdf.dato("Almacén", s["almacen"])

    r = c["rendimiento"]
    pdf.seccion("Rendimiento")
    pdf.dato("Peso de entrada", _kg(r["entrada_kg"]))
    pdf.dato("Peso final", _kg(r["peso_final_kg"]))
    if r["ruta"] == "completa":
        pdf.dato("Rendimiento de baba a seco", r["rendimiento"])
        pdf.dato("Banda de la cooperativa", f"{r['banda_min']} a {r['banda_max']}")
    else:
        pdf.dato("Peso final entre el seco de entrada", r["rendimiento"])
        pdf.dato("Límite", "El peso final no supera la entrada en más de 1 %")

    al = c["alertas"]
    pdf.seccion(
        "Alertas y explicación", "Las alertas no impiden consolidar: las de rendimiento exigen explicación."
    )
    if al["alertas"]:
        for codigo in al["alertas"]:
            pdf.parrafo(f"• {ALERTAS.get(codigo, codigo)}.", tamano=8.5, color=AMBAR)
    else:
        pdf.parrafo("Sin alertas al consolidar.", tamano=8.5, color=TINTA_3)
    pdf.dato("Explicación", al["explicacion"])

    pdf.seccion("No verificado", "Lo que el sistema no comprobó.")
    for linea in c["no_verificado"]:
        pdf.parrafo(f"• {linea}", tamano=8)
    return pdf

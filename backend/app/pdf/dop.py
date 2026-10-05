"""PDF del DOP (Parte 5): se genera una sola vez, al emitir, a partir del contenido sellado.

Encabezado con el código, la fecha, la huella y el código QR; una sección por cada bloque del contenido,
en el mismo orden; la parcela con un croquis dibujado desde su geometría, sin mapa de fondo; y al pie de
cada página, el código y el número de página.
"""

from datetime import datetime
from typing import Any

from app.fechas import LIMA
from app.pdf.base import AMBAR, TINTA, TINTA_3, Documento

NIVEL = {
    "declarado": "Declarado",
    "documentado": "Documentado",
    "verificado_en_fuente": "Verificado en fuente",
    "no_registrado": "No registrado",
    "no_registrada": "No registrada",
}
ESTADO_MIDAGRI = {
    "no_registrada": "No registrada",
    "sin_observacion": "Sin observación",
    "en_revision": "En revisión",
    "validado": "Validado",
}
REQUISITO = {
    "parcela_activa": "Parcela activa",
    "sin_superposiciones_abiertas": "Sin superposiciones abiertas",
    "analisis_vigente": "Análisis de cobertura vigente",
    "revision_atendida": "Revisión atendida en campo",
    "expediente_completo": "Expediente legal completo",
    "productor_listo": "Productor con DNI y consentimiento",
}
ESTADO_CASILLA = {
    "vigente": "Vigente",
    "por_vencer": "Por vencer",
    "vencido": "Vencido",
    "no_aplica": "No aplica",
    "faltante": "Falta",
}
ALERTAS = {
    "volumen_acumulado_excede_tope": "El volumen de la parcela en 365 días supera el tope por hectárea",
    "dias_cosecha_entrega_altos": "Pasaron más días de los configurados entre la cosecha y la entrega",
    "peso_difiere_de_guia": "El peso de la guía difiere del peso en balanza más que la tolerancia",
    "guia_usada_por_otro_productor": "La misma guía aparece en una tanda de otro productor",
    "parcela_con_alertas": "La parcela está habilitada pero tiene alertas vigentes",
    "area_discrepante": "El área declarada difiere más de 20 % de la calculada",
    "diez_hectareas_o_mas": "Parcela de 10 ha o más",
    "superposicion": "Se superpone con otra parcela",
    "sin_sustento_midagri": "Falta el sustento del estado en MIDAGRI",
    "sin_analisis_vigente": "Falta un análisis de cobertura vigente",
    "analisis_requiere_revision": "Una fuente o un conjunto de datos pide revisión en campo",
    "analisis_con_error": "El último análisis de una fuente falló",
    "expediente_incompleto": "El expediente legal está incompleto",
    "documento_por_vencer": "Un documento legal vence pronto",
    "documento_vencido": "Un documento legal está vencido",
    "tenencia_solo_posesion": "La tenencia se apoya solo en una constancia de posesión",
    "superposicion_con_excluida": "Se superpone con una parcela excluida",
}


def _fecha(valor: str | None, *, hora: bool = False) -> str:
    if not valor:
        return "—"
    if len(valor) == 10:
        anio, mes, dia = valor.split("-")
        return f"{dia}/{mes}/{anio}"
    momento = datetime.fromisoformat(valor).astimezone(LIMA)
    return momento.strftime("%d/%m/%Y %H:%M") + " (hora de Lima)" if hora else momento.strftime("%d/%m/%Y")


def _kg(valor) -> str:
    return "—" if valor in (None, "") else f"{float(valor):,.2f} kg".replace(",", " ")


def _hectareas(valor) -> str:
    if valor in (None, ""):
        return "—"
    texto = f"{float(valor):.4f}".rstrip("0").rstrip(".")
    return f"{texto} ha"


def _encabezado(pdf: Documento, c: dict[str, Any], huella: str, url: str) -> None:
    ident = c["identificacion"]
    lado_qr = 34
    x_qr = pdf.w - pdf.r_margin - lado_qr
    y0 = pdf.get_y()
    pdf.qr(url, x_qr, y0, lado_qr)
    ancho = pdf.ancho - lado_qr - 6
    pdf.set_font("Jakarta", "B", 8)
    pdf.set_text_color(*TINTA_3)
    pdf.cell(ancho, 5, "CacaoTrace · DOP", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Mono", "", 15)
    pdf.set_text_color(*TINTA)
    pdf.cell(ancho, 8, ident["codigo"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Jakarta", "", 8.5)
    pdf.set_text_color(*TINTA)
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
    pdf.set_font("Jakarta", "", 6.5)
    pdf.set_text_color(*TINTA_3)
    pdf.set_xy(x_qr - 4, y0 + lado_qr + 0.5)
    enlace = url.replace("#/", "\n#/", 1).replace("/dop/", "/dop/\n", 1)
    pdf.multi_cell(lado_qr + 4, 3, "Verificación pública:\n" + enlace, align="C")
    pdf.set_y(max(pdf.get_y(), y0 + lado_qr + 10))
    pdf.ln(1)


def generar(contenido: dict[str, Any], huella: str, url: str) -> bytes:
    return bytes(documento(contenido, huella, url).output())


def documento(contenido: dict[str, Any], huella: str, url: str) -> Documento:
    c = contenido
    pdf = Documento(c["identificacion"]["codigo"])
    pdf.add_page()
    _encabezado(pdf, c, huella, url)
    pdf.recuadro(c["leyenda"] + ".")
    if c.get("es_demo"):
        pdf.parrafo("DEMOSTRACIÓN — DATOS FICTICIOS", tamano=9, color=AMBAR)

    # Identificación
    ident = c["identificacion"]
    pdf.seccion("Identificación")
    pdf.dato("Código", ident["codigo"], mono=True)
    pdf.dato("Cooperativa", f"{ident['cooperativa']['razon_social']} ({ident['cooperativa']['codigo']})")
    pdf.dato("RUC de la cooperativa", ident["cooperativa"]["ruc"], mono=True)
    pdf.dato("Fecha de emisión", _fecha(ident["emitido_en"], hora=True))
    pdf.dato("Registró la tanda", ident["registrada_por"])
    pdf.dato("Validó la tanda", ident["validada_por"])
    if ident["misma_persona"]:
        pdf.parrafo("La misma persona registró y validó la tanda.", tamano=8, color=TINTA_3)

    # Productor
    p = c["productor"]
    pdf.seccion("Productor", "Cada dato con su nivel de verificación.")
    pdf.dato("DNI", p["dni"]["valor"], nivel=NIVEL[p["dni"]["nivel"]], mono=True)
    pdf.dato("Nombres y apellidos", p["nombres"]["valor"], nivel=NIVEL[p["nombres"]["nivel"]])
    pdf.dato("Dirección postal", p["direccion_postal"]["valor"], nivel=NIVEL[p["direccion_postal"]["nivel"]])
    pdf.dato("Correo", p["correo"]["valor"], nivel=NIVEL[p["correo"]["nivel"]])
    pdf.dato("RUC", p["ruc"]["valor"], nivel=NIVEL[p["ruc"]["nivel"]], mono=True)
    ppa = p["ppa"]
    pdf.dato(
        "Registro en el PPA",
        (ppa["codigo"] or "Registrado") if ppa["registrado"] else "No registrado",
        nivel=NIVEL[ppa["nivel"]],
    )

    # Parcela
    pa = c["parcela"]
    pdf.seccion("Parcela")
    y = pdf.get_y()
    lado = 52
    nota_croquis = pdf.croquis(pa["geometria"], pdf.w - pdf.r_margin - lado, y, lado)
    pdf.set_xy(pdf.l_margin, y)
    ubicacion = pa["ubicacion"]
    lugar = ", ".join(
        v
        for v in (
            ubicacion["centro_poblado"],
            ubicacion["distrito"],
            ubicacion["provincia"],
            ubicacion["departamento"],
        )
        if v
    )
    pdf.set_right_margin(pdf.r_margin + lado + 4)
    pdf.dato("Código", pa["codigo"], mono=True)
    pdf.dato("Nombre", pa["nombre"])
    pdf.dato("Ubicación", lugar)
    pdf.dato("Geometría", "Polígono" if pa["tipo_geometria"] == "poligono" else "Punto")
    pdf.dato("Área calculada", _hectareas(pa["area_calculada_ha"]))
    pdf.dato("Área declarada", _hectareas(pa["area_declarada_ha"]))
    pdf.dato("Área con cacao", _hectareas(pa["area_cultivada_ha"]))
    midagri = pa["midagri"]
    pdf.dato(
        "Estado en MIDAGRI",
        f"{ESTADO_MIDAGRI.get(midagri['estado'], midagri['estado'])} {midagri['codigo'] or ''}".strip(),
        nivel=NIVEL.get(midagri["nivel"], midagri["nivel"]),
    )
    proc = pa["procedencia"] or {}
    recorrida = (
        f"Lindero recorrido en campo el {_fecha(proc.get('fecha_recorrido'))}"
        if proc.get("recorrida_en_campo")
        else "Lindero sin recorrer en campo"
    )
    pdf.dato(
        "Procedencia",
        f"{'Archivo' if proc.get('origen_geometria') == 'archivo' else 'Dibujo'}; registrada por "
        f"{'el productor' if proc.get('registrada_por_rol') == 'productor' else 'la cooperativa'}. "
        f"{recorrida}.",
    )
    pdf.set_right_margin(16)
    pdf.set_y(max(pdf.get_y(), y + lado + 2))
    pdf.parrafo(nota_croquis, tamano=7.5, color=TINTA_3)

    # Habilitación
    hab = c["habilitacion"]
    pdf.seccion("Habilitación", "La decisión vigente de la cooperativa sobre la parcela.")
    pdf.dato("Estado de la parcela", hab["estado"].capitalize())
    decision = hab["decision"]
    if decision:
        pdf.dato("Decidió", decision.get("decidida_por_nombre"))
        pdf.dato("Fecha", _fecha(decision.get("decidida_en"), hora=True))
        pdf.dato("Nota", decision.get("nota"))
        requisitos = (decision.get("requisitos") or {}).get("requisitos", [])
        if requisitos:
            pdf.tabla(
                ["Requisito al habilitar", "Cumplía", "Detalle"],
                [
                    [
                        REQUISITO.get(r.get("codigo"), r.get("codigo")),
                        "Sí" if r.get("cumple") else "No",
                        r.get("detalle"),
                    ]
                    for r in requisitos
                ],
                [50, 14, pdf.ancho - 64],
            )

    # Cobertura forestal
    pdf.seccion(
        "Cobertura forestal",
        "Lo que dijo cada fuente, tal como lo entregó, con su fecha, su versión y la huella de su respuesta.",
    )
    for fuente in c["cobertura"]:
        pdf.set_font("Jakarta", "B", 9.5)
        pdf.set_text_color(*TINTA)
        pdf.cell(0, 6, fuente["nombre"], new_x="LMARGIN", new_y="NEXT")
        pdf.dato("Resultado", fuente.get("resultado_texto"))
        pdf.dato("Valor de la fuente", fuente.get("resultado_fuente"))
        pdf.dato("Fecha", _fecha(fuente.get("completado_en"), hora=True))
        pdf.dato("Versión", fuente.get("version"))
        pdf.dato("Huella de la respuesta", fuente.get("respuesta_sha256"), mono=True)
        if fuente.get("es_aproximacion"):
            pdf.dato("Geometría analizada", "Círculo con el área declarada (la parcela es un punto)")
    conv = c["convergencia"]
    if conv.get("filas"):
        pdf.ln(1)
        pdf.set_font("Jakarta", "B", 9.5)
        pdf.cell(0, 6, "Conjuntos de datos y las dos preguntas del Reglamento", new_x="LMARGIN", new_y="NEXT")

        def medidas(lista):
            if not lista:
                return ""
            visibles = [m for m in lista if not m.get("serie")] or lista
            return "; ".join(
                f"{m['valor']} {m.get('unidad') or ''} ({m['nombre']}, {m['via']})".replace("  ", " ")
                for m in visibles
            )

        pdf.tabla(
            ["Conjunto de datos", "Vía", "Al 31/12/2020", "Después de 2020"],
            [
                [
                    f["nombre"],
                    " y ".join(f["vias"]),
                    medidas(f.get("al_2020"))
                    + (" · registra bosque" if f.get("registra_bosque_2020") else ""),
                    medidas(f.get("despues_2020"))
                    + (" · registra cambios" if f.get("registra_cambio") else ""),
                ]
                for f in conv["filas"]
            ],
            [46, 18, (pdf.ancho - 64) / 2, (pdf.ancho - 64) / 2],
            tamano=6.5,
        )
        pdf.parrafo(conv["frase"], tamano=8.5)

    # Expediente legal
    exp = c["expediente"]
    pdf.seccion(
        "Expediente legal", f"Expediente {exp['estado']}. Las 7 casillas, con su documento o su exención."
    )
    filas = []
    for casilla in exp["casillas"]:
        doc = casilla.get("documento")
        exencion = casilla.get("exencion")
        if doc:
            detalle = (
                f"N.º {doc['numero']} · {doc['entidad_emisora']} · emitido {_fecha(doc['fecha_emision'])}"
                + (f" · vence {_fecha(doc['fecha_vencimiento'])}" if doc.get("fecha_vencimiento") else "")
            )
        elif exencion:
            detalle = f"No aplica: {exencion['motivo']}"
        else:
            detalle = ""
        filas.append(
            [
                casilla["nombre"],
                ESTADO_CASILLA.get(casilla["estado"], casilla["estado"]),
                NIVEL.get(casilla.get("nivel") or "", "—"),
                detalle,
            ]
        )
    pdf.tabla(
        ["Casilla", "Estado", "Nivel", "Documento o exención"], filas, [52, 18, 26, pdf.ancho - 96], tamano=7
    )

    # Tanda
    t = c["tanda"]
    pdf.seccion("Tanda")
    pdf.dato("Código", t["codigo"], mono=True)
    pdf.dato("Lugar", f"{t['lugar']['nombre']} ({t['lugar']['distrito']}, {t['lugar']['provincia']})")
    pdf.dato("Recepción", _fecha(t["recibida_en"], hora=True))
    pdf.dato("Producto", "Cacao en baba" if t["estado_producto"] == "baba" else "Cacao seco")
    pdf.dato("Peso en balanza", _kg(t["peso_kg"]))
    pdf.dato("Peso seco equivalente (estimado)", _kg(t["peso_seco_equivalente_kg"]))
    pdf.dato("Sacos", t.get("numero_sacos"))
    if t.get("humedad_pct"):
        pdf.dato("Humedad", f"{t['humedad_pct']} %")
    pdf.dato("Variedad", t["variedad"])
    pdf.dato("Tipo de semilla", t.get("tipo_semilla"))
    pdf.dato("Cosecha", f"Del {_fecha(t['cosecha_desde'])} al {_fecha(t['cosecha_hasta'])}")
    g = t["guia_remision"]
    pdf.dato("Guía de remisión", g["numero"], nivel=NIVEL[g["nivel"]], mono=True)
    pdf.dato("Emisión de la guía", _fecha(g["fecha_emision"]))
    pdf.dato("RUC del emisor", g["ruc_emisor"], mono=True)
    pdf.dato("Peso declarado en la guía", _kg(g.get("peso_kg")))
    pdf.dato("Huella del archivo de la guía", g.get("documento_sha256"), mono=True)

    # Alertas y nota
    al = c["alertas"]
    pdf.seccion("Alertas y nota", "Las alertas no impiden validar: obligan a dejar una nota.")
    if al["tanda"]:
        for codigo in al["tanda"]:
            pdf.parrafo(f"Tanda: {ALERTAS.get(codigo, codigo)}.", tamano=8.5)
    else:
        pdf.parrafo("La tanda no tenía alertas al validarse.", tamano=8.5)
    for codigo in al["parcela"]:
        pdf.parrafo(f"Parcela: {ALERTAS.get(codigo, codigo)}.", tamano=8.5)
    pdf.dato("Nota de validación", al.get("nota"))

    # No verificado
    pdf.seccion("No verificado", "Lo que el sistema no comprobó.")
    for linea in c["no_verificado"]:
        pdf.parrafo(f"• {linea}", tamano=8.5)

    return pdf

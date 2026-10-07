"""PDF del DOP (Parte 5): se genera una sola vez, al emitir, a partir del contenido sellado.

Encabezado con el código, la fecha, la huella y el código QR; una sección por cada bloque del contenido,
en el mismo orden; la parcela con un croquis dibujado desde su geometría, sin mapa de fondo; y al pie de
cada página, el código y el número de página.
"""

import io
from datetime import datetime
from typing import Any

from app import ubigeo
from app.fechas import LIMA
from app.pdf.base import AMBAR, TEXTO_DEMO, TINTA, TINTA_3, Documento

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
    "revision_atendida": "Revisión de imágenes atendida",
    "expediente_completo": "Expediente legal completo",
    "productor_listo": "Productor con DNI y consentimiento",
}
OBSERVACION_2020 = {
    "bosque": "bosque",
    "cultivo_o_uso_agricola": "cultivo o uso agrícola",
    "mixto": "mixto",
    "no_se_distingue": "no se distingue",
}
OBSERVACION_CAMBIO = {
    "sin_cambio_visible": "sin cambio visible",
    "cambio_visible": "cambio visible",
    "no_se_distingue": "no se distingue",
}
PAPEL_IMAGEN = {"anterior_al_corte": "Anterior al corte", "reciente": "Reciente"}
ESTADO_CASILLA = {
    "vigente": "Vigente",
    "por_vencer": "Por vencer",
    "vencido": "Vencido",
    "no_aplica": "No aplica",
    "faltante": "Falta",
    "no_requerida": "No requerida",
}
ALERTAS = {
    "volumen_acumulado_excede_tope": "El volumen de la parcela en 365 días supera el tope por hectárea",
    "dias_cosecha_entrega_altos": "Pasaron más días de los configurados entre la cosecha y la entrega",
    # Adenda 3 de la Parte 5; las dos que siguen quedan para los DOP emitidos antes.
    "peso_difiere_del_documento": (
        "El peso del documento de entrega difiere del peso en balanza más que la tolerancia"
    ),
    "documento_usado_por_otro_productor": (
        "El mismo documento de entrega aparece en una tanda de otro productor"
    ),
    "liquidacion_con_productor_con_ruc": "Liquidación de compra a un productor que tiene RUC",
    "peso_difiere_de_guia": "El peso de la guía difiere del peso en balanza más que la tolerancia",
    "guia_usada_por_otro_productor": "La misma guía aparece en una tanda de otro productor",
    "parcela_con_alertas": "La parcela está habilitada pero tiene alertas vigentes",
    "area_discrepante": "El área declarada difiere más de 20 % de la calculada",
    "diez_hectareas_o_mas": "Parcela de 10 ha o más",
    "superposicion": "Se superpone con otra parcela",
    "sin_sustento_midagri": "Falta el sustento del estado en MIDAGRI",
    "sin_analisis_vigente": "Falta un análisis de cobertura vigente",
    "analisis_requiere_revision": "Una fuente o un conjunto de datos pide revisar imágenes de la parcela",
    "analisis_con_error": "El último análisis de una fuente falló",
    "expediente_incompleto": "El expediente legal está incompleto",
    "documento_por_vencer": "Un documento legal vence pronto",
    "documento_vencido": "Un documento legal está vencido",
    "tenencia_solo_posesion": "La tenencia se apoya solo en una constancia de posesión",
    "superposicion_con_excluida": "Se superpone con una parcela excluida",
}


def _marca_cambio(fila: dict) -> str:
    """Desde la versión 4, pérdida de bosque y alteración de la vegetación por separado; antes, "cambios"."""
    if "registra_perdida" not in fila:
        return " · registra cambios" if fila.get("registra_cambio") else ""
    marcas = [" · registra pérdida de bosque" if fila.get("registra_perdida") else ""]
    marcas.append(" · registra alteración de la vegetación" if fila.get("registra_alteracion") else "")
    return "".join(marcas)


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


def generar(
    contenido: dict[str, Any], huella: str, url: str, imagenes: dict[str, bytes] | None = None
) -> bytes:
    return bytes(documento(contenido, huella, url, imagenes).output())


def _imagenes(pdf: Documento, bloque: dict[str, Any], png: dict[str, bytes]) -> None:
    """Adenda 2 (12): las dos imágenes de Sentinel-2 en color natural con el lindero, su fecha de captura,
    y la revisión de imágenes. Wayback se lista solo con sus datos."""
    papeles = [p for p in ("anterior_al_corte", "reciente") if bloque.get(p)]
    ancho = (pdf.ancho - 6) / 2
    alto_max = ancho * 1.15
    # El título no queda solo al pie de una página: va con las imágenes.
    if papeles and pdf.get_y() + 18 + alto_max + 22 > pdf.page_break_trigger:
        pdf.add_page()
    pdf.ln(1)
    pdf.set_font("Jakarta", "B", 9.5)
    pdf.set_text_color(*TINTA)
    pdf.cell(0, 6, "Imágenes de la parcela", new_x="LMARGIN", new_y="NEXT")
    pdf.parrafo(
        "La parcela tuvo la alerta de análisis: el administrador revisó imágenes satelitales anteriores y "
        "posteriores al 31/12/2020. Resolución real de Sentinel-2: 10 m.",
        tamano=8,
        color=TINTA_3,
    )
    if papeles:
        y = pdf.get_y()
        for i, papel in enumerate(papeles):
            dato = bloque[papel]
            x = pdf.l_margin + i * (ancho + 6)
            alto = alto_max
            if png.get(papel):
                imagen = pdf.image(io.BytesIO(png[papel]), x=x, y=y, w=ancho)
                alto = imagen.rendered_height
            pdf.set_xy(x, y + alto + 1)
            pdf.set_font("Jakarta", "B", 9)
            pdf.set_text_color(*TINTA)
            pdf.multi_cell(
                ancho,
                4.4,
                f"{PAPEL_IMAGEN[papel]}: {_fecha(dato['fecha_captura'])} "
                f"({dato['dias_respecto_al_corte']:+d} días)",
                new_x="RIGHT",
                new_y="NEXT",
            )
            pdf.set_x(x)
            pdf.set_font("Jakarta", "", 7.5)
            pdf.set_text_color(*TINTA_3)
            nubes = dato.get("nubes_parcela_pct")
            pdf.multi_cell(
                ancho,
                3.6,
                f"{dato.get('proveedor') or 'Sentinel-2'} · resolución {dato.get('resolucion_m') or 10:g} m"
                + (f" · nubes sobre la parcela {nubes:g} %" if nubes is not None else "")
                + f"\n{dato['atribucion']}",
                new_x="RIGHT",
                new_y="NEXT",
            )
            pdf.set_x(x)
            pdf.set_font("Mono", "", 6)
            pdf.multi_cell(ancho, 3, "SHA-256 de la imagen\n" + dato["sha256"], new_x="RIGHT", new_y="NEXT")
            fin = pdf.get_y()
            if i == 0:
                fin_primera = fin
        pdf.set_xy(pdf.l_margin, max(fin, fin_primera) + 2)
    revision = bloque.get("revision")
    if revision:
        pdf.dato("Revisó las imágenes", revision.get("revisada_por"))
        pdf.dato("Fecha de la revisión", _fecha(revision.get("revisada_en"), hora=True))
        pdf.dato("En la imagen anterior al corte", OBSERVACION_2020.get(revision["observacion_2020"]))
        pdf.dato("Cambio después del corte", OBSERVACION_CAMBIO.get(revision["observacion_cambio"]))
        pdf.dato("Lo que observó", revision.get("descripcion"))
    else:
        pdf.dato("Revisión de imágenes", "Sin revisión vigente al emitirse")
    altas = bloque.get("alta_resolucion") or []
    if altas:
        pdf.dato(
            "Alta resolución (Esri Wayback)",
            "; ".join(
                f"{_fecha(a['fecha_captura'])}, {a.get('proveedor') or 'sin proveedor'}"
                + (f", {a['resolucion_m']:g} m" if a.get("resolucion_m") is not None else "")
                for a in altas
            )
            + f". Se listan solo sus datos. {bloque.get('atribucion_alta_resolucion') or ''}".rstrip(),
        )


def documento(
    contenido: dict[str, Any], huella: str, url: str, imagenes: dict[str, bytes] | None = None
) -> Documento:
    c = contenido
    pdf = Documento(c["identificacion"]["codigo"], marca_agua=TEXTO_DEMO if c.get("es_demo") else None)
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
            *(ubigeo.mostrar(ubicacion[c]) for c in ("distrito", "provincia", "departamento")),
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
                    medidas(f.get("despues_2020")) + _marca_cambio(f),
                ]
                for f in conv["filas"]
            ],
            [46, 18, (pdf.ancho - 64) / 2, (pdf.ancho - 64) / 2],
            tamano=6.5,
        )
        pdf.parrafo(conv["frase"], tamano=8.5)
    if c.get("imagenes"):
        _imagenes(pdf, c["imagenes"], imagenes or {})

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
        elif casilla.get("cubierta_por_nombre"):
            detalle = f"La tenencia está cubierta por {casilla['cubierta_por_nombre']}"
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
    lugar_tanda = t["lugar"]
    pdf.dato(
        "Lugar",
        f"{lugar_tanda['nombre']} ({ubigeo.mostrar(lugar_tanda['distrito'])}, "
        f"{ubigeo.mostrar(lugar_tanda['provincia'])})",
    )
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
    if "documento_entrega" in t:
        # Adenda 3: con su nombre completo, por ejemplo "Liquidación de compra, L001-123".
        d = t["documento_entrega"]
        pdf.dato(
            "Documento de entrega",
            f"{d['nombre_tipo']}, {d['numero']}" if d.get("numero") else d["nombre_tipo"],
            nivel=NIVEL[d["nivel"]],
        )
        pdf.dato("Emisión del documento", _fecha(d["fecha_emision"]))
        pdf.dato("RUC del emisor", d["ruc_emisor"], mono=True)
        pdf.dato("Peso declarado en el documento", _kg(d.get("peso_kg")))
        pdf.dato("Huella del archivo del documento", d.get("documento_sha256"), mono=True)
    else:
        # DOP emitidos antes de la adenda 3: su contenido sellado guarda la guía de remisión.
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

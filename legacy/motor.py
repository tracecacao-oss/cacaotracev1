"""Reglas de negocio de CacaoTrace. Funciones puras: no tocan la base de datos.

Cadena documental:
    DOP (parcela)  ->  DPP (lote)  ->  DEX (embarque)
La DDS la presenta el operador de la UE en TRACES NT; queda fuera de este sistema.
"""
import hashlib
import json
import math

NIVELES = {"declarado": 1, "documentado": 2, "verificado": 3}
NIVEL_TXT = {
    "declarado": "Declarado",
    "documentado": "Documentado",
    "verificado": "Verificado en fuente",
}
ETAPAS = [
    ("fermentacion", "Fermentación"),
    ("secado", "Secado"),
    ("seleccion", "Selección"),
    ("ensacado", "Ensacado"),
]
ETAPAS_OBLIGATORIAS = ("fermentacion", "secado")
FUENTES_GEO = {
    "midagri": "MIDAGRI AgroDigital",
    "habilitacion": "Levantamiento de la cooperativa (ruta de habilitación)",
    "gps": "GPS en campo",
}
# Catálogo de trabajo de documentos por ámbito. "req" marca los que exige una compuerta.
CATALOGO = {
    "parcela": [
        {"tipo": "tenencia", "nombre": "Título de propiedad o constancia de posesión", "req": True},
        {"tipo": "dj_deforestacion", "nombre": "Declaración jurada de no deforestación"},
        {"tipo": "padron", "nombre": "Ficha de socio o padrón de productores"},
    ],
    "cooperativa": [
        {"tipo": "ruc", "nombre": "Ficha RUC"},
        {"tipo": "partida", "nombre": "Partida registral y vigencia de poder"},
        {"tipo": "senasa", "nombre": "Registro sanitario SENASA"},
        {"tipo": "certificacion", "nombre": "Certificación (orgánica, comercio justo u otra)"},
    ],
    "orden": [
        {"tipo": "dam", "nombre": "DAM, Declaración Aduanera de Mercancías", "req": True},
        {"tipo": "contrato", "nombre": "Contrato de compraventa"},
        {"tipo": "factura", "nombre": "Factura comercial"},
        {"tipo": "fitosanitario", "nombre": "Certificado fitosanitario (SENASA)"},
        {"tipo": "origen", "nombre": "Certificado de origen"},
        {"tipo": "bl", "nombre": "Conocimiento de embarque"},
    ],
}
# Solo la DAM se puede contrastar contra una fuente pública (consulta de SUNAT).
VERIFICABLES_EN_FUENTE = {"dam"}
LIMITE_PUNTO_HA = 4.0


# ---------- Geometría ----------

def validar_geometria(g):
    """Acepta Point o Polygon en GeoJSON (lng, lat). Devuelve la geometría normalizada."""
    if isinstance(g, str):
        g = json.loads(g)
    if not isinstance(g, dict):
        raise ValueError("La geolocalización no tiene un formato válido")
    if g.get("type") == "Feature":
        g = g.get("geometry") or {}
    if g.get("type") == "FeatureCollection":
        g = ((g.get("features") or [{}])[0]).get("geometry") or {}
    if g.get("type") == "MultiPolygon":
        g = {"type": "Polygon", "coordinates": (g.get("coordinates") or [[]])[0]}

    def par(c):
        lng, lat = float(c[0]), float(c[1])
        if not (-180 <= lng <= 180 and -90 <= lat <= 90):
            raise ValueError("Coordenadas fuera de rango (se espera longitud, latitud)")
        return [round(lng, 6), round(lat, 6)]

    try:
        if g.get("type") == "Point":
            return {"type": "Point", "coordinates": par(g["coordinates"])}
        if g.get("type") == "Polygon":
            anillo = [par(c) for c in g["coordinates"][0]]
            if anillo[0] != anillo[-1]:
                anillo.append(anillo[0])
            if len(anillo) < 4:
                raise ValueError("Un polígono necesita al menos 3 vértices")
            return {"type": "Polygon", "coordinates": [anillo]}
    except (KeyError, IndexError, TypeError):
        raise ValueError("La geolocalización no tiene un formato válido")
    raise ValueError("Solo se admite un punto o un polígono")


def area_ha(g):
    """Área de un polígono pequeño en hectáreas (proyección local)."""
    if not g or g.get("type") != "Polygon":
        return None
    r = g["coordinates"][0]
    lat0 = sum(c[1] for c in r) / len(r)
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 110540.0
    s = 0.0
    for i in range(len(r) - 1):
        x1, y1 = r[i][0] * kx, r[i][1] * ky
        x2, y2 = r[i + 1][0] * kx, r[i + 1][1] * ky
        s += x1 * y2 - x2 * y1
    return round(abs(s) / 2 / 10000, 2)


def poligono_demo(lat, lng, ha, giro):
    """Hexágono irregular de ~ha hectáreas alrededor de un punto. Solo para datos de ejemplo."""
    radio = math.sqrt(ha * 10000 / 2.6)
    pts = []
    for i in range(6):
        ang = math.radians(60 * i + giro)
        k = 0.82 + 0.36 * (((i * 37 + giro) % 10) / 10)
        dx, dy = radio * k * math.cos(ang), radio * k * math.sin(ang)
        pts.append([round(lng + dx / (111320 * math.cos(math.radians(lat))), 6),
                    round(lat + dy / 110540, 6)])
    pts.append(pts[0])
    return {"type": "Polygon", "coordinates": [pts]}


# ---------- DOP: estado de la parcela ----------

def estado_dop(p, docs, hoy):
    g = p.get("geometria")
    area = p.get("area_ha") or 0
    motivos = []

    geo_ok = bool(g) and area > 0
    if not g:
        motivos.append("Falta la geolocalización de la parcela")
    elif area <= 0:
        motivos.append("Falta el área de la parcela")
    elif g["type"] == "Point" and area > LIMITE_PUNTO_HA:
        geo_ok = False
        motivos.append("Las parcelas de más de 4 ha necesitan polígono, no un punto")

    vigente = not p.get("vigente_hasta") or p["vigente_hasta"] >= hoy
    if not vigente:
        motivos.append("El DOP venció el {}: hay que revalidarlo para la campaña actual".format(p["vigente_hasta"]))

    sat, rev = p.get("sat_estado") or "pendiente", p.get("rev_resultado")
    sat_ok, sat_bloquea = False, False
    if sat == "verde":
        sat_ok = True
    elif sat == "ambar" and rev == "conforme":
        sat_ok = True
    elif sat == "ambar" and rev == "no_conforme":
        sat_bloquea = True
        motivos.append("La revisión humana confirmó pérdida de bosque después de 2020")
    elif sat == "ambar":
        motivos.append("Resultado satelital no concluyente: falta la revisión humana")
    elif sat == "rojo":
        sat_bloquea = True
        motivos.append("Alerta satelital de deforestación posterior al 31/12/2020")
    else:
        motivos.append("Falta la verificación satelital")

    mejor = max([NIVELES.get(d["nivel"], 0) for d in docs if d["tipo"] == "tenencia"] or [0])
    legal_ok = mejor >= NIVELES["documentado"]
    if mejor == 0:
        motivos.append("Falta el documento de tenencia de la tierra")
    elif not legal_ok:
        motivos.append("La tenencia solo está declarada: falta el documento que la respalde")

    if sat_bloquea:
        estado = "bloqueado"
    elif not vigente:
        estado = "vencido"
    elif not geo_ok:
        estado = "incompleto"
    elif not (sat_ok and legal_ok):
        estado = "observado"
    else:
        estado = "vigente"
    return {"estado": estado, "motivos": motivos, "geo_ok": geo_ok, "vigente": vigente,
            "sat_ok": sat_ok, "sat_bloquea": sat_bloquea, "legal_ok": legal_ok}


# ---------- DPP: balance de masa del lote ----------

def equivalente_seco(e, factor):
    return e["kg"] * factor if e["tipo"] == "baba" else e["kg"]


def balance(lote, entregas, factor, tol):
    baba = sum(e["kg"] for e in entregas if e["tipo"] == "baba")
    seco_in = sum(e["kg"] for e in entregas if e["tipo"] != "baba")
    esperado = baba * factor + seco_in
    b = {
        "kg_baba": round(baba, 1), "kg_seco_recibido": round(seco_in, 1),
        "esperado": round(esperado, 1), "maximo": round(esperado * (1 + tol), 1),
        "sin_gre": [e["id"] for e in entregas if not (e.get("gre") or "").strip()],
        "estado": "abierto", "desvio": None, "rendimiento": None,
    }
    if lote["estado"] == "cerrado" and lote.get("kg_seco"):
        if esperado <= 0:
            b["estado"] = "sin_origen"
        else:
            b["desvio"] = round(lote["kg_seco"] / esperado - 1, 4)
            if baba > 0:
                b["rendimiento"] = round((lote["kg_seco"] - seco_in) / baba, 4)
            b["estado"] = "excedente" if b["desvio"] > tol else ("merma_alta" if b["desvio"] < -0.30 else "ok")
    return b


# ---------- Genealogía: de qué parcelas sale cada kilo de la orden ----------

def genealogia(orden, asignaciones, lotes, entregas_por_lote, factor):
    por_parcela, enlaces, por_lote = {}, [], []
    total = 0.0
    for a in asignaciones:
        lote = lotes.get(a["lote_id"])
        if not lote:
            continue
        total += a["kg"]
        por_lote.append({"lote_id": lote["id"], "asignacion_id": a["id"], "kg": round(a["kg"], 1)})
        ents = entregas_por_lote.get(lote["id"], [])
        base = sum(equivalente_seco(e, factor) for e in ents)
        aporte = {}
        for e in ents:
            aporte[e["parcela_id"]] = aporte.get(e["parcela_id"], 0) + equivalente_seco(e, factor)
        for pid, eq in aporte.items():
            kg = a["kg"] * eq / base if base else 0
            por_parcela[pid] = por_parcela.get(pid, 0) + kg
            enlaces.append({"parcela_id": pid, "lote_id": lote["id"], "kg": round(kg, 1)})
    parcelas = [{"parcela_id": pid, "kg": round(kg, 1), "pct": round(kg / total * 100, 1) if total else 0}
                for pid, kg in sorted(por_parcela.items(), key=lambda x: -x[1])]
    return {"asignado": round(total, 1),
            "cobertura": round(total / orden["kg"], 4) if orden["kg"] else 0,
            "parcelas": parcelas, "lotes": por_lote, "enlaces": enlaces}


# ---------- Las cinco compuertas antes del DEX ----------

def compuertas(orden, gen, parcelas, productores, lotes, docs_orden):
    ps = [parcelas[x["parcela_id"]] for x in gen["parcelas"] if x["parcela_id"] in parcelas]
    ls = [lotes[x["lote_id"]] for x in gen["lotes"] if x["lote_id"] in lotes]
    sin_lotes = [{"texto": "La orden todavía no tiene lotes asignados, así que no hay parcelas que evaluar"}]

    def nombre_p(p):
        prod = productores.get(p["productor_id"], {})
        return "{} ({}, {})".format(p["codigo"], p["nombre"], prod.get("nombre", "sin productor"))

    def puerta(n, nombre, que, motivos, fuentes):
        return {"n": n, "nombre": nombre, "que": que, "estado": "cerrada" if motivos else "abierta",
                "motivos": motivos, "fuentes": fuentes}

    m1, m2, m3 = [], [], []
    for p in ps:
        d = p["dop"]
        if not d["geo_ok"]:
            m1.append({"texto": "{}: geolocalización incompleta".format(nombre_p(p)), "parcela_id": p["id"]})
        if not d["vigente"]:
            m1.append({"texto": "{}: DOP vencido el {}".format(nombre_p(p), p["vigente_hasta"]), "parcela_id": p["id"]})
        if not d["sat_ok"]:
            causa = {"rojo": "alerta de deforestación posterior a 2020",
                     "ambar": "resultado no concluyente sin revisión humana",
                     "pendiente": "sin verificación satelital"}.get(p["sat_estado"], "sin verificación satelital")
            if p["sat_estado"] == "ambar" and p.get("rev_resultado") == "no_conforme":
                causa = "la revisión humana confirmó pérdida de bosque"
            m2.append({"texto": "{}: {}".format(nombre_p(p), causa), "parcela_id": p["id"]})
        if not d["legal_ok"]:
            m3.append({"texto": "{}: tenencia sin documento de respaldo".format(nombre_p(p)), "parcela_id": p["id"]})

    m4 = []
    if gen["asignado"] + 0.05 < orden["kg"]:
        m4.append({"texto": "Los lotes asignados cubren {:,.0f} de {:,.0f} kg".format(gen["asignado"], orden["kg"])})
    for l in ls:
        b = l["balance"]
        if l["estado"] != "cerrado":
            m4.append({"texto": "{}: el lote no está cerrado ni tiene DPP".format(l["codigo"]), "lote_id": l["id"]})
        if b["sin_gre"]:
            m4.append({"texto": "{}: {} entrega(s) sin guía de remisión (GRE)".format(l["codigo"], len(b["sin_gre"])),
                       "lote_id": l["id"]})
        if b["estado"] == "excedente":
            m4.append({"texto": "{}: salieron {:,.0f} kg secos y las entregas solo explican {:,.0f} kg".format(
                l["codigo"], l["kg_seco"], b["maximo"]), "lote_id": l["id"]})
        if b["estado"] == "sin_origen":
            m4.append({"texto": "{}: el lote no tiene entregas registradas".format(l["codigo"]), "lote_id": l["id"]})

    m5 = []
    dam = [d for d in docs_orden if d["tipo"] == "dam"]
    if not dam:
        m5.append({"texto": "Falta registrar la DAM del embarque"})
    if not (orden.get("comprador") and orden.get("pais")):
        m5.append({"texto": "Faltan los datos del importador o el país de destino"})

    fuentes_sat = sorted({p.get("sat_fuente") for p in ps if p.get("sat_fuente")})
    return [
        puerta(1, "Origen", "Cada parcela tiene geolocalización y DOP vigente",
               (sin_lotes if not ps else m1), ["DOP de cada parcela", "MIDAGRI AgroDigital o levantamiento propio"]),
        puerta(2, "Deforestación", "Ninguna parcela perdió bosque después del 31/12/2020",
               (sin_lotes if not ps else m2), fuentes_sat or ["Verificación satelital"]),
        puerta(3, "Tenencia", "Cada parcela tiene un documento de tenencia que la respalda",
               (sin_lotes if not ps else m3), ["Título o constancia de posesión adjunta al DOP"]),
        puerta(4, "Custodia", "Los kilos salen de lotes cerrados, con guías y balance de masa coherente",
               m4, ["Guías de remisión (GRE, SUNAT)", "DPP de cada lote"]),
        puerta(5, "Embarque", "La orden tiene importador, destino y DAM",
               m5, ["DAM (SUNAT)", "Datos de la orden de compra"]),
    ]


# ---------- Cálculo completo sobre el estado de una cooperativa ----------

def calcular(S, hoy):
    coop = S["cooperativa"]
    factor = coop.get("factor_baba") or 0.42
    tol = coop.get("tolerancia") if coop.get("tolerancia") is not None else 0.10

    docs = {}
    for d in S["documentos"]:
        docs.setdefault((d["ambito"], d["ref_id"]), []).append(d)
    productores = {p["id"]: p for p in S["productores"]}

    for p in S["parcelas"]:
        if isinstance(p.get("geometria"), str):
            p["geometria"] = json.loads(p["geometria"]) if p["geometria"] else None
        p["dop"] = estado_dop(p, docs.get(("parcela", p["id"]), []), hoy)
    parcelas = {p["id"]: p for p in S["parcelas"]}

    ent_lote, asig_lote, asig_orden = {}, {}, {}
    for e in S["entregas"]:
        ent_lote.setdefault(e["lote_id"], []).append(e)
    for a in S["asignaciones"]:
        asig_lote.setdefault(a["lote_id"], []).append(a)
        asig_orden.setdefault(a["orden_id"], []).append(a)

    for l in S["lotes"]:
        l["balance"] = balance(l, ent_lote.get(l["id"], []), factor, tol)
        l["asignado"] = round(sum(a["kg"] for a in asig_lote.get(l["id"], [])), 1)
        l["disponible"] = round(max(0, (l.get("kg_seco") or 0) - l["asignado"]), 1) if l["estado"] == "cerrado" else 0
    lotes = {l["id"]: l for l in S["lotes"]}

    for o in S["ordenes"]:
        o["genealogia"] = genealogia(o, asig_orden.get(o["id"], []), lotes, ent_lote, factor)
        o["compuertas"] = compuertas(o, o["genealogia"], parcelas, productores, lotes,
                                     docs.get(("orden", o["id"]), []))
        o["lista"] = all(c["estado"] == "abierta" for c in o["compuertas"])
    return S


# ---------- DEX ----------

def paquete_dex(codigo, emitido, usuario, orden, S):
    """Arma el paquete del embarque con el peso probatorio de cada dato."""
    parcelas = {p["id"]: p for p in S["parcelas"]}
    productores = {p["id"]: p for p in S["productores"]}
    lotes = {l["id"]: l for l in S["lotes"]}
    etapas = {}
    for e in S["etapas"]:
        etapas.setdefault(e["lote_id"], []).append(e)
    docs = {}
    for d in S["documentos"]:
        docs.setdefault((d["ambito"], d["ref_id"]), []).append(d)

    def ficha_doc(d):
        cat = {c["tipo"]: c["nombre"] for c in CATALOGO.get(d["ambito"], [])}
        return {"documento": cat.get(d["tipo"], d["tipo"]), "numero": d.get("numero"),
                "fecha": d.get("fecha"), "nivel": NIVEL_TXT.get(d["nivel"], d["nivel"])}

    gen = orden["genealogia"]
    coop = S["cooperativa"]
    paquete = {
        "dex": codigo,
        "emitido": emitido,
        "emitido_por": usuario,
        "cooperativa": {"nombre": coop["nombre"], "ruc": coop.get("ruc"), "region": coop.get("region"),
                        "documentos": [ficha_doc(d) for d in docs.get(("cooperativa", coop["id"]), [])]},
        "orden": {"codigo": orden["codigo"], "importador": orden["comprador"],
                  "identificador_importador": orden.get("comprador_id"), "pais_destino": orden.get("pais"),
                  "kg": orden["kg"], "fecha": orden.get("fecha"), "contrato": orden.get("contrato"),
                  "documentos": [ficha_doc(d) for d in docs.get(("orden", orden["id"]), [])]},
        "lotes": [],
        "parcelas": [],
        "compuertas": [{"n": c["n"], "nombre": c["nombre"], "criterio": c["que"], "estado": c["estado"],
                        "fuentes": c["fuentes"]} for c in orden["compuertas"]],
        "alcance": ("Este DEX reúne la evidencia de origen, proceso y custodia que la cooperativa pone a "
                    "disposición del importador. No es la declaración de diligencia debida: esa la presenta "
                    "el operador de la UE en TRACES NT."),
    }
    for x in gen["lotes"]:
        l = lotes[x["lote_id"]]
        b = l["balance"]
        paquete["lotes"].append({
            "codigo": l["codigo"], "dpp": l.get("dpp_codigo"), "dpp_fecha": l.get("dpp_fecha"),
            "kg_en_esta_orden": x["kg"], "kg_seco_del_lote": l.get("kg_seco"), "humedad_pct": l.get("humedad"),
            "balance_de_masa": {"kg_baba": b["kg_baba"], "kg_seco_recibido": b["kg_seco_recibido"],
                                "kg_seco_esperado": b["esperado"], "rendimiento": b["rendimiento"],
                                "estado": b["estado"]},
            "etapas": [{"etapa": dict(ETAPAS).get(e["tipo"], e["tipo"]), "inicio": e.get("fecha_inicio"),
                        "fin": e.get("fecha_fin"), "kg_entrada": e.get("kg_entrada"),
                        "kg_salida": e.get("kg_salida"), "responsable": e.get("responsable")}
                       for e in sorted(etapas.get(l["id"], []), key=lambda e: [t for t, _ in ETAPAS].index(e["tipo"]))],
            "guias_de_remision": sorted({e["gre"] for e in S["entregas"]
                                         if e["lote_id"] == l["id"] and (e.get("gre") or "").strip()}),
        })
    for x in gen["parcelas"]:
        p = parcelas[x["parcela_id"]]
        prod = productores.get(p["productor_id"], {})
        paquete["parcelas"].append({
            "dop": p["codigo"], "parcela": p["nombre"], "productor": prod.get("nombre"),
            "documento_productor": prod.get("dni"), "distrito": prod.get("distrito"),
            "provincia": prod.get("provincia"), "area_ha": p.get("area_ha"),
            "fuente_geolocalizacion": FUENTES_GEO.get(p.get("fuente_geo"), p.get("fuente_geo")),
            "geometria": p["geometria"], "kg_en_esta_orden": x["kg"], "porcentaje": x["pct"],
            "verificacion_satelital": {"resultado": p["sat_estado"], "detalle": p.get("sat_detalle"),
                                       "fuente": p.get("sat_fuente"), "fecha": p.get("sat_fecha"),
                                       "revision_humana": ({"resultado": p["rev_resultado"], "nota": p.get("rev_nota"),
                                                            "revisor": p.get("rev_usuario"), "fecha": p.get("rev_fecha")}
                                                           if p.get("rev_resultado") else None)},
            "documentos": [ficha_doc(d) for d in docs.get(("parcela", p["id"]), [])],
        })
    return paquete


def huella(paquete):
    crudo = json.dumps(paquete, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


def geojson_parcelas(paquete):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": p["geometria"],
         "properties": {"ProducerName": p["productor"], "ProducerCountry": "PE",
                        "ProductionPlace": p["dop"], "Area": p["area_ha"],
                        "dex": paquete["dex"], "kg": p["kg_en_esta_orden"]}}
        for p in paquete["parcelas"]]}

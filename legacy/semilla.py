"""Datos de ejemplo. Todo es ficticio: nombres, DNI, parcelas, guías y documentos."""
import json

import motor

CAMPANIA_FIN = "2027-03-31"

PRODUCTORES = [
    # nombre, dni, comunidad, distrito, provincia
    ("Wilder Tapullima Sangama", "40000001", "Tununtunumba", "Chazuta", "San Martín"),
    ("Rosa Elvira Pinedo Shupingahua", "40000002", "Aguano Muyuna", "Chazuta", "San Martín"),
    ("Segundo Fasabi Amasifuén", "40000003", "Pucallpillo", "Juanjuí", "Mariscal Cáceres"),
    ("Nelly Isuiza Cachique", "40000004", "Huayabamba", "Pachiza", "Mariscal Cáceres"),
    ("Edinson Saboya Tuanama", "40000005", "Shamboyacu", "Lamas", "Lamas"),
    ("Marleni Chujandama Guerra", "40000006", "Pasarraya", "Saposoa", "Huallaga"),
]

# productor, nombre, lat, lng, ha, giro, fuente, vigente_hasta, satélite, tenencia (tipo doc, nivel) o None
PARCELAS = [
    (0, "La Banda", -6.5712, -76.1405, 3.2, 10, "midagri", CAMPANIA_FIN,
     ("verde", "Sin pérdida de cobertura arbórea desde 2021."), ("Título de propiedad", "documentado")),
    (1, "El Mirador", -6.5894, -76.1287, 2.4, 40, "midagri", CAMPANIA_FIN,
     ("verde", "Sin pérdida de cobertura arbórea desde 2021."), ("Constancia de posesión", "documentado")),
    (2, "Santa Fe", -7.1832, -76.7411, 5.1, 25, "habilitacion", CAMPANIA_FIN,
     ("verde", "Sin pérdida de cobertura arbórea desde 2021."), ("Título de propiedad", "documentado")),
    (3, "Bajo Huayabamba", -7.3015, -76.7742, 4.3, 5, "habilitacion", CAMPANIA_FIN,
     ("ambar", "Cambio de cobertura no concluyente en el borde norte, compatible con manejo de sombra."),
     ("Constancia de posesión", "documentado")),
    (4, "Shamboyacu Alto", -6.4288, -76.5231, 2.9, 55, "gps", CAMPANIA_FIN,
     ("ambar", "Cambio de cobertura no concluyente, compatible con manejo de sombra."),
     ("Constancia de posesión", "documentado")),
    (5, "Pasarraya", -6.9391, -76.7803, 6.4, 15, "habilitacion", CAMPANIA_FIN,
     ("rojo", "Pérdida de 1.1 ha de cobertura arbórea en 2022 dentro del polígono."),
     ("Constancia de posesión", "documentado")),
    (0, "Chacra Vieja", -6.5648, -76.1522, 1.5, 0, "gps", CAMPANIA_FIN,
     ("verde", "Sin pérdida de cobertura arbórea desde 2021."), ("Constancia de posesión", "declarado")),
    (2, "Pucallpillo", -7.1955, -76.7268, 3.6, 70, "midagri", CAMPANIA_FIN, None,
     ("Título de propiedad", "documentado")),
]
FUENTE_SAT = "Simulación de CacaoTrace (dato de ejemplo)"


def cargar(db, coop_id, usuario, ahora):
    """Inserta el juego de datos de ejemplo en una cooperativa vacía."""
    prod = [db.insertar("productores", dict(coop_id=coop_id, nombre=n, dni=d, comunidad=c, distrito=di,
                                           provincia=p, telefono="", creado=ahora))
            for n, d, c, di, p in PRODUCTORES]

    parc = []
    for i, (pi, nombre, lat, lng, ha, giro, fuente, vig, sat, ten) in enumerate(PARCELAS):
        if nombre == "Chacra Vieja":  # caso de parcela pequeña registrada con un solo punto
            geom, area = {"type": "Point", "coordinates": [lng, lat]}, ha
        else:
            geom = motor.poligono_demo(lat, lng, ha, giro)
            area = motor.area_ha(geom)
        fila = dict(coop_id=coop_id, productor_id=prod[pi], codigo="DOP-2026-{:04d}".format(i + 1), nombre=nombre,
                    area_ha=area, geometria=json.dumps(geom), fuente_geo=fuente, vigente_hasta=vig, creado=ahora)
        if sat:
            fila.update(sat_estado=sat[0], sat_detalle=sat[1], sat_fuente=FUENTE_SAT, sat_fecha="2026-08-04")
        if nombre == "Bajo Huayabamba":  # ámbar ya resuelto por una persona
            fila.update(rev_resultado="conforme", rev_usuario=usuario, rev_fecha="2026-08-11",
                        rev_nota="Visita de campo: raleo de guabas de sombra, sin apertura de bosque. Fotos en el expediente.")
        pid = db.insertar("parcelas", fila)
        parc.append(pid)
        db.insertar("documentos", dict(coop_id=coop_id, ambito="parcela", ref_id=pid, tipo="tenencia",
                                       numero="{} (ejemplo)".format(ten[0]), nivel=ten[1], fecha="2026-07-15",
                                       nota="", creado=ahora))

    def lote(codigo, nombre, inicio, **mas):
        return db.insertar("lotes", dict(coop_id=coop_id, codigo=codigo, nombre=nombre, fecha_inicio=inicio,
                                         creado=ahora, **mas))

    def entrega(l, p, fecha, kg, gre, tipo="baba"):
        db.insertar("entregas", dict(coop_id=coop_id, parcela_id=parc[p], lote_id=l, fecha=fecha, tipo=tipo,
                                     kg=kg, gre=gre, creado=ahora))

    def etapa(l, tipo, ini, fin, ent, sal, resp):
        db.insertar("etapas", dict(coop_id=coop_id, lote_id=l, tipo=tipo, fecha_inicio=ini, fecha_fin=fin,
                                   kg_entrada=ent, kg_salida=sal, responsable=resp, nota=""))

    # Lote 1: limpio de punta a punta.
    l1 = lote("LOT-2026-001", "Acopio Chazuta, agosto", "2026-08-17", estado="cerrado", kg_seco=1010, humedad=7.0,
              dpp_codigo="DPP-2026-001", dpp_fecha="2026-09-02")
    entrega(l1, 0, "2026-08-17", 980, "EG07-00001201")
    entrega(l1, 1, "2026-08-17", 720, "EG07-00001202")
    entrega(l1, 3, "2026-08-18", 760, "EG07-00001207")
    etapa(l1, "fermentacion", "2026-08-18", "2026-08-24", 2460, 2090, "Planta Chazuta")
    etapa(l1, "secado", "2026-08-24", "2026-08-31", 2090, 1045, "Planta Chazuta")
    etapa(l1, "seleccion", "2026-09-01", "2026-09-01", 1045, 1012, "Planta Chazuta")
    etapa(l1, "ensacado", "2026-09-02", "2026-09-02", 1012, 1010, "Almacén central")

    # Lote 2: arrastra una parcela con alerta roja y una entrega sin guía.
    l2 = lote("LOT-2026-002", "Acopio Huallaga, agosto", "2026-08-24", estado="cerrado", kg_seco=1260, humedad=7.2,
              dpp_codigo="DPP-2026-002", dpp_fecha="2026-09-10")
    entrega(l2, 2, "2026-08-24", 1500, "EG07-00001230")
    entrega(l2, 5, "2026-08-25", 900, "EG07-00001236")
    entrega(l2, 5, "2026-08-27", 700, "")
    etapa(l2, "fermentacion", "2026-08-25", "2026-08-31", 3100, 2640, "Planta Juanjuí")
    etapa(l2, "secado", "2026-08-31", "2026-09-08", 2640, 1290, "Planta Juanjuí")
    etapa(l2, "seleccion", "2026-09-09", "2026-09-09", 1290, 1262, "Planta Juanjuí")
    etapa(l2, "ensacado", "2026-09-10", "2026-09-10", 1262, 1260, "Almacén central")

    # Lote 3: en proceso, para registrar etapas y cerrarlo en vivo.
    l3 = lote("LOT-2026-003", "Acopio Chazuta, septiembre", "2026-09-21", estado="abierto")
    entrega(l3, 0, "2026-09-21", 640, "EG07-00001288")
    entrega(l3, 2, "2026-09-22", 1100, "EG07-00001290")
    etapa(l3, "fermentacion", "2026-09-22", "2026-09-28", 1740, 1480, "Planta Chazuta")

    def orden(codigo, comprador, kg, fecha, contrato):
        return db.insertar("ordenes", dict(coop_id=coop_id, codigo=codigo, comprador=comprador,
                                           comprador_id="", pais="Países Bajos", kg=kg, fecha=fecha,
                                           contrato=contrato, creado=ahora))

    o1 = orden("OC-2026-001", "Importador de ejemplo A (Ámsterdam)", 900, "2026-09-05", "CT-EJ-001")
    o2 = orden("OC-2026-002", "Importador de ejemplo B (Róterdam)", 1200, "2026-09-14", "CT-EJ-002")
    db.insertar("asignaciones", dict(coop_id=coop_id, orden_id=o1, lote_id=l1, kg=900))
    db.insertar("asignaciones", dict(coop_id=coop_id, orden_id=o2, lote_id=l2, kg=1200))
    db.insertar("documentos", dict(coop_id=coop_id, ambito="orden", ref_id=o1, tipo="dam",
                                   numero="118-2026-40-000000 (ejemplo)", nivel="documentado", fecha="2026-09-20",
                                   nota="", creado=ahora))
    db.insertar("documentos", dict(coop_id=coop_id, ambito="orden", ref_id=o1, tipo="contrato",
                                   numero="CT-EJ-001", nivel="documentado", fecha="2026-09-05", nota="", creado=ahora))

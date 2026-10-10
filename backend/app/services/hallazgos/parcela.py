"""Reglas de la etapa 1: la parcela, con el estado de hoy (no el sellado en el DOP). Una función por regla;
agregar una regla no modifica las demás."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app import textos
from app.catalogos import capas_legales, documentos_legales, requisitos_legales
from app.models import AnalisisCobertura, Parcela
from app.services import analisis, imagenes
from app.services.hallazgos.catalogo import Hallazgo, sujeto
from app.services.hallazgos.datos import DatosLote
from app.services.parcelas import UMBRAL_DISCREPANCIA, _area_total

DIAS_PREVIA_LEJANA = 180
NOMBRE_CORTO = {"whisp": "Whisp", "gfw": "GFW", "mapbiomas": "MapBiomas Perú"}
UNIDADES = {"ha": "ha", "percent": "%"}


def _sujeto(p: Parcela) -> dict:
    return sujeto("parcela", p.id, p.codigo)


def _nuevo(d: DatosLote, codigo: str, p: Parcela, explicacion: str | None = None, **datos) -> Hallazgo:
    return Hallazgo(
        codigo, _sujeto(p), {"parcela": p.codigo, **datos}, d.peso_parcela[p.id], explicacion=explicacion
    )


def _verbo(idioma: str, n: int) -> str:
    """ "1 de 13 conjuntos de datos registra", "2 de 13 registran"."""
    return textos.obtener(idioma, "comun.registra_uno" if n == 1 else "comun.registra_varios")


def _g(valor: Any) -> str:
    return f"{valor:g}" if isinstance(valor, int | float) else str(valor)


def texto_fuente(idioma: str, fuente: str, resultado_fuente: str | None, indicadores: dict | None) -> str:
    """Lo que dijo la fuente, con su nombre, armado desde sus valores. En inglés, el valor de Whisp va tal
    como lo entregó."""
    ind = indicadores or {}
    if fuente == "whisp" and resultado_fuente:
        valor = textos.obtener(idioma, "whisp_valores").get(resultado_fuente, resultado_fuente)
        return textos.t(idioma, "citas.whisp", valor=valor)
    if (
        fuente == "gfw"
        and ind.get("alertas_desde_2021") is not None
        and ind.get("perdida_ha_total") is not None
    ):
        # Cada medida por separado, con singular para 1 (pedido del equipo del 2026-10-07).
        def alertas(clave: str, valor) -> str:
            return textos.t(idioma, f"citas.{clave}_{'uno' if valor == 1 else 'varios'}", n=_g(valor))

        partes = [
            alertas("gfw_alertas", ind["alertas_desde_2021"]),
            textos.t(idioma, "citas.gfw_perdida", n=_g(ind["perdida_ha_total"])),
        ]
        if ind.get("bosque_natural_2020_ha") is not None:
            partes.append(textos.t(idioma, "citas.gfw_bosque", n=_g(ind["bosque_natural_2020_ha"])))
        if ind.get("alertas_dist_desde_2021") is not None:
            partes.append(alertas("gfw_dist", ind["alertas_dist_desde_2021"]))
        return textos.t(idioma, "citas.gfw", medidas="; ".join(partes))
    claves = ("clase_predominante_2020", "bosque_2020_ha", "cambio_bosque_a_no_bosque_ha")
    if fuente == "mapbiomas" and all(ind.get(k) is not None for k in claves):
        return textos.t(
            idioma,
            "citas.mapbiomas",
            clase=ind["clase_predominante_2020"],
            bosque=_g(ind["bosque_2020_ha"]),
            cambio=_g(ind["cambio_bosque_a_no_bosque_ha"]),
            anio=ind.get("ultimo_anio"),
        )
    return textos.t(idioma, "citas.sin_resultado", fuente=NOMBRE_CORTO.get(fuente, fuente))


def cita(idioma: str, a: AnalisisCobertura) -> str:
    """Lo que dijo la fuente, entre comillas y con su nombre."""
    return f'"{texto_fuente(idioma, a.fuente, a.resultado_fuente, a.indicadores)}"'


def _tiene_alerta_de_analisis(d: DatosLote, p: Parcela) -> bool:
    return "analisis_requiere_revision" in analisis.alertas(d.resumenes[p.id])


# ---------- Requiere atención ----------


def analisis_requiere_revision(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        resumen = d.resumenes[p.id]
        if not _tiene_alerta_de_analisis(d, p):
            continue
        piden = [a for a in d.completados[p.id] if a.fuente in resumen["requiere_revision"]]
        citas = {}
        for idioma in textos.IDIOMAS:
            lista = [cita(idioma, a) for a in piden]
            if resumen.get("bosque_2020"):
                n = len(resumen["bosque_2020"])
                lista.append(
                    textos.t(
                        idioma,
                        "comun.citas_bosque_2020",
                        n=n,
                        total=d.convergencias[p.id].conteos["bosque_miden"],
                        verbo=_verbo(idioma, n),
                    )
                )
            citas[idioma] = lista
        resultado.append(
            _nuevo(
                d,
                "analisis_requiere_revision",
                p,
                d.nota_habilitacion(p.id),
                citas={i: textos.lista(i, citas[i]) for i in textos.IDIOMAS},
                citas_lista=citas,
                fuentes=[
                    {
                        "fuente": a.fuente,
                        "resultado_fuente": a.resultado_fuente,
                        "completado_en": a.completado_en.isoformat() if a.completado_en else None,
                        "version": a.version_fuente,
                    }
                    for a in piden
                ],
            )
        )
    return resultado


def area_discrepante(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        calculada, declarada = p.area_calculada_ha, p.area_declarada_ha
        if p.tipo_geometria != "poligono" or declarada is None or not calculada:
            continue
        razon = abs(Decimal(declarada) - Decimal(calculada)) / Decimal(calculada)
        if razon > UMBRAL_DISCREPANCIA:
            resultado.append(
                _nuevo(
                    d,
                    "area_discrepante",
                    p,
                    d.nota_habilitacion(p.id),
                    declarada=textos.hectareas(declarada),
                    calculada=textos.hectareas(calculada),
                    diferencia=textos.numero((razon * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                )
            )
    return resultado


def superposicion_aceptada(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        aceptadas = [s for s in d.superposiciones.get(p.id, []) if s.estado == "aceptada"]
        if not aceptadas:
            continue
        area = sum((Decimal(s.area_ha or 0) for s in aceptadas), Decimal("0"))
        notas = [s.nota for s in aceptadas if s.nota]
        resultado.append(
            _nuevo(
                d,
                "superposicion_aceptada",
                p,
                " / ".join(notas) or None,
                n=len(aceptadas),
                area=textos.hectareas(area),
            )
        )
    return resultado


def superposicion_con_excluida(d: DatosLote) -> list[Hallazgo]:
    return [
        _nuevo(d, "superposicion_con_excluida", p, d.nota_habilitacion(p.id))
        for p in d.parcelas_ordenadas()
        if "superposicion_con_excluida" in d.evaluaciones[p.id].alertas
    ]


def tenencia_solo_posesion(d: DatosLote) -> list[Hallazgo]:
    return [
        _nuevo(d, "tenencia_solo_posesion", p, d.nota_habilitacion(p.id))
        for p in d.parcelas_ordenadas()
        if _leg(d, p).tenencia_solo_posesion
    ]


def documento_por_vencer(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        for tipo, r, documento in _sustentos(d, p):
            if r.estado == "por_vencer":
                resultado.append(
                    _nuevo(
                        d,
                        "documento_por_vencer",
                        p,
                        documento=_nombre_doc(tipo.codigo),
                        fecha=textos.fechas(documento.fecha_vencimiento),
                        tipo=tipo.codigo,
                        vence=documento.fecha_vencimiento.isoformat(),
                        requisito=r.codigo,
                    )
                )
    return resultado


def conjuntos_registran_bosque_2020(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        conv = d.convergencias[p.id]
        filas = [f for f in conv.filas if f.registra_bosque_2020]
        if not filas:
            continue
        conjuntos = []
        for f in filas:
            medida = next((m for m in f.al_2020 if m.mide_bosque and isinstance(m.valor, int | float)), None)
            valor = (
                f" ({_g(medida.valor)} {UNIDADES.get(medida.unidad, medida.unidad or '')})" if medida else ""
            )
            conjuntos.append(f"{f.nombre}{valor}".replace(" )", ")"))
        resultado.append(
            _nuevo(
                d,
                "conjuntos_registran_bosque_2020",
                p,
                d.nota_habilitacion(p.id),
                n=len(filas),
                total=conv.conteos["bosque_miden"],
                verbo={i: _verbo(i, len(filas)) for i in textos.IDIOMAS},
                conjuntos={i: textos.lista(i, conjuntos) for i in textos.IDIOMAS},
            )
        )
    return resultado


def conjuntos_registran_cambio_posterior(d: DatosLote) -> list[Hallazgo]:
    """Solo la pérdida de bosque pide atención (pedido del equipo del 2026-10-07). La alteración de la
    vegetación (DIST-ALERT, incendios, cambio de clase en Esri Land Cover) se ve en la tabla de
    convergencia."""
    resultado = []
    for p in d.parcelas_ordenadas():
        conv = d.convergencias[p.id]
        nombres = [f.nombre for f in conv.filas if f.registra_perdida]
        if nombres:
            resultado.append(
                _nuevo(
                    d,
                    "conjuntos_registran_cambio_posterior",
                    p,
                    d.nota_habilitacion(p.id),
                    n=len(nombres),
                    total=conv.conteos["perdida_miden"],
                    verbo={i: _verbo(i, len(nombres)) for i in textos.IDIOMAS},
                    conjuntos={i: textos.lista(i, nombres) for i in textos.IDIOMAS},
                )
            )
    return resultado


def revision_de_imagenes_registrada(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        revision = d.evaluaciones[p.id].revision
        if revision is None or not _tiene_alerta_de_analisis(d, p):
            continue
        bloque = (d.imagenes.get(p.id) or (None, {}))[0] or {}

        def fecha_de(papel: str, bloque=bloque):
            dato = bloque.get(papel)
            if not dato:
                return {i: textos.obtener(i, "comun.sin_fecha") for i in textos.IDIOMAS}
            return textos.fechas(dato["fecha_captura"])

        resultado.append(
            _nuevo(
                d,
                "revision_de_imagenes_registrada",
                p,
                revision.descripcion,
                revisor=d.nombres.get(revision.revisada_por, ""),
                fecha=textos.fechas(revision.revisada_en),
                fecha_previa=fecha_de("anterior_al_corte"),
                fecha_reciente=fecha_de("reciente"),
                obs_2020={
                    i: textos.obtener(i, f"observaciones.{revision.observacion_2020}") for i in textos.IDIOMAS
                },
                obs_cambio={
                    i: textos.obtener(i, f"observaciones.{revision.observacion_cambio}")
                    for i in textos.IDIOMAS
                },
                imagenes=list(revision.imagenes or []),
            )
        )
    return resultado


def habilitada_con_cambio_visible(d: DatosLote) -> list[Hallazgo]:
    return [
        _nuevo(d, "habilitada_con_cambio_visible", p, d.nota_habilitacion(p.id))
        for p in d.parcelas_ordenadas()
        if (r := d.evaluaciones[p.id].revision) is not None
        and r.observacion_cambio == "cambio_visible"
        and p.habilitacion_estado == "habilitada"
    ]


# ---------- No verificado ----------


def coordenada_no_recorrida(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        procedencia = d.evaluaciones[p.id].procedencia
        if procedencia.recorrida_en_campo:
            continue
        rol = "productor" if procedencia.registrada_por_rol == "productor" else "cooperativa"
        resultado.append(
            _nuevo(
                d,
                "coordenada_no_recorrida",
                p,
                quien={i: textos.obtener(i, f"comun.registrada_{rol}") for i in textos.IDIOMAS},
                registrada_por_rol=procedencia.registrada_por_rol,
                origen_geometria=procedencia.origen_geometria,
            )
        )
    return resultado


def analisis_por_aproximacion(d: DatosLote) -> list[Hallazgo]:
    return [
        _nuevo(
            d,
            "analisis_por_aproximacion",
            p,
            fuentes=[a.fuente for a in d.completados[p.id] if a.es_aproximacion],
        )
        for p in d.parcelas_ordenadas()
        if any(a.es_aproximacion for a in d.completados[p.id])
    ]


def documento_sin_registro_consultable(d: DatosLote) -> list[Hallazgo]:
    """La declaración jurada tiene su propio hallazgo (tenencia_sin_documento_formal)."""
    return [
        _nuevo(
            d, "documento_sin_registro_consultable", p, documento=_nombre_doc(tipo.codigo), tipo=tipo.codigo
        )
        for p in d.parcelas_ordenadas()
        for tipo, _, _ in _sustentos(d, p)
        if not tipo.registro_consultable and tipo.codigo != "declaracion_jurada_tenencia"
    ]


def documento_sin_cotejar(d: DatosLote) -> list[Hallazgo]:
    return [
        _nuevo(d, "documento_sin_cotejar", p, documento=_nombre_doc(tipo.codigo), tipo=tipo.codigo)
        for p in d.parcelas_ordenadas()
        for tipo, _, documento in _sustentos(d, p)
        if tipo.registro_consultable and documento.cotejado_en is None
    ]


def _mapbiomas(d: DatosLote, p: Parcela) -> AnalisisCobertura | None:
    return next((a for a in d.completados[p.id] if a.fuente == "mapbiomas"), None)


def mapbiomas_pocos_pixeles(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        a = _mapbiomas(d, p)
        indicadores = (a.indicadores or {}) if a else {}
        if a and indicadores.get("pocos_pixeles"):
            resultado.append(_nuevo(d, "mapbiomas_pocos_pixeles", p, pixeles=indicadores.get("pixeles")))
    return resultado


def mapbiomas_sin_cobertura_reciente(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        a = _mapbiomas(d, p)
        if a and (a.indicadores or {}).get("ultimo_anio"):
            resultado.append(
                _nuevo(d, "mapbiomas_sin_cobertura_reciente", p, anio=a.indicadores["ultimo_anio"])
            )
    return resultado


def imagen_previa_lejana(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        bloque = (d.imagenes.get(p.id) or (None, {}))[0]
        previa = (bloque or {}).get("anterior_al_corte")
        if previa and previa["dias_respecto_al_corte"] < -DIAS_PREVIA_LEJANA:
            resultado.append(
                _nuevo(
                    d,
                    "imagen_previa_lejana",
                    p,
                    fecha=textos.fechas(previa["fecha_captura"]),
                    dias=abs(previa["dias_respecto_al_corte"]),
                    fecha_captura=previa["fecha_captura"],
                )
            )
    return resultado


def sin_imagen_de_alta_resolucion_previa(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        if not _tiene_alerta_de_analisis(d, p):
            continue
        altas = [
            f
            for f in imagenes.juego_actual(d.sesion, p)
            if f.estado == "generada"
            and f.fuente in ("esri_wayback", "externa")
            and f.fecha_captura is not None
            and f.fecha_captura <= imagenes.CORTE
        ]
        if not altas:
            resultado.append(_nuevo(d, "sin_imagen_de_alta_resolucion_previa", p))
    return resultado


# ---------- Adenda 4: legalidad de la parcela por requisito ----------


def _leg(d: DatosLote, p: Parcela):
    return d.evaluaciones[p.id].legalidad


def _del_requisito(r) -> dict:
    """Cada hallazgo de requisito lleva la referencia del orientador, el nivel y la diligencia."""
    req = r.requisito
    return {
        "referencias": ", ".join(req.referencias),
        "nivel_orientador": req.nivel,
        "diligencia": req.diligencia,
    }


def _cita(fila) -> dict[str, str]:
    """Todo hallazgo que sale de un cruce cita la capa y la fecha de consulta."""
    if fila is None:
        return {i: "" for i in textos.IDIOMAS}
    if fila.origen == "cruce":
        codigos = (fila.detalle or {}).get("capas") or []
        capas = "; ".join(
            capas_legales.POR_CODIGO[c].nombre for c in codigos if c in capas_legales.POR_CODIGO
        )
        return {
            i: textos.t(i, "comun.cita_capa", capas=capas, fecha=textos.fecha(i, fila.registrada_en))
            for i in textos.IDIOMAS
        }
    return {
        i: textos.t(i, "comun.cita_declarado", fecha=textos.fecha(i, fila.registrada_en))
        for i in textos.IDIOMAS
    }


def _nombre_doc(tipo: str) -> dict[str, str]:
    return {i: textos.obtener(i, f"documentos.{tipo}") for i in textos.IDIOMAS}


def _nota(nota: str | None) -> dict[str, str]:
    """Si hay nota o no. La nota misma va como explicación: es lo que escribió una persona y no se traduce."""
    return {i: textos.obtener(i, "comun.con_nota" if nota else "comun.sin_nota") for i in textos.IDIOMAS}


def _sustentos(d: DatosLote, p: Parcela):
    """Los documentos que hoy sustentan un requisito (vigentes o por vencer), una vez cada uno."""
    vistos = set()
    for r in _leg(d, p).requisitos.values():
        documento = r.sustento
        if documento is None or r.estado not in ("sustentado", "por_vencer") or documento.id in vistos:
            continue
        vistos.add(documento.id)
        yield documento_tipo(documento.tipo), r, documento


def documento_tipo(codigo: str):
    return documentos_legales.POR_CODIGO[codigo]


def tenencia_sin_documento_formal(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        leg = _leg(d, p)
        if not leg.tenencia_sin_documento_formal:
            continue
        r = leg.requisitos["tenencia"]
        resultado.append(
            _nuevo(
                d,
                "tenencia_sin_documento_formal",
                p,
                d.nota_habilitacion(p.id),
                fecha=textos.fechas(r.sustento.fecha_emision),
                vence=r.sustento.fecha_vencimiento.isoformat() if r.sustento.fecha_vencimiento else None,
                **_del_requisito(r),
            )
        )
    return resultado


def perfil_declarado_sin_cruce(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        variables = [v for v, valor in _leg(d, p).perfil.items() if valor.declarado_sin_cruce]
        if variables:
            resultado.append(
                _nuevo(
                    d,
                    "perfil_declarado_sin_cruce",
                    p,
                    variables={
                        i: textos.lista(i, [textos.obtener(i, f"variables.{v}") for v in variables])
                        for i in textos.IDIOMAS
                    },
                    codigos_variables=variables,
                )
            )
    return resultado


def en_area_de_conservacion(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        fila = _leg(d, p).perfil["en_anp"].cruce
        areas = ((fila.detalle or {}).get("areas_de_conservacion") or []) if fila else []
        if not areas:
            continue
        nombres = [f"{a.get('nombre') or '—'} ({a.get('categoria')})" for a in areas]
        resultado.append(
            _nuevo(
                d,
                "en_area_de_conservacion",
                p,
                d.nota_habilitacion(p.id),
                areas={i: textos.lista(i, nombres) for i in textos.IDIOMAS},
                cita=_cita(fila),
            )
        )
    return resultado


def tierra_forestal_por_excepcion(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        leg = _leg(d, p)
        r = leg.requisitos["tierra_forestal"]
        if not r.por_excepcion:
            continue
        doc = r.sustento
        if doc.fecha_emision is not None and doc.tipo != "constancia_saneamiento_31145":
            documento = {
                i: textos.t(
                    i,
                    "comun.documento_emitido",
                    documento=textos.obtener(i, f"documentos.{doc.tipo}"),
                    fecha=textos.fecha(i, doc.fecha_emision),
                )
                for i in textos.IDIOMAS
            }
        else:
            documento = _nombre_doc(doc.tipo)
        reserva = leg.valor("reserva_bosque_30")
        resultado.append(
            _nuevo(
                d,
                "tierra_forestal_por_excepcion",
                p,
                d.nota_habilitacion(p.id),
                documento=documento,
                reserva={
                    i: textos.obtener(
                        i, f"reserva_bosque_30.{reserva}" if reserva else "comun.reserva_sin_dato"
                    )
                    for i in textos.IDIOMAS
                },
                reserva_bosque_30=reserva,
                cita=_cita(leg.perfil["en_tierra_forestal"].manda),
                tipo=doc.tipo,
                **_del_requisito(r),
            )
        )
    return resultado


def zonificacion_forestal_desconocida(d: DatosLote) -> list[Hallazgo]:
    return [
        _nuevo(
            d,
            "zonificacion_forestal_desconocida",
            p,
            d.nota_habilitacion(p.id),
            cita=_cita(_leg(d, p).perfil["en_tierra_forestal"].manda),
        )
        for p in d.parcelas_ordenadas()
        if _leg(d, p).valor("en_tierra_forestal") == "sin_zonificacion"
    ]


def en_area_protegida(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        leg = _leg(d, p)
        valor = leg.perfil["en_anp"]
        if valor.valor not in ("dentro", "zona_de_amortiguamiento"):
            continue
        fila = valor.manda
        detalle = fila.detalle or {}
        lista = detalle.get("areas") if valor.valor == "dentro" else detalle.get("zonas_de_amortiguamiento")
        nombres = [
            f"{a.get('nombre')} ({a['categoria']})" if a.get("categoria") else a.get("nombre") or "—"
            for a in lista or []
        ] or [detalle.get("area_nombre") or "—"]
        r = leg.requisitos["area_protegida"]
        situacion = {}
        for i in textos.IDIOMAS:
            area = textos.lista(i, nombres)
            if valor.valor == "zona_de_amortiguamiento":
                situacion[i] = textos.t(i, "comun.anp_amortiguamiento", area=area)
            elif r.sustento is not None:
                situacion[i] = textos.t(
                    i,
                    "comun.anp_dentro",
                    area=area,
                    sustento=textos.obtener(i, f"documentos.{r.sustento.tipo}"),
                )
            else:
                situacion[i] = textos.t(i, "comun.anp_dentro_sin_sustento", area=area)
        resultado.append(
            _nuevo(
                d,
                "en_area_protegida",
                p,
                d.nota_habilitacion(p.id),
                situacion=situacion,
                en_anp=valor.valor,
                cita=_cita(fila),
                **_del_requisito(r),
            )
        )
    return resultado


def comunidad_no_inscrita(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        leg = _leg(d, p)
        valor = leg.perfil["en_tierra_comunal"]
        if valor.valor != "si":
            continue
        declarado = (valor.declarado.detalle or {}) if valor.declarado else {}
        cruce = (valor.cruce.detalle or {}) if valor.cruce else {}
        inscrita = declarado.get("inscrita") or "no_se_sabe"
        if inscrita == "si":
            continue
        nombre = declarado.get("comunidad_nombre") or cruce.get("comunidad_nombre")
        resultado.append(
            _nuevo(
                d,
                "comunidad_no_inscrita",
                p,
                comunidad=nombre
                or {i: textos.obtener(i, "comun.comunidad_sin_nombre") for i in textos.IDIOMAS},
                inscrita={
                    i: textos.obtener(
                        i, "comun.comunidad_no_inscrita" if inscrita == "no" else "comun.comunidad_no_se_sabe"
                    )
                    for i in textos.IDIOMAS
                },
                **_del_requisito(leg.requisitos["acuerdo_comunal"]),
            )
        )
    return resultado


def _estado_sin_sustento(estado: str) -> dict[str, str]:
    return {
        i: textos.obtener(i, "comun.tiene_vencido" if estado == "vencido" else "comun.no_tiene")
        for i in textos.IDIOMAS
    }


def riego_sin_licencia(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        r = _leg(d, p).requisitos["agua_de_riego"]
        if r.estado in ("sin_sustento", "vencido"):
            resultado.append(
                _nuevo(
                    d,
                    "riego_sin_licencia",
                    p,
                    d.nota_habilitacion(p.id),
                    estado=_estado_sin_sustento(r.estado),
                    **_del_requisito(r),
                )
            )
    return resultado


def instrumento_ambiental_sin_sustento(d: DatosLote) -> list[Hallazgo]:
    """Reemplaza a diez_hectareas_o_mas (adenda 4, sección 12)."""
    resultado = []
    for p in d.parcelas_ordenadas():
        r = _leg(d, p).requisitos["instrumento_ambiental"]
        if r.estado not in ("sin_sustento", "vencido"):
            continue
        total = _area_total(p.tipo_geometria, p.area_calculada_ha, p.area_declarada_ha)
        mayor = total is not None and total > requisitos_legales.UMBRAL_INSTRUMENTO_MAYOR_HA
        resultado.append(
            _nuevo(
                d,
                "instrumento_ambiental_sin_sustento",
                p,
                d.nota_habilitacion(p.id),
                area=textos.hectareas(total),
                estado=_estado_sin_sustento(r.estado),
                instrumento={
                    i: textos.obtener(i, "comun.instrumento_mayor" if mayor else "comun.ficha_tecnica")
                    for i in textos.IDIOMAS
                },
                **_del_requisito(r),
            )
        )
    return resultado


def junto_a_cuerpo_de_agua(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        leg = _leg(d, p)
        valor = leg.perfil["junto_a_cuerpo_de_agua"]
        if valor.valor != "si":
            continue
        detalle = (valor.cruce.detalle or {}) if valor.cruce else {}
        agua = {i: "" for i in textos.IDIOMAS}
        if detalle.get("distancia_m") is not None:
            agua = {
                i: textos.t(
                    i,
                    "comun.agua_cerca",
                    nombre=detalle.get("nombre") or textos.obtener(i, "comun.sin_nombre"),
                    distancia=textos.numero(detalle["distancia_m"], 0),
                )
                for i in textos.IDIOMAS
            }
        r = leg.requisitos["faja_marginal"]
        resultado.append(
            _nuevo(
                d,
                "junto_a_cuerpo_de_agua",
                p,
                r.nota,
                agua=agua,
                cita=_cita(valor.manda),
                nota=_nota(r.nota),
                distancia_m=detalle.get("distancia_m"),
                **_del_requisito(r),
            )
        )
    return resultado


def en_patrimonio_cultural(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        leg = _leg(d, p)
        valor = leg.perfil["en_patrimonio_cultural"]
        if valor.valor != "si":
            continue
        detalle = (valor.cruce.detalle or {}) if valor.cruce else {}
        nombres = [m.get("nombre") for m in detalle.get("monumentos") or [] if m.get("nombre")]
        sitio = {
            i: textos.t(i, "comun.sitio", nombre=textos.lista(i, nombres)) if nombres else ""
            for i in textos.IDIOMAS
        }
        r = leg.requisitos["patrimonio_cultural"]
        resultado.append(
            _nuevo(
                d,
                "en_patrimonio_cultural",
                p,
                r.nota,
                sitio=sitio,
                cita=_cita(valor.manda),
                nota=_nota(r.nota),
                **_del_requisito(r),
            )
        )
    return resultado


def incidencia_registrada(d: DatosLote) -> list[Hallazgo]:
    """Una incidencia abierta que no es de tenencia, o una cerrada. Tema 4 si es de tenencia; 11 si no."""
    resultado = []
    for p in d.parcelas_ordenadas():
        for i in sorted(_leg(d, p).incidencias, key=lambda x: x.registrada_en):
            if i.estado == "abierta" and i.tipo == "tenencia":
                continue
            estado = {
                idioma: textos.obtener(idioma, "comun.incidencia_abierta")
                if i.estado == "abierta"
                else textos.t(idioma, "comun.incidencia_cerrada", fecha=textos.fecha(idioma, i.cerrada_en))
                for idioma in textos.IDIOMAS
            }
            explicacion = i.descripcion if i.estado == "abierta" else f"{i.descripcion} / {i.cierre_nota}"
            hallazgo = _nuevo(
                d,
                "incidencia_registrada",
                p,
                explicacion,
                tipo={idioma: textos.obtener(idioma, f"incidencias.{i.tipo}") for idioma in textos.IDIOMAS},
                estado=estado,
                fecha=textos.fechas(i.registrada_en),
                fuente=i.fuente,
                tipo_incidencia=i.tipo,
                estado_incidencia=i.estado,
            )
            hallazgo.criterio = 4 if i.tipo == "tenencia" else 11
            resultado.append(hallazgo)
    return resultado


REGLAS = (
    analisis_requiere_revision,
    area_discrepante,
    superposicion_aceptada,
    superposicion_con_excluida,
    tenencia_solo_posesion,
    documento_por_vencer,
    conjuntos_registran_bosque_2020,
    conjuntos_registran_cambio_posterior,
    revision_de_imagenes_registrada,
    habilitada_con_cambio_visible,
    coordenada_no_recorrida,
    analisis_por_aproximacion,
    documento_sin_registro_consultable,
    documento_sin_cotejar,
    mapbiomas_pocos_pixeles,
    mapbiomas_sin_cobertura_reciente,
    imagen_previa_lejana,
    sin_imagen_de_alta_resolucion_previa,
    # Adenda 4, sección 12. exencion_declarada y diez_hectareas_o_mas ya no se generan.
    tenencia_sin_documento_formal,
    perfil_declarado_sin_cruce,
    en_area_de_conservacion,
    tierra_forestal_por_excepcion,
    zonificacion_forestal_desconocida,
    en_area_protegida,
    comunidad_no_inscrita,
    riego_sin_licencia,
    instrumento_ambiental_sin_sustento,
    junto_a_cuerpo_de_agua,
    en_patrimonio_cultural,
    incidencia_registrada,
)

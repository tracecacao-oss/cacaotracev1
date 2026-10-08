"""Reglas de la etapa 1: la parcela, con el estado de hoy (no el sellado en el DOP). Una función por regla;
agregar una regla no modifica las demás."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app import textos
from app.catalogos import documentos_legales
from app.models import AnalisisCobertura, Parcela
from app.services import analisis, imagenes
from app.services.hallazgos.catalogo import Hallazgo, sujeto
from app.services.hallazgos.datos import DatosLote
from app.services.parcelas import UMBRAL_DIEZ_HA, UMBRAL_DISCREPANCIA, _area_total

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
    """"1 de 13 conjuntos de datos registra", "2 de 13 registran"."""
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


def _casillas_con_documento(d: DatosLote, p: Parcela):
    """Casillas cubiertas por un documento (vigente o por vencer), en el orden del catálogo."""
    exp = d.evaluaciones[p.id].expediente
    for tipo in documentos_legales.TIPOS:
        c = exp.casillas[tipo.codigo]
        if c.documento is not None and c.estado in ("vigente", "por_vencer"):
            yield tipo, c


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


def diez_hectareas_o_mas(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        total = _area_total(p.tipo_geometria, p.area_calculada_ha, p.area_declarada_ha)
        if total is not None and total >= UMBRAL_DIEZ_HA:
            resultado.append(
                _nuevo(d, "diez_hectareas_o_mas", p, d.nota_habilitacion(p.id), area=textos.hectareas(total))
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
        if d.evaluaciones[p.id].expediente.tenencia_solo_posesion
    ]


def exencion_declarada(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        exp = d.evaluaciones[p.id].expediente
        for tipo in documentos_legales.TIPOS:
            c = exp.casillas[tipo.codigo]
            if c.estado == "no_aplica" and c.exencion is not None:
                resultado.append(
                    _nuevo(
                        d,
                        "exencion_declarada",
                        p,
                        c.exencion.motivo,
                        casilla={i: textos.obtener(i, f"documentos.{tipo.codigo}") for i in textos.IDIOMAS},
                        tipo=tipo.codigo,
                    )
                )
    return resultado


def documento_por_vencer(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p in d.parcelas_ordenadas():
        for tipo, c in _casillas_con_documento(d, p):
            if c.estado == "por_vencer":
                resultado.append(
                    _nuevo(
                        d,
                        "documento_por_vencer",
                        p,
                        documento={i: textos.obtener(i, f"documentos.{tipo.codigo}") for i in textos.IDIOMAS},
                        fecha=textos.fechas(c.documento.fecha_vencimiento),
                        tipo=tipo.codigo,
                        vence=c.documento.fecha_vencimiento.isoformat(),
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
    return [
        _nuevo(
            d,
            "documento_sin_registro_consultable",
            p,
            documento={i: textos.obtener(i, f"documentos.{tipo.codigo}") for i in textos.IDIOMAS},
            tipo=tipo.codigo,
        )
        for p in d.parcelas_ordenadas()
        for tipo, _ in _casillas_con_documento(d, p)
        if not tipo.registro_consultable
    ]


def documento_sin_cotejar(d: DatosLote) -> list[Hallazgo]:
    return [
        _nuevo(
            d,
            "documento_sin_cotejar",
            p,
            documento={i: textos.obtener(i, f"documentos.{tipo.codigo}") for i in textos.IDIOMAS},
            tipo=tipo.codigo,
        )
        for p in d.parcelas_ordenadas()
        for tipo, c in _casillas_con_documento(d, p)
        if tipo.registro_consultable and c.nivel != "verificado_en_fuente"
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


REGLAS = (
    analisis_requiere_revision,
    diez_hectareas_o_mas,
    area_discrepante,
    superposicion_aceptada,
    superposicion_con_excluida,
    tenencia_solo_posesion,
    exencion_declarada,
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
)

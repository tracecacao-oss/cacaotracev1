"""Reglas de la etapa 3 sobre la organización y la declaración aduanera del lote (adenda 6, sección 11, y
adenda 7, sección 8), con el estado de hoy. Una función por regla.

Su sujeto es la organización, salvo `lote_sin_dam` y `dam_difiere_del_lote`, que son del lote. Las de la
organización y `lote_sin_dam` van a No verificado: son documentos o registros que faltan;
`dam_difiere_del_lote`, a Requiere atención. Nada de esto frena el lote ni dice que la organización cumple o
no: dice qué falta en su expediente, en su política o en su registro de actuaciones, y en qué difiere lo
declarado en aduanas.
"""

from app import textos
from app.services import cooperativa as servicio_cooperativa
from app.services import diligencia, embarque
from app.services.hallazgos.catalogo import Hallazgo, sujeto
from app.services.hallazgos.datos import DatosLote

CUBIERTOS = ("vigente", "por_vencer")


def _organizacion(d: DatosLote) -> dict:
    coop = d.cooperativa
    return sujeto("organizacion", coop.id, coop.codigo or coop.ruc)


def _estado(casilla) -> dict[str, str]:
    return {i: textos.obtener(i, "estados").get(casilla.estado, casilla.estado) for i in textos.IDIOMAS}


def tributos_organizacion_sin_sustento(d: DatosLote) -> list[Hallazgo]:
    """No hay una declaración anual de renta vigente (o por vencer)."""
    casilla = servicio_cooperativa.casillas(d.sesion, d.cooperativa.id, d.hoy)["renta_anual"]
    if casilla.estado in CUBIERTOS:
        return []
    return [
        Hallazgo(
            "tributos_organizacion_sin_sustento",
            _organizacion(d),
            {"organizacion": d.cooperativa.razon_social, "estado": _estado(casilla), "referencias": "7.1"},
        )
    ]


def registro_cooperativas_sin_sustento(d: DatosLote) -> list[Hallazgo]:
    """Es cooperativa agraria y no hay constancia de inscripción vigente."""
    casilla = servicio_cooperativa.casillas(d.sesion, d.cooperativa.id, d.hoy).get("rnca")
    if casilla is None or casilla.estado in CUBIERTOS:
        return []
    return [
        Hallazgo(
            "registro_cooperativas_sin_sustento",
            _organizacion(d),
            {"organizacion": d.cooperativa.razon_social, "estado": _estado(casilla), "referencias": "7.1"},
        )
    ]


def politica_incompleta(d: DatosLote) -> list[Hallazgo]:
    """Algún tema de la política no está sustentado. Lista cuáles; el canal sin contacto lo dice."""
    faltan = [t for t in diligencia.temas(d.sesion, d.cooperativa) if t.estado != "sustentado"]
    if not faltan:
        return []

    def nombre(idioma: str, t) -> str:
        texto = textos.obtener(idioma, f"organizacion.temas_politica.{t.codigo}")
        if t.politicas:  # cubierto por una política, pero sin el contacto del canal
            texto += f" ({textos.obtener(idioma, 'organizacion.falta_contacto')})"
        return texto

    return [
        Hallazgo(
            "politica_incompleta",
            _organizacion(d),
            {
                "organizacion": d.cooperativa.razon_social,
                "temas": {i: textos.lista(i, [nombre(i, t) for t in faltan]) for i in textos.IDIOMAS},
                "codigos_temas": [t.codigo for t in faltan],
                "referencias": "7.3, 5.5",
            },
        )
    ]


def sin_actuaciones_de_diligencia(d: DatosLote) -> list[Hallazgo]:
    """Algún tema esperado no tiene una actuación vigente. Lista cada tema con su señal."""
    faltan = [s for s in diligencia.senales(d.sesion, d.cooperativa.id, d.hoy) if s.estado == "sin_sustento"]
    if not faltan:
        return []

    def nombre(idioma: str, s) -> str:
        return f"{textos.obtener(idioma, f'organizacion.temas.{s.codigo}')} ({s.texto_en(idioma)})"

    return [
        Hallazgo(
            "sin_actuaciones_de_diligencia",
            _organizacion(d) | {"detalle_tipo": "diligencia"},
            {
                "organizacion": d.cooperativa.razon_social,
                "temas": {i: textos.lista(i, [nombre(i, s) for s in faltan]) for i in textos.IDIOMAS},
                "codigos_temas": [s.codigo for s in faltan],
            },
        )
    ]


def _lote(d: DatosLote) -> dict:
    return sujeto("lote", d.lote.id, d.lote.codigo) | {"detalle_tipo": "embarque"}


def lote_sin_dam(d: DatosLote) -> list[Hallazgo]:
    """Adenda 6, sección 7, regla 5, y adenda 7, sección 8: el lote no tiene una declaración aduanera sin
    anular al emitir el DEX (y en el informe preliminar, hoy)."""
    if embarque.vigente(d.sesion, d.lote.id) is not None:
        return []
    return [Hallazgo("lote_sin_dam", _lote(d), {"lote": d.lote.codigo, "referencias": "7.2"})]


def dam_difiere_del_lote(d: DatosLote) -> list[Hallazgo]:
    """Adenda 7, sección 4.2: el peso o la subpartida que la persona escribió de la declaración aduanera
    difieren del lote. Dice cuál, con los dos valores. No bloquea."""
    declaracion = embarque.vigente(d.sesion, d.lote.id)
    if declaracion is None:
        return []
    c = embarque.comparar(d.sesion, declaracion, d.lote)
    if not c.difiere:
        return []
    valores = {
        "peso_declarado": textos.numero(c.peso_declarado_kg),
        "peso_lote": textos.numero(c.peso_lote_kg),
        "diferencia_pct": textos.numero(c.diferencia_pct) if c.diferencia_pct is not None else "—",
        "subpartida": c.subpartida,
        "partida": c.partida_orden,
    }
    partes = {
        i: textos.lista(
            i,
            [
                *([textos.t(i, "aduanas.difiere_peso", **valores)] if c.peso_difiere else []),
                *([textos.t(i, "aduanas.difiere_subpartida", **valores)] if c.subpartida_difiere else []),
            ],
        )
        for i in textos.IDIOMAS
    }
    return [
        Hallazgo(
            "dam_difiere_del_lote",
            _lote(d),
            {
                "lote": d.lote.codigo,
                "numero": declaracion.numero,
                "diferencias": partes,
                "peso_difiere": c.peso_difiere,
                "subpartida_difiere": c.subpartida_difiere,
                "peso_declarado_kg": c.peso_declarado_kg,
                "peso_lote_kg": c.peso_lote_kg,
                "diferencia_pct": c.diferencia_pct,
                "subpartida": c.subpartida,
                "partida_orden": c.partida_orden,
                "referencias": "7.2",
            },
        )
    ]


REGLAS = (
    tributos_organizacion_sin_sustento,
    registro_cooperativas_sin_sustento,
    politica_incompleta,
    sin_actuaciones_de_diligencia,
    lote_sin_dam,
    dam_difiere_del_lote,
)

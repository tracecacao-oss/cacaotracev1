"""Reglas de la etapa 3 sobre la organización y la declaración aduanera del lote (adenda 6, sección 11), con
el estado de hoy. Una función por regla.

Su sujeto es la organización, salvo `lote_sin_dam`, que es del lote. Todas van a No verificado: son
documentos o registros que faltan. Nada de esto frena el lote ni dice que la organización cumple o no: dice
qué falta en su expediente, en su política o en su registro de actuaciones.
"""

from sqlalchemy import select

from app import textos
from app.catalogos import documentos_embarque
from app.models import Documento
from app.services import cooperativa as servicio_cooperativa
from app.services import diligencia
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


def lote_sin_dam(d: DatosLote) -> list[Hallazgo]:
    """Sección 7, regla 5: el lote no tiene la declaración aduanera al emitir el DEX (y en el informe
    preliminar, hoy)."""
    tiene = d.sesion.scalar(
        select(Documento.id)
        .where(
            Documento.entidad == "lote",
            Documento.entidad_id == d.lote.id,
            Documento.tipo.in_(documentos_embarque.DESPUES_DEL_DEX),
            Documento.anulado_en.is_(None),
        )
        .limit(1)
    )
    if tiene:
        return []
    return [
        Hallazgo(
            "lote_sin_dam",
            sujeto("lote", d.lote.id, d.lote.codigo) | {"detalle_tipo": "embarque"},
            {"lote": d.lote.codigo, "referencias": "7.2"},
        )
    ]


REGLAS = (
    tributos_organizacion_sin_sustento,
    registro_cooperativas_sin_sustento,
    politica_incompleta,
    sin_actuaciones_de_diligencia,
    lote_sin_dam,
)

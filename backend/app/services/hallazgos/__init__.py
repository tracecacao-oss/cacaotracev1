"""Informe de hallazgos del lote (Parte 9).

Recorre las tres etapas hacia atrás desde el lote. Cada regla es una función propia (parcela.py, acopio.py
y lote.py) y genera un hallazgo por sujeto; el informe los agrupa (informe.py). Se puede consultar en
cualquier momento para un lote armado, bloqueado o listo (preliminar), y al emitir el DEX se calcula una
última vez y queda sellado.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.contexto import Contexto
from app.errores import error_api
from app.models import Lote
from app.services import imagenes, recomprobacion, revisiones_imagenes
from app.services.hallazgos import acopio, lote, parcela, productor
from app.services.hallazgos.catalogo import CATALOGO, GRUPOS, Hallazgo
from app.services.hallazgos.datos import DatosLote, cargar
from app.services.hallazgos.informe import armar

REGLAS = (*parcela.REGLAS, *productor.REGLAS, *acopio.REGLAS, *lote.REGLAS)
CON_INFORME = ("armado", "bloqueado", "listo")

__all__ = ["CATALOGO", "GRUPOS", "REGLAS", "DatosLote", "Hallazgo", "calcular", "preliminar", "reunir"]


def reunir(sesion: Session, lote_: Lote, comprobaciones: list[dict[str, Any]]) -> DatosLote:
    """Los datos del lote, con las comprobaciones de la Parte 8 de este momento y las imágenes de cada
    parcela con la alerta de análisis."""
    d = cargar(sesion, lote_)
    d.comprobaciones = comprobaciones
    for p in d.parcelas_ordenadas():
        revision = d.evaluaciones[p.id].revision
        resumen = revisiones_imagenes.resumen(
            revision, d.nombres.get(revision.revisada_por) if revision else None
        )
        d.imagenes[p.id] = imagenes.para_dop(sesion, p, resumen)
    return d


def hallazgos_de(d: DatosLote) -> list[Hallazgo]:
    return [h for regla in REGLAS for h in regla(d)]


def calcular(d: DatosLote, *, preliminar: bool) -> dict[str, Any]:
    return armar(d, hallazgos_de(d), preliminar=preliminar)


def preliminar(contexto: Contexto, lote_id) -> dict[str, Any]:
    """Informe preliminar: cambia con los datos. Las comprobaciones se calculan con la fecha de hoy, sin
    guardar una recomprobación."""
    from app.services.lotes import lote_visible  # evita importación circular

    sesion = contexto.sesion
    lote_ = lote_visible(contexto, lote_id)
    if lote_.estado not in CON_INFORME:
        raise error_api(
            400,
            "lote_sin_informe",
            "El informe preliminar se calcula para un lote armado, bloqueado o listo.",
        )
    d = reunir(sesion, lote_, recomprobacion.comprobar(sesion, lote_))
    return calcular(d, preliminar=True)

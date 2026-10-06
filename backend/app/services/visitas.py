"""Visitas de campo y procedencia de la geometría (Parte 4).

Desde la adenda 2 de la Parte 4 (decisión del equipo del 2026-10-05) ya no se registran visitas: no hay
pantalla ni endpoints, y una visita no atiende un análisis. La tabla y sus registros se conservan, y una
visita registrada antes sigue diciendo si el lindero se recorrió en campo (procedencia de la geometría).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.fechas import dia_lima
from app.models import Parcela, VisitaCampo
from app.schemas.habilitacion import Procedencia


def vigentes(sesion: Session, parcela_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[VisitaCampo]]:
    resultado: dict[uuid.UUID, list[VisitaCampo]] = {pid: [] for pid in parcela_ids}
    if not parcela_ids:
        return resultado
    for v in sesion.scalars(
        select(VisitaCampo)
        .where(VisitaCampo.parcela_id.in_(parcela_ids), VisitaCampo.anulada_en.is_(None))
        .order_by(VisitaCampo.fecha.desc(), VisitaCampo.creado_en.desc())
    ):
        resultado[v.parcela_id].append(v)
    return resultado


def posterior_a_la_geometria(visita: VisitaCampo, parcela: Parcela) -> bool:
    """La visita se registró después del último cambio de geometría y no es de un día anterior a él."""
    cambio = parcela.geometria_actualizada_en
    return visita.creado_en > cambio and visita.fecha >= dia_lima(cambio)


def procedencia(parcela: Parcela, visitas_vigentes: list[VisitaCampo]) -> Procedencia:
    recorrida = next(
        (v for v in visitas_vigentes if v.perimetro_recorrido and posterior_a_la_geometria(v, parcela)), None
    )
    return Procedencia(
        origen_geometria=parcela.origen_geometria,
        registrada_por_rol=parcela.registrada_por_rol,
        recorrida_en_campo=recorrida is not None,
        fecha_recorrido=recorrida.fecha if recorrida else None,
    )

"""Revisiones de imágenes (adenda 2 de la Parte 4, sección 7).

Una revisión registra lo que una persona con nombre observó en imágenes identificadas; no es un veredicto
del sistema. La registra solo un administrador. No se edita: si está mal, se anula con motivo y se registra
otra (un trigger lo impide en la base). Deja de estar vigente si cambia la geometría de la parcela, si se
anula o si llega un análisis posterior a ella.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contexto import Contexto
from app.errores import error_api, no_encontrado
from app.fechas import ahora
from app.models import AnalisisCobertura, Parcela, Perfil, RevisionImagenes
from app.schemas.imagenes import RevisionNueva, RevisionSalida
from app.services import imagenes as servicio_imagenes
from app.services.auditoria import registrar_auditoria

TEXTO_2020 = {
    "bosque": "bosque",
    "cultivo_o_uso_agricola": "cultivo o uso agrícola",
    "mixto": "mixto",
    "no_se_distingue": "no se distingue",
}
TEXTO_CAMBIO = {
    "sin_cambio_visible": "sin cambio visible",
    "cambio_visible": "cambio visible",
    "no_se_distingue": "no se distingue",
}


def de_parcelas(sesion: Session, parcela_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[RevisionImagenes]]:
    """Revisiones de cada parcela, de la más reciente a la más antigua."""
    resultado: dict[uuid.UUID, list[RevisionImagenes]] = {pid: [] for pid in parcela_ids}
    if not parcela_ids:
        return resultado
    for r in sesion.scalars(
        select(RevisionImagenes)
        .where(RevisionImagenes.parcela_id.in_(parcela_ids))
        .order_by(RevisionImagenes.revisada_en.desc())
    ):
        resultado[r.parcela_id].append(r)
    return resultado


def es_vigente(revision: RevisionImagenes, huella_actual: str, ultimo_analisis) -> bool:
    return (
        revision.anulada_en is None
        and revision.geometria_sha256 == huella_actual
        and (ultimo_analisis is None or revision.revisada_en > ultimo_analisis)
    )


def ultimo_analisis(analisis: list[AnalisisCobertura], huella_actual: str):
    fechas = [
        a.completado_en
        for a in analisis
        if a.estado == "completado" and a.geometria_sha256 == huella_actual and a.completado_en
    ]
    return max(fechas) if fechas else None


def vigente(
    revisiones: list[RevisionImagenes], huella_actual: str, analisis: list[AnalisisCobertura]
) -> RevisionImagenes | None:
    """La revisión vigente más reciente: no anulada, de la geometría actual y posterior al último análisis."""
    ultimo = ultimo_analisis(analisis, huella_actual)
    return next((r for r in revisiones if es_vigente(r, huella_actual, ultimo)), None)


def resumen(revision: RevisionImagenes | None, nombre: str | None) -> dict | None:
    """Lo que se copia en la decisión de habilitación y en el DOP."""
    if revision is None:
        return None
    return {
        "id": str(revision.id),
        "revisada_por": nombre,
        "revisada_en": revision.revisada_en.isoformat(),
        "observacion_2020": revision.observacion_2020,
        "observacion_cambio": revision.observacion_cambio,
        "descripcion": revision.descripcion,
        "imagenes": revision.imagenes,
    }


def _nombres(sesion: Session, ids) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {
        p.id: f"{p.nombres} {p.apellidos}".strip()
        for p in sesion.scalars(select(Perfil).where(Perfil.id.in_(ids)))
    }


def nombre_de(sesion: Session, revision: RevisionImagenes | None) -> str | None:
    if revision is None:
        return None
    return _nombres(sesion, [revision.revisada_por]).get(revision.revisada_por)


def listar(sesion: Session, parcela: Parcela) -> list[RevisionSalida]:
    from app.services import analisis

    huella_actual = servicio_imagenes.huella(parcela)
    revisiones = de_parcelas(sesion, [parcela.id])[parcela.id]
    ultimo = ultimo_analisis(analisis.de_parcelas(sesion, [parcela.id])[parcela.id], huella_actual)
    nombres = _nombres(sesion, [r.revisada_por for r in revisiones] + [r.anulada_por for r in revisiones])
    return [
        RevisionSalida(
            id=r.id,
            parcela_id=r.parcela_id,
            revisada_por_nombre=nombres.get(r.revisada_por),
            revisada_en=r.revisada_en,
            imagenes=[str(i) for i in r.imagenes],
            observacion_2020=r.observacion_2020,
            observacion_cambio=r.observacion_cambio,
            descripcion=r.descripcion,
            anulada_en=r.anulada_en,
            anulada_por_nombre=nombres.get(r.anulada_por),
            motivo_anulacion=r.motivo_anulacion,
            vigente=es_vigente(r, huella_actual, ultimo),
        )
        for r in revisiones
    ]


def registrar(contexto: Contexto, parcela: Parcela, datos: RevisionNueva) -> list[RevisionSalida]:
    from app.services.expediente import no_excluida

    no_excluida(parcela)
    juego = [f for f in servicio_imagenes.juego_actual(contexto.sesion, parcela) if f.estado == "generada"]
    # Cuentan las imágenes guardadas (Sentinel-2 o externas); Wayback se mira, pero no se guarda.
    guardadas = [f for f in juego if f.fuente in ("sentinel2", "externa") and f.fecha_captura]
    previas = [f for f in guardadas if f.fecha_captura <= servicio_imagenes.CORTE]
    posteriores = [f for f in guardadas if f.fecha_captura > servicio_imagenes.CORTE]
    if not previas or not posteriores:
        raise error_api(
            400,
            "imagenes_insuficientes",
            "Para registrar una revisión hace falta la imagen anterior al corte y al menos una posterior.",
        )
    revision = RevisionImagenes(
        parcela_id=parcela.id,
        cooperativa_id=contexto.cooperativa_id,
        revisada_por=contexto.usuario_id,
        revisada_en=ahora(),
        imagenes=[str(f.id) for f in juego],
        observacion_2020=datos.observacion_2020,
        observacion_cambio=datos.observacion_cambio,
        descripcion=datos.descripcion,
        geometria_sha256=servicio_imagenes.huella(parcela),
    )
    contexto.sesion.add(revision)
    contexto.sesion.flush()
    registrar_auditoria(
        contexto,
        "revision_imagenes.registrar",
        "parcela",
        parcela.id,
        {
            "revision_id": revision.id,
            "observacion_2020": datos.observacion_2020,
            "observacion_cambio": datos.observacion_cambio,
            "imagenes": len(juego),
        },
    )
    contexto.sesion.commit()
    return listar(contexto.sesion, parcela)


def revision_visible(contexto: Contexto, revision_id: uuid.UUID) -> RevisionImagenes:
    revision = contexto.sesion.get(RevisionImagenes, revision_id)
    if revision is None or revision.cooperativa_id != contexto.cooperativa_id:
        raise no_encontrado("Revisión no encontrada.")
    return revision


def anular(contexto: Contexto, revision_id: uuid.UUID, motivo: str) -> list[RevisionSalida]:
    revision = revision_visible(contexto, revision_id)
    if revision.anulada_en is not None:
        raise error_api(400, "revision_anulada", "La revisión ya está anulada.")
    revision.anulada_en = ahora()
    revision.anulada_por = contexto.usuario_id
    revision.motivo_anulacion = motivo
    registrar_auditoria(
        contexto,
        "revision_imagenes.anular",
        "parcela",
        revision.parcela_id,
        {"revision_id": revision.id, "motivo": motivo},
    )
    contexto.sesion.commit()
    parcela = contexto.sesion.get(Parcela, revision.parcela_id)
    return listar(contexto.sesion, parcela)

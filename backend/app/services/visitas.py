"""Visitas de campo y procedencia de la geometría (Parte 4).

La visita registra lo que un técnico vio en la parcela; no declara que cumple ni que no cumple.
No se edita: si está mal, se anula con motivo y se registra otra. Lleva al menos una foto.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contexto import Contexto
from app.errores import error_api, no_encontrado
from app.fechas import ahora, dia_lima, hoy_lima
from app.models import Parcela, Perfil, VisitaCampo
from app.schemas.habilitacion import Procedencia, VisitaNueva, VisitaSalida
from app.services import documentos
from app.services.auditoria import registrar_auditoria
from app.services.documentos import Archivo
from app.services.expediente import no_excluida
from app.storage import ArchivoNoPermitido, ClienteStorage, validar_documento


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


def _salida(visita: VisitaCampo, registrada_por: str | None, fotos) -> VisitaSalida:
    from app.services.productores import documento_salida  # evita importación circular

    return VisitaSalida(
        id=visita.id,
        parcela_id=visita.parcela_id,
        fecha=visita.fecha,
        realizada_por_nombre=visita.realizada_por_nombre,
        realizada_por_cargo=visita.realizada_por_cargo,
        registrada_por_nombre=registrada_por,
        motivo=visita.motivo,
        perimetro_recorrido=visita.perimetro_recorrido,
        uso_observado=visita.uso_observado,
        descripcion=visita.descripcion,
        creado_en=visita.creado_en,
        anulada_en=visita.anulada_en,
        motivo_anulacion=visita.motivo_anulacion,
        vigente=visita.anulada_en is None,
        fotos=[documento_salida(d, n) for d, n in fotos],
    )


def registrar(
    contexto: Contexto, storage: ClienteStorage, parcela: Parcela, datos: VisitaNueva, fotos: list[Archivo]
) -> VisitaSalida:
    no_excluida(parcela)
    if datos.fecha > hoy_lima():
        raise error_api(422, "fecha_futura", "La fecha de la visita no puede ser futura.")
    if not fotos:
        raise error_api(422, "foto_requerida", "Toda visita lleva al menos una foto de la parcela.")
    for foto in fotos:
        try:
            extension = validar_documento(foto.contenido)
        except ArchivoNoPermitido as exc:
            raise error_api(422, "formato_no_admitido", f"{exc} Las fotos deben ser JPG o PNG.") from exc
        if extension not in ("jpg", "png"):
            raise error_api(422, "formato_no_admitido", "Las fotos de la visita deben ser JPG o PNG.")

    visita = VisitaCampo(
        parcela_id=parcela.id,
        cooperativa_id=contexto.cooperativa_id,
        registrada_por=contexto.usuario_id,
        # Desde Python y no con now() de Postgres, que es el inicio de la transacción: se compara con el
        # momento del último cambio de geometría.
        creado_en=ahora(),
        **datos.model_dump(),
    )
    contexto.sesion.add(visita)
    contexto.sesion.flush()
    rutas = []
    try:
        for foto in fotos:
            _, ruta = documentos.guardar(
                contexto, storage, entidad="visita", entidad_id=visita.id, tipo="foto_visita", archivo=foto
            )
            rutas.append(ruta)
        registrar_auditoria(
            contexto,
            "visita.registrar",
            "parcela",
            parcela.id,
            {
                "visita_id": visita.id,
                "fecha": datos.fecha,
                "motivo": datos.motivo,
                "perimetro_recorrido": datos.perimetro_recorrido,
                "uso_observado": datos.uso_observado,
                "fotos": len(fotos),
            },
        )
        contexto.sesion.commit()
    except Exception:
        contexto.sesion.rollback()
        for ruta in rutas:
            documentos.descartar(storage, ruta)
        raise
    return obtener(contexto, visita.id)


def _con_nombres(contexto: Contexto, visitas: list[VisitaCampo]) -> list[VisitaSalida]:
    nombres = dict(
        contexto.sesion.execute(
            select(Perfil.id, func.concat(Perfil.nombres, " ", Perfil.apellidos)).where(
                Perfil.id.in_({v.registrada_por for v in visitas})
            )
        ).all()
    )
    return [
        _salida(v, nombres.get(v.registrada_por), documentos.documentos_de(contexto.sesion, "visita", v.id))
        for v in visitas
    ]


def listar(contexto: Contexto, parcela_id: uuid.UUID) -> list[VisitaSalida]:
    visitas = list(
        contexto.sesion.scalars(
            select(VisitaCampo)
            .where(VisitaCampo.parcela_id == parcela_id)
            .order_by(VisitaCampo.fecha.desc(), VisitaCampo.creado_en.desc())
        )
    )
    return _con_nombres(contexto, visitas)


def visita_visible(contexto: Contexto, visita_id: uuid.UUID) -> VisitaCampo:
    from app.services.parcelas import parcela_visible  # evita importación circular

    visita = contexto.sesion.get(VisitaCampo, visita_id)
    if visita is None:
        raise no_encontrado("La visita no existe.")
    parcela_visible(contexto, visita.parcela_id)
    return visita


def obtener(contexto: Contexto, visita_id: uuid.UUID) -> VisitaSalida:
    return _con_nombres(contexto, [visita_visible(contexto, visita_id)])[0]


def anular(contexto: Contexto, visita_id: uuid.UUID, motivo: str) -> VisitaSalida:
    visita = visita_visible(contexto, visita_id)
    no_excluida(contexto.sesion.get(Parcela, visita.parcela_id))
    if visita.anulada_en is not None:
        raise error_api(400, "visita_anulada", "La visita ya estaba anulada.")
    visita.anulada_en = ahora()
    visita.anulada_por = contexto.usuario_id
    visita.motivo_anulacion = motivo
    registrar_auditoria(
        contexto, "visita.anular", "parcela", visita.parcela_id, {"visita_id": visita.id, "motivo": motivo}
    )
    contexto.sesion.commit()
    return obtener(contexto, visita.id)

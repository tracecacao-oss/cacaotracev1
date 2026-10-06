"""Importadores y órdenes de compra (Parte 7). El importador es un registro de la cooperativa, no un usuario.

Estados de la orden: abierta (se edita), con_lote (tiene un lote confirmado; ya no se edita), cerrada (su lote
tiene DEX; lo fija la Parte 9) y anulada (con motivo, solo sin lote confirmado).
"""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import LIMA, ahora
from app.models import Calidad, Importador, Lote, OrdenCompra, Perfil
from app.models.exportacion import PARTIDA_SA
from app.schemas.exportacion import (
    ImportadorCambios,
    ImportadorDeOrden,
    ImportadorNuevo,
    ImportadorSalida,
    LoteDeOrden,
    OrdenCambios,
    OrdenDetalle,
    OrdenNueva,
    OrdenSalida,
)
from app.services import correlativos
from app.services.auditoria import aplicar_cambios, registrar_auditoria

CENTIMO = Decimal("0.01")

# ---------- Importadores ----------


def importador_visible(contexto: Contexto, importador_id: uuid.UUID) -> Importador:
    importador = contexto.sesion.get(Importador, importador_id)
    if importador is None or importador.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("El importador no existe.")
    return importador


def _importador_salida(i: Importador) -> ImportadorSalida:
    return ImportadorSalida(
        id=i.id,
        razon_social=i.razon_social,
        direccion=i.direccion,
        pais=i.pais,
        correo=i.correo,
        eori=i.eori,
        activo=i.activo,
    )


def importadores(contexto: Contexto) -> list[ImportadorSalida]:
    filas = contexto.sesion.scalars(
        select(Importador)
        .where(Importador.cooperativa_id == cooperativa_del_contexto(contexto))
        .order_by(Importador.razon_social)
    )
    return [_importador_salida(i) for i in filas]


def crear_importador(contexto: Contexto, datos: ImportadorNuevo) -> ImportadorSalida:
    importador = Importador(
        cooperativa_id=cooperativa_del_contexto(contexto), activo=True, **datos.model_dump()
    )
    contexto.sesion.add(importador)
    contexto.sesion.flush()
    registrar_auditoria(
        contexto, "importador.crear", "importador", importador.id, {"razon_social": importador.razon_social}
    )
    contexto.sesion.commit()
    return _importador_salida(importador)


def editar_importador(
    contexto: Contexto, importador_id: uuid.UUID, datos: ImportadorCambios
) -> ImportadorSalida:
    importador = importador_visible(contexto, importador_id)
    valores = datos.model_dump(exclude_unset=True)
    # El EORI es opcional: se puede borrar. El resto de los campos no se vacía.
    valores = {k: v for k, v in valores.items() if v is not None or k == "eori"}
    cambios = aplicar_cambios(importador, valores)
    if cambios:
        registrar_auditoria(contexto, "importador.editar", "importador", importador.id, cambios)
    contexto.sesion.commit()
    return _importador_salida(importador)


# ---------- Órdenes de compra ----------


def orden_visible(contexto: Contexto, orden_id: uuid.UUID, *, bloquear: bool = False) -> OrdenCompra:
    consulta = select(OrdenCompra).where(OrdenCompra.id == orden_id)
    if bloquear:
        consulta = consulta.with_for_update()
    orden = contexto.sesion.scalar(consulta)
    if orden is None or orden.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("La orden de compra no existe.")
    return orden


def limites(orden: OrdenCompra) -> tuple[Decimal, Decimal]:
    """Kilos mínimo y máximo que admite la tolerancia de la orden."""
    margen = (Decimal(orden.cantidad_kg) * Decimal(orden.tolerancia_pct) / 100).quantize(
        CENTIMO, rounding=ROUND_HALF_UP
    )
    return Decimal(orden.cantidad_kg) - margen, Decimal(orden.cantidad_kg) + margen


def lote_vigente(sesion: Session, orden_id: uuid.UUID) -> Lote | None:
    return sesion.scalar(select(Lote).where(Lote.orden_compra_id == orden_id, Lote.estado != "anulado"))


def _calidad_de_la_cooperativa(contexto: Contexto, calidad_id: uuid.UUID) -> Calidad:
    calidad = contexto.sesion.get(Calidad, calidad_id)
    if calidad is None or calidad.cooperativa_id != cooperativa_del_contexto(contexto) or not calidad.activo:
        raise error_api(422, "calidad_invalida", "Elige una calidad activa del catálogo de la cooperativa.")
    return calidad


def _importador_activo(contexto: Contexto, importador_id: uuid.UUID) -> Importador:
    importador = contexto.sesion.get(Importador, importador_id)
    if importador is None or importador.cooperativa_id != cooperativa_del_contexto(contexto):
        raise error_api(422, "importador_invalido", "El importador no existe en la cooperativa.")
    if not importador.activo:
        raise error_api(422, "importador_inactivo", "El importador está desactivado.")
    return importador


def _lote_de_orden(lote: Lote) -> LoteDeOrden:
    return LoteDeOrden(id=lote.id, codigo=lote.codigo, estado=lote.estado, masa_neta_kg=lote.masa_neta_kg)


def _salidas(sesion: Session, ordenes: list[OrdenCompra]) -> list[OrdenSalida]:
    if not ordenes:
        return []
    importadores_ = {
        i.id: i
        for i in sesion.scalars(
            select(Importador).where(Importador.id.in_({o.importador_id for o in ordenes}))
        )
    }
    calidades = {
        c.id: c
        for c in sesion.scalars(select(Calidad).where(Calidad.id.in_({o.calidad_id for o in ordenes})))
    }
    lotes = {
        lo.orden_compra_id: lo
        for lo in sesion.scalars(
            select(Lote).where(Lote.orden_compra_id.in_([o.id for o in ordenes]), Lote.estado != "anulado")
        )
    }
    salida = []
    for o in ordenes:
        i = importadores_[o.importador_id]
        lote = lotes.get(o.id)
        salida.append(
            OrdenSalida(
                id=o.id,
                codigo=o.codigo,
                importador=ImportadorDeOrden(id=i.id, razon_social=i.razon_social, pais=i.pais),
                referencia_importador=o.referencia_importador,
                cantidad_kg=o.cantidad_kg,
                tolerancia_pct=o.tolerancia_pct,
                calidad_id=o.calidad_id,
                calidad=calidades[o.calidad_id].nombre,
                partida_sa=o.partida_sa,
                pais_destino=o.pais_destino,
                lugar_destino=o.lugar_destino,
                fecha_entrega=o.fecha_entrega,
                estado=o.estado,
                creada_en=o.creado_en,
                lote=_lote_de_orden(lote) if lote else None,
            )
        )
    return salida


def listar(
    contexto: Contexto,
    *,
    estado: str | None = None,
    importador_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> list[OrdenSalida]:
    """Filtros por estado, importador y fecha de entrega."""
    consulta = select(OrdenCompra).where(OrdenCompra.cooperativa_id == cooperativa_del_contexto(contexto))
    if estado:
        consulta = consulta.where(OrdenCompra.estado == estado)
    if importador_id:
        consulta = consulta.where(OrdenCompra.importador_id == importador_id)
    if desde:
        consulta = consulta.where(OrdenCompra.fecha_entrega >= desde)
    if hasta:
        consulta = consulta.where(OrdenCompra.fecha_entrega <= hasta)
    ordenes = list(
        contexto.sesion.scalars(consulta.order_by(OrdenCompra.creado_en.desc(), OrdenCompra.codigo))
    )
    return _salidas(contexto.sesion, ordenes)


def obtener(contexto: Contexto, orden_id: uuid.UUID) -> OrdenDetalle:
    sesion = contexto.sesion
    orden = orden_visible(contexto, orden_id)
    base = _salidas(sesion, [orden])[0]
    minimo, maximo = limites(orden)
    creador = sesion.get(Perfil, orden.creada_por)
    anulados = sesion.scalars(
        select(Lote)
        .where(Lote.orden_compra_id == orden.id, Lote.estado == "anulado")
        .order_by(Lote.anulado_en.desc())
    )
    return OrdenDetalle(
        **base.model_dump(),
        creada_por_nombre=f"{creador.nombres} {creador.apellidos}".strip() if creador else None,
        anulada_en=orden.anulada_en,
        motivo_anulacion=orden.motivo_anulacion,
        minimo_kg=minimo,
        maximo_kg=maximo,
        lotes_anulados=[_lote_de_orden(lo) for lo in anulados],
    )


def crear(contexto: Contexto, datos: OrdenNueva) -> OrdenDetalle:
    sesion = contexto.sesion
    cooperativa_id = cooperativa_del_contexto(contexto)
    _importador_activo(contexto, datos.importador_id)
    _calidad_de_la_cooperativa(contexto, datos.calidad_id)
    momento = ahora()
    anio = momento.astimezone(LIMA).year
    numero = correlativos.siguiente(sesion, cooperativa_id, "orden", anio)
    orden = OrdenCompra(
        cooperativa_id=cooperativa_id,
        codigo=f"OC-{anio}-{numero:06d}",
        partida_sa=PARTIDA_SA,
        estado="abierta",
        creada_por=contexto.usuario_id,
        **datos.model_dump(),
    )
    sesion.add(orden)
    sesion.flush()
    registrar_auditoria(
        contexto,
        "orden.crear",
        "orden_compra",
        orden.id,
        {"codigo": orden.codigo, "cantidad_kg": orden.cantidad_kg, "importador_id": orden.importador_id},
    )
    sesion.commit()
    return obtener(contexto, orden.id)


def editar(contexto: Contexto, orden_id: uuid.UUID, datos: OrdenCambios) -> OrdenDetalle:
    orden = orden_visible(contexto, orden_id, bloquear=True)
    if orden.estado != "abierta":
        raise error_api(400, "orden_no_editable", "Solo se edita una orden abierta, sin lote confirmado.")
    valores = datos.model_dump(exclude_unset=True)
    # La referencia del importador es opcional: se puede borrar. El resto de los campos no se vacía.
    valores = {k: v for k, v in valores.items() if v is not None or k == "referencia_importador"}
    if "referencia_importador" in valores and not valores["referencia_importador"]:
        valores["referencia_importador"] = None
    if "importador_id" in valores:
        _importador_activo(contexto, valores["importador_id"])
    if "calidad_id" in valores:
        _calidad_de_la_cooperativa(contexto, valores["calidad_id"])
    cambios = aplicar_cambios(orden, valores)
    if cambios:
        registrar_auditoria(
            contexto, "orden.editar", "orden_compra", orden.id, {"codigo": orden.codigo} | cambios
        )
    contexto.sesion.commit()
    return obtener(contexto, orden.id)


def anular(contexto: Contexto, orden_id: uuid.UUID, motivo: str) -> OrdenDetalle:
    """Solo sin lote confirmado. Un lote en armado se anula con la orden, con el mismo motivo."""
    from app.services import lotes  # evita el import circular

    sesion = contexto.sesion
    orden = orden_visible(contexto, orden_id, bloquear=True)
    if orden.estado == "anulada":
        raise error_api(400, "orden_anulada", "La orden ya estaba anulada.")
    if orden.estado != "abierta":
        raise error_api(400, "orden_con_lote", "La orden tiene un lote confirmado: anula primero el lote.")
    momento = ahora()
    en_armado = lote_vigente(sesion, orden.id)
    if en_armado is not None:
        lotes.anular_en_armado(contexto, en_armado, motivo, momento)
    orden.estado = "anulada"
    orden.anulada_en = momento
    orden.anulada_por = contexto.usuario_id
    orden.motivo_anulacion = motivo
    registrar_auditoria(
        contexto,
        "orden.anular",
        "orden_compra",
        orden.id,
        {"codigo": orden.codigo, "motivo": motivo, "lote_anulado": en_armado.codigo if en_armado else None},
    )
    sesion.commit()
    return obtener(contexto, orden.id)

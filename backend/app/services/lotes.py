"""El lote de exportación (Parte 7): reúne el stock que cumple una orden de compra.

Nace en_armado con la sugerencia FIFO como selección. El usuario la acepta o la cambia; apartarse del orden
FIFO no se impide, pero exige un motivo escrito. Confirmar, en una sola transacción y con bloqueo de fila
sobre cada tanda final, descuenta los saldos, fija la masa neta, calcula la genealogía y deja el lote armado.
Anular un lote armado devuelve los saldos; su genealogía queda como historial.
"""

import uuid
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import LIMA, ahora
from app.models import (
    Calidad,
    Corrida,
    CorridaTanda,
    Dop,
    Dpp,
    Importador,
    Lote,
    LoteAsignacion,
    LoteGenealogia,
    OrdenCompra,
    Parcela,
    Perfil,
    Productor,
    Tanda,
    TandaFinal,
)
from app.models.exportacion import MOTIVO_DESVIACION_MINIMO
from app.schemas.exportacion import (
    Asignacion,
    AsignacionSalida,
    Candidata,
    Confirmacion,
    FilaGenealogia,
    Genealogia,
    Indicador,
    LoteDetalle,
    LoteSalida,
    ParcelaDeGenealogia,
    ProductorDeGenealogia,
    Seleccion,
    SugerenciaFifo,
)
from app.schemas.proceso import Referencia
from app.schemas.recepcion import ProductorDeTanda
from app.services import correlativos, geometria, ordenes, recomprobacion
from app.services.auditoria import registrar_auditoria

CENTIMO = Decimal("0.01")
DIEZMILESIMA = Decimal("0.0001")
SEIS = Decimal("0.000001")
CERO = Decimal("0")
# Un lote confirmado: las Partes 8 y 9 agregan estados después de armado.
NO_CONFIRMADOS = ("en_armado", "anulado")


def lote_visible(contexto: Contexto, lote_id: uuid.UUID, *, bloquear: bool = False) -> Lote:
    consulta = select(Lote).where(Lote.id == lote_id)
    if bloquear:
        consulta = consulta.with_for_update().execution_options(populate_existing=True)
    lote = contexto.sesion.scalar(consulta)
    if lote is None or lote.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("El lote no existe.")
    return lote


def _nombre(sesion: Session, perfil_id: uuid.UUID | None) -> str | None:
    perfil = sesion.get(Perfil, perfil_id) if perfil_id else None
    return f"{perfil.nombres} {perfil.apellidos}".strip() if perfil else None


# ---------- Sugerencia FIFO ----------


def _candidatas(sesion: Session, cooperativa_id: uuid.UUID, calidad_id: uuid.UUID) -> list[TandaFinal]:
    """Reglas 1 y 2: en stock, con saldo y de la calidad de la orden, de la más antigua a la más nueva."""
    return list(
        sesion.scalars(
            select(TandaFinal)
            .where(
                TandaFinal.cooperativa_id == cooperativa_id,
                TandaFinal.estado == "en_stock",
                TandaFinal.saldo_kg > 0,
                TandaFinal.calidad_id == calidad_id,
            )
            .order_by(TandaFinal.ingreso_stock_en, TandaFinal.codigo)
        )
    )


def sugerencia(
    sesion: Session, orden: OrdenCompra
) -> tuple[list[tuple[TandaFinal, Decimal]], list[TandaFinal]]:
    """Regla 3: el saldo de cada una, en orden, hasta completar la cantidad; la última puede quedar en parte.
    No reserva nada: se recalcula en cada consulta."""
    candidatas = _candidatas(sesion, orden.cooperativa_id, orden.calidad_id)
    # Parte 8: una tanda final retenida (cacao de una parcela excluida) no entra en la sugerencia.
    retenidas = recomprobacion.retenidas(sesion, [tf.id for tf in candidatas])
    candidatas = [tf for tf in candidatas if tf.id not in retenidas]
    falta = Decimal(orden.cantidad_kg)
    asignaciones = []
    for tf in candidatas:
        if falta <= 0:
            break
        kg = min(Decimal(tf.saldo_kg), falta)
        asignaciones.append((tf, kg))
        falta -= kg
    return asignaciones, candidatas


def _referencias(sesion: Session, tandas_finales: list[TandaFinal]):
    corridas = {
        c.id: c
        for c in sesion.scalars(
            select(Corrida).where(Corrida.id.in_({tf.corrida_id for tf in tandas_finales}))
        )
    }
    dpps = {
        d.tanda_final_id: d
        for d in sesion.scalars(
            select(Dpp).where(
                Dpp.tanda_final_id.in_([tf.id for tf in tandas_finales]), Dpp.estado == "vigente"
            )
        )
    }
    return corridas, dpps


def _de_lote(tf: TandaFinal, corridas: dict, dpps: dict) -> dict[str, Any]:
    dpp = dpps.get(tf.id)
    return {
        "tanda_final_id": tf.id,
        "codigo": tf.codigo,
        "corrida_codigo": corridas[tf.corrida_id].codigo,
        "calidad": tf.calidad,
        "ingreso_stock_en": tf.ingreso_stock_en,
        "saldo_kg": tf.saldo_kg,
        "estado": tf.estado,
        "dpp": Referencia(id=dpp.id, codigo=dpp.codigo, estado=dpp.estado) if dpp else None,
    }


def sugerencia_fifo(contexto: Contexto, lote_id: uuid.UUID) -> SugerenciaFifo:
    sesion = contexto.sesion
    lote = lote_visible(contexto, lote_id)
    orden = sesion.get(OrdenCompra, lote.orden_compra_id)
    asignaciones, candidatas = sugerencia(sesion, orden)
    minimo, maximo = ordenes.limites(orden)
    disponible = sum((Decimal(tf.saldo_kg) for tf in candidatas), CERO)
    total = sum((kg for _, kg in asignaciones), CERO)
    sugeridos = {tf.id: kg for tf, kg in asignaciones}
    corridas, dpps = _referencias(sesion, candidatas)
    return SugerenciaFifo(
        cantidad_kg=orden.cantidad_kg,
        minimo_kg=minimo,
        maximo_kg=maximo,
        disponible_kg=disponible,
        total_kg=total,
        faltan_kg=max(Decimal(orden.cantidad_kg) - total, CERO),
        alcanza=disponible >= minimo,
        asignaciones=[Asignacion(tanda_final_id=tf.id, kg_asignados=kg) for tf, kg in asignaciones],
        candidatas=[
            Candidata(**_de_lote(tf, corridas, dpps), kg_sugeridos=sugeridos.get(tf.id, CERO))
            for tf in candidatas
        ],
    )


# ---------- Listas y detalle ----------


def _asignaciones(sesion: Session, lote: Lote) -> list[tuple[LoteAsignacion, TandaFinal]]:
    filas = list(sesion.scalars(select(LoteAsignacion).where(LoteAsignacion.lote_id == lote.id)))
    finales = {
        tf.id: tf
        for tf in sesion.scalars(
            select(TandaFinal).where(TandaFinal.id.in_([a.tanda_final_id for a in filas]))
        )
    }
    pares = [(a, finales[a.tanda_final_id]) for a in filas]
    return sorted(pares, key=lambda p: (p[1].ingreso_stock_en, p[1].codigo))


def _filas_genealogia(sesion: Session, lote_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[LoteGenealogia]]:
    resultado: dict[uuid.UUID, list[LoteGenealogia]] = defaultdict(list)
    if lote_ids:
        for g in sesion.scalars(select(LoteGenealogia).where(LoteGenealogia.lote_id.in_(lote_ids))):
            resultado[g.lote_id].append(g)
    return resultado


def _salidas(sesion: Session, lotes: list[Lote]) -> list[LoteSalida]:
    if not lotes:
        return []
    ordenes_ = {
        o.id: o
        for o in sesion.scalars(
            select(OrdenCompra).where(OrdenCompra.id.in_({lo.orden_compra_id for lo in lotes}))
        )
    }
    importadores = {
        i.id: i
        for i in sesion.scalars(
            select(Importador).where(Importador.id.in_({o.importador_id for o in ordenes_.values()}))
        )
    }
    calidades = {
        c.id: c
        for c in sesion.scalars(
            select(Calidad).where(Calidad.id.in_({o.calidad_id for o in ordenes_.values()}))
        )
    }
    seleccionado: dict[uuid.UUID, Decimal] = defaultdict(lambda: CERO)
    for a in sesion.scalars(
        select(LoteAsignacion).where(LoteAsignacion.lote_id.in_([lo.id for lo in lotes]))
    ):
        seleccionado[a.lote_id] += Decimal(a.kg_asignados)
    genealogias = _filas_genealogia(sesion, [lo.id for lo in lotes if lo.estado != "en_armado"])
    salida = []
    for lo in lotes:
        o = ordenes_[lo.orden_compra_id]
        filas = genealogias.get(lo.id)
        salida.append(
            LoteSalida(
                id=lo.id,
                codigo=lo.codigo,
                estado=lo.estado,
                orden=Referencia(id=o.id, codigo=o.codigo, estado=o.estado),
                importador=importadores[o.importador_id].razon_social,
                calidad=calidades[o.calidad_id].nombre,
                cantidad_kg=o.cantidad_kg,
                masa_neta_kg=lo.masa_neta_kg,
                seleccionado_kg=lo.masa_neta_kg if lo.masa_neta_kg is not None else seleccionado[lo.id],
                numero_parcelas=len({g.parcela_id for g in filas}) if filas else None,
                desviacion_fifo=lo.desviacion_fifo,
                creado_en=lo.creado_en,
                armado_en=lo.armado_en,
            )
        )
    return salida


def listar(contexto: Contexto, estado: str | None = None) -> list[LoteSalida]:
    consulta = select(Lote).where(Lote.cooperativa_id == cooperativa_del_contexto(contexto))
    if estado:
        consulta = consulta.where(Lote.estado == estado)
    lotes = list(contexto.sesion.scalars(consulta.order_by(Lote.creado_en.desc(), Lote.codigo.desc())))
    return _salidas(contexto.sesion, lotes)


def obtener(contexto: Contexto, lote_id: uuid.UUID) -> LoteDetalle:
    sesion = contexto.sesion
    lote = lote_visible(contexto, lote_id)
    base = _salidas(sesion, [lote])[0]
    orden = sesion.get(OrdenCompra, lote.orden_compra_id)
    minimo, maximo = ordenes.limites(orden)
    pares = _asignaciones(sesion, lote)
    corridas, dpps = _referencias(sesion, [tf for _, tf in pares])
    ultima = recomprobacion.ultima(sesion, lote.id)
    indicadores_ = None
    if lote.estado != "en_armado":
        indicadores_ = indicadores(sesion, lote, _filas_genealogia(sesion, [lote.id]).get(lote.id, []))
    return LoteDetalle(
        **base.model_dump(),
        tolerancia_pct=orden.tolerancia_pct,
        minimo_kg=minimo,
        maximo_kg=maximo,
        motivo_desviacion=lote.motivo_desviacion,
        creado_por_nombre=_nombre(sesion, lote.creado_por),
        armado_por_nombre=_nombre(sesion, lote.armado_por),
        anulado_en=lote.anulado_en,
        anulado_por_nombre=_nombre(sesion, lote.anulado_por),
        motivo_anulacion=lote.motivo_anulacion,
        asignaciones=[
            AsignacionSalida(**_de_lote(tf, corridas, dpps), kg_asignados=a.kg_asignados) for a, tf in pares
        ],
        indicadores=indicadores_,
        alertas=lote.alertas or [],
        recomprobacion=recomprobacion.salida(sesion, ultima) if ultima else None,
        dex=_dex_de(sesion, lote.id),
    )


def _dex_de(sesion: Session, lote_id: uuid.UUID) -> Referencia | None:
    from app.services import dex  # evita importación circular

    fila = dex.de_lote(sesion, lote_id)
    return Referencia(id=fila.id, codigo=fila.codigo, estado=fila.estado) if fila else None


# ---------- Crear y cambiar la selección ----------


def crear(contexto: Contexto, orden_id: uuid.UUID) -> LoteDetalle:
    """El lote nace en_armado con la sugerencia FIFO como selección inicial."""
    sesion = contexto.sesion
    orden = ordenes.orden_visible(contexto, orden_id, bloquear=True)
    if orden.estado != "abierta":
        raise error_api(400, "orden_no_abierta", "Solo una orden abierta recibe un lote.")
    if ordenes.lote_vigente(sesion, orden.id) is not None:
        raise error_api(409, "lote_existente", "La orden ya tiene un lote. Anúlalo para armar otro.")
    momento = ahora()
    anio = momento.astimezone(LIMA).year
    numero = correlativos.siguiente(sesion, orden.cooperativa_id, "lote", anio)
    lote = Lote(
        cooperativa_id=orden.cooperativa_id,
        codigo=f"LE-{anio}-{numero:06d}",
        orden_compra_id=orden.id,
        estado="en_armado",
        desviacion_fifo=False,
        creado_por=contexto.usuario_id,
    )
    sesion.add(lote)
    try:
        sesion.flush()
    except IntegrityError as exc:
        sesion.rollback()
        raise error_api(409, "lote_existente", "La orden ya tiene un lote. Anúlalo para armar otro.") from exc
    asignaciones, _ = sugerencia(sesion, orden)
    for tf, kg in asignaciones:
        sesion.add(LoteAsignacion(lote_id=lote.id, tanda_final_id=tf.id, kg_asignados=kg))
    registrar_auditoria(
        contexto,
        "lote.crear",
        "lote",
        lote.id,
        {
            "codigo": lote.codigo,
            "orden": orden.codigo,
            "sugerencia": [{"tanda_final": tf.codigo, "kg": kg} for tf, kg in asignaciones],
        },
    )
    sesion.commit()
    return obtener(contexto, lote.id)


def _no_retenida(tf: TandaFinal, retenidas: set[uuid.UUID]) -> None:
    if tf.id in retenidas:
        raise error_api(
            400,
            "stock_retenido",
            f"La tanda final {tf.codigo} está retenida: tiene cacao de una parcela excluida y no se "
            "puede usar.",
        )


def _exigir_en_armado(lote: Lote) -> None:
    if lote.estado != "en_armado":
        raise error_api(400, "lote_no_en_armado", "La selección solo cambia mientras el lote está en armado.")


def _tandas_finales(
    sesion: Session, ids: list[uuid.UUID], *, bloquear: bool = False
) -> dict[uuid.UUID, TandaFinal]:
    if not ids:
        return {}
    consulta = select(TandaFinal).where(TandaFinal.id.in_(ids)).order_by(TandaFinal.id)
    if bloquear:
        # Bloqueo de fila en orden fijo: dos lotes que confirman a la vez se esperan sin bloquearse entre sí.
        consulta = consulta.with_for_update().execution_options(populate_existing=True)
    return {tf.id: tf for tf in sesion.scalars(consulta)}


def cambiar_seleccion(contexto: Contexto, lote_id: uuid.UUID, datos: Seleccion) -> LoteDetalle:
    """Reemplaza la selección: quitar, agregar de la misma calidad o cambiar los kilos."""
    sesion = contexto.sesion
    lote = lote_visible(contexto, lote_id, bloquear=True)
    _exigir_en_armado(lote)
    orden = sesion.get(OrdenCompra, lote.orden_compra_id)
    ids = [a.tanda_final_id for a in datos.asignaciones]
    if len(ids) != len(set(ids)):
        raise error_api(422, "tanda_final_repetida", "Cada tanda final va una sola vez en la selección.")
    finales = _tandas_finales(sesion, ids)
    retenidas = recomprobacion.retenidas(sesion, ids)
    for a in datos.asignaciones:
        tf = finales.get(a.tanda_final_id)
        if tf is None or tf.cooperativa_id != lote.cooperativa_id:
            raise error_api(422, "tanda_final_invalida", "La tanda final no existe en la cooperativa.")
        _no_retenida(tf, retenidas)
        if tf.calidad_id != orden.calidad_id:
            raise error_api(
                400,
                "calidad_no_coincide",
                f"La tanda final {tf.codigo} no es de la calidad que pide la orden.",
            )
        if tf.estado != "en_stock":
            raise error_api(400, "tanda_final_no_disponible", f"La tanda final {tf.codigo} no está en stock.")
        if a.kg_asignados > tf.saldo_kg:
            raise error_api(
                422,
                "kg_mayor_que_saldo",
                f"La tanda final {tf.codigo} tiene {tf.saldo_kg} kg de saldo: no se pueden tomar "
                f"{a.kg_asignados}.",
            )
    antes = {
        str(a.tanda_final_id): str(a.kg_asignados)
        for a in sesion.scalars(select(LoteAsignacion).where(LoteAsignacion.lote_id == lote.id))
    }
    for a in sesion.scalars(select(LoteAsignacion).where(LoteAsignacion.lote_id == lote.id)):
        sesion.delete(a)
    sesion.flush()
    for a in datos.asignaciones:
        sesion.add(
            LoteAsignacion(lote_id=lote.id, tanda_final_id=a.tanda_final_id, kg_asignados=a.kg_asignados)
        )
    despues = {str(a.tanda_final_id): str(a.kg_asignados) for a in datos.asignaciones}
    if antes != despues:
        codigos = {
            str(tf.id): tf.codigo for tf in _tandas_finales(sesion, [uuid.UUID(k) for k in antes]).values()
        }
        codigos |= {str(tf.id): tf.codigo for tf in finales.values()}
        registrar_auditoria(
            contexto,
            "lote.cambiar_seleccion",
            "lote",
            lote.id,
            {
                "codigo": lote.codigo,
                "antes": {codigos[k]: v for k, v in antes.items()},
                "despues": {codigos[k]: v for k, v in despues.items()},
            },
        )
    sesion.commit()
    return obtener(contexto, lote.id)


# ---------- Genealogía e indicadores ----------


def _ajustar(valores: list[Decimal], total: Decimal) -> list[Decimal]:
    """La fila más grande absorbe la diferencia de redondeo, para que la suma sea exactamente el total."""
    if not valores:
        return valores
    mayor = max(range(len(valores)), key=lambda i: valores[i])
    valores[mayor] += total - sum(valores, CERO)
    return valores


def calcular_genealogia(
    sesion: Session, pares: list[tuple[TandaFinal, Decimal]], masa: Decimal
) -> list[dict[str, Any]]:
    """Por cada asignación, los kilos tomados de la tanda final por la proporción de cada tanda en su corrida
    (Parte 6). Cada tanda lleva a su DOP, a su parcela y a su productor."""
    filas_corrida: dict[uuid.UUID, list[CorridaTanda]] = defaultdict(list)
    corrida_ids = {tf.corrida_id for tf, _ in pares}
    for ct in sesion.scalars(
        select(CorridaTanda)
        .where(CorridaTanda.corrida_id.in_(corrida_ids), CorridaTanda.liberada_en.is_(None))
        .order_by(CorridaTanda.agregada_en, CorridaTanda.id)
    ):
        filas_corrida[ct.corrida_id].append(ct)
    tanda_ids = [ct.tanda_id for filas in filas_corrida.values() for ct in filas]
    tandas = {t.id: t for t in sesion.scalars(select(Tanda).where(Tanda.id.in_(tanda_ids)))}
    dops: dict[uuid.UUID, Dop] = {}
    # El DOP vigente de cada tanda; si no lo hubiera, el último emitido (no se pierde el origen).
    for d in sesion.scalars(select(Dop).where(Dop.tanda_id.in_(tanda_ids)).order_by(Dop.emitido_en)):
        if d.tanda_id not in dops or d.estado == "vigente" or dops[d.tanda_id].estado != "vigente":
            dops[d.tanda_id] = d
    dpps = {
        d.tanda_final_id: d
        for d in sesion.scalars(
            select(Dpp).where(Dpp.tanda_final_id.in_([tf.id for tf, _ in pares]), Dpp.estado == "vigente")
        )
    }
    filas = []
    for tf, kg in pares:
        dpp = dpps.get(tf.id)
        if dpp is None:
            raise error_api(
                400, "tanda_final_sin_dpp", f"La tanda final {tf.codigo} no tiene un DPP vigente."
            )
        origen = filas_corrida[tf.corrida_id]
        if not origen or any(ct.proporcion is None for ct in origen):
            raise error_api(
                400,
                "corrida_sin_proporciones",
                f"La corrida de la tanda final {tf.codigo} no fijó sus proporciones.",
            )
        for ct in origen:
            t = tandas[ct.tanda_id]
            filas.append(
                {
                    "tanda_final_id": tf.id,
                    "dpp_id": dpp.id,
                    "tanda_id": t.id,
                    "dop_id": dops[t.id].id,
                    "parcela_id": t.parcela_id,
                    "productor_id": t.productor_id,
                    "kg_atribuidos": (Decimal(kg) * Decimal(ct.proporcion)).quantize(
                        DIEZMILESIMA, rounding=ROUND_HALF_UP
                    ),
                }
            )
    kilos = _ajustar([f["kg_atribuidos"] for f in filas], Decimal(masa))
    proporciones = _ajustar(
        [(k / Decimal(masa)).quantize(SEIS, rounding=ROUND_HALF_UP) for k in kilos], Decimal("1.000000")
    )
    for fila, k, p in zip(filas, kilos, proporciones, strict=True):
        fila["kg_atribuidos"] = k
        fila["proporcion_lote"] = p
    return filas


def _pct(parte: Decimal, total: Decimal) -> Decimal:
    if not total:
        return CERO
    return (Decimal(parte) * 100 / Decimal(total)).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def indicadores(sesion: Session, lote: Lote, filas: list[LoteGenealogia]) -> list[Indicador]:
    """Se calculan y se muestran tal cual: ninguno aprueba ni desaprueba el lote. Pasan al informe de
    hallazgos de la Parte 9."""
    masa = Decimal(lote.masa_neta_kg or 0)
    suma = sum((Decimal(f.kg_atribuidos) for f in filas), CERO)
    por_parcela: dict[uuid.UUID, Decimal] = defaultdict(lambda: CERO)
    for f in filas:
        por_parcela[f.parcela_id] += Decimal(f.kg_atribuidos)
    mayores = sorted(por_parcela.values(), reverse=True)
    vigentes = {
        d.id
        for d in sesion.scalars(
            select(Dop).where(Dop.id.in_({f.dop_id for f in filas}), Dop.estado == "vigente")
        )
    }
    cubierto = sum((Decimal(f.kg_atribuidos) for f in filas if f.dop_id in vigentes), CERO)
    finales = {
        tf.id: tf.corrida_id
        for tf in sesion.scalars(
            select(TandaFinal).where(TandaFinal.id.in_({f.tanda_final_id for f in filas}))
        )
    }
    corridas = {
        c.id: c.tipo_manejo
        for c in sesion.scalars(select(Corrida).where(Corrida.id.in_(set(finales.values()))))
    }
    return [
        Indicador(
            clave="balance_masa",
            nombre="Balance de masa",
            valor={"masa_neta_kg": masa, "suma_atribuida_kg": suma, "diferencia_kg": masa - suma},
            explicacion="Masa neta del lote, suma de los kilos atribuidos a sus tandas de origen y su "
            "diferencia, que debe ser cero.",
        ),
        Indicador(
            clave="numero_parcelas",
            nombre="Parcelas de origen",
            valor=len(por_parcela),
            explicacion="Cuántas parcelas distintas aportan cacao al lote.",
        ),
        Indicador(
            clave="numero_productores",
            nombre="Productores de origen",
            valor=len({f.productor_id for f in filas}),
            explicacion="Cuántos productores distintos aportan cacao al lote.",
        ),
        Indicador(
            clave="numero_dops",
            nombre="DOP de origen",
            valor=len({f.dop_id for f in filas}),
            explicacion="Cuántos documentos de origen distintos respaldan el cacao del lote.",
        ),
        Indicador(
            clave="corridas_mezcladas",
            nombre="Corridas mezcladas",
            valor={
                "mezcladas": sum(1 for t in corridas.values() if t == "mezclado"),
                "corridas": len(corridas),
            },
            explicacion="Cuántas de las corridas de origen mezclaron tandas de varios productores.",
        ),
        Indicador(
            clave="cobertura_genealogia_pct",
            nombre="Cobertura de la genealogía",
            valor=_pct(cubierto, masa),
            explicacion="Porcentaje de la masa del lote que llega hasta un DOP vigente.",
        ),
        Indicador(
            clave="concentracion_mayor_parcela_pct",
            nombre="Concentración en la mayor parcela",
            valor=_pct(mayores[0] if mayores else CERO, masa),
            explicacion="Parte del lote que viene de la parcela que más aporta.",
        ),
        Indicador(
            clave="concentracion_tres_parcelas_pct",
            nombre="Concentración en las tres mayores parcelas",
            valor=_pct(sum(mayores[:3], CERO), masa),
            explicacion="Parte del lote que viene de las tres parcelas que más aportan.",
        ),
        Indicador(
            clave="desviacion_fifo",
            nombre="Desviación del orden FIFO",
            valor={"desviacion": lote.desviacion_fifo, "motivo": lote.motivo_desviacion},
            explicacion="Si la selección se apartó del orden de ingreso al stock, con el motivo escrito.",
        ),
    ]


# ---------- Confirmar y anular ----------


def confirmar(contexto: Contexto, lote_id: uuid.UUID, datos: Confirmacion) -> LoteDetalle:
    sesion = contexto.sesion
    lote = lote_visible(contexto, lote_id, bloquear=True)
    _exigir_en_armado(lote)
    orden = ordenes.orden_visible(contexto, lote.orden_compra_id, bloquear=True)
    if orden.estado != "abierta":
        raise error_api(400, "orden_no_abierta", "La orden del lote no está abierta.")
    seleccion = list(sesion.scalars(select(LoteAsignacion).where(LoteAsignacion.lote_id == lote.id)))
    if not seleccion:
        raise error_api(400, "lote_sin_seleccion", "El lote no tiene tandas finales seleccionadas.")
    finales = _tandas_finales(sesion, [a.tanda_final_id for a in seleccion], bloquear=True)
    retenidas = recomprobacion.retenidas(sesion, list(finales))
    for a in seleccion:
        tf = finales[a.tanda_final_id]
        _no_retenida(tf, retenidas)
        if tf.calidad_id != orden.calidad_id:
            raise error_api(
                400,
                "calidad_no_coincide",
                f"La tanda final {tf.codigo} no es de la calidad que pide la orden.",
            )
        if tf.estado == "anulada":
            raise error_api(400, "tanda_final_no_disponible", f"La tanda final {tf.codigo} fue anulada.")
        if tf.estado != "en_stock" or Decimal(tf.saldo_kg) < Decimal(a.kg_asignados):
            raise error_api(
                409,
                "saldo_insuficiente",
                f"La tanda final {tf.codigo} ya no tiene saldo para {a.kg_asignados} kg: otro lote se "
                "confirmó antes. Revisa la selección.",
            )
    masa = sum((Decimal(a.kg_asignados) for a in seleccion), CERO)
    minimo, maximo = ordenes.limites(orden)
    if not minimo <= masa <= maximo:
        raise error_api(
            400,
            "masa_fuera_de_tolerancia",
            f"La selección suma {masa} kg y la orden admite de {minimo} a {maximo} kg.",
        )
    # La sugerencia FIFO de este momento, con los saldos ya bloqueados.
    sugeridas, _ = sugerencia(sesion, orden)
    desviacion = {tf.id: Decimal(kg) for tf, kg in sugeridas} != {
        a.tanda_final_id: Decimal(a.kg_asignados) for a in seleccion
    }
    motivo = (datos.motivo_desviacion or "").strip() or None
    if desviacion and (motivo is None or len(motivo) < MOTIVO_DESVIACION_MINIMO):
        raise error_api(
            422,
            "motivo_desviacion_requerido",
            f"La selección se aparta del orden FIFO: escribe el motivo (mínimo {MOTIVO_DESVIACION_MINIMO} "
            "caracteres).",
        )
    pares = [(finales[a.tanda_final_id], Decimal(a.kg_asignados)) for a in seleccion]
    filas = calcular_genealogia(sesion, pares, masa)
    for tf, kg in pares:
        tf.saldo_kg = Decimal(tf.saldo_kg) - kg
        if tf.saldo_kg == 0:
            tf.estado = "agotada"
    for fila in filas:
        sesion.add(LoteGenealogia(lote_id=lote.id, **fila))
    momento = ahora()
    lote.estado = "armado"
    lote.masa_neta_kg = masa
    lote.desviacion_fifo = desviacion
    lote.motivo_desviacion = motivo if desviacion else None
    lote.armado_por = contexto.usuario_id
    lote.armado_en = momento
    orden.estado = "con_lote"
    registrar_auditoria(
        contexto,
        "lote.confirmar",
        "lote",
        lote.id,
        {
            "codigo": lote.codigo,
            "orden": orden.codigo,
            "masa_neta_kg": masa,
            "asignaciones": {tf.codigo: kg for tf, kg in pares},
            "desviacion_fifo": desviacion,
            "motivo_desviacion": lote.motivo_desviacion,
            "parcelas": len({f["parcela_id"] for f in filas}),
        },
    )
    sesion.commit()
    return obtener(contexto, lote.id)


def anular_en_armado(contexto: Contexto, lote: Lote, motivo: str, momento: datetime) -> None:
    """Anula un lote en armado dentro de la transacción de quien llama (la anulación de su orden)."""
    lote.estado = "anulado"
    lote.anulado_en = momento
    lote.anulado_por = contexto.usuario_id
    lote.motivo_anulacion = motivo
    registrar_auditoria(
        contexto,
        "lote.anular",
        "lote",
        lote.id,
        {"codigo": lote.codigo, "motivo": motivo, "estaba": "en_armado"},
    )


def anular(contexto: Contexto, lote_id: uuid.UUID, motivo: str) -> LoteDetalle:
    """Un lote confirmado (armado, bloqueado o listo) devuelve sus saldos: las tandas finales agotadas vuelven
    al stock y la orden queda abierta. Su genealogía se conserva como historial. Un lote bloqueado o listo
    solo lo anula un administrador (Parte 8); uno cerrado, con DEX, ya no se anula por esta vía."""
    sesion = contexto.sesion
    lote = lote_visible(contexto, lote_id, bloquear=True)
    if lote.estado == "anulado":
        raise error_api(400, "lote_anulado", "El lote ya estaba anulado.")
    if lote.estado not in ("en_armado", "armado", "bloqueado", "listo"):
        raise error_api(400, "lote_no_anulable", "Este lote ya no se anula por esta vía.")
    if lote.estado in ("bloqueado", "listo") and contexto.rol != "admin_cooperativa":
        raise error_api(
            403, "solo_administrador", "Un lote bloqueado o listo solo lo anula un administrador."
        )
    momento = ahora()
    if lote.estado == "en_armado":
        anular_en_armado(contexto, lote, motivo, momento)
        sesion.commit()
        return obtener(contexto, lote.id)
    estaba = lote.estado
    orden = ordenes.orden_visible(contexto, lote.orden_compra_id, bloquear=True)
    seleccion = list(sesion.scalars(select(LoteAsignacion).where(LoteAsignacion.lote_id == lote.id)))
    finales = _tandas_finales(sesion, [a.tanda_final_id for a in seleccion], bloquear=True)
    devueltos = {}
    for a in seleccion:
        tf = finales[a.tanda_final_id]
        tf.saldo_kg = Decimal(tf.saldo_kg) + Decimal(a.kg_asignados)
        if tf.estado == "agotada":
            tf.estado = "en_stock"
        devueltos[tf.codigo] = a.kg_asignados
    lote.estado = "anulado"
    lote.anulado_en = momento
    lote.anulado_por = contexto.usuario_id
    lote.motivo_anulacion = motivo
    if orden.estado == "con_lote":
        orden.estado = "abierta"
    registrar_auditoria(
        contexto,
        "lote.anular",
        "lote",
        lote.id,
        {"codigo": lote.codigo, "motivo": motivo, "estaba": estaba, "saldos_devueltos": devueltos},
    )
    sesion.commit()
    return obtener(contexto, lote.id)


# ---------- Vista de genealogía ----------


def genealogia(contexto: Contexto, lote_id: uuid.UUID) -> Genealogia:
    sesion = contexto.sesion
    lote = lote_visible(contexto, lote_id)
    if lote.estado == "en_armado":
        raise error_api(400, "lote_en_armado", "La genealogía se calcula al confirmar el lote.")
    filas = _filas_genealogia(sesion, [lote.id]).get(lote.id, [])
    finales = {
        tf.id: tf
        for tf in sesion.scalars(
            select(TandaFinal).where(TandaFinal.id.in_({f.tanda_final_id for f in filas}))
        )
    }
    corridas = {
        c.id: c
        for c in sesion.scalars(
            select(Corrida).where(Corrida.id.in_({tf.corrida_id for tf in finales.values()}))
        )
    }
    dpps = {d.id: d for d in sesion.scalars(select(Dpp).where(Dpp.id.in_({f.dpp_id for f in filas})))}
    tandas = {t.id: t for t in sesion.scalars(select(Tanda).where(Tanda.id.in_({f.tanda_id for f in filas})))}
    dops = {d.id: d for d in sesion.scalars(select(Dop).where(Dop.id.in_({f.dop_id for f in filas})))}
    parcelas = {
        p.id: p for p in sesion.scalars(select(Parcela).where(Parcela.id.in_({f.parcela_id for f in filas})))
    }
    productores = {
        p.id: p
        for p in sesion.scalars(select(Productor).where(Productor.id.in_({f.productor_id for f in filas})))
    }

    def productor(pid: uuid.UUID) -> ProductorDeTanda:
        p = productores[pid]
        return ProductorDeTanda(id=p.id, dni=p.dni, nombres=p.nombres, apellidos=p.apellidos)

    masa = Decimal(lote.masa_neta_kg)
    salida_filas = []
    kg_parcela: dict[uuid.UUID, Decimal] = defaultdict(lambda: CERO)
    kg_productor: dict[uuid.UUID, Decimal] = defaultdict(lambda: CERO)
    parcelas_productor: dict[uuid.UUID, set] = defaultdict(set)
    for f in sorted(filas, key=lambda f: (-Decimal(f.kg_atribuidos), str(f.id))):
        tf = finales[f.tanda_final_id]
        corrida = corridas[tf.corrida_id]
        tanda = tandas[f.tanda_id]
        dpp, dop = dpps[f.dpp_id], dops[f.dop_id]
        salida_filas.append(
            FilaGenealogia(
                tanda_final=Referencia(id=tf.id, codigo=tf.codigo, estado=tf.estado),
                dpp=Referencia(id=dpp.id, codigo=dpp.codigo, estado=dpp.estado),
                corrida=Referencia(id=corrida.id, codigo=corrida.codigo, estado=corrida.estado),
                tipo_manejo=corrida.tipo_manejo,
                tanda=Referencia(id=tanda.id, codigo=tanda.codigo, estado=tanda.estado),
                dop=Referencia(id=dop.id, codigo=dop.codigo, estado=dop.estado),
                parcela_id=f.parcela_id,
                parcela_codigo=parcelas[f.parcela_id].codigo,
                productor_id=f.productor_id,
                kg_atribuidos=f.kg_atribuidos,
                proporcion_lote=f.proporcion_lote,
            )
        )
        kg_parcela[f.parcela_id] += Decimal(f.kg_atribuidos)
        kg_productor[f.productor_id] += Decimal(f.kg_atribuidos)
        parcelas_productor[f.productor_id].add(f.parcela_id)
    por_parcela = [
        ParcelaDeGenealogia(
            parcela_id=pid,
            codigo=parcelas[pid].codigo,
            nombre=parcelas[pid].nombre,
            productor=productor(parcelas[pid].productor_id),
            kg=kg,
            proporcion=(kg / masa).quantize(SEIS, rounding=ROUND_HALF_UP),
            geometria=geometria.a_geojson(to_shape(parcelas[pid].geometria)),
        )
        for pid, kg in sorted(kg_parcela.items(), key=lambda par: (-par[1], parcelas[par[0]].codigo))
    ]
    por_productor = [
        ProductorDeGenealogia(
            productor=productor(pid),
            numero_parcelas=len(parcelas_productor[pid]),
            kg=kg,
            proporcion=(kg / masa).quantize(SEIS, rounding=ROUND_HALF_UP),
        )
        for pid, kg in sorted(kg_productor.items(), key=lambda par: -par[1])
    ]
    return Genealogia(
        lote=Referencia(id=lote.id, codigo=lote.codigo, estado=lote.estado),
        anulada=lote.estado == "anulado",
        masa_neta_kg=masa,
        filas=salida_filas,
        por_parcela=por_parcela,
        por_productor=por_productor,
        indicadores=indicadores(sesion, lote, filas),
    )

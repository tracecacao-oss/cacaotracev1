"""Trazabilidad hacia adelante (Parte 7): desde una parcela, un productor o un DOP, las tandas, sus DOP, las
corridas, las tandas finales y los lotes de exportación donde terminó su cacao, con kilos.

Los kilos en cada lote salen de la genealogía guardada al confirmarlo; no se estiman.
"""

import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import no_encontrado
from app.models import (
    Corrida,
    CorridaTanda,
    Dop,
    Lote,
    LoteGenealogia,
    OrdenCompra,
    Parcela,
    Productor,
    Tanda,
    TandaFinal,
)
from app.schemas.exportacion import LoteDeRecorrido, Recorrido, TandaDeRecorrido
from app.schemas.proceso import Referencia
from app.schemas.recepcion import ProductorDeTanda
from app.services import dops as servicio_dops
from app.services import parcelas as servicio_parcelas
from app.services import productores as servicio_productores

CENTIMO = Decimal("0.01")
CERO = Decimal("0")


def _tandas_de(sesion: Session, cooperativa_id: uuid.UUID, **filtro) -> list[Tanda]:
    consulta = select(Tanda).where(Tanda.cooperativa_id == cooperativa_id)
    for campo, valor in filtro.items():
        consulta = consulta.where(getattr(Tanda, campo) == valor)
    return list(sesion.scalars(consulta.order_by(Tanda.recibida_en)))


def _recorrido(sesion: Session, tandas: list[Tanda]) -> tuple[list[TandaDeRecorrido], list, list, Decimal]:
    ids = [t.id for t in tandas]
    if not ids:
        return [], [], [], CERO
    productores = {
        p.id: p
        for p in sesion.scalars(select(Productor).where(Productor.id.in_({t.productor_id for t in tandas})))
    }
    parcelas = {
        p.id: p for p in sesion.scalars(select(Parcela).where(Parcela.id.in_({t.parcela_id for t in tandas})))
    }
    dops: dict[uuid.UUID, Dop] = {}
    for d in sesion.scalars(select(Dop).where(Dop.tanda_id.in_(ids)).order_by(Dop.emitido_en)):
        if d.tanda_id not in dops or d.estado == "vigente" or dops[d.tanda_id].estado != "vigente":
            dops[d.tanda_id] = d
    # La corrida donde está la tanda (no liberada), con su proporción.
    en_corrida = {
        ct.tanda_id: ct
        for ct in sesion.scalars(
            select(CorridaTanda).where(CorridaTanda.tanda_id.in_(ids), CorridaTanda.liberada_en.is_(None))
        )
    }
    corridas = {
        c.id: c
        for c in sesion.scalars(
            select(Corrida).where(Corrida.id.in_({ct.corrida_id for ct in en_corrida.values()}))
        )
    }
    finales = {
        tf.corrida_id: tf
        for tf in sesion.scalars(
            select(TandaFinal).where(
                TandaFinal.corrida_id.in_(list(corridas)), TandaFinal.estado != "anulada"
            )
        )
    }
    genealogia: dict[uuid.UUID, dict[uuid.UUID, Decimal]] = defaultdict(lambda: defaultdict(lambda: CERO))
    for g in sesion.scalars(select(LoteGenealogia).where(LoteGenealogia.tanda_id.in_(ids))):
        genealogia[g.tanda_id][g.lote_id] += Decimal(g.kg_atribuidos)
    lote_ids = {lid for por_lote in genealogia.values() for lid in por_lote}
    lotes = {lo.id: lo for lo in sesion.scalars(select(Lote).where(Lote.id.in_(lote_ids)))}
    ordenes = {
        o.id: o
        for o in sesion.scalars(
            select(OrdenCompra).where(OrdenCompra.id.in_({lo.orden_compra_id for lo in lotes.values()}))
        )
    }

    def de_lote(lote_id: uuid.UUID, kg: Decimal) -> LoteDeRecorrido:
        lote = lotes[lote_id]
        orden = ordenes[lote.orden_compra_id]
        return LoteDeRecorrido(
            lote=Referencia(id=lote.id, codigo=lote.codigo, estado=lote.estado),
            orden=Referencia(id=orden.id, codigo=orden.codigo, estado=orden.estado),
            kg=kg.quantize(CENTIMO, rounding=ROUND_HALF_UP),
        )

    salida = []
    totales: dict[uuid.UUID, Decimal] = defaultdict(lambda: CERO)
    for t in tandas:
        dop = dops.get(t.id)
        ct = en_corrida.get(t.id)
        corrida = corridas.get(ct.corrida_id) if ct else None
        tf = finales.get(corrida.id) if corrida else None
        kg_tf = None
        if tf is not None and ct.proporcion is not None:
            kg_tf = (Decimal(tf.peso_seco_kg) * Decimal(ct.proporcion)).quantize(
                CENTIMO, rounding=ROUND_HALF_UP
            )
        p = productores[t.productor_id]
        for lote_id, kg in genealogia[t.id].items():
            totales[lote_id] += kg
        salida.append(
            TandaDeRecorrido(
                tanda=Referencia(id=t.id, codigo=t.codigo, estado=t.estado),
                recibida_en=t.recibida_en,
                peso_kg=t.peso_kg,
                estado_producto=t.estado_producto,
                parcela_codigo=parcelas[t.parcela_id].codigo,
                productor=ProductorDeTanda(id=p.id, dni=p.dni, nombres=p.nombres, apellidos=p.apellidos),
                dop=Referencia(id=dop.id, codigo=dop.codigo, estado=dop.estado) if dop else None,
                corrida=Referencia(id=corrida.id, codigo=corrida.codigo, estado=corrida.estado)
                if corrida
                else None,
                proporcion=ct.proporcion if ct else None,
                tanda_final=Referencia(id=tf.id, codigo=tf.codigo, estado=tf.estado) if tf else None,
                kg_en_tanda_final=kg_tf,
                lotes=[
                    de_lote(lid, kg)
                    for lid, kg in sorted(genealogia[t.id].items(), key=lambda par: lotes[par[0]].codigo)
                ],
            )
        )
    vigentes = [de_lote(lid, kg) for lid, kg in totales.items() if lotes[lid].estado != "anulado"]
    anulados = [de_lote(lid, kg) for lid, kg in totales.items() if lotes[lid].estado == "anulado"]
    vigentes.sort(key=lambda lo: lo.lote.codigo)
    anulados.sort(key=lambda lo: lo.lote.codigo)
    return salida, vigentes, anulados, sum((lo.kg for lo in vigentes), CERO)


def _armar(tipo: str, id_: uuid.UUID, titulo: str, subtitulo: str, sesion: Session, tandas) -> Recorrido:
    filas, vigentes, anulados, total = _recorrido(sesion, tandas)
    return Recorrido(
        tipo=tipo,
        id=id_,
        titulo=titulo,
        subtitulo=subtitulo,
        tandas=filas,
        lotes=vigentes,
        lotes_anulados=anulados,
        kg_en_lotes=total,
    )


def de_parcela(contexto: Contexto, parcela_id: uuid.UUID) -> Recorrido:
    sesion = contexto.sesion
    cooperativa_id = cooperativa_del_contexto(contexto)
    tandas = _tandas_de(sesion, cooperativa_id, parcela_id=parcela_id)
    # Sin tandas en la cooperativa, la parcela tiene que ser visible (productor afiliado).
    parcela = (
        sesion.get(Parcela, parcela_id) if tandas else servicio_parcelas.parcela_visible(contexto, parcela_id)
    )
    if parcela is None:
        raise no_encontrado("La parcela no existe.")
    productor = sesion.get(Productor, parcela.productor_id)
    return _armar(
        "parcela",
        parcela.id,
        f"{parcela.codigo} · {parcela.nombre}",
        f"{productor.nombres} {productor.apellidos} · DNI {productor.dni}",
        sesion,
        tandas,
    )


def de_productor(contexto: Contexto, productor_id: uuid.UUID) -> Recorrido:
    sesion = contexto.sesion
    cooperativa_id = cooperativa_del_contexto(contexto)
    tandas = _tandas_de(sesion, cooperativa_id, productor_id=productor_id)
    if not tandas:
        servicio_productores.obtener(contexto, productor_id)  # 404 si no está afiliado
    productor = sesion.get(Productor, productor_id)
    parcelas = len({t.parcela_id for t in tandas})
    return _armar(
        "productor",
        productor.id,
        f"{productor.nombres} {productor.apellidos}",
        f"DNI {productor.dni} · {parcelas} {'parcela' if parcelas == 1 else 'parcelas'} con entregas",
        sesion,
        tandas,
    )


def de_dop(contexto: Contexto, dop_id: uuid.UUID) -> Recorrido:
    sesion = contexto.sesion
    dop = servicio_dops.dop_visible(contexto, dop_id)
    tanda = sesion.get(Tanda, dop.tanda_id)
    parcela = sesion.get(Parcela, tanda.parcela_id)
    return _armar(
        "dop",
        dop.id,
        dop.codigo,
        f"Tanda {tanda.codigo} · parcela {parcela.codigo}",
        sesion,
        [tanda],
    )

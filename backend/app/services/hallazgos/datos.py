"""Todo lo que las reglas del informe necesitan de un lote, reunido una sola vez.

El peso de cada sujeto en el lote sale de la genealogía guardada al confirmarlo (proporcion_lote): por
parcela, por tanda y por corrida, en porcentaje con dos decimales. La fila más grande absorbe el redondeo,
así la suma de las parcelas es exactamente 100.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.fechas import hoy_lima
from app.models import (
    AnalisisCobertura,
    Calidad,
    Cooperativa,
    Corrida,
    DecisionHabilitacion,
    DecisionTanda,
    Dop,
    Dpp,
    Importador,
    Lote,
    LoteGenealogia,
    OrdenCompra,
    Parcela,
    Perfil,
    Productor,
    Superposicion,
    Tanda,
    TandaFinal,
)
from app.services import analisis, convergencia, declaracion_productor, habilitacion
from app.services.fuentes import registro

CIEN = Decimal("100")
CENTIMO = Decimal("0.01")


@dataclass
class DatosLote:
    sesion: Session
    lote: Lote
    orden: OrdenCompra
    importador: Importador
    calidad: Calidad
    cooperativa: Cooperativa
    filas: list[LoteGenealogia]
    parcelas: dict[uuid.UUID, Parcela]
    productores: dict[uuid.UUID, Productor]
    tandas: dict[uuid.UUID, Tanda]
    dops: dict[uuid.UUID, Dop]  # por id del DOP
    dop_de_tanda: dict[uuid.UUID, Dop]
    dpps: dict[uuid.UUID, Dpp]  # por id del DPP
    finales: dict[uuid.UUID, TandaFinal]
    corridas: dict[uuid.UUID, Corrida]
    peso_parcela: dict[uuid.UUID, Decimal]
    peso_tanda: dict[uuid.UUID, Decimal]
    peso_corrida: dict[uuid.UUID, Decimal]
    evaluaciones: dict[uuid.UUID, habilitacion.Evaluacion]
    fuentes: dict
    completados: dict[uuid.UUID, list[AnalisisCobertura]]
    resumenes: dict[uuid.UUID, dict]
    convergencias: dict[uuid.UUID, convergencia.Convergencia]
    decisiones: dict[uuid.UUID, list[DecisionHabilitacion]]  # de la más antigua a la más reciente
    decisiones_tanda: dict[uuid.UUID, list[DecisionTanda]]
    superposiciones: dict[uuid.UUID, list[Superposicion]]
    nombres: dict[uuid.UUID, str]
    hoy: date
    # Adenda 5: la declaración de cada productor ante la organización del lote, con el estado de hoy.
    declaraciones: dict[uuid.UUID, declaracion_productor.EstadoProductor] = field(default_factory=dict)
    # Adenda 6, sección 11, regla 2: las actuaciones vigentes de la organización que alcanzaron a cada
    # productor, de la más reciente a la más antigua.
    actuaciones_productor: dict[uuid.UUID, list[Any]] = field(default_factory=dict)
    # Las nueve comprobaciones de la Parte 8 con la fecha de hoy (las llena quien arma el informe).
    comprobaciones: list[dict[str, Any]] = field(default_factory=list)
    # Bloque de imágenes de cada parcela con la alerta de análisis y las rutas de sus dos imágenes.
    imagenes: dict[uuid.UUID, tuple[dict | None, dict[str, str]]] = field(default_factory=dict)

    @property
    def masa(self) -> Decimal:
        return Decimal(self.lote.masa_neta_kg or 0)

    def parcelas_ordenadas(self) -> list[Parcela]:
        return sorted(self.parcelas.values(), key=lambda p: p.codigo)

    def tandas_ordenadas(self) -> list[Tanda]:
        return sorted(self.tandas.values(), key=lambda t: t.codigo)

    def corridas_ordenadas(self) -> list[Corrida]:
        return sorted(self.corridas.values(), key=lambda c: c.codigo)

    def productores_ordenados(self) -> list[Productor]:
        return sorted(self.productores.values(), key=lambda p: (p.apellidos, p.nombres, str(p.id)))

    def peso_productor(self, productor_id: uuid.UUID) -> Decimal:
        """Adenda 5: el peso de un productor en el lote es la suma de los pesos de sus parcelas."""
        return sum(
            (self.peso_parcela[p.id] for p in self.parcelas.values() if p.productor_id == productor_id),
            Decimal("0"),
        )

    def nota_habilitacion(self, parcela_id: uuid.UUID) -> str | None:
        """La nota de la decisión de habilitar vigente: explica por qué se habilitó con alertas."""
        habilitar = [d for d in self.decisiones.get(parcela_id, []) if d.decision == "habilitar"]
        return habilitar[-1].nota if habilitar else None


def _ajustar(valores: dict[Any, Decimal]) -> dict[Any, Decimal]:
    """Porcentajes con dos decimales cuya suma es exactamente 100: la clave más grande absorbe el redondeo."""
    if not valores:
        return {}
    redondeados = {k: v.quantize(CENTIMO, rounding=ROUND_HALF_UP) for k, v in valores.items()}
    mayor = max(sorted(redondeados, key=str), key=lambda k: redondeados[k])
    redondeados[mayor] += CIEN - sum(redondeados.values(), Decimal("0"))
    return redondeados


def _por(filas: list[LoteGenealogia], clave) -> dict[Any, Decimal]:
    suma: dict[Any, Decimal] = defaultdict(lambda: Decimal("0"))
    for f in filas:
        suma[clave(f)] += Decimal(f.proporcion_lote) * CIEN
    return _ajustar(dict(suma))


def _todos(sesion: Session, modelo, ids) -> dict:
    ids = list(ids)
    if not ids:
        return {}
    return {x.id: x for x in sesion.scalars(select(modelo).where(modelo.id.in_(ids)))}


def cargar(sesion: Session, lote: Lote) -> DatosLote:
    orden = sesion.get(OrdenCompra, lote.orden_compra_id)
    filas = list(
        sesion.scalars(
            select(LoteGenealogia).where(LoteGenealogia.lote_id == lote.id).order_by(LoteGenealogia.id)
        )
    )
    parcelas = _todos(sesion, Parcela, {f.parcela_id for f in filas})
    tandas = _todos(sesion, Tanda, {f.tanda_id for f in filas})
    dops = _todos(sesion, Dop, {f.dop_id for f in filas})
    dpps = _todos(sesion, Dpp, {f.dpp_id for f in filas})
    finales = _todos(sesion, TandaFinal, {f.tanda_final_id for f in filas})
    corridas = _todos(sesion, Corrida, {tf.corrida_id for tf in finales.values()})
    productores = _todos(sesion, Productor, {f.productor_id for f in filas})
    corrida_de_final = {tf.id: tf.corrida_id for tf in finales.values()}

    ids = sorted(parcelas, key=lambda pid: parcelas[pid].codigo)
    ordenadas = [parcelas[pid] for pid in ids]
    evaluaciones = habilitacion.evaluar(sesion, ordenadas)
    fuentes = registro.actuales()
    completados, resumenes, convergencias = {}, {}, {}
    for p in ordenadas:
        todos = evaluaciones[p.id].analisis
        completados[p.id] = analisis.ultimos_completados(fuentes, p, todos)
        resumenes[p.id] = analisis.resumen(fuentes, p, todos)
        convergencias[p.id] = analisis.convergencia_de(fuentes, p, todos)

    decisiones: dict[uuid.UUID, list[DecisionHabilitacion]] = defaultdict(list)
    if ids:
        for d in sesion.scalars(
            select(DecisionHabilitacion)
            .where(DecisionHabilitacion.parcela_id.in_(ids))
            .order_by(DecisionHabilitacion.decidida_en, DecisionHabilitacion.id)
        ):
            decisiones[d.parcela_id].append(d)
    decisiones_tanda: dict[uuid.UUID, list[DecisionTanda]] = defaultdict(list)
    if tandas:
        for d in sesion.scalars(
            select(DecisionTanda)
            .where(DecisionTanda.tanda_id.in_(list(tandas)))
            .order_by(DecisionTanda.decidida_en, DecisionTanda.id)
        ):
            decisiones_tanda[d.tanda_id].append(d)
    superposiciones: dict[uuid.UUID, list[Superposicion]] = defaultdict(list)
    if ids:
        for s in sesion.scalars(
            select(Superposicion)
            .where(
                (Superposicion.parcela_a_id.in_(ids)) | (Superposicion.parcela_b_id.in_(ids)),
            )
            .order_by(Superposicion.id)
        ):
            for pid in (s.parcela_a_id, s.parcela_b_id):
                if pid in parcelas:
                    superposiciones[pid].append(s)
    personas = {e.revision.revisada_por for e in evaluaciones.values() if e.revision} | {
        d.decidida_por for lista in decisiones.values() for d in lista if d.decidida_por
    }
    nombres = {
        p.id: f"{p.nombres} {p.apellidos}".strip()
        for p in (sesion.scalars(select(Perfil).where(Perfil.id.in_(personas))) if personas else [])
    }
    from app.services import diligencia  # evita importación circular

    hoy = hoy_lima()
    return DatosLote(
        sesion=sesion,
        lote=lote,
        orden=orden,
        importador=sesion.get(Importador, orden.importador_id),
        calidad=sesion.get(Calidad, orden.calidad_id),
        cooperativa=sesion.get(Cooperativa, lote.cooperativa_id),
        filas=filas,
        parcelas={pid: parcelas[pid] for pid in ids},
        productores=productores,
        tandas=tandas,
        dops=dops,
        dop_de_tanda={f.tanda_id: dops[f.dop_id] for f in filas},
        dpps=dpps,
        finales=finales,
        corridas=corridas,
        peso_parcela=_por(filas, lambda f: f.parcela_id),
        peso_tanda=_por(filas, lambda f: f.tanda_id),
        peso_corrida=_por(filas, lambda f: corrida_de_final[f.tanda_final_id]),
        evaluaciones=evaluaciones,
        fuentes=fuentes,
        completados=completados,
        resumenes=resumenes,
        convergencias=convergencias,
        decisiones=dict(decisiones),
        decisiones_tanda=dict(decisiones_tanda),
        superposiciones=dict(superposiciones),
        nombres=nombres,
        hoy=hoy,
        declaraciones={
            productor_id: estado
            for (productor_id, _), estado in declaracion_productor.estados(
                sesion, {(pid, lote.cooperativa_id) for pid in productores}
            ).items()
        },
        actuaciones_productor=diligencia.de_productores(sesion, set(productores), lote.cooperativa_id, hoy),
    )

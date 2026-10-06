"""Recomprobación del lote (Parte 8): antes de embarcar, el sistema vuelve a mirar con la fecha del día todo
lo que respalda el lote.

No es una evaluación de riesgo: solo confirma que cada requisito que ya se cumplió sigue en pie. Si las
nueve comprobaciones pasan, el lote queda listo; si alguna falla, bloqueado. Ninguna persona marca un lote
como listo. Una parcela excluida bloquea para siempre todo stock que contenga su cacao.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.catalogos import documentos_embarque
from app.contexto import Contexto
from app.errores import error_api
from app.fechas import ahora
from app.models import (
    Cooperativa,
    CorridaTanda,
    Documento,
    Dop,
    Dpp,
    Importador,
    Lote,
    LoteGenealogia,
    OrdenCompra,
    Parcela,
    Perfil,
    Recomprobacion,
    Tanda,
    TandaFinal,
)
from app.schemas.cooperativa import Caso, Comprobacion, RecomprobacionSalida
from app.services import cooperativa as servicio_cooperativa
from app.services.auditoria import registrar_auditoria

# Estados del lote que se recomprueban; cerrado (Parte 9) ya no cambia.
RECOMPROBABLES = ("armado", "bloqueado", "listo")
NOMBRES_ESTADO = {
    "vigente": "vigente",
    "por_vencer": "por vencer",
    "vencido": "vencido",
    "faltante": "faltante",
}

COMPROBACIONES = (
    ("parcelas_habilitadas", "Parcelas habilitadas", "Cada parcela de la genealogía"),
    ("sin_parcelas_excluidas", "Ninguna parcela excluida", "Cada parcela de la genealogía"),
    ("dops_vigentes", "DOP vigentes", "Cada DOP de la genealogía"),
    ("dpps_vigentes", "DPP vigentes", "Cada DPP de las tandas finales del lote"),
    ("genealogia_cuadra", "La genealogía cuadra", "El lote"),
    ("expediente_cooperativa_completo", "Expediente legal de la cooperativa", "La cooperativa"),
    ("datos_cooperativa_completos", "Datos de la cooperativa", "La cooperativa"),
    ("importador_completo", "Datos del importador", "El importador de la orden"),
    ("documentos_embarque_completos", "Documentos de embarque", "El lote"),
)


# ---------- Stock retenido ----------


def retenidas(sesion: Session, tanda_final_ids) -> set[uuid.UUID]:
    """Tandas finales con alguna tanda de una parcela excluida en su corrida: el cacao ya se mezcló y no se
    puede separar. Se calcula al consultar; no es un estado guardado."""
    ids = list(tanda_final_ids)
    if not ids:
        return set()
    return set(
        sesion.scalars(
            select(TandaFinal.id)
            .join(
                CorridaTanda,
                and_(CorridaTanda.corrida_id == TandaFinal.corrida_id, CorridaTanda.liberada_en.is_(None)),
            )
            .join(Tanda, Tanda.id == CorridaTanda.tanda_id)
            .join(Parcela, Parcela.id == Tanda.parcela_id)
            .where(TandaFinal.id.in_(ids), Parcela.habilitacion_estado == "excluida")
            .distinct()
        )
    )


# ---------- Las nueve comprobaciones ----------


def _comprobacion(codigo: str, casos: list[Caso]) -> dict[str, Any]:
    nombre, sobre = next((n, s) for c, n, s in COMPROBACIONES if c == codigo)
    return Comprobacion(
        codigo=codigo,
        nombre=nombre,
        sobre=sobre,
        resultado="con_observaciones" if casos else "sin_observaciones",
        casos=casos,
    ).model_dump()


def comprobar(sesion: Session, lote: Lote) -> list[dict[str, Any]]:
    """Las nueve comprobaciones, cada una con su resultado y sus casos, con el estado de hoy (no el sellado
    en el DOP)."""
    from app.services import habilitacion  # evita importación circular

    filas = list(sesion.scalars(select(LoteGenealogia).where(LoteGenealogia.lote_id == lote.id)))
    parcelas = list(
        sesion.scalars(
            select(Parcela).where(Parcela.id.in_({f.parcela_id for f in filas})).order_by(Parcela.codigo)
        )
    )
    # Evaluar pasa a observada la parcela habilitada que dejó de cumplir algún requisito (Parte 4).
    evaluaciones = habilitacion.evaluar(sesion, parcelas)
    no_habilitadas = []
    excluidas = []
    for p in parcelas:
        if p.habilitacion_estado == "excluida":
            excluidas.append(
                Caso(
                    texto=f"La parcela {p.codigo} ({p.nombre}) está excluida",
                    detalle="Su cacao bloquea el lote para siempre: el lote no tiene salida y solo puede "
                    "anularse.",
                    tipo="parcela",
                    id=str(p.id),
                    codigo=p.codigo,
                )
            )
        if p.habilitacion_estado != "habilitada":
            incumplidos = [r.detalle for r in evaluaciones[p.id].requisitos if not r.cumple]
            no_habilitadas.append(
                Caso(
                    texto=f"La parcela {p.codigo} ({p.nombre}) está {p.habilitacion_estado}",
                    detalle=(
                        "Requisito que no cumple: " + "; ".join(d.rstrip(".") for d in incumplidos) + "."
                    )
                    if incumplidos
                    else None,
                    tipo="parcela",
                    id=str(p.id),
                    codigo=p.codigo,
                )
            )
    dops = list(sesion.scalars(select(Dop).where(Dop.id.in_({f.dop_id for f in filas})).order_by(Dop.codigo)))
    dpps = list(sesion.scalars(select(Dpp).where(Dpp.id.in_({f.dpp_id for f in filas})).order_by(Dpp.codigo)))
    masa = Decimal(lote.masa_neta_kg or 0)
    suma = sum((Decimal(f.kg_atribuidos) for f in filas), Decimal("0"))
    cooperativa = sesion.get(Cooperativa, lote.cooperativa_id)
    casillas = servicio_cooperativa.casillas(sesion, lote.cooperativa_id)
    orden = sesion.get(OrdenCompra, lote.orden_compra_id)
    importador = sesion.get(Importador, orden.importador_id)
    faltan_importador = [
        nombre
        for campo, nombre in (("razon_social", "nombre"), ("direccion", "dirección"), ("correo", "correo"))
        if not (getattr(importador, campo) or "").strip()
    ]
    embarque = set(
        sesion.scalars(
            select(Documento.tipo).where(
                Documento.entidad == "lote", Documento.entidad_id == lote.id, Documento.anulado_en.is_(None)
            )
        )
    )
    return [
        _comprobacion("parcelas_habilitadas", no_habilitadas),
        _comprobacion("sin_parcelas_excluidas", excluidas),
        _comprobacion(
            "dops_vigentes",
            [
                Caso(texto=f"El DOP {d.codigo} está {d.estado}", tipo="dop", id=str(d.id), codigo=d.codigo)
                for d in dops
                if d.estado != "vigente"
            ],
        ),
        _comprobacion(
            "dpps_vigentes",
            [
                Caso(texto=f"El DPP {d.codigo} está {d.estado}", tipo="dpp", id=str(d.id), codigo=d.codigo)
                for d in dpps
                if d.estado != "vigente"
            ],
        ),
        _comprobacion(
            "genealogia_cuadra",
            []
            if masa == suma and filas
            else [
                Caso(
                    texto=f"La masa del lote ({masa} kg) y la suma atribuida ({suma} kg) difieren en "
                    f"{masa - suma} kg",
                    tipo="lote",
                    id=str(lote.id),
                    codigo=lote.codigo,
                )
            ],
        ),
        _comprobacion(
            "expediente_cooperativa_completo",
            [
                Caso(
                    texto=f"{servicio_cooperativa.catalogo.POR_CODIGO_COOPERATIVA[c].nombre}: "
                    f"{NOMBRES_ESTADO.get(casillas[c].estado, casillas[c].estado)}",
                    detalle=f"Venció el {casillas[c].documento.fecha_vencimiento.isoformat()}"
                    if casillas[c].estado == "vencido"
                    else None,
                    tipo="expediente_cooperativa",
                    codigo=c,
                )
                for c in servicio_cooperativa.faltan_casillas(casillas)
            ],
        ),
        _comprobacion(
            "datos_cooperativa_completos",
            [
                Caso(texto=f"Falta el dato: {nombre}", tipo="cooperativa")
                for nombre in servicio_cooperativa.faltan_datos(cooperativa)
            ],
        ),
        _comprobacion(
            "importador_completo",
            [
                Caso(
                    texto=f"Falta el dato del importador {importador.razon_social or ''}: {nombre}".replace(
                        "  ", " "
                    ),
                    tipo="importador",
                    id=str(importador.id),
                )
                for nombre in faltan_importador
            ],
        ),
        _comprobacion(
            "documentos_embarque_completos",
            [
                Caso(texto=f"Falta: {t.nombre}", tipo="embarque", id=str(lote.id), codigo=t.codigo)
                for t in documentos_embarque.TIPOS
                if t.codigo not in embarque
            ],
        ),
    ]


# ---------- Ejecutar ----------


def _resultado(comprobaciones: list[dict[str, Any]]) -> str:
    return (
        "sin_observaciones"
        if all(c["resultado"] == "sin_observaciones" for c in comprobaciones)
        else ("con_observaciones")
    )


def ultima(sesion: Session, lote_id: uuid.UUID) -> Recomprobacion | None:
    return sesion.scalar(
        select(Recomprobacion)
        .where(Recomprobacion.lote_id == lote_id)
        .order_by(Recomprobacion.ejecutada_en.desc(), Recomprobacion.id.desc())
        .limit(1)
    )


def _cambiar_estado(sesion: Session, contexto: Contexto | None, lote: Lote, resultado: str) -> str | None:
    nuevo = "listo" if resultado == "sin_observaciones" else "bloqueado"
    if lote.estado == nuevo:
        return None
    anterior = lote.estado
    lote.estado = nuevo
    registrar_auditoria(
        contexto,
        "lote.cambiar_estado",
        "lote",
        lote.id,
        {"codigo": lote.codigo, "de": anterior, "a": nuevo, "por": "recomprobacion"},
        cooperativa_id=lote.cooperativa_id,
        sesion=sesion,
    )
    return nuevo


def recomprobar(contexto: Contexto, lote_id: uuid.UUID) -> RecomprobacionSalida:
    from app.services.lotes import lote_visible  # evita importación circular

    sesion = contexto.sesion
    lote = lote_visible(contexto, lote_id, bloquear=True)
    if lote.estado not in RECOMPROBABLES:
        raise error_api(
            400, "lote_no_recomprobable", "Solo se recomprueba un lote armado, bloqueado o listo."
        )
    comprobaciones = comprobar(sesion, lote)
    resultado = _resultado(comprobaciones)
    fila = Recomprobacion(
        lote_id=lote.id,
        ejecutada_por=contexto.usuario_id,
        ejecutada_en=ahora(),
        resultado=resultado,
        detalle={"comprobaciones": comprobaciones},
    )
    sesion.add(fila)
    sesion.flush()
    registrar_auditoria(
        contexto,
        "lote.recomprobar",
        "lote",
        lote.id,
        {
            "codigo": lote.codigo,
            "resultado": resultado,
            "con_observaciones": [
                c["codigo"] for c in comprobaciones if c["resultado"] == "con_observaciones"
            ],
        },
    )
    _cambiar_estado(sesion, contexto, lote, resultado)
    sesion.commit()
    return salida(sesion, fila, lote.estado)


def tarea_diaria(sesion: Session) -> int:
    """Recomprueba los lotes listo y bloqueado. Guarda una fila nueva solo cuando el resultado o sus casos
    cambian; así un lote se desbloquea solo cuando sus parcelas vuelven a estar habilitadas."""
    nuevas = 0
    ids = list(sesion.scalars(select(Lote.id).where(Lote.estado.in_(("listo", "bloqueado")))))
    for lote_id in ids:
        lote = sesion.scalar(
            select(Lote).where(Lote.id == lote_id).with_for_update().execution_options(populate_existing=True)
        )
        if lote is None or lote.estado not in ("listo", "bloqueado"):
            continue
        comprobaciones = comprobar(sesion, lote)
        resultado = _resultado(comprobaciones)
        anterior = ultima(sesion, lote.id)
        if anterior is not None and anterior.detalle == {"comprobaciones": comprobaciones}:
            sesion.rollback()
            continue
        sesion.add(
            Recomprobacion(
                lote_id=lote.id,
                ejecutada_por=None,
                ejecutada_en=ahora(),
                resultado=resultado,
                detalle={"comprobaciones": comprobaciones},
            )
        )
        registrar_auditoria(
            None,
            "lote.recomprobar",
            "lote",
            lote.id,
            {"codigo": lote.codigo, "resultado": resultado, "por": "tarea_diaria"},
            cooperativa_id=lote.cooperativa_id,
            sesion=sesion,
        )
        _cambiar_estado(sesion, None, lote, resultado)
        sesion.commit()
        nuevas += 1
    return nuevas


def salida(sesion: Session, fila: Recomprobacion, estado_lote: str | None = None) -> RecomprobacionSalida:
    perfil = sesion.get(Perfil, fila.ejecutada_por) if fila.ejecutada_por else None
    return RecomprobacionSalida(
        id=fila.id,
        lote_id=fila.lote_id,
        ejecutada_por_nombre=f"{perfil.nombres} {perfil.apellidos}".strip() if perfil else None,
        ejecutada_en=fila.ejecutada_en,
        resultado=fila.resultado,
        comprobaciones=[Comprobacion(**c) for c in fila.detalle["comprobaciones"]],
        estado_lote=estado_lote,
    )


def historial(contexto: Contexto, lote_id: uuid.UUID) -> list[RecomprobacionSalida]:
    from app.services.lotes import lote_visible  # evita importación circular

    lote = lote_visible(contexto, lote_id)
    filas = contexto.sesion.scalars(
        select(Recomprobacion)
        .where(Recomprobacion.lote_id == lote.id)
        .order_by(Recomprobacion.ejecutada_en.desc(), Recomprobacion.id.desc())
    )
    return [salida(contexto.sesion, f) for f in filas]


# ---------- Exclusión posterior al cierre ----------


def exclusion_posterior_al_cierre(contexto: Contexto, parcela: Parcela) -> list[str]:
    """Si el cacao de una parcela recién excluida ya está en un lote cerrado, el DEX no se altera (está
    sellado): el lote recibe la alerta, que se audita y aparece en la pantalla de inicio. Informar al
    importador es responsabilidad de la cooperativa y ocurre fuera del sistema."""
    sesion = contexto.sesion
    lotes = list(
        sesion.scalars(
            select(Lote)
            .join(LoteGenealogia, LoteGenealogia.lote_id == Lote.id)
            .where(LoteGenealogia.parcela_id == parcela.id, Lote.estado == "cerrado")
            .distinct()
        )
    )
    codigos = []
    for lote in lotes:
        if any(
            a.get("codigo") == "exclusion_posterior_al_cierre" and a.get("parcela_id") == str(parcela.id)
            for a in lote.alertas or []
        ):
            continue
        alerta = {
            "codigo": "exclusion_posterior_al_cierre",
            "parcela_id": str(parcela.id),
            "parcela_codigo": parcela.codigo,
            "en": ahora().isoformat(),
        }
        lote.alertas = [*(lote.alertas or []), alerta]
        registrar_auditoria(
            contexto,
            "lote.alerta",
            "lote",
            lote.id,
            {"codigo": lote.codigo, "alerta": "exclusion_posterior_al_cierre", "parcela": parcela.codigo},
        )
        codigos.append(lote.codigo)
    return codigos

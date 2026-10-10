"""Pendientes de la cooperativa (Parte 8): lo que requiere atención, para la pantalla de inicio.

Primero lo vencido, luego lo que está por vencer y al final lo demás. Cada pendiente enlaza al registro donde
se atiende. No hay avisos por correo ni mensajes: los pendientes se ven al entrar.
"""

from datetime import timedelta

from sqlalchemy import select

from app.catalogos import documentos_legales
from app.contexto import Contexto, cooperativa_del_contexto
from app.fechas import LIMA, hoy_lima
from app.models import Afiliacion, Lote, OrdenCompra, Parcela, Productor, Tanda
from app.schemas.cooperativa import GrupoPendientes, Pendiente, PendientesSalida
from app.services import cooperativa as servicio_cooperativa
from app.services import legalidad as servicio_legalidad
from app.services import productores as servicio_productores
from app.services import recomprobacion

DIAS_ANTES_DE_LA_ENTREGA = 15
MAXIMO_POR_GRUPO = 50
ORDEN_PRIORIDAD = {"vencido": 0, "por_vencer": 1, "otro": 2}


def _fecha(d) -> str:
    return d.strftime("%d/%m/%Y")


def _grupo(clave: str, titulo: str, prioridad: str, items: list[Pendiente]) -> GrupoPendientes:
    return GrupoPendientes(
        clave=clave, titulo=titulo, prioridad=prioridad, cantidad=len(items), items=items[:MAXIMO_POR_GRUPO]
    )


def _declaraciones(contexto: Contexto, cooperativa_id) -> GrupoPendientes:
    """Adenda 5, sección 10: vencidas, por vencer, por firmar y sin declaración, en ese orden. Un productor
    con una declaración por firmar cuenta solo como por firmar, como en sus pendientes."""
    filas = contexto.sesion.execute(
        select(
            Productor,
            servicio_productores._declaracion_hasta(cooperativa_id),
            servicio_productores._declaracion_por_firmar(cooperativa_id),
        )
        .join(Afiliacion, Afiliacion.productor_id == Productor.id)
        .where(Afiliacion.cooperativa_id == cooperativa_id, Afiliacion.estado == "activa")
        .order_by(Productor.apellidos, Productor.nombres)
    ).all()
    casos: dict[str, list[Pendiente]] = {"vencida": [], "por_vencer": [], "por_firmar": [], "sin": []}
    for productor, hasta, por_firmar in filas:
        titulo = f"{productor.nombres} {productor.apellidos}"
        enlace = f"#/productores/{productor.id}/declaracion"
        estado = servicio_productores.estado_declaracion(hasta, por_firmar)
        if por_firmar:
            detalle = "Falta la hoja firmada"
            casos["por_firmar"].append(Pendiente(titulo=titulo, detalle=detalle, enlace=enlace))
        elif estado == "vencida":
            detalle = f"Venció el {_fecha(hasta)}"
            casos["vencida"].append(Pendiente(titulo=titulo, detalle=detalle, enlace=enlace, fecha=hasta))
        elif estado == "por_vencer":
            detalle = f"Vence el {_fecha(hasta)}"
            casos["por_vencer"].append(Pendiente(titulo=titulo, detalle=detalle, enlace=enlace, fecha=hasta))
        elif estado == "sin_declaracion":
            casos["sin"].append(Pendiente(titulo=titulo, detalle="Sin declaración anual", enlace=enlace))
    por_fecha = [
        *sorted(casos["vencida"], key=lambda x: x.fecha),
        *sorted(casos["por_vencer"], key=lambda x: x.fecha),
    ]
    items = por_fecha + casos["por_firmar"] + casos["sin"]
    prioridad = "vencido" if casos["vencida"] else "por_vencer" if casos["por_vencer"] else "otro"
    return _grupo("declaraciones_productores", "Declaraciones de productores", prioridad, items)


def pendientes(contexto: Contexto) -> PendientesSalida:
    from app.services.parcelas import _visibles  # evita importación circular

    sesion = contexto.sesion
    cooperativa_id = cooperativa_del_contexto(contexto)
    hoy = hoy_lima()
    parcelas = {p.id: p for p in sesion.scalars(_visibles(contexto).where(Parcela.estado == "activa"))}

    # Documentos de las parcelas, vencidos y por vencer.
    docs_parcelas = {"vencido": [], "por_vencer": []}
    for p, requisito, documento in servicio_legalidad.sustentos_por_vencer(sesion, list(parcelas.values())):
        vence = documento.fecha_vencimiento
        docs_parcelas[requisito.estado].append(
            Pendiente(
                titulo=f"{p.codigo} · {documentos_legales.POR_CODIGO[documento.tipo].nombre}",
                detalle=f"{'Venció' if requisito.estado == 'vencido' else 'Vence'} el {_fecha(vence)}",
                enlace=f"#/parcelas/{p.id}",
                fecha=vence,
            )
        )
    # Documentos de la cooperativa, vencidos y por vencer.
    docs_cooperativa = {"vencido": [], "por_vencer": []}
    for casilla in servicio_cooperativa.documentos_por_vencer(sesion, cooperativa_id):
        vence = casilla.documento.fecha_vencimiento
        docs_cooperativa[casilla.estado].append(
            Pendiente(
                titulo=documentos_legales.POR_CODIGO_COOPERATIVA[casilla.codigo].nombre,
                detalle=f"{'Venció' if casilla.estado == 'vencido' else 'Vence'} el {_fecha(vence)}",
                enlace="#/cooperativa/legal",
                fecha=vence,
            )
        )
    observadas = [
        Pendiente(titulo=f"{p.codigo} · {p.nombre}", detalle="Parcela observada", enlace=f"#/parcelas/{p.id}")
        for p in sorted(parcelas.values(), key=lambda p: p.codigo)
        if p.habilitacion_estado == "observada"
    ]
    tandas = [
        Pendiente(
            titulo=t.codigo,
            detalle="Observada" if t.estado == "observada" else "Registrada, sin validar",
            enlace=f"#/tandas/{t.id}",
            fecha=t.recibida_en.astimezone(LIMA).date(),
        )
        for t in sesion.scalars(
            select(Tanda)
            .where(Tanda.cooperativa_id == cooperativa_id, Tanda.estado.in_(("registrada", "observada")))
            .order_by(Tanda.recibida_en)
        )
    ]
    lotes = list(
        sesion.scalars(
            select(Lote)
            .where(Lote.cooperativa_id == cooperativa_id, Lote.estado != "anulado")
            .order_by(Lote.codigo)
        )
    )
    ordenes = {
        o.id: o
        for o in sesion.scalars(
            select(OrdenCompra).where(OrdenCompra.id.in_({lo.orden_compra_id for lo in lotes}))
        )
    }
    bloqueados = []
    for lo in lotes:
        if lo.estado != "bloqueado":
            continue
        ultima = recomprobacion.ultima(sesion, lo.id)
        fallan = (
            [c["nombre"] for c in ultima.detalle["comprobaciones"] if c["resultado"] == "con_observaciones"]
            if ultima
            else []
        )
        bloqueados.append(
            Pendiente(
                titulo=lo.codigo,
                detalle=("Con observaciones en: " + ", ".join(fallan)) if fallan else "Bloqueado",
                enlace=f"#/lotes-exportacion/{lo.id}",
            )
        )
    limite = hoy + timedelta(days=DIAS_ANTES_DE_LA_ENTREGA)
    por_entregar = [
        Pendiente(
            titulo=lo.codigo,
            detalle=f"No está listo y la entrega es el {_fecha(ordenes[lo.orden_compra_id].fecha_entrega)}",
            enlace=f"#/lotes-exportacion/{lo.id}",
            fecha=ordenes[lo.orden_compra_id].fecha_entrega,
        )
        for lo in lotes
        if lo.estado in ("en_armado", "armado", "bloqueado")
        and ordenes[lo.orden_compra_id].fecha_entrega <= limite
    ]
    alertas = [
        Pendiente(
            titulo=lo.codigo,
            detalle=f"La parcela {a.get('parcela_codigo')} se excluyó después de cerrar el lote: el DEX no "
            "cambia; informar al importador corresponde a la cooperativa.",
            enlace=f"#/lotes-exportacion/{lo.id}",
        )
        for lo in lotes
        for a in lo.alertas or []
        if a.get("codigo") == "exclusion_posterior_al_cierre"
    ]
    grupos = [
        _grupo(
            "documentos_parcelas_vencidos",
            "Documentos de parcelas vencidos",
            "vencido",
            docs_parcelas["vencido"],
        ),
        _grupo(
            "documentos_cooperativa_vencidos",
            "Documentos de la cooperativa vencidos",
            "vencido",
            docs_cooperativa["vencido"],
        ),
        _grupo(
            "documentos_parcelas_por_vencer",
            "Documentos de parcelas por vencer",
            "por_vencer",
            docs_parcelas["por_vencer"],
        ),
        _grupo(
            "documentos_cooperativa_por_vencer",
            "Documentos de la cooperativa por vencer",
            "por_vencer",
            docs_cooperativa["por_vencer"],
        ),
        _grupo("lotes_bloqueados", "Lotes bloqueados", "otro", bloqueados),
        _grupo(
            "lotes_por_entregar", "Lotes que no están listos a 15 días de la entrega", "otro", por_entregar
        ),
        _grupo("exclusion_posterior_al_cierre", "Exclusiones después de cerrar un lote", "otro", alertas),
        _grupo("parcelas_observadas", "Parcelas observadas", "otro", observadas),
        _grupo("tandas_sin_validar", "Tandas sin validar", "otro", tandas),
        _declaraciones(contexto, cooperativa_id),
    ]
    # Primero lo vencido, luego lo que está por vencer y al final lo demás; dentro, el orden de arriba.
    grupos = sorted((g for g in grupos if g.cantidad), key=lambda g: ORDEN_PRIORIDAD[g.prioridad])
    return PendientesSalida(total=sum(g.cantidad for g in grupos), grupos=grupos)

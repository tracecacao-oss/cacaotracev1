"""La corrida de proceso (Parte 6): una o varias tandas validadas que pasan juntas por las 23 etapas y
terminan en una tanda final que entra al stock.

Estados: abierta (se agregan o quitan tandas), en_proceso (se registran las etapas), consolidada (se emitió
el DPP) y anulada. Consolidar cierra la corrida en una sola transacción: compara el grano que salió con el
que entró, fija la proporción de cada tanda, crea la tanda final y emite el DPP. Ninguna alerta impide
consolidar; las de rendimiento exigen una explicación.
"""

import uuid
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalogos import etapas_proceso as catalogo
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import LIMA, ahora
from app.models import (
    Calidad,
    Cooperativa,
    Corrida,
    CorridaEtapa,
    CorridaTanda,
    Dop,
    Dpp,
    Lugar,
    Parcela,
    Perfil,
    Productor,
    Tanda,
    TandaFinal,
)
from app.schemas.proceso import (
    Consolidacion,
    CorridaDetalle,
    CorridaNueva,
    CorridaSalida,
    EtapaDeCorrida,
    EtapaRegistro,
    ParcelaDeCorrida,
    PlantillaDeEtapa,
    Referencia,
    Rendimiento,
    TandaACorrida,
    TandaDeCorrida,
    TandaDisponible,
)
from app.schemas.recepcion import ProductorDeTanda
from app.services import configuracion, correlativos, documentos, proceso
from app.services.auditoria import aplicar_cambios, registrar_auditoria
from app.storage import ClienteStorage

NOTA_MINIMA = 50
# Ruta seco: el peso final no debe superar la entrada en más de 1 %. No hay límite inferior: la selección
# descarta grano.
TOLERANCIA_SECO = Decimal("0.01")
ALERTAS_RENDIMIENTO = ("rendimiento_sobre_banda", "rendimiento_bajo_banda", "peso_final_supera_entrada")
PRODUCTO_DE_RUTA = {"completa": "baba", "seco": "seco"}
SEIS = Decimal("0.000001")
SIN_ORDEN = (3, 4)


# ---------- Lectura ----------


def corrida_visible(contexto: Contexto, corrida_id: uuid.UUID) -> Corrida:
    corrida = contexto.sesion.get(Corrida, corrida_id)
    if corrida is None or corrida.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("La corrida no existe.")
    return corrida


def filas_de_tandas(sesion: Session, corrida: Corrida) -> list[CorridaTanda]:
    """Las tandas de la corrida. Una anulada conserva las suyas como historial."""
    consulta = select(CorridaTanda).where(CorridaTanda.corrida_id == corrida.id)
    if corrida.estado != "anulada":
        consulta = consulta.where(CorridaTanda.liberada_en.is_(None))
    return list(sesion.scalars(consulta.order_by(CorridaTanda.agregada_en)))


def etapas_de(sesion: Session, corrida_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[int, CorridaEtapa]]:
    resultado: dict[uuid.UUID, dict[int, CorridaEtapa]] = {cid: {} for cid in corrida_ids}
    if corrida_ids:
        for e in sesion.scalars(select(CorridaEtapa).where(CorridaEtapa.corrida_id.in_(corrida_ids))):
            resultado[e.corrida_id][e.numero] = e
    return resultado


def fase(corrida: Corrida, etapas: dict[int, CorridaEtapa]) -> tuple[str, str, int | None]:
    """La fase visible es la de la primera etapa todavía pendiente (regla 6 del registro de etapas)."""
    if corrida.estado == "consolidada":
        return "stock", "En stock", None
    if corrida.estado == "anulada":
        return "anulada", "Anulada", None
    for numero in catalogo.NUMEROS:
        etapa = etapas.get(numero)
        if etapa is not None and etapa.situacion == "pendiente":
            e = catalogo.POR_NUMERO[numero]
            return e.fase, catalogo.NOMBRE_FASE[e.fase], numero
    return "envasado", catalogo.NOMBRE_FASE["envasado"], None


def _ocupadas(
    sesion: Session, tanda_ids: list[uuid.UUID], excepto: uuid.UUID | None = None
) -> set[uuid.UUID]:
    """Tandas que ya están en una corrida no anulada."""
    if not tanda_ids:
        return set()
    consulta = select(CorridaTanda.tanda_id).where(
        CorridaTanda.tanda_id.in_(tanda_ids), CorridaTanda.liberada_en.is_(None)
    )
    if excepto:
        consulta = consulta.where(CorridaTanda.corrida_id != excepto)
    return set(sesion.scalars(consulta))


def _alertas_de_ingreso(sesion: Session, filas: list[CorridaTanda]) -> list[str]:
    """Una tanda de una parcela que pasó a observada después de su DOP entra con alerta (regla 5)."""
    if not filas:
        return []
    observadas = sesion.scalar(
        select(func.count())
        .select_from(Tanda)
        .join(Parcela, Parcela.id == Tanda.parcela_id)
        .where(Tanda.id.in_([f.tanda_id for f in filas]), Parcela.habilitacion_estado == "observada")
    )
    return ["tanda_de_parcela_observada"] if observadas else []


def _dato(etapa: CorridaEtapa | None, clave: str) -> Any:
    return (etapa.datos or {}).get(clave) if etapa is not None else None


def rendimiento(
    sesion: Session, corrida: Corrida, filas: list[CorridaTanda], etapas: dict[int, CorridaEtapa]
) -> Rendimiento:
    entrada = sum((Decimal(f.peso_kg) for f in filas), Decimal("0"))
    valor = _dato(etapas.get(19), "peso_final_kg")
    peso_final = Decimal(str(valor)) if valor is not None else None
    return _rendimiento(sesion, corrida, entrada, peso_final)


def _rendimiento(
    sesion: Session, corrida: Corrida, entrada: Decimal, peso_final: Decimal | None
) -> Rendimiento:
    conf = configuracion.de_cooperativa(sesion, corrida.cooperativa_id)
    completa = corrida.ruta == "completa"
    banda_min = conf.rendimiento_min if completa else None
    banda_max = conf.rendimiento_max if completa else None
    if peso_final is None or entrada <= 0:
        return Rendimiento(
            entrada_kg=entrada,
            peso_final_kg=peso_final,
            rendimiento=None,
            banda_min=banda_min,
            banda_max=banda_max,
            alerta=None,
        )
    razon = (peso_final / entrada).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    alerta = None
    if completa:
        exacta = peso_final / entrada
        if exacta > conf.rendimiento_max:
            alerta = "rendimiento_sobre_banda"
        elif exacta < conf.rendimiento_min:
            alerta = "rendimiento_bajo_banda"
    elif peso_final > entrada * (1 + TOLERANCIA_SECO):
        alerta = "peso_final_supera_entrada"
    return Rendimiento(
        entrada_kg=entrada,
        peso_final_kg=peso_final,
        rendimiento=razon,
        banda_min=banda_min,
        banda_max=banda_max,
        alerta=alerta,
    )


def faltan(sesion: Session, corrida: Corrida, etapas: dict[int, CorridaEtapa]) -> tuple[list[str], list[str]]:
    """(incompletas, fuera de orden) según la comprobación al consolidar."""
    incompletas = []
    for e in catalogo.ETAPAS:
        fila = etapas.get(e.numero)
        if fila is None or fila.situacion == "no_aplica":
            continue
        if fila.situacion == "pendiente":
            incompletas.append(f"Etapa {e.numero}: {e.nombre}")
    for numero, clave in catalogo.OBLIGATORIOS_AL_CONSOLIDAR[corrida.ruta]:
        fila = etapas.get(numero)
        if fila is not None and fila.situacion == "registrada" and _dato(fila, clave) in (None, ""):
            dato = next(d for d in catalogo.POR_NUMERO[numero].datos if d.clave == clave)
            incompletas.append(f"Etapa {numero}: falta {dato.etiqueta.lower()}")
    if not proceso.hay_calidad_activa(sesion, corrida.cooperativa_id):
        incompletas.append("La cooperativa no tiene ninguna calidad activa en su catálogo")
    # Los inicios de las etapas registradas no retroceden de una etapa a la siguiente. Las etapas 3 y 4 son
    # registros del sistema, fechados al iniciar la corrida: no cuentan.
    fuera_de_orden = []
    anterior: CorridaEtapa | None = None
    for numero in catalogo.NUMEROS:
        if numero in SIN_ORDEN:
            continue
        fila = etapas.get(numero)
        if fila is None or fila.situacion != "registrada" or fila.inicio is None:
            continue
        if anterior is not None and fila.inicio < anterior.inicio:
            fuera_de_orden.append(f"La etapa {fila.numero} empieza antes que la etapa {anterior.numero}")
        anterior = fila
    return incompletas, fuera_de_orden


def _nombres(sesion: Session, ids) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {
        p.id: f"{p.nombres} {p.apellidos}".strip()
        for p in sesion.scalars(select(Perfil).where(Perfil.id.in_(ids)))
    }


def _referencias(sesion: Session, corrida_ids: list[uuid.UUID]):
    finales: dict[uuid.UUID, TandaFinal] = {}
    dpps: dict[uuid.UUID, Dpp] = {}
    if corrida_ids:
        for tf in sesion.scalars(
            select(TandaFinal).where(TandaFinal.corrida_id.in_(corrida_ids), TandaFinal.estado != "anulada")
        ):
            finales[tf.corrida_id] = tf
        for d in sesion.scalars(select(Dpp).where(Dpp.corrida_id.in_(corrida_ids), Dpp.estado == "vigente")):
            dpps[d.corrida_id] = d
    return finales, dpps


def _salidas(sesion: Session, corridas: list[Corrida]) -> list[CorridaSalida]:
    ids = [c.id for c in corridas]
    etapas = etapas_de(sesion, ids)
    finales, dpps = _referencias(sesion, ids)
    filas_por_corrida: dict[uuid.UUID, list[CorridaTanda]] = {cid: [] for cid in ids}
    if ids:
        for f in sesion.scalars(select(CorridaTanda).where(CorridaTanda.corrida_id.in_(ids))):
            corrida = next(c for c in corridas if c.id == f.corrida_id)
            if corrida.estado == "anulada" or f.liberada_en is None:
                filas_por_corrida[f.corrida_id].append(f)
    salida = []
    for c in corridas:
        clave, nombre, actual = fase(c, etapas[c.id])
        filas = filas_por_corrida[c.id]
        tf, dpp = finales.get(c.id), dpps.get(c.id)
        if c.estado in ("abierta", "en_proceso"):
            alertas = _alertas_de_ingreso(sesion, filas)
        else:
            # Consolidada: las alertas son las que quedaron selladas en su DPP vigente.
            alertas = list(dpp.contenido["alertas"]["alertas"]) if dpp else []
        salida.append(
            CorridaSalida(
                id=c.id,
                codigo=c.codigo,
                ruta=c.ruta,
                tipo_manejo=c.tipo_manejo,
                estado=c.estado,
                fase=clave,
                fase_nombre=nombre,
                etapa_actual=actual,
                etapa_actual_nombre=catalogo.POR_NUMERO[actual].nombre if actual else None,
                numero_tandas=len(filas),
                entrada_kg=sum((Decimal(f.peso_kg) for f in filas), Decimal("0")),
                abierta_en=c.abierta_en,
                iniciada_en=c.iniciada_en,
                consolidada_en=c.consolidada_en,
                alertas=alertas,
                tanda_final=Referencia(id=tf.id, codigo=tf.codigo, estado=tf.estado) if tf else None,
                dpp=Referencia(id=dpp.id, codigo=dpp.codigo, estado=dpp.estado) if dpp else None,
            )
        )
    return salida


def listar(contexto: Contexto, *, estado: str | None = None, fase_: str | None = None) -> list[CorridaSalida]:
    consulta = select(Corrida).where(Corrida.cooperativa_id == cooperativa_del_contexto(contexto))
    if estado:
        consulta = consulta.where(Corrida.estado == estado)
    corridas = list(contexto.sesion.scalars(consulta.order_by(Corrida.abierta_en.desc()).limit(500)))
    salidas = _salidas(contexto.sesion, corridas)
    return [s for s in salidas if not fase_ or s.fase == fase_]


def _tandas_de_corrida(sesion: Session, filas: list[CorridaTanda]) -> list[TandaDeCorrida]:
    if not filas:
        return []
    tandas = {t.id: t for t in sesion.scalars(select(Tanda).where(Tanda.id.in_([f.tanda_id for f in filas])))}
    productores = {
        p.id: p
        for p in sesion.scalars(
            select(Productor).where(Productor.id.in_({t.productor_id for t in tandas.values()}))
        )
    }
    parcelas = {
        p.id: p
        for p in sesion.scalars(
            select(Parcela).where(Parcela.id.in_({t.parcela_id for t in tandas.values()}))
        )
    }
    dops = {d.tanda_id: d for d in sesion.scalars(select(Dop).where(Dop.tanda_id.in_(list(tandas))))}
    salida = []
    for f in filas:
        t = tandas[f.tanda_id]
        p, pa, d = productores[t.productor_id], parcelas[t.parcela_id], dops.get(t.id)
        salida.append(
            TandaDeCorrida(
                tanda_id=t.id,
                codigo=t.codigo,
                productor=ProductorDeTanda(id=p.id, dni=p.dni, nombres=p.nombres, apellidos=p.apellidos),
                parcela=ParcelaDeCorrida(
                    id=pa.id, codigo=pa.codigo, nombre=pa.nombre, habilitacion_estado=pa.habilitacion_estado
                ),
                dop=Referencia(id=d.id, codigo=d.codigo, estado=d.estado) if d else None,
                estado_producto=t.estado_producto,
                recibida_en=t.recibida_en,
                peso_kg=f.peso_kg,
                observacion_calidad=f.observacion_calidad,
                proporcion=f.proporcion,
            )
        )
    return salida


def _horas(inicio: datetime | None, fin: datetime | None) -> Decimal | None:
    if inicio is None or fin is None:
        return None
    return (Decimal((fin - inicio).total_seconds()) / Decimal(3600)).quantize(Decimal("0.01"))


def _etapas_salida(
    sesion: Session, corrida: Corrida, etapas: dict[int, CorridaEtapa]
) -> list[EtapaDeCorrida]:
    plantilla = proceso.plantilla_de(sesion, corrida.cooperativa_id)
    lugares = {
        lu.id: lu.nombre
        for lu in sesion.scalars(
            select(Lugar).where(Lugar.id.in_([e.lugar_id for e in etapas.values() if e.lugar_id]))
        )
    }
    nombres = _nombres(sesion, [e.registrada_por for e in etapas.values()])
    salida = []
    for e in catalogo.ETAPAS:
        fila = etapas[e.numero]
        p = plantilla.get(e.numero)
        salida.append(
            EtapaDeCorrida(
                numero=e.numero,
                nombre=e.nombre,
                tipo=e.tipo,
                fase=e.fase,
                situacion=fila.situacion,
                automatica=e.automatica,
                opcional=e.opcional,
                transporte=e.transporte,
                editable=corrida.estado == "en_proceso"
                and not e.automatica
                and fila.situacion != "no_aplica",
                lugar_id=fila.lugar_id,
                lugar_nombre=lugares.get(fila.lugar_id),
                inicio=fila.inicio,
                fin=fila.fin,
                duracion_horas=_horas(fila.inicio, fila.fin),
                metodo=fila.metodo,
                responsable=fila.responsable,
                observacion=fila.observacion,
                distancia_m=fila.distancia_m,
                datos=fila.datos or {},
                desde_plantilla=fila.desde_plantilla,
                registrada_por_nombre=nombres.get(fila.registrada_por),
                registrada_en=fila.registrada_en,
                plantilla=PlantillaDeEtapa(
                    lugar_id=p.lugar_id,
                    metodo=p.metodo,
                    distancia_m=p.distancia_m,
                    duracion_horas=p.duracion_horas,
                )
                if p
                else None,
            )
        )
    return salida


def obtener(contexto: Contexto, corrida_id: uuid.UUID) -> CorridaDetalle:
    sesion = contexto.sesion
    corrida = corrida_visible(contexto, corrida_id)
    base = _salidas(sesion, [corrida])[0]
    filas = filas_de_tandas(sesion, corrida)
    etapas = etapas_de(sesion, [corrida.id])[corrida.id]
    rend = rendimiento(sesion, corrida, filas, etapas)
    incompletas, fuera_de_orden = (
        faltan(sesion, corrida, etapas) if corrida.estado == "en_proceso" else ([], [])
    )
    alertas = list(base.alertas)
    if rend.alerta and corrida.estado == "en_proceso":
        alertas.append(rend.alerta)
    historial = sesion.scalars(
        select(Dpp).where(Dpp.corrida_id == corrida.id).order_by(Dpp.emitido_en.desc())
    )
    return CorridaDetalle(
        **(base.model_dump() | {"alertas": alertas}),
        abierta_por_nombre=_nombres(sesion, [corrida.abierta_por]).get(corrida.abierta_por),
        anulada_en=corrida.anulada_en,
        motivo_anulacion=corrida.motivo_anulacion,
        tandas=_tandas_de_corrida(sesion, filas),
        etapas=_etapas_salida(sesion, corrida, etapas),
        rendimiento=rend,
        faltan_para_consolidar=incompletas + fuera_de_orden,
        puede_consolidar=corrida.estado == "en_proceso" and not incompletas and not fuera_de_orden,
        dpps=[Referencia(id=d.id, codigo=d.codigo, estado=d.estado) for d in historial],
    )


# ---------- Crear y armar la corrida ----------


def crear(contexto: Contexto, datos: CorridaNueva) -> CorridaDetalle:
    sesion = contexto.sesion
    cooperativa_id = cooperativa_del_contexto(contexto)
    if (
        sesion.scalar(select(Lugar.id).where(Lugar.cooperativa_id == cooperativa_id, Lugar.activo).limit(1))
        is None
    ):
        raise error_api(400, "sin_lugares", "Antes de crear una corrida, registra al menos un lugar activo.")
    momento = ahora()
    anio = momento.astimezone(LIMA).year
    numero = correlativos.siguiente(sesion, cooperativa_id, "corrida", anio)
    corrida = Corrida(
        cooperativa_id=cooperativa_id,
        codigo=f"CP-{anio}-{numero:06d}",
        ruta=datos.ruta,
        tipo_manejo=datos.tipo_manejo,
        estado="abierta",
        abierta_por=contexto.usuario_id,
        abierta_en=momento,
    )
    sesion.add(corrida)
    sesion.flush()
    plantilla = proceso.plantilla_de(sesion, cooperativa_id)
    for e in catalogo.ETAPAS:
        aplica = catalogo.aplica(e, datos.ruta)
        p = plantilla.get(e.numero) if aplica and not e.automatica else None
        sesion.add(
            CorridaEtapa(
                corrida_id=corrida.id,
                numero=e.numero,
                situacion="pendiente" if aplica else "no_aplica",
                lugar_id=p.lugar_id if p else None,
                metodo=p.metodo if p else None,
                distancia_m=p.distancia_m if p and e.transporte else None,
                # La etapa 5 se llena con el tipo de manejo elegido al crear la corrida.
                datos={"tipo_manejo": datos.tipo_manejo} if e.numero == 5 else {},
            )
        )
    registrar_auditoria(
        contexto,
        "corrida.crear",
        "corrida",
        corrida.id,
        {"codigo": corrida.codigo, "ruta": datos.ruta, "tipo_manejo": datos.tipo_manejo},
    )
    sesion.commit()
    return obtener(contexto, corrida.id)


def _dop_vigente(sesion: Session, tanda_id: uuid.UUID) -> Dop | None:
    return sesion.scalar(select(Dop).where(Dop.tanda_id == tanda_id, Dop.estado == "vigente"))


def _comprobar_ingreso(sesion: Session, corrida: Corrida, tanda: Tanda, *, al_iniciar: bool = False) -> None:
    """Reglas de ingreso de una tanda (1 a 4). Al iniciar se repiten la 1 y la 4."""
    if tanda.estado != "validada" or _dop_vigente(sesion, tanda.id) is None:
        raise error_api(
            400, "tanda_no_disponible", f"La tanda {tanda.codigo} no está validada o su DOP no está vigente."
        )
    if tanda.id in _ocupadas(sesion, [tanda.id], excepto=corrida.id):
        raise error_api(400, "tanda_en_otra_corrida", f"La tanda {tanda.codigo} ya está en otra corrida.")
    parcela = sesion.get(Parcela, tanda.parcela_id)
    if parcela.habilitacion_estado == "excluida":
        raise error_api(
            400,
            "parcela_excluida",
            f"La parcela de la tanda {tanda.codigo} está excluida: no entra a proceso.",
        )
    if al_iniciar:
        return
    if tanda.estado_producto != PRODUCTO_DE_RUTA[corrida.ruta]:
        raise error_api(
            400,
            "ruta_no_coincide",
            "Una corrida no mezcla baba con seco: las tandas en baba van a la ruta completa y las secas a la "
            "ruta seco.",
        )
    if corrida.tipo_manejo == "segregado":
        otros = sesion.scalar(
            select(func.count())
            .select_from(CorridaTanda)
            .join(Tanda, Tanda.id == CorridaTanda.tanda_id)
            .where(
                CorridaTanda.corrida_id == corrida.id,
                CorridaTanda.liberada_en.is_(None),
                Tanda.productor_id != tanda.productor_id,
            )
        )
        if otros:
            raise error_api(
                400, "corrida_segregada", "Una corrida segregada lleva tandas de un solo productor."
            )


def tandas_disponibles(
    contexto: Contexto, ruta: str, productor_id: uuid.UUID | None = None
) -> list[TandaDisponible]:
    sesion = contexto.sesion
    ocupada = exists().where(CorridaTanda.tanda_id == Tanda.id, CorridaTanda.liberada_en.is_(None))
    consulta = (
        select(Tanda, Dop, Parcela, Productor)
        .join(Dop, (Dop.tanda_id == Tanda.id) & (Dop.estado == "vigente"))
        .join(Parcela, Parcela.id == Tanda.parcela_id)
        .join(Productor, Productor.id == Tanda.productor_id)
        .where(
            Tanda.cooperativa_id == cooperativa_del_contexto(contexto),
            Tanda.estado == "validada",
            Tanda.estado_producto == PRODUCTO_DE_RUTA[ruta],
            Parcela.habilitacion_estado != "excluida",
            ~ocupada,
        )
    )
    if productor_id:
        consulta = consulta.where(Tanda.productor_id == productor_id)
    return [
        TandaDisponible(
            tanda_id=t.id,
            codigo=t.codigo,
            productor=ProductorDeTanda(id=p.id, dni=p.dni, nombres=p.nombres, apellidos=p.apellidos),
            parcela=ParcelaDeCorrida(
                id=pa.id, codigo=pa.codigo, nombre=pa.nombre, habilitacion_estado=pa.habilitacion_estado
            ),
            dop=Referencia(id=d.id, codigo=d.codigo, estado=d.estado),
            estado_producto=t.estado_producto,
            recibida_en=t.recibida_en,
            peso_kg=t.peso_kg,
            parcela_observada=pa.habilitacion_estado == "observada",
        )
        for t, d, pa, p in sesion.execute(consulta.order_by(Tanda.recibida_en)).all()
    ]


def _exigir_estado(corrida: Corrida, *estados: str) -> None:
    if corrida.estado in estados:
        return
    mensajes = {
        "abierta": "La corrida todavía no se inició.",
        "en_proceso": "La corrida ya se inició: su lista de tandas no cambia.",
        "consolidada": "La corrida está consolidada: para corregirla, anula primero su DPP.",
        "anulada": "La corrida está anulada.",
    }
    raise error_api(400, f"corrida_{corrida.estado}", mensajes[corrida.estado])


def agregar_tanda(contexto: Contexto, corrida_id: uuid.UUID, datos: TandaACorrida) -> CorridaDetalle:
    sesion = contexto.sesion
    corrida = corrida_visible(contexto, corrida_id)
    _exigir_estado(corrida, "abierta")
    tanda = sesion.get(Tanda, datos.tanda_id)
    if tanda is None or tanda.cooperativa_id != corrida.cooperativa_id:
        raise no_encontrado("La tanda no existe.")
    if tanda.id in {f.tanda_id for f in filas_de_tandas(sesion, corrida)}:
        raise error_api(409, "tanda_ya_en_corrida", f"La tanda {tanda.codigo} ya está en esta corrida.")
    _comprobar_ingreso(sesion, corrida, tanda)
    sesion.add(
        CorridaTanda(
            corrida_id=corrida.id,
            tanda_id=tanda.id,
            peso_kg=tanda.peso_kg,
            observacion_calidad=datos.observacion_calidad or None,
            agregada_en=ahora(),
        )
    )
    try:
        sesion.flush()
    except IntegrityError as exc:  # otra corrida la tomó al mismo tiempo
        sesion.rollback()
        raise error_api(
            400, "tanda_en_otra_corrida", f"La tanda {tanda.codigo} ya está en otra corrida."
        ) from exc
    registrar_auditoria(
        contexto,
        "corrida.agregar_tanda",
        "corrida",
        corrida.id,
        {"corrida": corrida.codigo, "tanda": tanda.codigo, "peso_kg": tanda.peso_kg},
    )
    sesion.commit()
    return obtener(contexto, corrida.id)


def quitar_tanda(contexto: Contexto, corrida_id: uuid.UUID, tanda_id: uuid.UUID) -> CorridaDetalle:
    sesion = contexto.sesion
    corrida = corrida_visible(contexto, corrida_id)
    _exigir_estado(corrida, "abierta")
    fila = next((f for f in filas_de_tandas(sesion, corrida) if f.tanda_id == tanda_id), None)
    if fila is None:
        raise no_encontrado("La tanda no está en esta corrida.")
    codigo = sesion.get(Tanda, tanda_id).codigo
    sesion.delete(fila)
    registrar_auditoria(
        contexto, "corrida.quitar_tanda", "corrida", corrida.id, {"corrida": corrida.codigo, "tanda": codigo}
    )
    sesion.commit()
    return obtener(contexto, corrida.id)


def iniciar(contexto: Contexto, corrida_id: uuid.UUID) -> CorridaDetalle:
    """Pasa la corrida a en_proceso y llena las etapas 1, 3 y 4 con las tandas y sus DOP."""
    sesion = contexto.sesion
    corrida = corrida_visible(contexto, corrida_id)
    _exigir_estado(corrida, "abierta")
    filas = filas_de_tandas(sesion, corrida)
    if not filas:
        raise error_api(400, "corrida_sin_tandas", "Agrega al menos una tanda antes de iniciar la corrida.")
    tandas = {t.id: t for t in sesion.scalars(select(Tanda).where(Tanda.id.in_([f.tanda_id for f in filas])))}
    for tanda in tandas.values():
        _comprobar_ingreso(sesion, corrida, tanda, al_iniciar=True)
    momento = ahora()
    corrida.estado = "en_proceso"
    corrida.iniciada_en = momento
    _llenar_automaticas(sesion, contexto, corrida, filas, tandas, momento)
    registrar_auditoria(
        contexto,
        "corrida.iniciar",
        "corrida",
        corrida.id,
        {"corrida": corrida.codigo, "tandas": [t.codigo for t in tandas.values()]},
    )
    sesion.commit()
    return obtener(contexto, corrida.id)


def _llenar_automaticas(sesion, contexto, corrida, filas, tandas, momento) -> None:
    """Etapas 1, 3 y 4 (regla 4 del catálogo). La 1 va de la primera a la última recepción; la 3 y la 4 se
    fechan cuando CacaoTrace registra la corrida, al iniciarla: son registros del sistema y no cuentan en la
    comprobación del orden cronológico."""
    etapas = etapas_de(sesion, [corrida.id])[corrida.id]
    ordenadas = sorted(tandas.values(), key=lambda t: t.recibida_en)
    dops = {d.tanda_id: d for d in sesion.scalars(select(Dop).where(Dop.tanda_id.in_(list(tandas))))}
    parcelas = {
        p.id: p
        for p in sesion.scalars(select(Parcela).where(Parcela.id.in_({t.parcela_id for t in ordenadas})))
    }
    plantilla = proceso.plantilla_de(sesion, corrida.cooperativa_id)
    registradores = _nombres(sesion, [t.registrada_por for t in ordenadas])
    quien = _nombres(sesion, [contexto.usuario_id]).get(contexto.usuario_id)
    primera, ultima = ordenadas[0], ordenadas[-1]
    pesos = {f.tanda_id: f.peso_kg for f in filas}

    def lugar_de(numero: int):
        p = plantilla.get(numero)
        return p.lugar_id if p and p.lugar_id else primera.lugar_id

    comunes = {"situacion": "registrada", "registrada_por": contexto.usuario_id, "registrada_en": momento}
    for numero, valores in {
        1: {
            "lugar_id": primera.lugar_id,
            "inicio": primera.recibida_en,
            "fin": ultima.recibida_en,
            "metodo": "Pesaje en balanza de cada tanda al recibirla",
            "responsable": ", ".join(sorted(set(registradores.values()))) or None,
            "datos": {
                "tandas": [
                    {
                        "codigo": t.codigo,
                        "peso_kg": str(pesos[t.id]),
                        "recibida_en": t.recibida_en.isoformat(),
                    }
                    for t in ordenadas
                ],
                "peso_total_kg": str(sum((Decimal(p) for p in pesos.values()), Decimal("0"))),
            },
        },
        3: {
            "lugar_id": lugar_de(3),
            "inicio": momento,
            "fin": momento,
            "metodo": "Código de corrida y DOP de cada tanda, asignados por CacaoTrace",
            "responsable": quien,
            "datos": {"codigo_corrida": corrida.codigo, "dops": [dops[t.id].codigo for t in ordenadas]},
        },
        4: {
            "lugar_id": lugar_de(4),
            "inicio": momento,
            "fin": momento,
            "metodo": "Compuerta de cada tanda y estado de su parcela en CacaoTrace",
            "responsable": quien,
            "datos": {
                "tandas": [
                    {
                        "codigo": t.codigo,
                        "dop": dops[t.id].codigo,
                        "dop_estado": dops[t.id].estado,
                        "parcela": parcelas[t.parcela_id].codigo,
                        "habilitacion_estado": parcelas[t.parcela_id].habilitacion_estado,
                    }
                    for t in ordenadas
                ]
            },
        },
    }.items():
        fila = etapas[numero]
        for clave, valor in (comunes | valores).items():
            setattr(fila, clave, valor)
        fila.desde_plantilla = False


# ---------- Etapas ----------


def _validar_datos(sesion: Session, corrida: Corrida, numero: int, entrada: dict[str, Any]) -> dict[str, Any]:
    """El dato propio de la etapa, con las claves y los rangos del catálogo."""
    etapa = catalogo.POR_NUMERO[numero]
    if numero == 5:
        return {"tipo_manejo": corrida.tipo_manejo}
    permitidos = {d.clave: d for d in etapa.datos}
    desconocidos = set(entrada) - set(permitidos)
    if desconocidos:
        raise error_api(
            422, "dato_desconocido", f"La etapa {numero} no tiene el dato {', '.join(sorted(desconocidos))}."
        )
    salida: dict[str, Any] = {}
    for clave, valor in entrada.items():
        dato = permitidos[clave]
        if valor in (None, "", []):
            continue
        error = error_api(422, "dato_invalido", f"Revisa {dato.etiqueta.lower()} de la etapa {numero}.")
        if dato.tipo == "texto":
            texto = str(valor).strip()
            if len(texto) > 4000:
                raise error
            if texto:
                salida[clave] = texto
        elif dato.tipo in ("numero", "entero"):
            try:
                numero_ = Decimal(str(valor))
            except Exception as exc:
                raise error from exc
            if not numero_.is_finite() or (dato.tipo == "entero" and numero_ != numero_.to_integral_value()):
                raise error
            if (dato.minimo is not None and numero_ < Decimal(str(dato.minimo))) or (
                dato.maximo is not None and numero_ > Decimal(str(dato.maximo))
            ):
                raise error
            salida[clave] = int(numero_) if dato.tipo == "entero" else str(numero_.quantize(Decimal("0.01")))
        elif dato.tipo == "fechas":
            if not isinstance(valor, list) or len(valor) > 100:
                raise error
            fechas = []
            for texto in valor:
                try:
                    momento = datetime.fromisoformat(str(texto))
                except ValueError as exc:
                    raise error from exc
                if momento.tzinfo is not None and momento > ahora() + timedelta(minutes=5):
                    raise error_api(422, "fecha_futura", "Una fecha de volteo no puede ser futura.")
                fechas.append(momento.isoformat())
            salida[clave] = sorted(fechas)
        elif dato.tipo == "calidad":
            try:
                calidad = sesion.get(Calidad, uuid.UUID(str(valor)))
            except ValueError as exc:
                raise error from exc
            if calidad is None or calidad.cooperativa_id != corrida.cooperativa_id or not calidad.activo:
                raise error_api(
                    422, "calidad_invalida", "Elige una calidad activa del catálogo de la cooperativa."
                )
            salida["calidad_id"] = str(calidad.id)
            salida["calidad"] = calidad.nombre
    return salida


def registrar_etapa(
    contexto: Contexto, corrida_id: uuid.UUID, numero: int, datos: EtapaRegistro
) -> CorridaDetalle:
    sesion = contexto.sesion
    corrida = corrida_visible(contexto, corrida_id)
    if numero not in catalogo.POR_NUMERO:
        raise no_encontrado("La etapa no existe.")
    _exigir_estado(corrida, "en_proceso")
    etapa = catalogo.POR_NUMERO[numero]
    fila = etapas_de(sesion, [corrida.id])[corrida.id][numero]
    if fila.situacion == "no_aplica":
        raise error_api(400, "etapa_no_aplica", "Esta etapa no aplica en la ruta de la corrida.")
    if etapa.automatica:
        raise error_api(400, "etapa_automatica", "Esta etapa la llena el sistema con las tandas y sus DOP.")
    momento = ahora()
    if datos.situacion == "no_ocurrio":
        if not etapa.opcional:
            raise error_api(
                422,
                "no_ocurrio_no_admitido",
                "Solo las etapas 7 y 14 pueden marcarse como que no ocurrieron.",
            )
        valores = {
            "situacion": "no_ocurrio",
            "lugar_id": None,
            "inicio": None,
            "fin": None,
            "metodo": None,
            "responsable": None,
            "distancia_m": None,
            "observacion": datos.observacion or None,
            "datos": {},
            "desde_plantilla": False,
        }
    else:
        faltantes = [
            nombre
            for nombre, valor in (
                ("lugar", datos.lugar_id),
                ("inicio", datos.inicio),
                ("fin", datos.fin),
                ("método", datos.metodo),
                ("responsable", datos.responsable),
            )
            if not valor
        ]
        if etapa.transporte and datos.distancia_m is None:
            faltantes.append("distancia")
        if faltantes:
            codigo = "distancia_requerida" if faltantes == ["distancia"] else "datos_incompletos"
            raise error_api(422, codigo, f"Falta: {', '.join(faltantes)}.")
        if datos.inicio.tzinfo is None or datos.fin.tzinfo is None:
            raise error_api(422, "fecha_sin_zona", "Las fechas deben llevar su zona horaria.")
        if datos.fin < datos.inicio:
            raise error_api(
                422, "fin_antes_de_inicio", "El fin de la etapa no puede ser anterior a su inicio."
            )
        if max(datos.inicio, datos.fin) > momento + timedelta(minutes=5):
            raise error_api(422, "fecha_futura", "Las fechas de la etapa no pueden ser futuras.")
        lugar = proceso.lugar_de_la_cooperativa(sesion, corrida.cooperativa_id, datos.lugar_id)
        if not lugar.activo and lugar.id != fila.lugar_id:
            raise error_api(422, "lugar_inactivo", "El lugar está inactivo.")
        distancia = datos.distancia_m if etapa.transporte else None
        p = proceso.plantilla_de(sesion, corrida.cooperativa_id).get(numero)
        desde_plantilla = bool(
            p
            and p.lugar_id == datos.lugar_id
            and (p.metodo or "") == (datos.metodo or "")
            and (p.distancia_m if etapa.transporte else None) == distancia
        )
        valores = {
            "situacion": "registrada",
            "lugar_id": datos.lugar_id,
            "inicio": datos.inicio,
            "fin": datos.fin,
            "metodo": datos.metodo,
            "responsable": datos.responsable,
            "distancia_m": distancia,
            "observacion": datos.observacion or None,
            "datos": _validar_datos(sesion, corrida, numero, datos.datos),
            "desde_plantilla": desde_plantilla,
        }
    correccion = fila.situacion != "pendiente"
    cambios = aplicar_cambios(fila, valores)
    fila.registrada_por = contexto.usuario_id
    fila.registrada_en = momento
    registrar_auditoria(
        contexto,
        "corrida.registrar_etapa",
        "corrida",
        corrida.id,
        {"corrida": corrida.codigo, "etapa": numero, "correccion": correccion, "cambios": cambios},
    )
    sesion.commit()
    return obtener(contexto, corrida.id)


# ---------- Consolidar y anular ----------


def proporciones(pesos: list[Decimal]) -> list[Decimal]:
    """Peso de cada tanda entre el total, con 6 decimales; la última se ajusta para que sumen 1."""
    total = sum(pesos, Decimal("0"))
    resultado = [(p / total).quantize(SEIS, rounding=ROUND_HALF_UP) for p in pesos[:-1]]
    resultado.append(Decimal("1.000000") - sum(resultado, Decimal("0")))
    return resultado


def consolidar(
    contexto: Contexto, storage: ClienteStorage, corrida_id: uuid.UUID, datos: Consolidacion
) -> CorridaDetalle:
    """Consolida, fija las proporciones, crea la tanda final y emite el DPP en una sola transacción."""
    from app.services import dpps  # evita importación circular

    sesion = contexto.sesion
    corrida = corrida_visible(contexto, corrida_id)
    _exigir_estado(corrida, "en_proceso")
    etapas = etapas_de(sesion, [corrida.id])[corrida.id]
    incompletas, fuera_de_orden = faltan(sesion, corrida, etapas)
    if incompletas:
        error = error_api(400, "etapas_incompletas", f"Falta registrar: {'; '.join(incompletas)}.")
        error.detail["faltan"] = incompletas
        raise error
    if fuera_de_orden:
        error = error_api(400, "etapas_fuera_de_orden", f"{'; '.join(fuera_de_orden)}.")
        error.detail["faltan"] = fuera_de_orden
        raise error
    cooperativa = sesion.get(Cooperativa, corrida.cooperativa_id)
    if not cooperativa.codigo:
        raise error_api(
            400,
            "configuracion_incompleta",
            "La cooperativa todavía no tiene su código; lo fija el equipo CacaoTrace.",
        )
    peso_etapa = Decimal(str(_dato(etapas[19], "peso_final_kg")))
    if datos.peso_final_kg is not None and Decimal(datos.peso_final_kg) != peso_etapa:
        raise error_api(
            422,
            "peso_final_distinto",
            f"El peso final no coincide con el de la etapa 19 ({peso_etapa} kg): corrige la etapa o el peso.",
        )
    calidad = sesion.get(Calidad, uuid.UUID(_dato(etapas[17], "calidad_id")))
    if calidad is None or not calidad.activo:
        raise error_api(
            400, "calidad_inactiva", "La calidad de la etapa 17 ya no está activa: corrige la etapa."
        )
    almacen = proceso.lugar_de_la_cooperativa(sesion, corrida.cooperativa_id, datos.lugar_id)
    if not almacen.activo:
        raise error_api(422, "lugar_inactivo", "El almacén está inactivo.")
    filas = filas_de_tandas(sesion, corrida)
    rend = _rendimiento(sesion, corrida, sum((Decimal(f.peso_kg) for f in filas), Decimal("0")), peso_etapa)
    alertas = _alertas_de_ingreso(sesion, filas) + ([rend.alerta] if rend.alerta else [])
    explicacion = (datos.explicacion or "").strip() or None
    if rend.alerta and (not explicacion or len(explicacion) < NOTA_MINIMA):
        raise error_api(
            422,
            "explicacion_requerida",
            f"El rendimiento quedó fuera de lo esperado: explica por qué en al menos {NOTA_MINIMA} "
            "caracteres.",
        )

    momento = ahora()
    for fila, proporcion in zip(filas, proporciones([Decimal(f.peso_kg) for f in filas]), strict=True):
        fila.proporcion = proporcion
    anio = momento.astimezone(LIMA).year
    numero = correlativos.siguiente(sesion, corrida.cooperativa_id, "tanda_final", anio)
    tanda_final = TandaFinal(
        cooperativa_id=corrida.cooperativa_id,
        codigo=f"TF-{anio}-{numero:06d}",
        corrida_id=corrida.id,
        peso_seco_kg=peso_etapa,
        saldo_kg=peso_etapa,
        humedad_pct=datos.humedad_pct,
        calidad=calidad.nombre,
        calidad_id=calidad.id,
        numero_sacos=int(_dato(etapas[21], "numero_sacos")),
        lugar_id=almacen.id,
        ingreso_stock_en=momento,
        estado="en_stock",
    )
    sesion.add(tanda_final)
    corrida.estado = "consolidada"
    corrida.consolidada_en = momento
    sesion.flush()
    ruta_pdf = None
    try:
        dpp, ruta_pdf = dpps.emitir(
            contexto, storage, corrida, tanda_final, filas, etapas, rend, alertas, explicacion, momento
        )
        registrar_auditoria(
            contexto,
            "corrida.consolidar",
            "corrida",
            corrida.id,
            {
                "corrida": corrida.codigo,
                "tanda_final": tanda_final.codigo,
                "dpp": dpp.codigo,
                "rendimiento": rend.rendimiento,
                "alertas": alertas,
                "explicacion": explicacion,
            },
        )
        sesion.commit()
    except Exception:
        sesion.rollback()
        if ruta_pdf:
            documentos.descartar(storage, ruta_pdf)
        raise
    return obtener(contexto, corrida.id)


def anular(contexto: Contexto, corrida_id: uuid.UUID, motivo: str) -> CorridaDetalle:
    """Anula una corrida no consolidada; sus tandas quedan libres para otra corrida."""
    sesion = contexto.sesion
    corrida = corrida_visible(contexto, corrida_id)
    _exigir_estado(corrida, "abierta", "en_proceso")
    momento = ahora()
    filas = filas_de_tandas(sesion, corrida)
    for fila in filas:
        fila.liberada_en = momento
    corrida.estado = "anulada"
    corrida.anulada_en = momento
    corrida.anulada_por = contexto.usuario_id
    corrida.motivo_anulacion = motivo
    registrar_auditoria(
        contexto,
        "corrida.anular",
        "corrida",
        corrida.id,
        {"corrida": corrida.codigo, "motivo": motivo, "tandas_liberadas": len(filas)},
    )
    sesion.commit()
    return obtener(contexto, corrida.id)


# ---------- Para "Mis entregas" ----------


def proceso_de_tandas(sesion: Session, tanda_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    """En qué fase está la corrida de cada tanda, o si ya entró al stock. Sin datos de otros productores."""
    if not tanda_ids:
        return {}
    filas = sesion.execute(
        select(CorridaTanda.tanda_id, Corrida)
        .join(Corrida, Corrida.id == CorridaTanda.corrida_id)
        .where(CorridaTanda.tanda_id.in_(tanda_ids), CorridaTanda.liberada_en.is_(None))
    ).all()
    if not filas:
        return {}
    etapas = etapas_de(sesion, [c.id for _, c in filas])
    resultado = {}
    for tanda_id, corrida in filas:
        clave, nombre, _ = fase(corrida, etapas[corrida.id])
        resultado[tanda_id] = {"estado": corrida.estado, "fase": clave, "fase_nombre": nombre}
    return resultado

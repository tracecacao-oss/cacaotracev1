"""La tanda (Parte 5): cacao de una sola parcela que un productor entrega y la cooperativa pesa en cancha.

La registra el personal de la cooperativa. Genera su DOP solo al validarse: si algo no cuadra, se observa
con un motivo, se corrige y se valida de nuevo. Validada y anulada son estados finales.

Las alertas no bloquean: obligan a escribir una nota y llegan al informe de hallazgos.

Adenda 3: la tanda se sustenta con un documento de entrega (guía de remisión o liquidación de compra), con
reglas propias de cada tipo (app/catalogos/documento_entrega.py).
"""

import uuid
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.catalogos import documento_entrega, variedades
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import LIMA, ahora, dia_lima, hoy_lima
from app.models import (
    Afiliacion,
    ConfiguracionCooperativa,
    Cooperativa,
    DecisionTanda,
    Documento,
    Dop,
    Lugar,
    Parcela,
    Perfil,
    Productor,
    Tanda,
)
from app.schemas.recepcion import (
    DecisionTandaSalida,
    DopDeTanda,
    ParcelaDeTanda,
    ProductorDeTanda,
    Requisito,
    TandaCambios,
    TandaDetalle,
    TandaNueva,
    TandaSalida,
)
from app.services import configuracion, correlativos, documentos
from app.services.auditoria import aplicar_cambios, registrar_auditoria
from app.services.documentos import Archivo
from app.services.productores import documento_salida
from app.storage import ClienteStorage

NOTA_MINIMA = 50
DIAS_VOLUMEN = 365
EDITABLES = ("registrada", "observada")
CAMPOS_DATOS = (
    "lugar_id",
    "recibida_en",
    "estado_producto",
    "peso_kg",
    "numero_sacos",
    "humedad_pct",
    "variedad",
    "variedad_otra",
    "tipo_semilla",
    "cosecha_desde",
    "cosecha_hasta",
    "doc_entrega_tipo",
    "doc_entrega_numero",
    "doc_entrega_fecha_emision",
    "doc_entrega_ruc_emisor",
    "doc_entrega_peso_kg",
)
CAMPOS_DOCUMENTO = CAMPOS_DATOS[-5:]
NOMBRE_REQUISITO = {
    "parcela_habilitada": "Parcela habilitada",
    "productor_afiliado": "Productor afiliado y con consentimiento",
    "datos_completos": "Datos de la tanda completos",
    "documento_entrega_completo": "Documento de entrega completo",
    "configuracion_lista": "Configuración de la cooperativa lista",
}


# ---------- Reglas de los datos ----------


def _dos_decimales(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def peso_seco_equivalente(estado_producto: str, peso_kg: Decimal, factor: Decimal) -> Decimal:
    """Estimación para comparar tandas; el peso seco real se mide en la Parte 6."""
    if estado_producto == "seco":
        return _dos_decimales(peso_kg)
    return _dos_decimales(Decimal(peso_kg) * Decimal(factor))


def _comprobar_documento(valores: dict[str, Any], cooperativa: Cooperativa, dias_max: int) -> None:
    """Reglas del documento de entrega según su tipo (adenda 3, sección 5). Responde 422."""
    codigo = valores.get("doc_entrega_tipo")
    if codigo is None:
        if any(valores.get(campo) is not None for campo in CAMPOS_DOCUMENTO[1:]):
            raise error_api(422, "documento_tipo_requerido", "Elige el tipo de documento de entrega.")
        return
    tipo = documento_entrega.TIPOS[codigo]
    if tipo.emite_la_organizacion:
        # La emite la organización que recibe: su RUC se llena solo y no admite otro.
        if not valores.get("doc_entrega_ruc_emisor"):
            valores["doc_entrega_ruc_emisor"] = cooperativa.ruc
        elif valores["doc_entrega_ruc_emisor"] != cooperativa.ruc:
            raise error_api(
                422,
                "emisor_no_corresponde",
                f"La {tipo.nombre.lower()} la emite la organización que recibe: el RUC del emisor debe ser "
                f"{cooperativa.ruc}.",
            )
    fecha = valores.get("doc_entrega_fecha_emision")
    if fecha:
        dia_recepcion = dia_lima(valores["recibida_en"])
        if fecha > hoy_lima():
            raise error_api(422, "fecha_futura", "La fecha de emisión del documento no puede ser futura.")
        if tipo.emitido_despues_de_recibir:
            if not dia_recepcion <= fecha <= dia_recepcion + timedelta(days=dias_max):
                raise error_api(
                    422,
                    "documento_fecha_invalida",
                    f"La {tipo.nombre.lower()} se emite entre el día de la recepción y {dias_max} "
                    "días después.",
                )
        elif fecha > dia_recepcion:
            raise error_api(
                422,
                "documento_fecha_invalida",
                f"La {tipo.nombre.lower()} no puede emitirse después de la recepción.",
            )
    if valores.get("doc_entrega_numero"):
        valores["doc_entrega_numero"] = documento_entrega.validar_numero(
            codigo, valores["doc_entrega_numero"]
        )


def _comprobar_datos(
    valores: dict[str, Any], cooperativa: Cooperativa, conf: ConfiguracionCooperativa
) -> None:
    """Reglas de una tanda completa (alta o resultado de una edición). Responde 422 con un mensaje claro."""
    recibida = valores["recibida_en"]
    if recibida.tzinfo is None:
        raise error_api(422, "fecha_sin_zona", "La fecha de recepción debe llevar su zona horaria.")
    if recibida > ahora() + timedelta(minutes=5):
        raise error_api(422, "fecha_futura", "La fecha de recepción no puede ser futura.")
    dia_recepcion = dia_lima(recibida)
    if valores["cosecha_desde"] > valores["cosecha_hasta"]:
        raise error_api(422, "cosecha_invalida", "El inicio de la cosecha no puede ser posterior a su fin.")
    if valores["cosecha_hasta"] > dia_recepcion:
        raise error_api(422, "cosecha_invalida", "La cosecha no puede terminar después de la recepción.")
    if valores.get("humedad_pct") is not None and valores["estado_producto"] != "seco":
        raise error_api(422, "humedad_solo_en_seco", "La humedad solo se registra para cacao seco.")
    if valores["variedad"] == "otra" and not valores.get("variedad_otra"):
        raise error_api(422, "variedad_requerida", "Escribe el nombre de la variedad.")
    if valores["variedad"] != "otra":
        valores["variedad_otra"] = None
    _comprobar_documento(valores, cooperativa, conf.dias_max_emision_doc_entrega)


def _lugar_de_acopio(sesion: Session, cooperativa_id: uuid.UUID, lugar_id: uuid.UUID) -> Lugar:
    lugar = sesion.get(Lugar, lugar_id)
    if lugar is None or lugar.cooperativa_id != cooperativa_id:
        raise error_api(422, "lugar_invalido", "El lugar no existe en la cooperativa.")
    if lugar.tipo != "cancha_acopio" or not lugar.activo:
        raise error_api(422, "lugar_invalido", "La tanda se pesa en una cancha de acopio activa.")
    return lugar


# ---------- Alta y edición ----------


def _productor_afiliado(contexto: Contexto, productor_id: uuid.UUID) -> Productor:
    """Un productor sin afiliación activa en la cooperativa responde 404."""
    productor = contexto.sesion.scalar(
        select(Productor)
        .join(Afiliacion, Afiliacion.productor_id == Productor.id)
        .where(
            Productor.id == productor_id,
            Afiliacion.cooperativa_id == cooperativa_del_contexto(contexto),
            Afiliacion.estado == "activa",
        )
    )
    if productor is None:
        raise no_encontrado("El productor no existe.")
    return productor


def registrar(contexto: Contexto, datos: TandaNueva) -> TandaDetalle:
    cooperativa_id = cooperativa_del_contexto(contexto)
    configuracion.exigir_lista(contexto.sesion, cooperativa_id)
    productor = _productor_afiliado(contexto, datos.productor_id)
    parcela = contexto.sesion.get(Parcela, datos.parcela_id)
    if parcela is None or parcela.productor_id != productor.id:
        raise error_api(422, "parcela_de_otro_productor", "La parcela no pertenece a ese productor.")
    valores = datos.model_dump(exclude={"productor_id", "parcela_id"})
    _comprobar_datos(
        valores,
        contexto.sesion.get(Cooperativa, cooperativa_id),
        configuracion.de_cooperativa(contexto.sesion, cooperativa_id),
    )
    _lugar_de_acopio(contexto.sesion, cooperativa_id, valores["lugar_id"])

    anio = valores["recibida_en"].astimezone(LIMA).year
    numero = correlativos.siguiente(contexto.sesion, cooperativa_id, "tanda", anio)
    tanda = Tanda(
        cooperativa_id=cooperativa_id,
        codigo=f"TD-{anio}-{numero:06d}",
        productor_id=productor.id,
        parcela_id=parcela.id,
        registrada_por=contexto.usuario_id,
        estado="registrada",
        **valores,
    )
    contexto.sesion.add(tanda)
    contexto.sesion.flush()
    registrar_auditoria(
        contexto,
        "tanda.registrar",
        "tanda",
        tanda.id,
        {"codigo": tanda.codigo, "productor_id": productor.id, "parcela_id": parcela.id, **valores},
    )
    contexto.sesion.commit()
    return obtener(contexto, tanda.id)


def tanda_visible(contexto: Contexto, tanda_id: uuid.UUID) -> Tanda:
    tanda = contexto.sesion.get(Tanda, tanda_id)
    if tanda is None or tanda.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("La tanda no existe.")
    if contexto.rol == "productor" and tanda.productor_id != contexto.productor_id:
        raise no_encontrado("La tanda no existe.")
    return tanda


def _exigir_editable(tanda: Tanda) -> None:
    if tanda.estado not in EDITABLES:
        mensaje = {
            "validada": "La tanda está validada y tiene DOP: ya no cambia.",
            "anulada": "La tanda está anulada.",
        }[tanda.estado]
        raise error_api(400, f"tanda_{tanda.estado}", mensaje)


def editar(contexto: Contexto, tanda_id: uuid.UUID, datos: TandaCambios) -> TandaDetalle:
    tanda = tanda_visible(contexto, tanda_id)
    _exigir_editable(tanda)
    cambios_pedidos = datos.model_dump(exclude_unset=True)
    # Los obligatorios no se vacían con null; los opcionales sí.
    obligatorios = ("lugar_id", "recibida_en", "estado_producto", "peso_kg", "variedad", "cosecha_desde")
    cambios_pedidos = {
        k: v for k, v in cambios_pedidos.items() if v is not None or k not in (*obligatorios, "cosecha_hasta")
    }
    valores = {campo: getattr(tanda, campo) for campo in CAMPOS_DATOS} | cambios_pedidos
    if valores["estado_producto"] != "seco" and "humedad_pct" not in cambios_pedidos:
        valores["humedad_pct"] = None
    _comprobar_datos(
        valores,
        contexto.sesion.get(Cooperativa, tanda.cooperativa_id),
        configuracion.de_cooperativa(contexto.sesion, tanda.cooperativa_id),
    )
    if "lugar_id" in cambios_pedidos:
        _lugar_de_acopio(contexto.sesion, tanda.cooperativa_id, valores["lugar_id"])
    cambios = aplicar_cambios(tanda, {k: valores[k] for k in CAMPOS_DATOS})
    if cambios:
        registrar_auditoria(contexto, "tanda.editar", "tanda", tanda.id, cambios)
    contexto.sesion.commit()
    return obtener(contexto, tanda.id)


def cargar_documento(
    contexto: Contexto, storage: ClienteStorage, tanda_id: uuid.UUID, archivo: Archivo
) -> TandaDetalle:
    """El archivo del documento de entrega: foto o PDF."""
    tanda = tanda_visible(contexto, tanda_id)
    _exigir_editable(tanda)
    documentos.cargar(
        contexto, storage, entidad="tanda", entidad_id=tanda.id, tipo="documento_entrega", archivo=archivo
    )
    return obtener(contexto, tanda.id)


# ---------- Requisitos y alertas ----------


def _dop_anulado(sesion: Session, tanda_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not tanda_ids:
        return set()
    return set(
        sesion.scalars(select(Dop.tanda_id).where(Dop.tanda_id.in_(tanda_ids), Dop.estado == "anulado"))
    )


def _peso_seco_de(sesion: Session, tanda: Tanda, factor: Decimal) -> Decimal:
    """Una tanda validada usa el valor con que se validó; las demás, la configuración actual."""
    if tanda.estado == "validada":
        guardado = sesion.scalar(
            select(DecisionTanda.requisitos["peso_seco_equivalente_kg"].astext)
            .where(DecisionTanda.tanda_id == tanda.id, DecisionTanda.decision == "validar")
            .order_by(DecisionTanda.decidida_en.desc())
            .limit(1)
        )
        if guardado is not None:
            return Decimal(guardado)
    return peso_seco_equivalente(tanda.estado_producto, tanda.peso_kg, factor)


def _volumen_acumulado(sesion: Session, tanda: Tanda, factor: Decimal) -> Decimal:
    """Peso seco equivalente de las tandas no anuladas de la parcela en los 365 días previos, con esta.
    La tanda con DOP anulado se trata como anulada."""
    desde = tanda.recibida_en - timedelta(days=DIAS_VOLUMEN)
    otras = list(
        sesion.scalars(
            select(Tanda).where(
                Tanda.parcela_id == tanda.parcela_id,
                Tanda.id != tanda.id,
                Tanda.estado != "anulada",
                Tanda.recibida_en > desde,
                Tanda.recibida_en <= tanda.recibida_en,
            )
        )
    )
    anuladas = _dop_anulado(sesion, [t.id for t in otras])
    total = peso_seco_equivalente(tanda.estado_producto, tanda.peso_kg, factor)
    for otra in otras:
        if otra.id not in anuladas:
            total += _peso_seco_de(sesion, otra, factor)
    return total


def _documento_vigente(sesion: Session, tanda: Tanda) -> Documento | None:
    return sesion.scalar(
        select(Documento)
        .where(
            Documento.entidad == "tanda",
            Documento.entidad_id == tanda.id,
            Documento.tipo == "documento_entrega",
            Documento.anulado_en.is_(None),
        )
        .order_by(Documento.creado_en.desc())
        .limit(1)
    )


def evaluar(contexto: Contexto, tanda: Tanda) -> dict[str, Any]:
    """Requisitos, alertas y los valores con que se evaluaron, tal como se copian en cada decisión."""
    from app.services import habilitacion, parcelas  # evita importación circular

    sesion = contexto.sesion
    conf = configuracion.de_cooperativa(sesion, tanda.cooperativa_id)
    valores_conf = configuracion.valores(conf)
    parcela = sesion.get(Parcela, tanda.parcela_id)
    # Al evaluar, la compuerta de la Parte 4 pone al día el estado de la parcela.
    habilitacion.evaluar(sesion, [parcela])
    productor = sesion.get(Productor, tanda.productor_id)
    afiliado = sesion.scalar(
        select(func.count())
        .select_from(Afiliacion)
        .where(
            Afiliacion.productor_id == productor.id,
            Afiliacion.cooperativa_id == tanda.cooperativa_id,
            Afiliacion.estado == "activa",
        )
    )
    lugar = sesion.get(Lugar, tanda.lugar_id)
    documento = _documento_vigente(sesion, tanda)
    dia_recepcion = dia_lima(tanda.recibida_en)

    datos_ok = (
        tanda.peso_kg > 0
        and tanda.variedad in variedades.CODIGOS
        and lugar is not None
        and lugar.activo
        and lugar.tipo == "cancha_acopio"
        and tanda.cosecha_desde <= tanda.cosecha_hasta <= dia_recepcion
    )
    nombre_doc = documento_entrega.nombre(tanda.doc_entrega_tipo)
    faltan_doc = [
        nombre
        for nombre, valor in (
            ("tipo", tanda.doc_entrega_tipo),
            ("número", tanda.doc_entrega_numero),
            ("fecha de emisión", tanda.doc_entrega_fecha_emision),
            ("RUC del emisor", tanda.doc_entrega_ruc_emisor),
            ("archivo", documento),
        )
        if not valor
    ]
    # Las reglas de su tipo se revisan de nuevo: el plazo de la configuración o el RUC pueden haber cambiado.
    regla_doc = None
    if not faltan_doc:
        try:
            _comprobar_documento(
                {campo: getattr(tanda, campo) for campo in (*CAMPOS_DOCUMENTO, "recibida_en")},
                sesion.get(Cooperativa, tanda.cooperativa_id),
                conf.dias_max_emision_doc_entrega,
            )
        except HTTPException as exc:
            regla_doc = exc.detail["mensaje"]
    doc_ok = not faltan_doc and regla_doc is None
    requisitos = [
        Requisito(
            codigo="parcela_habilitada",
            cumple=parcela.habilitacion_estado == "habilitada",
            detalle="La parcela está habilitada."
            if parcela.habilitacion_estado == "habilitada"
            else f"La parcela está {parcela.habilitacion_estado}: solo una parcela habilitada recibe tandas.",
        ),
        Requisito(
            codigo="productor_afiliado",
            cumple=bool(afiliado) and productor.consentimiento_datos_en is not None,
            detalle="El productor está afiliado y su consentimiento está registrado."
            if afiliado and productor.consentimiento_datos_en
            else "Falta la afiliación activa o el consentimiento de datos del productor.",
        ),
        Requisito(
            codigo="datos_completos",
            cumple=datos_ok,
            detalle="Peso, producto, variedad, lugar y cosecha están completos."
            if datos_ok
            else "Revisa el lugar (una cancha de acopio activa) y las fechas de cosecha.",
        ),
        Requisito(
            codigo="documento_entrega_completo",
            cumple=doc_ok,
            detalle=f"{nombre_doc}: tiene número, fecha, RUC del emisor y archivo."
            if doc_ok
            else regla_doc or f"Al documento de entrega le falta: {', '.join(faltan_doc)}.",
        ),
        Requisito(
            codigo="configuracion_lista",
            cumple=conf.tope_kg_seco_ha_anio is not None,
            detalle="La cooperativa tiene su tope de kilos por hectárea."
            if conf.tope_kg_seco_ha_anio is not None
            else "Falta fijar el tope de kilos por hectárea en Configuración.",
        ),
    ]

    alertas: list[str] = []
    detalle: dict[str, Any] = {}
    factor = conf.factor_baba_a_seco
    peso_seco = peso_seco_equivalente(tanda.estado_producto, tanda.peso_kg, factor)
    if conf.tope_kg_seco_ha_anio is not None and parcela.area_cultivada_ha:
        acumulado = _volumen_acumulado(sesion, tanda, factor)
        por_ha = _dos_decimales(acumulado / Decimal(parcela.area_cultivada_ha))
        detalle["volumen_acumulado_kg_seco"] = acumulado
        detalle["kg_seco_por_ha_365_dias"] = por_ha
        if por_ha > conf.tope_kg_seco_ha_anio:
            alertas.append("volumen_acumulado_excede_tope")
    dias = (dia_recepcion - tanda.cosecha_hasta).days
    maximo = (
        conf.dias_max_cosecha_entrega_baba
        if tanda.estado_producto == "baba"
        else conf.dias_max_cosecha_entrega_seco
    )
    detalle["dias_cosecha_entrega"] = dias
    if dias > maximo:
        alertas.append("dias_cosecha_entrega_altos")
    if tanda.doc_entrega_peso_kg is not None:
        diferencia = (
            abs(Decimal(tanda.doc_entrega_peso_kg) - Decimal(tanda.peso_kg)) / Decimal(tanda.peso_kg) * 100
        )
        detalle["diferencia_peso_documento_pct"] = diferencia.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if diferencia > conf.tolerancia_peso_guia_pct:
            alertas.append("peso_difiere_del_documento")
    if tanda.doc_entrega_tipo and tanda.doc_entrega_numero and tanda.doc_entrega_ruc_emisor:
        # En toda la plataforma: el fraude no respeta cooperativas. Solo se dice que existe.
        otra = sesion.scalar(
            select(func.count())
            .select_from(Tanda)
            .where(
                Tanda.doc_entrega_tipo == tanda.doc_entrega_tipo,
                Tanda.doc_entrega_numero == tanda.doc_entrega_numero,
                Tanda.doc_entrega_ruc_emisor == tanda.doc_entrega_ruc_emisor,
                Tanda.productor_id != tanda.productor_id,
                Tanda.estado != "anulada",
            )
        )
        if otra:
            alertas.append("documento_usado_por_otro_productor")
    # La liquidación de compra corresponde cuando el productor no tiene RUC (adenda 3, 6.2).
    if tanda.doc_entrega_tipo == "liquidacion_compra" and productor.ruc:
        alertas.append("liquidacion_con_productor_con_ruc")
    alertas_parcela = parcelas.salidas(contexto, [parcela])[0].alertas if parcela.estado == "activa" else []
    if parcela.habilitacion_estado == "habilitada" and alertas_parcela:
        alertas.append("parcela_con_alertas")
        detalle["alertas_parcela"] = alertas_parcela

    return {
        "requisitos": requisitos,
        "alertas": alertas,
        "alertas_parcela": alertas_parcela,
        "detalle": detalle,
        "configuracion": valores_conf,
        "peso_seco_equivalente_kg": peso_seco,
        "documento": documento,
    }


def _foto(evaluacion: dict[str, Any]) -> dict[str, Any]:
    """Copia de requisitos, alertas y valores de configuración usados, para la decisión."""
    return {
        "requisitos": [r.model_dump() for r in evaluacion["requisitos"]],
        "alertas": evaluacion["alertas"],
        "alertas_parcela": evaluacion["alertas_parcela"],
        "detalle": evaluacion["detalle"],
        "configuracion": evaluacion["configuracion"],
        "peso_seco_equivalente_kg": evaluacion["peso_seco_equivalente_kg"],
    }


def _json(valor: Any) -> Any:
    """Decimales y fechas a texto, para guardar en jsonb."""
    if isinstance(valor, dict):
        return {k: _json(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_json(v) for v in valor]
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, datetime) or hasattr(valor, "isoformat"):
        return valor.isoformat()
    if isinstance(valor, uuid.UUID):
        return str(valor)
    return valor


# ---------- Decisiones ----------


def validar(
    contexto: Contexto, storage: ClienteStorage, tanda_id: uuid.UUID, nota: str | None
) -> TandaDetalle:
    """Valida la tanda y emite su DOP en una sola transacción: si la emisión falla, nada queda."""
    from app.services import dops  # evita importación circular

    tanda = tanda_visible(contexto, tanda_id)
    _exigir_editable(tanda)
    evaluacion = evaluar(contexto, tanda)
    incumplidos = [r for r in evaluacion["requisitos"] if not r.cumple]
    if incumplidos:
        contexto.sesion.commit()  # deja confirmado lo que la compuerta de la Parte 4 haya cambiado
        nombres = ", ".join(NOMBRE_REQUISITO[r.codigo].lower() for r in incumplidos)
        error = error_api(400, "requisitos_incompletos", f"Falta: {nombres}.")
        error.detail["faltan"] = [r.codigo for r in incumplidos]
        raise error
    nota = (nota or "").strip() or None
    if evaluacion["alertas"] and (not nota or len(nota) < NOTA_MINIMA):
        raise error_api(
            422,
            "nota_requerida",
            f"La tanda tiene alertas: escribe una nota de al menos {NOTA_MINIMA} caracteres para validar.",
        )

    momento = ahora()
    foto = _json(_foto(evaluacion))
    decision = DecisionTanda(
        tanda_id=tanda.id,
        decision="validar",
        decidida_por=contexto.usuario_id,
        decidida_en=momento,
        nota=nota,
        requisitos=foto,
    )
    contexto.sesion.add(decision)
    tanda.estado = "validada"
    contexto.sesion.flush()
    ruta_pdf = None
    try:
        dop, ruta_pdf = dops.emitir(contexto, storage, tanda, evaluacion, nota, momento)
        registrar_auditoria(
            contexto,
            "tanda.validar",
            "tanda",
            tanda.id,
            {"codigo": tanda.codigo, "alertas": evaluacion["alertas"], "nota": nota, "dop": dop.codigo},
        )
        contexto.sesion.commit()
    except Exception:
        contexto.sesion.rollback()
        if ruta_pdf:
            documentos.descartar(storage, ruta_pdf)
        raise
    return obtener(contexto, tanda.id)


def _decidir(contexto: Contexto, tanda_id: uuid.UUID, decision: str, motivo: str, desde: tuple[str, ...]):
    tanda = tanda_visible(contexto, tanda_id)
    if tanda.estado not in desde:
        _exigir_editable(tanda)
        raise error_api(400, f"tanda_{tanda.estado}", "La tanda ya está observada: corrígela y valídala.")
    evaluacion = evaluar(contexto, tanda)
    contexto.sesion.add(
        DecisionTanda(
            tanda_id=tanda.id,
            decision=decision,
            decidida_por=contexto.usuario_id,
            decidida_en=ahora(),
            nota=motivo,
            requisitos=_json(_foto(evaluacion)),
        )
    )
    tanda.estado = {"observar": "observada", "anular": "anulada"}[decision]
    registrar_auditoria(
        contexto, f"tanda.{decision}", "tanda", tanda.id, {"codigo": tanda.codigo, "motivo": motivo}
    )
    contexto.sesion.commit()
    return obtener(contexto, tanda.id)


def observar(contexto: Contexto, tanda_id: uuid.UUID, motivo: str) -> TandaDetalle:
    return _decidir(contexto, tanda_id, "observar", motivo, ("registrada",))


def anular(contexto: Contexto, tanda_id: uuid.UUID, motivo: str) -> TandaDetalle:
    return _decidir(contexto, tanda_id, "anular", motivo, EDITABLES)


# ---------- Salidas ----------


def _nombres(sesion: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return dict(
        sesion.execute(
            select(Perfil.id, func.concat(Perfil.nombres, " ", Perfil.apellidos)).where(Perfil.id.in_(ids))
        ).all()
    )


def _salidas(sesion: Session, tandas: list[Tanda]) -> list[TandaSalida]:
    if not tandas:
        return []
    productores = {
        p.id: p
        for p in sesion.scalars(select(Productor).where(Productor.id.in_({t.productor_id for t in tandas})))
    }
    parcelas_ = {
        p.id: p for p in sesion.scalars(select(Parcela).where(Parcela.id.in_({t.parcela_id for t in tandas})))
    }
    lugares = {
        lu.id: lu for lu in sesion.scalars(select(Lugar).where(Lugar.id.in_({t.lugar_id for t in tandas})))
    }
    dops_ = {
        d.tanda_id: d for d in sesion.scalars(select(Dop).where(Dop.tanda_id.in_([t.id for t in tandas])))
    }
    nombres = _nombres(sesion, {t.registrada_por for t in tandas})
    factores = {}
    salida = []
    for t in tandas:
        if t.cooperativa_id not in factores:
            factores[t.cooperativa_id] = configuracion.de_cooperativa(
                sesion, t.cooperativa_id
            ).factor_baba_a_seco
        prod, par, dop = productores[t.productor_id], parcelas_[t.parcela_id], dops_.get(t.id)
        salida.append(
            TandaSalida(
                id=t.id,
                codigo=t.codigo,
                estado=t.estado,
                productor=ProductorDeTanda(
                    id=prod.id, dni=prod.dni, nombres=prod.nombres, apellidos=prod.apellidos
                ),
                parcela=ParcelaDeTanda(
                    id=par.id,
                    codigo=par.codigo,
                    nombre=par.nombre,
                    habilitacion_estado=par.habilitacion_estado,
                ),
                lugar_id=t.lugar_id,
                lugar_nombre=lugares[t.lugar_id].nombre,
                recibida_en=t.recibida_en,
                estado_producto=t.estado_producto,
                peso_kg=t.peso_kg,
                peso_seco_equivalente_kg=_peso_seco_de(sesion, t, factores[t.cooperativa_id]),
                numero_sacos=t.numero_sacos,
                humedad_pct=t.humedad_pct,
                variedad=t.variedad,
                variedad_otra=t.variedad_otra,
                variedad_nombre=variedades.nombre(t.variedad, t.variedad_otra),
                tipo_semilla=t.tipo_semilla,
                cosecha_desde=t.cosecha_desde,
                cosecha_hasta=t.cosecha_hasta,
                doc_entrega_tipo=t.doc_entrega_tipo,
                doc_entrega_tipo_nombre=documento_entrega.nombre(t.doc_entrega_tipo)
                if t.doc_entrega_tipo
                else None,
                doc_entrega_numero=t.doc_entrega_numero,
                doc_entrega_fecha_emision=t.doc_entrega_fecha_emision,
                doc_entrega_ruc_emisor=t.doc_entrega_ruc_emisor,
                doc_entrega_peso_kg=t.doc_entrega_peso_kg,
                registrada_por_nombre=nombres.get(t.registrada_por),
                creado_en=t.creado_en,
                dop=DopDeTanda(id=dop.id, codigo=dop.codigo, estado=dop.estado) if dop else None,
            )
        )
    return salida


def decisiones(sesion: Session, tanda_id: uuid.UUID) -> list[DecisionTandaSalida]:
    filas = list(
        sesion.scalars(
            select(DecisionTanda)
            .where(DecisionTanda.tanda_id == tanda_id)
            .order_by(DecisionTanda.decidida_en, DecisionTanda.id)
        )
    )
    nombres = _nombres(sesion, {d.decidida_por for d in filas})
    return [
        DecisionTandaSalida(
            id=d.id,
            decision=d.decision,
            decidida_por_nombre=nombres.get(d.decidida_por),
            decidida_en=d.decidida_en,
            nota=d.nota,
        )
        for d in filas
    ]


def obtener(contexto: Contexto, tanda_id: uuid.UUID) -> TandaDetalle:
    tanda = tanda_visible(contexto, tanda_id)
    base = _salidas(contexto.sesion, [tanda])[0]
    if tanda.estado in EDITABLES:
        evaluacion = evaluar(contexto, tanda)
        requisitos, alertas, detalle = evaluacion["requisitos"], evaluacion["alertas"], evaluacion["detalle"]
    else:
        # Validada o anulada: lo que se evaluó al decidir, no lo de hoy.
        ultima = contexto.sesion.scalar(
            select(DecisionTanda)
            .where(DecisionTanda.tanda_id == tanda.id, DecisionTanda.decision.in_(("validar", "anular")))
            .order_by(DecisionTanda.decidida_en.desc())
            .limit(1)
        )
        foto = ultima.requisitos if ultima else {}
        requisitos = [Requisito(**r) for r in foto.get("requisitos", [])]
        alertas, detalle = foto.get("alertas", []), foto.get("detalle", {})
    docs = [documento_salida(d, n) for d, n in documentos.documentos_de(contexto.sesion, "tanda", tanda.id)]
    return TandaDetalle(
        **base.model_dump(),
        requisitos=requisitos,
        alertas=alertas,
        alertas_detalle=_json(detalle),
        puede_validar=tanda.estado in EDITABLES and all(r.cumple for r in requisitos),
        nota_obligatoria=bool(alertas),
        documentos=docs,
        decisiones=decisiones(contexto.sesion, tanda.id),
    )


def listar(
    contexto: Contexto,
    *,
    estado: str | None = None,
    productor_id: uuid.UUID | None = None,
    parcela_id: uuid.UUID | None = None,
    desde=None,
    hasta=None,
    busqueda: str | None = None,
) -> list[TandaSalida]:
    consulta = select(Tanda).where(Tanda.cooperativa_id == cooperativa_del_contexto(contexto))
    if contexto.rol == "productor":
        consulta = consulta.where(Tanda.productor_id == contexto.productor_id)
    if estado:
        consulta = consulta.where(Tanda.estado == estado)
    if productor_id:
        consulta = consulta.where(Tanda.productor_id == productor_id)
    if parcela_id:
        consulta = consulta.where(Tanda.parcela_id == parcela_id)
    if desde:
        consulta = consulta.where(Tanda.recibida_en >= datetime.combine(desde, datetime.min.time(), LIMA))
    if hasta:
        consulta = consulta.where(
            Tanda.recibida_en < datetime.combine(hasta, datetime.min.time(), LIMA) + timedelta(days=1)
        )
    if busqueda:
        patron = f"%{busqueda.strip()}%"
        consulta = (
            consulta.join(Productor, Productor.id == Tanda.productor_id)
            .join(Parcela, Parcela.id == Tanda.parcela_id)
            .where(
                or_(
                    Tanda.codigo.ilike(patron),
                    Productor.dni.ilike(patron),
                    func.concat(Productor.nombres, " ", Productor.apellidos).ilike(patron),
                    Parcela.codigo.ilike(patron),
                    Parcela.nombre.ilike(patron),
                )
            )
        )
    tandas = list(contexto.sesion.scalars(consulta.order_by(Tanda.recibida_en.desc()).limit(500)))
    return _salidas(contexto.sesion, tandas)

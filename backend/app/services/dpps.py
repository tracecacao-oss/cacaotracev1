"""El DPP (Parte 6): copia sellada de una corrida consolidada. Qué DOP entraron, qué pasó en cada etapa y qué
salió. Se sella, se convierte en PDF y se verifica igual que el DOP (app/services/sello.py).

Las tandas finales (el stock) también viven aquí: cada una nace con su DPP y su composición por DOP.
"""

import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogos import etapas_proceso as catalogo
from app.config import get_settings
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import LIMA, ahora
from app.models import (
    Cooperativa,
    Corrida,
    CorridaEtapa,
    CorridaTanda,
    Documento,
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
    ComponenteDeTandaFinal,
    DppDetalle,
    DppPublico,
    DppSalida,
    Referencia,
    Rendimiento,
    TandaFinalDetalle,
    TandaFinalSalida,
)
from app.schemas.recepcion import ProductorDeTanda
from app.services import correlativos, documentos, sello
from app.services.auditoria import registrar_auditoria
from app.services.documentos import Archivo
from app.services.dops import matriz_qr
from app.storage import ClienteStorage, ErrorStorage

VERSION_CONTENIDO = 1
LEYENDA = (
    "Este documento reúne el registro del procesamiento de un lote de cacao tal como estaba al consolidarse. "
    "No es una constancia ni un certificado"
)
RUTA = {"completa": "Completa (cacao en baba)", "seco": "Seco (grano entregado seco)"}
MANEJO = {"segregado": "Segregado (un solo productor)", "mezclado": "Mezclado (varios productores)"}


def url_verificacion(codigo: str) -> str:
    return f"{get_settings().url_interfaz.rstrip('/')}/#/verificar/dpp/{codigo}"


def _texto(valor: Any) -> Any:
    """Valores listos para JSON: decimales y fechas como texto."""
    if isinstance(valor, dict):
        return {k: _texto(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_texto(v) for v in valor]
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return valor


def _nombre(sesion: Session, perfil_id: uuid.UUID | None) -> str | None:
    if perfil_id is None:
        return None
    perfil = sesion.get(Perfil, perfil_id)
    return f"{perfil.nombres} {perfil.apellidos}".strip() if perfil else None


# ---------- Contenido sellado ----------


def _bloque_entrada(sesion: Session, filas: list[CorridaTanda]) -> dict[str, Any]:
    tandas = {t.id: t for t in sesion.scalars(select(Tanda).where(Tanda.id.in_([f.tanda_id for f in filas])))}
    dops = {d.tanda_id: d for d in sesion.scalars(select(Dop).where(Dop.tanda_id.in_(list(tandas))))}
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
    entrada = []
    for f in filas:
        t = tandas[f.tanda_id]
        d, p, pa = dops[t.id], productores[t.productor_id], parcelas[t.parcela_id]
        entrada.append(
            {
                "tanda": t.codigo,
                "dop": d.codigo,
                "dop_sha256": d.contenido_sha256,
                "productor": {"nombres": f"{p.nombres} {p.apellidos}", "dni": p.dni},
                "parcela": {"codigo": pa.codigo, "nombre": pa.nombre},
                "estado_producto": t.estado_producto,
                "recibida_en": t.recibida_en,
                "peso_kg": f.peso_kg,
                "proporcion": f.proporcion,
            }
        )
    return {"tandas": entrada, "peso_total_kg": sum((Decimal(f.peso_kg) for f in filas), Decimal("0"))}


def _bloque_etapas(sesion: Session, etapas: dict[int, CorridaEtapa]) -> list[dict[str, Any]]:
    lugares = {
        lu.id: lu.nombre
        for lu in sesion.scalars(
            select(Lugar).where(Lugar.id.in_([e.lugar_id for e in etapas.values() if e.lugar_id]))
        )
    }
    bloque = []
    for e in catalogo.ETAPAS:
        fila = etapas[e.numero]
        horas = None
        if fila.inicio and fila.fin:
            horas = (Decimal((fila.fin - fila.inicio).total_seconds()) / Decimal(3600)).quantize(
                Decimal("0.01")
            )
        bloque.append(
            {
                "numero": e.numero,
                "nombre": e.nombre,
                "tipo": e.tipo,
                "fase": e.fase,
                "situacion": fila.situacion,
                "lugar": lugares.get(fila.lugar_id),
                "inicio": fila.inicio,
                "fin": fila.fin,
                "duracion_horas": horas,
                "metodo": fila.metodo,
                "responsable": fila.responsable,
                "distancia_m": fila.distancia_m,
                "datos": fila.datos or {},
                "desde_plantilla": fila.desde_plantilla,
            }
        )
    return bloque


def _no_verificado(etapas: list[dict[str, Any]], ruta: str) -> list[str]:
    """Etapas confirmadas con los valores de la plantilla sin cambios, y pesos sin un documento detrás."""
    lista = [
        f"Etapa {e['numero']} ({e['nombre']}): se confirmó con el lugar, el método y la distancia de la "
        "plantilla, sin corregirlos."
        for e in etapas
        if e["desde_plantilla"]
    ]
    lista.append(
        "El peso final (etapa 19) y los kilos descartados (etapa 18) los declara quien registró la etapa; "
        "ningún documento los respalda."
    )
    if ruta == "completa":
        lista.append("La humedad (etapa 13) la declara quien registró la etapa.")
    lista.append("El sistema no comprueba el vínculo físico entre el grano que entró y el que salió.")
    return lista


def construir_contenido(
    sesion: Session,
    contexto: Contexto,
    corrida: Corrida,
    tanda_final: TandaFinal,
    filas: list[CorridaTanda],
    etapas: dict[int, CorridaEtapa],
    rendimiento: Rendimiento,
    alertas: list[str],
    explicacion: str | None,
    codigo: str,
    momento: datetime,
) -> dict[str, Any]:
    cooperativa = sesion.get(Cooperativa, corrida.cooperativa_id)
    almacen = sesion.get(Lugar, tanda_final.lugar_id)
    bloque_etapas = _bloque_etapas(sesion, etapas)
    contenido = {
        "version": VERSION_CONTENIDO,
        "leyenda": LEYENDA,
        "identificacion": {
            "codigo": codigo,
            "cooperativa": {
                "razon_social": cooperativa.razon_social,
                "ruc": cooperativa.ruc,
                "codigo": cooperativa.codigo,
            },
            "emitido_en": momento,
            "corrida": corrida.codigo,
            "ruta": corrida.ruta,
            "tipo_manejo": corrida.tipo_manejo,
            "consolidada_por": _nombre(sesion, contexto.usuario_id),
        },
        "entrada": _bloque_entrada(sesion, filas),
        "etapas": bloque_etapas,
        "salida": {
            "tanda_final": tanda_final.codigo,
            "peso_final_kg": tanda_final.peso_seco_kg,
            "humedad_pct": tanda_final.humedad_pct,
            "calidad": tanda_final.calidad,
            "numero_sacos": tanda_final.numero_sacos,
            "almacen": almacen.nombre,
        },
        "rendimiento": {
            "ruta": corrida.ruta,
            "entrada_kg": rendimiento.entrada_kg,
            "peso_final_kg": rendimiento.peso_final_kg,
            "rendimiento": rendimiento.rendimiento,
            "banda_min": rendimiento.banda_min,
            "banda_max": rendimiento.banda_max,
        },
        "alertas": {"alertas": alertas, "explicacion": explicacion},
        "no_verificado": _no_verificado(bloque_etapas, corrida.ruta),
    }
    return _texto(contenido)


def emitir(
    contexto: Contexto,
    storage: ClienteStorage,
    corrida: Corrida,
    tanda_final: TandaFinal,
    filas: list[CorridaTanda],
    etapas: dict[int, CorridaEtapa],
    rendimiento: Rendimiento,
    alertas: list[str],
    explicacion: str | None,
    momento: datetime,
) -> tuple[Dpp, str]:
    """Emite el DPP dentro de la transacción de la consolidación. Devuelve (dpp, ruta del PDF en Storage)
    para que quien llama borre el archivo si la transacción falla."""
    from app.pdf import dpp as pdf_dpp  # evita cargar fpdf2 al importar

    sesion = contexto.sesion
    cooperativa = sesion.get(Cooperativa, corrida.cooperativa_id)
    anio = momento.astimezone(LIMA).year
    numero = correlativos.siguiente(sesion, corrida.cooperativa_id, "dpp", anio)
    codigo = f"DPP-{cooperativa.codigo}-{anio}-{numero:06d}"
    contenido = construir_contenido(
        sesion,
        contexto,
        corrida,
        tanda_final,
        filas,
        etapas,
        rendimiento,
        alertas,
        explicacion,
        codigo,
        momento,
    )
    huella = sello.huella(contenido)
    dpp = Dpp(
        cooperativa_id=corrida.cooperativa_id,
        codigo=codigo,
        corrida_id=corrida.id,
        tanda_final_id=tanda_final.id,
        emitido_en=momento,
        emitido_por=contexto.usuario_id,
        contenido=contenido,
        contenido_sha256=huella,
        estado="vigente",
    )
    sesion.add(dpp)
    sesion.flush()
    pdf = pdf_dpp.generar(contenido, huella, url_verificacion(codigo))
    documento, ruta = documentos.guardar(
        contexto,
        storage,
        entidad="dpp",
        entidad_id=dpp.id,
        tipo="dpp_pdf",
        archivo=Archivo(nombre=f"{codigo}.pdf", contenido=pdf),
    )
    dpp.pdf_documento_id = documento.id
    registrar_auditoria(
        contexto,
        "dpp.emitir",
        "dpp",
        dpp.id,
        {"codigo": codigo, "corrida": corrida.codigo, "tanda_final": tanda_final.codigo, "sha256": huella},
    )
    sesion.flush()
    return dpp, ruta


# ---------- Consultas del DPP ----------


def dpp_visible(contexto: Contexto, dpp_id: uuid.UUID) -> Dpp:
    dpp = contexto.sesion.get(Dpp, dpp_id)
    if dpp is None or dpp.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("El DPP no existe.")
    return dpp


def _salidas(sesion: Session, dpps: list[Dpp]) -> list[DppSalida]:
    if not dpps:
        return []
    corridas = {
        c.id: c for c in sesion.scalars(select(Corrida).where(Corrida.id.in_({d.corrida_id for d in dpps})))
    }
    finales = {
        t.id: t
        for t in sesion.scalars(select(TandaFinal).where(TandaFinal.id.in_([d.tanda_final_id for d in dpps])))
    }
    return [
        DppSalida(
            id=d.id,
            codigo=d.codigo,
            estado=d.estado,
            corrida_id=d.corrida_id,
            corrida_codigo=corridas[d.corrida_id].codigo,
            tanda_final_id=d.tanda_final_id,
            tanda_final_codigo=finales[d.tanda_final_id].codigo,
            peso_seco_kg=finales[d.tanda_final_id].peso_seco_kg,
            emitido_en=d.emitido_en,
            contenido_sha256=d.contenido_sha256,
        )
        for d in dpps
    ]


def listar(contexto: Contexto, estado: str | None = None) -> list[DppSalida]:
    consulta = select(Dpp).where(Dpp.cooperativa_id == cooperativa_del_contexto(contexto))
    if estado:
        consulta = consulta.where(Dpp.estado == estado)
    return _salidas(
        contexto.sesion, list(contexto.sesion.scalars(consulta.order_by(Dpp.emitido_en.desc()).limit(500)))
    )


def obtener(contexto: Contexto, dpp_id: uuid.UUID) -> DppDetalle:
    dpp = dpp_visible(contexto, dpp_id)
    url = url_verificacion(dpp.codigo)
    return DppDetalle(
        **_salidas(contexto.sesion, [dpp])[0].model_dump(),
        contenido=dpp.contenido,
        url_verificacion=url,
        qr=matriz_qr(url),
        anulado_en=dpp.anulado_en,
        anulado_por_nombre=_nombre(contexto.sesion, dpp.anulado_por),
        motivo_anulacion=dpp.motivo_anulacion,
    )


def url_pdf(contexto: Contexto, storage: ClienteStorage, dpp_id: uuid.UUID) -> str:
    dpp = dpp_visible(contexto, dpp_id)
    documento = contexto.sesion.get(Documento, dpp.pdf_documento_id)
    try:
        return storage.url_firmada(documento.ruta, descarga=f"{dpp.codigo}.pdf")
    except ErrorStorage as exc:
        raise error_api(
            503, "archivos_no_disponibles", "No se pudo preparar la descarga. Intenta de nuevo."
        ) from exc


def anular(contexto: Contexto, dpp_id: uuid.UUID, motivo: str) -> DppDetalle:
    """Solo si ninguna orden de compra usó la tanda final. La tanda final queda anulada y la corrida vuelve a
    en_proceso para corregirse; consolidar de nuevo emite otro DPP."""
    sesion = contexto.sesion
    dpp = dpp_visible(contexto, dpp_id)
    if dpp.estado == "anulado":
        raise error_api(400, "dpp_anulado", "El DPP ya estaba anulado.")
    tanda_final = sesion.get(TandaFinal, dpp.tanda_final_id)
    if tanda_final.saldo_kg != tanda_final.peso_seco_kg:
        raise error_api(
            400,
            "tanda_final_usada",
            "La tanda final ya se usó en una orden de compra: el DPP no se puede anular.",
        )
    momento = ahora()
    dpp.estado = "anulado"
    dpp.anulado_en = momento
    dpp.anulado_por = contexto.usuario_id
    dpp.motivo_anulacion = motivo
    tanda_final.estado = "anulada"
    corrida = sesion.get(Corrida, dpp.corrida_id)
    corrida.estado = "en_proceso"
    corrida.consolidada_en = None
    registrar_auditoria(
        contexto,
        "dpp.anular",
        "dpp",
        dpp.id,
        {
            "codigo": dpp.codigo,
            "motivo": motivo,
            "corrida": corrida.codigo,
            "tanda_final": tanda_final.codigo,
        },
    )
    sesion.commit()
    sesion.refresh(dpp)
    return obtener(contexto, dpp.id)


def publico(sesion: Session, codigo: str) -> DppPublico:
    """Sin token: solo código, estado, fecha de emisión, huella y razón social."""
    fila = sesion.execute(
        select(Dpp, Cooperativa.razon_social)
        .join(Cooperativa, Cooperativa.id == Dpp.cooperativa_id)
        .where(Dpp.codigo == codigo.strip().upper())
    ).first()
    if fila is None:
        raise no_encontrado("No existe un DPP con ese código.")
    dpp, razon_social = fila
    return DppPublico(
        codigo=dpp.codigo,
        estado=dpp.estado,
        emitido_en=dpp.emitido_en,
        contenido_sha256=dpp.contenido_sha256,
        cooperativa=razon_social,
    )


# ---------- Tandas finales (stock) ----------


def tanda_final_visible(contexto: Contexto, tanda_final_id: uuid.UUID) -> TandaFinal:
    tf = contexto.sesion.get(TandaFinal, tanda_final_id)
    if tf is None or tf.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("La tanda final no existe.")
    return tf


def _salidas_finales(sesion: Session, finales: list[TandaFinal]) -> list[TandaFinalSalida]:
    if not finales:
        return []
    corridas = {
        c.id: c
        for c in sesion.scalars(select(Corrida).where(Corrida.id.in_({t.corrida_id for t in finales})))
    }
    lugares = {
        lu.id: lu for lu in sesion.scalars(select(Lugar).where(Lugar.id.in_({t.lugar_id for t in finales})))
    }
    dpps = {
        d.tanda_final_id: d
        for d in sesion.scalars(select(Dpp).where(Dpp.tanda_final_id.in_([t.id for t in finales])))
    }
    from app.services import recomprobacion  # evita importación circular

    retenidas = recomprobacion.retenidas(sesion, [t.id for t in finales])
    return [
        TandaFinalSalida(
            id=t.id,
            codigo=t.codigo,
            corrida_id=t.corrida_id,
            corrida_codigo=corridas[t.corrida_id].codigo,
            peso_seco_kg=t.peso_seco_kg,
            saldo_kg=t.saldo_kg,
            humedad_pct=t.humedad_pct,
            calidad=t.calidad,
            calidad_id=t.calidad_id,
            numero_sacos=t.numero_sacos,
            lugar_id=t.lugar_id,
            lugar_nombre=lugares[t.lugar_id].nombre,
            ingreso_stock_en=t.ingreso_stock_en,
            estado=t.estado,
            dpp=Referencia(id=dpps[t.id].id, codigo=dpps[t.id].codigo, estado=dpps[t.id].estado)
            if t.id in dpps
            else None,
            retenida=t.id in retenidas,
        )
        for t in finales
    ]


def listar_finales(
    contexto: Contexto, estado: str | None = None, calidad_id: uuid.UUID | None = None
) -> list[TandaFinalSalida]:
    consulta = select(TandaFinal).where(TandaFinal.cooperativa_id == cooperativa_del_contexto(contexto))
    if estado:
        consulta = consulta.where(TandaFinal.estado == estado)
    if calidad_id:
        consulta = consulta.where(TandaFinal.calidad_id == calidad_id)
    finales = list(contexto.sesion.scalars(consulta.order_by(TandaFinal.ingreso_stock_en).limit(500)))
    return _salidas_finales(contexto.sesion, finales)


def obtener_final(contexto: Contexto, tanda_final_id: uuid.UUID) -> TandaFinalDetalle:
    """Con su composición por DOP: los kilos atribuibles a cada uno son su proporción por el peso seco."""
    sesion = contexto.sesion
    tf = tanda_final_visible(contexto, tanda_final_id)
    filas = list(
        sesion.scalars(
            select(CorridaTanda)
            .where(CorridaTanda.corrida_id == tf.corrida_id, CorridaTanda.liberada_en.is_(None))
            .order_by(CorridaTanda.agregada_en)
        )
    )
    tandas = {t.id: t for t in sesion.scalars(select(Tanda).where(Tanda.id.in_([f.tanda_id for f in filas])))}
    dops = {d.tanda_id: d for d in sesion.scalars(select(Dop).where(Dop.tanda_id.in_(list(tandas))))}
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
    composicion = []
    for f in filas:
        t = tandas[f.tanda_id]
        p, pa, d = productores[t.productor_id], parcelas[t.parcela_id], dops.get(t.id)
        proporcion = f.proporcion or Decimal("0")
        composicion.append(
            ComponenteDeTandaFinal(
                tanda_id=t.id,
                tanda_codigo=t.codigo,
                dop=Referencia(id=d.id, codigo=d.codigo, estado=d.estado) if d else None,
                productor=ProductorDeTanda(id=p.id, dni=p.dni, nombres=p.nombres, apellidos=p.apellidos),
                parcela_codigo=pa.codigo,
                parcela_nombre=pa.nombre,
                peso_entrada_kg=f.peso_kg,
                proporcion=proporcion,
                kg_atribuibles=(proporcion * Decimal(tf.peso_seco_kg)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
            )
        )
    return TandaFinalDetalle(**_salidas_finales(sesion, [tf])[0].model_dump(), composicion=composicion)

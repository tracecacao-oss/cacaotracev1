"""Documentos de embarque del lote (Parte 8; adendas 6 y 7): los del catálogo documentos_embarque.py.
Los obligatorios se cargan en un lote armado, bloqueado o listo, antes de emitir el DEX. La declaración
aduanera (`dam`) no es obligatoria y se puede agregar también con el lote cerrado, sin cambiar el DEX emitido.

Desde la adenda 7, la declaración aduanera guarda sus cuatro datos en `declaraciones_aduaneras` (número, fecha
de numeración, peso neto y subpartida) y el sistema los compara con el lote al cargarla y cada vez que se
consulta. La comparación no bloquea. Un lote tiene como máximo una sin anular; se anula con su archivo.

El sistema no lee el contenido de ningún documento ni compara las cifras de la factura con las del lote: eso
lo revisa una persona. Compara solo lo que la persona escribió de la declaración aduanera.
"""

import re
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select

from app.catalogos import documentos_embarque as catalogo
from app.config import get_settings
from app.contexto import Contexto
from app.errores import error_api
from app.fechas import ahora, hoy_lima
from app.models import DeclaracionAduanera, Documento, Lote, OrdenCompra, Perfil
from app.schemas.cooperativa import (
    ComparacionAduanera,
    ConsultaPublica,
    DeclaracionAduaneraSalida,
    DocumentoEmbarque,
    EmbarqueSalida,
)
from app.services import documentos
from app.services.auditoria import registrar_auditoria
from app.services.documentos import ESTADOS_LOTE_CON_EMBARQUE, Archivo, lote_admite
from app.services.lotes import lote_visible
from app.storage import ClienteStorage

CENTIMO = Decimal("0.01")
ALERTA_DIFIERE = "dam_difiere_del_lote"


# ---------- Comparación con el lote (adenda 7, sección 4.2) ----------


def comparar(sesion, declaracion: DeclaracionAduanera, lote: Lote) -> ComparacionAduanera:
    """El peso declarado frente a la masa neta del lote, y la subpartida frente a la partida de la orden."""
    tolerancia = Decimal(get_settings().dam_tolerancia_peso_pct)
    partida = sesion.get(OrdenCompra, lote.orden_compra_id).partida_sa
    peso = Decimal(declaracion.peso_neto_kg)
    masa = Decimal(lote.masa_neta_kg) if lote.masa_neta_kg is not None else None
    diferencia = (peso - masa).quantize(CENTIMO) if masa is not None else None
    pct = (
        (diferencia / masa * 100).quantize(CENTIMO, ROUND_HALF_UP) if masa is not None and masa > 0 else None
    )
    peso_difiere = pct is not None and abs(pct) > tolerancia
    subpartida_difiere = not declaracion.subpartida.startswith(partida)
    return ComparacionAduanera(
        peso_lote_kg=masa,
        peso_declarado_kg=peso,
        diferencia_kg=diferencia,
        diferencia_pct=pct,
        tolerancia_pct=tolerancia,
        peso_difiere=peso_difiere,
        partida_orden=partida,
        subpartida=declaracion.subpartida,
        subpartida_difiere=subpartida_difiere,
        difiere=peso_difiere or subpartida_difiere,
    )


def vigente(sesion, lote_id: uuid.UUID) -> DeclaracionAduanera | None:
    """La declaración aduanera sin anular del lote, si la hay."""
    return sesion.scalar(
        select(DeclaracionAduanera).where(
            DeclaracionAduanera.lote_id == lote_id, DeclaracionAduanera.anulada_en.is_(None)
        )
    )


def salida_declaracion(sesion, declaracion: DeclaracionAduanera, lote: Lote) -> DeclaracionAduaneraSalida:
    from app.services.productores import documento_salida  # evita importación circular

    documento = sesion.get(Documento, declaracion.documento_id)
    perfil = sesion.get(Perfil, declaracion.registrada_por)
    return DeclaracionAduaneraSalida(
        id=declaracion.id,
        numero=declaracion.numero,
        fecha_numeracion=declaracion.fecha_numeracion,
        peso_neto_kg=declaracion.peso_neto_kg,
        subpartida=declaracion.subpartida,
        posterior_al_dex=declaracion.posterior_al_dex,
        registrada_por_nombre=f"{perfil.nombres} {perfil.apellidos}".strip() if perfil else None,
        registrada_en=declaracion.registrada_en,
        documento=documento_salida(documento, None) if documento else None,
        comparacion=comparar(sesion, declaracion, lote),
    )


# ---------- Lista ----------


def listar(contexto: Contexto, lote_id: uuid.UUID) -> EmbarqueSalida:
    from app.services.productores import documento_salida  # evita importación circular

    sesion = contexto.sesion
    lote = lote_visible(contexto, lote_id)
    filas = list(
        sesion.scalars(
            select(Documento)
            .where(Documento.entidad == "lote", Documento.entidad_id == lote.id)
            .order_by(Documento.creado_en.desc())
        )
    )
    nombres = dict(
        sesion.execute(
            select(Perfil.id, func.concat(Perfil.nombres, " ", Perfil.apellidos)).where(
                Perfil.id.in_({d.subido_por for d in filas})
            )
        ).all()
    )
    declaracion = vigente(sesion, lote.id)
    tipos = []
    for t in catalogo.TIPOS:
        propios = [d for d in filas if d.tipo == t.codigo]
        # Adenda 7: la declaración aduanera cuenta por su registro con los cuatro datos.
        cargado = declaracion is not None if t.codigo == "dam" else any(d.anulado_en is None for d in propios)
        tipos.append(
            DocumentoEmbarque(
                codigo=t.codigo,
                nombre=t.nombre,
                emisor_habitual=t.emisor_habitual,
                obligatorio=t.obligatorio,
                registro_consultable=t.registro_consultable,
                editable=lote_admite(t.codigo, lote.estado),
                consultas=[
                    ConsultaPublica(url=url, nombre=nombre)
                    for url, nombre in (catalogo.CONSULTAS_DAM if t.codigo == "dam" else ())
                ],
                cargado=cargado,
                documentos=[documento_salida(d, nombres.get(d.subido_por)) for d in propios],
            )
        )
    faltan = [t.nombre for t in tipos if t.obligatorio and not t.cargado]
    return EmbarqueSalida(
        completo=not faltan,
        faltan=faltan,
        editable=lote.estado in ESTADOS_LOTE_CON_EMBARQUE,
        tipos=tipos,
        declaracion=salida_declaracion(sesion, declaracion, lote) if declaracion else None,
    )


# ---------- Carga ----------


def _datos_dam(
    numero: str | None,
    fecha_numeracion: date | None,
    peso_neto_kg: Decimal | None,
    subpartida: str | None,
) -> dict:
    """Adenda 7, sección 4.1: número, fecha de numeración, peso neto y subpartida. El número no tiene un
    formato confirmado (texto de 5 a 30 caracteres); la subpartida se guarda solo con dígitos."""
    faltan = [
        n
        for n, v in (
            ("número", numero),
            ("fecha de numeración", fecha_numeracion),
            ("peso neto", peso_neto_kg),
            ("subpartida", subpartida),
        )
        if v in (None, "")
    ]
    if faltan:
        raise error_api(422, "datos_requeridos", f"Falta: {', '.join(faltan)}.")
    numero = numero.strip()
    minimo, maximo = catalogo.LARGO_NUMERO_DAM
    if not minimo <= len(numero) <= maximo:
        raise error_api(
            422,
            "numero_invalido",
            f"El número de la declaración aduanera tiene de {minimo} a {maximo} caracteres.",
        )
    if fecha_numeracion > hoy_lima():
        raise error_api(422, "fecha_futura", "La fecha de numeración no puede ser futura.")
    if peso_neto_kg <= 0:
        raise error_api(422, "peso_invalido", "El peso neto declarado debe ser mayor que 0.")
    digitos = re.sub(r"\D", "", subpartida)
    if not 4 <= len(digitos) <= 10:
        raise error_api(
            422,
            "subpartida_invalida",
            "La subpartida nacional tiene de 4 a 10 dígitos, como figura en la declaración.",
        )
    return {
        "numero": numero,
        "fecha_numeracion": fecha_numeracion,
        "peso_neto_kg": Decimal(peso_neto_kg).quantize(CENTIMO, ROUND_HALF_UP),
        "subpartida": digitos,
    }


def _alerta_si_difiere(contexto: Contexto, lote: Lote, declaracion: DeclaracionAduanera) -> None:
    """Sección 4.4, regla 5: una declaración posterior al DEX que difiere deja la alerta en el lote, como
    exclusion_posterior_al_cierre. El DEX no cambia."""
    comparacion = comparar(contexto.sesion, declaracion, lote)
    if not comparacion.difiere:
        return
    alerta = {
        "codigo": ALERTA_DIFIERE,
        "declaracion_id": str(declaracion.id),
        "numero": declaracion.numero,
        "peso_difiere": comparacion.peso_difiere,
        "subpartida_difiere": comparacion.subpartida_difiere,
        "en": ahora().isoformat(),
    }
    lote.alertas = [*(lote.alertas or []), alerta]
    registrar_auditoria(
        contexto, "lote.alerta", "lote", lote.id, {"codigo": lote.codigo, "alerta": ALERTA_DIFIERE}
    )


def _cargar_dam(contexto: Contexto, storage: ClienteStorage, lote: Lote, archivo: Archivo, datos: dict):
    if vigente(contexto.sesion, lote.id) is not None:
        raise error_api(
            400,
            "declaracion_existente",
            "El lote ya tiene una declaración aduanera. Para cargar otra, anula primero la que tiene.",
        )
    documento, ruta = documentos.guardar(
        contexto,
        storage,
        entidad="lote",
        entidad_id=lote.id,
        tipo="dam",
        archivo=archivo,
        datos_legales={
            "numero": datos["numero"],
            "entidad_emisora": catalogo.POR_CODIGO["dam"].emisor_habitual,
            "fecha_emision": datos["fecha_numeracion"],
        },
    )
    try:
        declaracion = DeclaracionAduanera(
            lote_id=lote.id,
            documento_id=documento.id,
            registrada_por=contexto.usuario_id,
            posterior_al_dex=lote.estado == "cerrado",
            **datos,
        )
        contexto.sesion.add(declaracion)
        contexto.sesion.flush()
        registrar_auditoria(
            contexto,
            "declaracion_aduanera.registrar",
            "lote",
            lote.id,
            {
                "codigo": lote.codigo,
                "numero": datos["numero"],
                "fecha_numeracion": datos["fecha_numeracion"],
                "peso_neto_kg": str(datos["peso_neto_kg"]),
                "subpartida": datos["subpartida"],
                "posterior_al_dex": declaracion.posterior_al_dex,
                "documento_id": documento.id,
            },
        )
        if declaracion.posterior_al_dex:
            _alerta_si_difiere(contexto, lote, declaracion)
        contexto.sesion.commit()
    except Exception:
        contexto.sesion.rollback()
        documentos.descartar(storage, ruta)
        raise
    return documento


def cargar(
    contexto: Contexto,
    storage: ClienteStorage,
    lote_id: uuid.UUID,
    tipo: str,
    archivo: Archivo,
    numero: str | None,
    entidad_emisora: str | None,
    fecha_emision: date | None,
    peso_neto_kg: Decimal | None = None,
    subpartida: str | None = None,
):
    lote = lote_visible(contexto, lote_id)
    if tipo not in catalogo.POR_CODIGO:
        raise error_api(422, "tipo_documento_invalido", "Ese tipo de documento no es de embarque.")
    if not lote_admite(tipo, lote.estado):
        raise error_api(
            400,
            "lote_sin_embarque",
            "Los documentos de embarque se cargan en un lote armado, bloqueado o listo."
            if lote.estado != "cerrado"
            else "El lote ya tiene DEX: solo admite la declaración aduanera.",
        )
    if tipo == "dam":
        return _cargar_dam(
            contexto, storage, lote, archivo, _datos_dam(numero, fecha_emision, peso_neto_kg, subpartida)
        )
    faltan = [
        n
        for n, v in (
            ("número", numero),
            ("entidad emisora", entidad_emisora),
            ("fecha de emisión", fecha_emision),
        )
        if not v
    ]
    if faltan:
        raise error_api(422, "datos_requeridos", f"Falta: {', '.join(faltan)}.")
    if fecha_emision > hoy_lima():
        raise error_api(422, "fecha_futura", "La fecha de emisión no puede ser futura.")
    datos = {
        "numero": numero.strip(),
        "entidad_emisora": entidad_emisora.strip(),
        "fecha_emision": fecha_emision,
    }
    return documentos.cargar(
        contexto, storage, entidad="lote", entidad_id=lote.id, tipo=tipo, archivo=archivo, datos_legales=datos
    )


# ---------- Anulación ----------


def anular_declaracion(contexto: Contexto, lote_id: uuid.UUID, motivo: str) -> EmbarqueSalida:
    """Decisión del equipo del 2026-10-10: anular la declaración aduanera anula también su archivo, en la
    misma transacción. Se puede anular en los mismos estados del lote en que se carga."""
    lote = lote_visible(contexto, lote_id)
    if not lote_admite("dam", lote.estado):
        raise error_api(400, "lote_cerrado", "El lote está anulado: su declaración aduanera no cambia.")
    declaracion = vigente(contexto.sesion, lote.id)
    if declaracion is None:
        raise error_api(400, "sin_declaracion", "El lote no tiene una declaración aduanera sin anular.")
    momento = ahora()
    declaracion.anulada_en = momento
    declaracion.anulada_por = contexto.usuario_id
    declaracion.motivo_anulacion = motivo
    documento = contexto.sesion.get(Documento, declaracion.documento_id)
    if documento is not None and documento.anulado_en is None:
        documento.anulado_en = momento
        documento.anulado_por = contexto.usuario_id
        documento.motivo_anulacion = motivo
    registrar_auditoria(
        contexto,
        "declaracion_aduanera.anular",
        "lote",
        lote.id,
        {"codigo": lote.codigo, "numero": declaracion.numero, "motivo": motivo},
    )
    contexto.sesion.commit()
    return listar(contexto, lote.id)

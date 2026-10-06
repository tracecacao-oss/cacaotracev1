"""Documentos de embarque del lote (Parte 8): los cuatro del catálogo documentos_embarque.py. Se cargan en
un lote armado, bloqueado o listo, antes de emitir el DEX.

El sistema no lee su contenido ni compara sus cifras con las del lote: que la masa de la factura coincida
con la del lote lo revisa una persona. Tras emitir el DEX ya no se anulan ni se reemplazan.
"""

import uuid
from datetime import date

from sqlalchemy import func, select

from app.catalogos import documentos_embarque as catalogo
from app.contexto import Contexto
from app.errores import error_api
from app.fechas import hoy_lima
from app.models import Documento, Perfil
from app.schemas.cooperativa import DocumentoEmbarque, EmbarqueSalida
from app.services import documentos
from app.services.documentos import ESTADOS_LOTE_CON_EMBARQUE, Archivo
from app.services.lotes import lote_visible
from app.storage import ClienteStorage


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
    tipos = []
    for t in catalogo.TIPOS:
        propios = [d for d in filas if d.tipo == t.codigo]
        tipos.append(
            DocumentoEmbarque(
                codigo=t.codigo,
                nombre=t.nombre,
                emisor_habitual=t.emisor_habitual,
                cargado=any(d.anulado_en is None for d in propios),
                documentos=[documento_salida(d, nombres.get(d.subido_por)) for d in propios],
            )
        )
    faltan = [t.nombre for t in tipos if not t.cargado]
    return EmbarqueSalida(
        completo=not faltan, faltan=faltan, editable=lote.estado in ESTADOS_LOTE_CON_EMBARQUE, tipos=tipos
    )


def cargar(
    contexto: Contexto,
    storage: ClienteStorage,
    lote_id: uuid.UUID,
    tipo: str,
    archivo: Archivo,
    numero: str | None,
    entidad_emisora: str | None,
    fecha_emision: date | None,
):
    lote = lote_visible(contexto, lote_id)
    if lote.estado not in ESTADOS_LOTE_CON_EMBARQUE:
        raise error_api(
            400,
            "lote_sin_embarque",
            "Los documentos de embarque se cargan en un lote armado, bloqueado o listo.",
        )
    if tipo not in catalogo.POR_CODIGO:
        raise error_api(422, "tipo_documento_invalido", "Ese tipo de documento no es de embarque.")
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
    return documentos.cargar(
        contexto,
        storage,
        entidad="lote",
        entidad_id=lote.id,
        tipo=tipo,
        archivo=archivo,
        datos_legales={
            "numero": numero.strip(),
            "entidad_emisora": entidad_emisora.strip(),
            "fecha_emision": fecha_emision,
        },
    )

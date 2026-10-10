"""Documentos de embarque del lote (Parte 8; adenda 6, sección 7): los del catálogo documentos_embarque.py.
Los obligatorios se cargan en un lote armado, bloqueado o listo, antes de emitir el DEX; la declaración
aduanera (`dam`) no es obligatoria y se puede agregar también con el lote cerrado, sin cambiar el DEX emitido.

El sistema no lee su contenido ni compara sus cifras con las del lote: que la masa de la factura coincida
con la del lote lo revisa una persona. Tras emitir el DEX ya no se anulan ni se reemplazan, salvo la `dam`.
"""

import uuid
from datetime import date

from sqlalchemy import func, select

from app.catalogos import documentos_embarque as catalogo
from app.contexto import Contexto
from app.errores import error_api
from app.fechas import hoy_lima
from app.models import Documento, Perfil
from app.schemas.cooperativa import ConsultaPublica, DocumentoEmbarque, EmbarqueSalida
from app.services import documentos
from app.services.documentos import ESTADOS_LOTE_CON_EMBARQUE, Archivo, lote_admite
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
                obligatorio=t.obligatorio,
                registro_consultable=t.registro_consultable,
                editable=lote_admite(t.codigo, lote.estado),
                consultas=[
                    ConsultaPublica(url=url, nombre=nombre)
                    for url, nombre in (catalogo.CONSULTAS_DAM if t.codigo == "dam" else ())
                ],
                cargado=any(d.anulado_en is None for d in propios),
                documentos=[documento_salida(d, nombres.get(d.subido_por)) for d in propios],
            )
        )
    faltan = [t.nombre for t in tipos if t.obligatorio and not t.cargado]
    return EmbarqueSalida(
        completo=not faltan, faltan=faltan, editable=lote.estado in ESTADOS_LOTE_CON_EMBARQUE, tipos=tipos
    )


def _datos_dam(numero: str | None, fecha_emision: date | None, entidad_emisora: str | None) -> dict:
    """Adenda 6, sección 7, regla 3: número y fecha de numeración. El número no tiene un formato confirmado
    (sección 14): texto de 5 a 30 caracteres. El emisor es SUNAT."""
    faltan = [n for n, v in (("número", numero), ("fecha de numeración", fecha_emision)) if not v]
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
    if fecha_emision > hoy_lima():
        raise error_api(422, "fecha_futura", "La fecha de numeración no puede ser futura.")
    return {
        "numero": numero,
        "entidad_emisora": (entidad_emisora or "").strip() or catalogo.POR_CODIGO["dam"].emisor_habitual,
        "fecha_emision": fecha_emision,
    }


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
        datos = _datos_dam(numero, fecha_emision, entidad_emisora)
    else:
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

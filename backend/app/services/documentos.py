"""Documentos de sustento. El archivo vive en Storage; la tabla guarda dónde está y qué respalda.

Un documento no se borra: se anula con un motivo, y deja de contar para el nivel de
verificación. El sistema no lee su contenido: "documentado" significa que hay un archivo
adjunto, no que alguien comprobó lo que dice.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session

from app.catalogos import documentos_embarque, documentos_legales
from app.contexto import Contexto
from app.errores import error_api, no_encontrado
from app.models import (
    Afiliacion,
    AnalisisCobertura,
    Documento,
    Dop,
    ImagenParcela,
    Parcela,
    Perfil,
    Tanda,
    VisitaCampo,
)
from app.services.auditoria import registrar_auditoria
from app.services.geometria import ErrorArchivo
from app.storage import (
    TIPOS_MIME,
    ArchivoNoPermitido,
    ClienteStorage,
    ErrorStorage,
    construir_ruta,
    sha256,
    validar_documento,
)

log = logging.getLogger(__name__)

TIPOS_POR_ENTIDAD = {
    "productor": ("dni", "constancia_ppa"),
    "parcela": ("sustento_midagri", "archivo_geometria", *documentos_legales.CODIGOS),
    "visita": ("foto_visita",),
    "analisis": ("respuesta_analisis",),
    "tanda": ("documento_entrega",),
    "dop": ("dop_pdf",),
    "dpp": ("dpp_pdf",),
    "imagen": ("imagen_satelital", "imagen_externa"),
    # Parte 8
    "cooperativa": documentos_legales.CODIGOS_COOPERATIVA,
    "lote": documentos_embarque.CODIGOS,
}
NOMBRES_TIPO = {
    "dni": "copia del DNI",
    "constancia_ppa": "constancia del PPA",
    "sustento_midagri": "sustento de MIDAGRI",
    "archivo_geometria": "archivo de geometría",
    "foto_visita": "foto de la visita",
    "respuesta_analisis": "respuesta completa del análisis",
    "documento_entrega": "documento de entrega",
    "dop_pdf": "PDF del DOP",
    "dpp_pdf": "PDF del DPP",
    "imagen_satelital": "imagen satelital",
    "imagen_externa": "imagen externa",
    **{t.codigo: t.nombre for t in documentos_legales.TIPOS},
    **{t.codigo: t.nombre for t in documentos_legales.TIPOS_COOPERATIVA},
    **{t.codigo: t.nombre for t in documentos_embarque.TIPOS},
}
# Parte 8: un documento de embarque solo se carga o se anula en un lote confirmado y sin DEX.
ESTADOS_LOTE_CON_EMBARQUE = ("armado", "bloqueado", "listo")
# Los genera el sistema o forman parte de un registro que no se edita: no se anulan a mano.
NO_ANULABLES = (
    "respuesta_analisis",
    "foto_visita",
    "dop_pdf",
    "dpp_pdf",
    "imagen_satelital",
    "imagen_externa",
)


@dataclass(frozen=True)
class Archivo:
    nombre: str
    contenido: bytes


def vigente(entidad: str, entidad_id, tipo: str):
    """Condición SQL: existe un documento vigente de ese tipo para el registro."""
    return exists().where(
        Documento.entidad == entidad,
        Documento.entidad_id == entidad_id,
        Documento.tipo == tipo,
        Documento.anulado_en.is_(None),
    )


def documentos_de(sesion: Session, entidad: str, entidad_id: uuid.UUID) -> list[tuple[Documento, str | None]]:
    filas = sesion.execute(
        select(Documento, Perfil.nombres + " " + Perfil.apellidos)
        .outerjoin(Perfil, Perfil.id == Documento.subido_por)
        .where(Documento.entidad == entidad, Documento.entidad_id == entidad_id)
        .order_by(Documento.creado_en.desc())
    ).all()
    return [(d, nombre) for d, nombre in filas]


def guardar(
    contexto: Contexto,
    storage: ClienteStorage,
    *,
    entidad: str,
    entidad_id: uuid.UUID,
    tipo: str,
    archivo: Archivo,
    tipo_mime: str | None = None,
    datos_legales: dict | None = None,
) -> tuple[Documento, str]:
    """Sube el archivo y agrega su fila a la sesión, sin confirmar. Devuelve (documento, ruta en Storage).

    Si después la transacción falla, quien llama debe borrar el archivo con descartar().
    """
    if tipo not in TIPOS_POR_ENTIDAD[entidad]:
        raise error_api(
            422, "tipo_documento_invalido", f"Ese tipo de documento no corresponde a un {entidad}."
        )

    if tipo == "archivo_geometria":
        extension = archivo.nombre.rsplit(".", 1)[-1].lower()
        tipo_mime = tipo_mime or "application/octet-stream"
    else:
        try:
            extension = validar_documento(archivo.contenido)
        except ArchivoNoPermitido as exc:
            raise error_api(
                422, "formato_no_admitido", f"{exc} Sube una foto o un PDF del documento."
            ) from exc
        tipo_mime = TIPOS_MIME[extension]

    huella = sha256(archivo.contenido)
    duplicado = contexto.sesion.scalar(
        select(Documento.id).where(
            Documento.entidad == entidad,
            Documento.entidad_id == entidad_id,
            Documento.tipo == tipo,
            Documento.sha256 == huella,
            Documento.anulado_en.is_(None),
        )
    )
    if duplicado:
        raise error_api(409, "documento_duplicado", "Ese mismo archivo ya está cargado para este registro.")

    ruta = construir_ruta(contexto.cooperativa_id, entidad, entidad_id, extension)
    try:
        storage.subir(ruta, archivo.contenido, tipo_mime)
    except ErrorStorage as exc:
        log.error("No se pudo subir el archivo: %s", exc)
        raise error_api(
            503, "archivos_no_disponibles", "No se pudo guardar el archivo. Intenta de nuevo."
        ) from exc

    documento = Documento(
        cooperativa_id=contexto.cooperativa_id,
        entidad=entidad,
        entidad_id=entidad_id,
        tipo=tipo,
        ruta=ruta,
        nombre_original=(archivo.nombre or f"archivo.{extension}")[:200],
        tipo_mime=tipo_mime,
        tamano_bytes=len(archivo.contenido),
        sha256=huella,
        subido_por=contexto.usuario_id,
        **(datos_legales or {}),
    )
    contexto.sesion.add(documento)
    contexto.sesion.flush()
    registrar_auditoria(
        contexto,
        "documento.cargar",
        "documento",
        documento.id,
        {"tipo": tipo, "entidad": entidad, "entidad_id": entidad_id, "nombre": documento.nombre_original},
    )
    return documento, ruta


def descartar(storage: ClienteStorage, ruta: str) -> None:
    try:
        storage.borrar(ruta)
    except ErrorStorage:
        log.error("Quedó un archivo sin registro en Storage: %s", ruta)


def cargar(
    contexto: Contexto,
    storage: ClienteStorage,
    *,
    entidad: str,
    entidad_id: uuid.UUID,
    tipo: str,
    archivo: Archivo,
    datos_legales: dict | None = None,
):
    documento, ruta = guardar(
        contexto,
        storage,
        entidad=entidad,
        entidad_id=entidad_id,
        tipo=tipo,
        archivo=archivo,
        datos_legales=datos_legales,
    )
    try:
        contexto.sesion.commit()
    except Exception:
        contexto.sesion.rollback()
        descartar(storage, ruta)
        raise
    return documento


# ---------- Acceso a un documento ----------


def _parcela_del_documento(sesion: Session, documento: Documento) -> uuid.UUID | None:
    if documento.entidad == "parcela":
        return documento.entidad_id
    if documento.entidad == "visita":
        return sesion.scalar(select(VisitaCampo.parcela_id).where(VisitaCampo.id == documento.entidad_id))
    if documento.entidad == "analisis":
        return sesion.scalar(
            select(AnalisisCobertura.parcela_id).where(AnalisisCobertura.id == documento.entidad_id)
        )
    if documento.entidad == "tanda":
        return sesion.scalar(select(Tanda.parcela_id).where(Tanda.id == documento.entidad_id))
    if documento.entidad == "dop":
        return sesion.scalar(select(Dop.parcela_id).where(Dop.id == documento.entidad_id))
    if documento.entidad == "imagen":
        return sesion.scalar(select(ImagenParcela.parcela_id).where(ImagenParcela.id == documento.entidad_id))
    return None


def _productor_del_documento(sesion: Session, documento: Documento) -> uuid.UUID | None:
    if documento.entidad == "productor":
        return documento.entidad_id
    parcela_id = _parcela_del_documento(sesion, documento)
    return sesion.scalar(select(Parcela.productor_id).where(Parcela.id == parcela_id))


def documento_visible(contexto: Contexto, documento_id: uuid.UUID) -> Documento:
    """El personal ve los de productores afiliados a su cooperativa; el productor, los suyos."""
    documento = contexto.sesion.get(Documento, documento_id)
    if documento is None:
        raise no_encontrado("El documento no existe.")
    if documento.entidad in ("cooperativa", "lote"):
        # Parte 8: los de la cooperativa y los de embarque los ve el personal de esa cooperativa.
        if contexto.rol == "productor" or documento.cooperativa_id != contexto.cooperativa_id:
            raise no_encontrado("El documento no existe.")
        return documento
    productor_id = _productor_del_documento(contexto.sesion, documento)
    if contexto.rol == "productor":
        # El productor ve el resultado del análisis, no la respuesta completa de la fuente.
        permitido = productor_id == contexto.productor_id and documento.tipo != "respuesta_analisis"
    else:
        permitido = contexto.cooperativa_id is not None and contexto.sesion.scalar(
            select(
                exists().where(
                    and_(
                        Afiliacion.productor_id == productor_id,
                        Afiliacion.cooperativa_id == contexto.cooperativa_id,
                        Afiliacion.estado == "activa",
                    )
                )
            )
        )
    if not permitido:
        raise no_encontrado("El documento no existe.")
    return documento


def url_firmada(contexto: Contexto, storage: ClienteStorage, documento_id: uuid.UUID) -> str:
    documento = documento_visible(contexto, documento_id)
    try:
        return storage.url_firmada(documento.ruta)
    except ErrorStorage as exc:
        raise error_api(
            503, "archivos_no_disponibles", "No se pudo preparar la descarga. Intenta de nuevo."
        ) from exc


def anular(contexto: Contexto, documento_id: uuid.UUID, motivo: str) -> Documento:
    documento = documento_visible(contexto, documento_id)
    if documento.tipo in NO_ANULABLES:
        raise error_api(
            400, "documento_no_anulable", f"La {NOMBRES_TIPO[documento.tipo]} no se anula a mano."
        )
    if documento.entidad == "cooperativa" and contexto.rol != "admin_cooperativa":
        raise error_api(
            403, "solo_administrador", "Solo un administrador anula los documentos legales de la cooperativa."
        )
    if documento.entidad == "lote":
        from app.models import Lote  # evita importación circular

        lote = contexto.sesion.get(Lote, documento.entidad_id)
        if lote.estado not in ESTADOS_LOTE_CON_EMBARQUE:
            raise error_api(
                400,
                "lote_cerrado",
                "El lote ya tiene DEX o fue anulado: sus documentos de embarque no cambian.",
            )
    if documento.entidad == "tanda":
        # La guía de una tanda validada respalda su DOP: ya no se anula.
        tanda = contexto.sesion.get(Tanda, documento.entidad_id)
        if tanda.estado not in ("registrada", "observada"):
            raise error_api(400, "tanda_cerrada", "La tanda ya está validada o anulada: su guía no se anula.")
    parcela_id = _parcela_del_documento(contexto.sesion, documento) if documento.entidad != "tanda" else None
    if parcela_id is not None:
        from app.services.expediente import no_excluida  # evita importación circular

        no_excluida(contexto.sesion.get(Parcela, parcela_id))
    if documento.anulado_en is not None:
        raise error_api(400, "documento_anulado", "El documento ya estaba anulado.")
    documento.anulado_en = datetime.now(UTC)
    documento.anulado_por = contexto.usuario_id
    documento.motivo_anulacion = motivo
    registrar_auditoria(
        contexto, "documento.anular", "documento", documento.id, {"tipo": documento.tipo, "motivo": motivo}
    )
    contexto.sesion.commit()
    return documento


def error_de_archivo(exc: ErrorArchivo):
    estado = 422 if exc.codigo in ("formato_no_admitido", "archivo_invalido") else 400
    return error_api(estado, exc.codigo, exc.mensaje)

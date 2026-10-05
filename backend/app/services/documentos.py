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

from app.contexto import Contexto
from app.errores import error_api, no_encontrado
from app.models import Afiliacion, Documento, Parcela, Perfil
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
    "parcela": ("sustento_midagri", "archivo_geometria"),
}
NOMBRES_TIPO = {
    "dni": "copia del DNI",
    "constancia_ppa": "constancia del PPA",
    "sustento_midagri": "sustento de MIDAGRI",
    "archivo_geometria": "archivo de geometría",
}


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
):
    documento, ruta = guardar(
        contexto, storage, entidad=entidad, entidad_id=entidad_id, tipo=tipo, archivo=archivo
    )
    try:
        contexto.sesion.commit()
    except Exception:
        contexto.sesion.rollback()
        descartar(storage, ruta)
        raise
    return documento


# ---------- Acceso a un documento ----------


def _productor_del_documento(sesion: Session, documento: Documento) -> uuid.UUID | None:
    if documento.entidad == "productor":
        return documento.entidad_id
    return sesion.scalar(select(Parcela.productor_id).where(Parcela.id == documento.entidad_id))


def documento_visible(contexto: Contexto, documento_id: uuid.UUID) -> Documento:
    """El personal ve los de productores afiliados a su cooperativa; el productor, los suyos."""
    documento = contexto.sesion.get(Documento, documento_id)
    if documento is None:
        raise no_encontrado("El documento no existe.")
    productor_id = _productor_del_documento(contexto.sesion, documento)
    if contexto.rol == "productor":
        permitido = productor_id == contexto.productor_id
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

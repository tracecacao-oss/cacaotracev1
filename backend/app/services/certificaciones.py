"""Certificaciones de la cooperativa (Parte 9, contexto del informe: criterio 7). Las mantiene un
administrador, cada una con su documento de tipo `certificacion`. Una certificación no se borra: se anula
con motivo y deja de contar."""

import uuid
from datetime import date

from sqlalchemy import select

from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import ahora, hoy_lima
from app.models import Certificacion, Perfil
from app.schemas.dex import CertificacionCambios, CertificacionNueva, CertificacionSalida
from app.services import documentos
from app.services.auditoria import aplicar_cambios, registrar_auditoria
from app.services.documentos import Archivo
from app.storage import ClienteStorage

CAMPOS = ("nombre", "entidad_certificadora", "numero", "vigente_desde", "vigente_hasta")


def _estado(c: Certificacion, hoy: date) -> str:
    if c.anulada_en is not None:
        return "anulada"
    if c.vigente_desde > hoy:
        return "por_iniciar"
    if c.vigente_hasta < hoy:
        return "vencida"
    return "vigente"


def _salidas(sesion, filas: list[Certificacion]) -> list[CertificacionSalida]:
    ids = {c.registrada_por for c in filas}
    nombres = {
        p.id: f"{p.nombres} {p.apellidos}".strip()
        for p in (sesion.scalars(select(Perfil).where(Perfil.id.in_(ids))) if ids else [])
    }
    hoy = hoy_lima()
    return [
        CertificacionSalida(
            id=c.id,
            nombre=c.nombre,
            entidad_certificadora=c.entidad_certificadora,
            numero=c.numero,
            vigente_desde=c.vigente_desde,
            vigente_hasta=c.vigente_hasta,
            estado=_estado(c, hoy),
            documento_id=c.documento_id,
            registrada_por_nombre=nombres.get(c.registrada_por),
            creado_en=c.creado_en,
            anulada_en=c.anulada_en,
            motivo_anulacion=c.motivo_anulacion,
        )
        for c in filas
    ]


def listar(contexto: Contexto) -> list[CertificacionSalida]:
    filas = list(
        contexto.sesion.scalars(
            select(Certificacion)
            .where(Certificacion.cooperativa_id == cooperativa_del_contexto(contexto))
            .order_by(
                Certificacion.anulada_en.is_not(None),
                Certificacion.vigente_hasta.desc(),
                Certificacion.nombre,
            )
        )
    )
    return _salidas(contexto.sesion, filas)


def _visible(contexto: Contexto, certificacion_id: uuid.UUID) -> Certificacion:
    c = contexto.sesion.get(Certificacion, certificacion_id)
    if c is None or c.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("La certificación no existe.")
    return c


def registrar(
    contexto: Contexto, storage: ClienteStorage, datos: CertificacionNueva, archivo: Archivo
) -> CertificacionSalida:
    sesion = contexto.sesion
    certificacion = Certificacion(
        cooperativa_id=cooperativa_del_contexto(contexto),
        registrada_por=contexto.usuario_id,
        **datos.model_dump(),
    )
    sesion.add(certificacion)
    sesion.flush()
    documento, ruta = documentos.guardar(
        contexto,
        storage,
        entidad="certificacion",
        entidad_id=certificacion.id,
        tipo="certificacion",
        archivo=archivo,
        datos_legales={
            "numero": datos.numero,
            "entidad_emisora": datos.entidad_certificadora,
            "fecha_emision": datos.vigente_desde,
            "fecha_vencimiento": datos.vigente_hasta,
        },
    )
    certificacion.documento_id = documento.id
    registrar_auditoria(
        contexto,
        "certificacion.registrar",
        "certificacion",
        certificacion.id,
        {**datos.model_dump(mode="json"), "documento_sha256": documento.sha256},
    )
    try:
        sesion.commit()
    except Exception:
        sesion.rollback()
        documentos.descartar(storage, ruta)
        raise
    return _salidas(sesion, [certificacion])[0]


def editar(
    contexto: Contexto, certificacion_id: uuid.UUID, datos: CertificacionCambios
) -> CertificacionSalida:
    sesion = contexto.sesion
    c = _visible(contexto, certificacion_id)
    if c.anulada_en is not None:
        raise error_api(400, "certificacion_anulada", "La certificación está anulada: no se edita.")
    if datos.anular:
        c.anulada_en = ahora()
        c.anulada_por = contexto.usuario_id
        c.motivo_anulacion = datos.motivo.strip()
        registrar_auditoria(
            contexto,
            "certificacion.editar",
            "certificacion",
            c.id,
            {"anulada": True, "motivo": c.motivo_anulacion},
        )
    else:
        cambios = {
            k: v
            for k, v in datos.model_dump(include=set(CAMPOS), exclude_unset=True).items()
            if v is not None
        }
        desde = cambios.get("vigente_desde", c.vigente_desde)
        hasta = cambios.get("vigente_hasta", c.vigente_hasta)
        if hasta < desde:
            raise error_api(
                422, "periodo_invalido", "La fecha de fin de vigencia no puede ser anterior a la de inicio."
            )
        diferencias = aplicar_cambios(c, cambios)
        if diferencias:
            registrar_auditoria(contexto, "certificacion.editar", "certificacion", c.id, diferencias)
    sesion.commit()
    return _salidas(sesion, [c])[0]

"""Datos y expediente legal de la cooperativa (Parte 8).

La cooperativa tiene un expediente de 6 casillas sin exenciones: las seis deben estar vigentes (o por
vencer). El estado se calcula al consultar, con la fecha del día, con las mismas reglas de la Parte 4. Los
documentos los carga y los anula solo un administrador; el cotejo sigue las reglas de la Parte 4.
"""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalogos import documentos_legales as catalogo
from app.config import get_settings
from app.contexto import Contexto, cooperativa_del_contexto
from app.fechas import hoy_lima
from app.models import Cooperativa, Documento, Perfil
from app.schemas.cooperativa import CooperativaCambios, CooperativaPropia, ExpedienteCooperativa
from app.schemas.habilitacion import CasillaSalida
from app.services import expediente as servicio_expediente
from app.services.auditoria import aplicar_cambios, registrar_auditoria

DATOS_DEX = {
    "direccion_postal": "dirección postal",
    "correo": "correo",
    "representante_nombre": "nombre del representante legal",
    "representante_dni": "DNI del representante legal",
}


def faltan_datos(cooperativa: Cooperativa) -> list[str]:
    return [nombre for campo, nombre in DATOS_DEX.items() if not getattr(cooperativa, campo)]


def propia(sesion: Session, cooperativa: Cooperativa) -> CooperativaPropia:
    return CooperativaPropia(
        id=cooperativa.id,
        razon_social=cooperativa.razon_social,
        nombre_comercial=cooperativa.nombre_comercial,
        ruc=cooperativa.ruc,
        codigo=cooperativa.codigo,
        tipo_organizacion=cooperativa.tipo_organizacion,
        departamento=cooperativa.departamento,
        provincia=cooperativa.provincia,
        distrito=cooperativa.distrito,
        direccion_postal=cooperativa.direccion_postal,
        correo=cooperativa.correo,
        representante_nombre=cooperativa.representante_nombre,
        representante_dni=cooperativa.representante_dni,
        faltan_datos=faltan_datos(cooperativa),
    )


def obtener(contexto: Contexto) -> CooperativaPropia:
    return propia(contexto.sesion, contexto.sesion.get(Cooperativa, cooperativa_del_contexto(contexto)))


def editar(contexto: Contexto, datos: CooperativaCambios) -> CooperativaPropia:
    cooperativa = contexto.sesion.get(Cooperativa, cooperativa_del_contexto(contexto))
    valores = {k: v for k, v in datos.model_dump(exclude_unset=True).items() if v is not None}
    cambios = aplicar_cambios(cooperativa, valores)
    if cambios:
        registrar_auditoria(contexto, "cooperativa.editar", "cooperativa", cooperativa.id, cambios)
    contexto.sesion.commit()
    return propia(contexto.sesion, cooperativa)


# ---------- Expediente ----------


def casillas(
    sesion: Session, cooperativa_id: uuid.UUID, hoy: date | None = None
) -> dict[str, servicio_expediente.Casilla]:
    """Las 6 casillas con el documento que cuenta (el de mejor estado y vencimiento más lejano)."""
    hoy = hoy or hoy_lima()
    aviso = get_settings().aviso_vencimiento_dias
    docs: dict[str, list[Documento]] = {}
    for d in sesion.scalars(
        select(Documento).where(
            Documento.entidad == "cooperativa",
            Documento.entidad_id == cooperativa_id,
            Documento.tipo.in_(catalogo.CODIGOS_COOPERATIVA),
            Documento.anulado_en.is_(None),
        )
    ):
        docs.setdefault(d.tipo, []).append(d)
    return {
        c: servicio_expediente._casilla(c, docs.get(c, []), None, hoy, aviso)
        for c in catalogo.CODIGOS_COOPERATIVA
    }


def faltan_casillas(cas: dict[str, servicio_expediente.Casilla]) -> list[str]:
    return [c for c, casilla in cas.items() if casilla.estado not in ("vigente", "por_vencer")]


def expediente(contexto: Contexto) -> ExpedienteCooperativa:
    from app.services.productores import documento_salida  # evita importación circular

    sesion = contexto.sesion
    cooperativa_id = cooperativa_del_contexto(contexto)
    cas = casillas(sesion, cooperativa_id)
    personas = {d.subido_por for c in cas.values() for d in c.documentos}
    nombres = dict(
        sesion.execute(
            select(Perfil.id, func.concat(Perfil.nombres, " ", Perfil.apellidos)).where(
                Perfil.id.in_(personas)
            )
        ).all()
    )
    # Los anulados también se listan, como historial de la casilla.
    todos: dict[str, list[Documento]] = {}
    for d in sesion.scalars(
        select(Documento)
        .where(Documento.entidad == "cooperativa", Documento.entidad_id == cooperativa_id)
        .order_by(Documento.creado_en.desc())
    ):
        todos.setdefault(d.tipo, []).append(d)
    salida = []
    for tipo in catalogo.TIPOS_COOPERATIVA:
        c = cas[tipo.codigo]
        salida.append(
            CasillaSalida(
                codigo=tipo.codigo,
                nombre=tipo.nombre,
                grupo=tipo.grupo,
                tenencia=False,
                registro_consultable=tipo.registro_consultable,
                admite_exencion=False,
                estado=c.estado,
                nivel=c.nivel,
                vence_en=c.documento.fecha_vencimiento if c.documento else None,
                documentos=[
                    documento_salida(d, nombres.get(d.subido_por)) for d in todos.get(tipo.codigo, [])
                ],
                exencion=None,
            )
        )
    faltan = faltan_casillas(cas)
    return ExpedienteCooperativa(
        estado="incompleto" if faltan else "completo", faltan=faltan, casillas=salida
    )


def documentos_por_vencer(sesion: Session, cooperativa_id: uuid.UUID) -> list[servicio_expediente.Casilla]:
    """Casillas por vencer o vencidas, ordenadas por fecha de vencimiento."""
    return sorted(
        (c for c in casillas(sesion, cooperativa_id).values() if c.estado in ("por_vencer", "vencido")),
        key=lambda c: c.documento.fecha_vencimiento,
    )

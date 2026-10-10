"""Datos y expediente legal de la organización (Parte 8; adenda 6, secciones 3 y 4).

Desde la adenda 6, cada organización ve los documentos que le tocan según su `tipo_organizacion`, sin
exenciones, y solo los tres de identidad (ficha RUC, partida registral y vigencia de poderes) frenan un lote.
El estado se calcula al consultar, con la fecha del día, con las mismas reglas de la Parte 4. Los documentos
los carga y los anula solo un administrador; el cotejo sigue las reglas de la Parte 4. Los requisitos de la
política y de las actuaciones los calcula services/diligencia.py.
"""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalogos import documentos_legales as catalogo
from app.catalogos import requisitos_organizacion
from app.config import get_settings
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api
from app.fechas import hoy_lima
from app.models import Cooperativa, Documento, Perfil
from app.schemas.cooperativa import (
    CasillaOrganizacion,
    CooperativaCambios,
    CooperativaPropia,
    ExpedienteCooperativa,
    RequisitoOrganizacionSalida,
)
from app.services import documentos
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
        canal_denuncias_contacto=cooperativa.canal_denuncias_contacto,
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

CONSULTA_RUC = "https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp"
CUBIERTOS = ("vigente", "por_vencer")


def _documentos(sesion: Session, cooperativa_id: uuid.UUID, tipos) -> dict[str, list[Documento]]:
    docs: dict[str, list[Documento]] = {}
    for d in sesion.scalars(
        select(Documento).where(
            Documento.entidad == "cooperativa",
            Documento.entidad_id == cooperativa_id,
            Documento.tipo.in_(tipos),
            Documento.anulado_en.is_(None),
        )
    ):
        docs.setdefault(d.tipo, []).append(d)
    return docs


def casillas(
    sesion: Session, cooperativa_id: uuid.UUID, hoy: date | None = None
) -> dict[str, servicio_expediente.Casilla]:
    """Las casillas que aplican al tipo de organización, con el documento que cuenta (el de mejor estado y
    vencimiento más lejano)."""
    hoy = hoy or hoy_lima()
    aviso = get_settings().aviso_vencimiento_dias
    tipo_organizacion = sesion.get(Cooperativa, cooperativa_id).tipo_organizacion
    codigos = [t.codigo for t in catalogo.tipos_de_organizacion(tipo_organizacion)]
    docs = _documentos(sesion, cooperativa_id, codigos)
    return {c: servicio_expediente._casilla(c, docs.get(c, []), None, hoy, aviso) for c in codigos}


def faltan_identidad(cas: dict[str, servicio_expediente.Casilla]) -> list[str]:
    """Adenda 6, sección 4, regla 1: los documentos de identidad que no están vigentes ni por vencer."""
    return [c for c in catalogo.IDENTIDAD if cas[c].estado not in CUBIERTOS]


def requisito_salida(
    codigo: str, estado: str, motivo: str, falta: list[str], falta_codigos: list[str] | None = None
) -> RequisitoOrganizacionSalida:
    r = requisitos_organizacion.POR_CODIGO[codigo]
    return RequisitoOrganizacionSalida(
        codigo=r.codigo,
        nombre=r.nombre,
        referencias=list(r.referencias),
        nivel=r.nivel,
        diligencia=r.diligencia,
        bloquea=r.bloquea,
        que_pide=r.que_pide,
        estado=estado,
        motivo=motivo,
        falta=falta,
        falta_codigos=falta_codigos or [],
    )


def _con_documentos(
    codigo: str, cas: dict[str, servicio_expediente.Casilla], tipos: tuple[str, ...], motivo: str
) -> RequisitoOrganizacionSalida:
    """Un requisito con varios sustentos está sustentado solo cuando los tiene todos (sección 3)."""
    propias = [cas[t] for t in tipos]
    falta = [c.codigo for c in propias if c.estado not in CUBIERTOS]
    if any(c.estado == "faltante" for c in propias):
        estado = "sin_sustento"
    elif falta:
        estado = "vencido"
    elif any(c.estado == "por_vencer" for c in propias):
        estado = "por_vencer"
    else:
        estado = "sustentado"
    nombres = [catalogo.POR_CODIGO_COOPERATIVA[f].nombre for f in falta]
    return requisito_salida(codigo, estado, motivo, nombres, falta)


def requisitos_documentales(cas: dict[str, servicio_expediente.Casilla]) -> list[RequisitoOrganizacionSalida]:
    """Identidad, tributos y registro de cooperativas (sección 3)."""
    salida = [
        _con_documentos(
            "identidad", cas, catalogo.IDENTIDAD, "Siempre: el DEX nombra al exportador y a su representante."
        ),
        _con_documentos("tributos", cas, ("ficha_ruc", "renta_anual"), "Siempre."),
    ]
    if "rnca" in cas:
        salida.append(_con_documentos("registro_cooperativas", cas, ("rnca",), "Es una cooperativa agraria."))
    else:
        salida.append(
            requisito_salida("registro_cooperativas", "no_aplica", "No es una cooperativa agraria.", [])
        )
    return salida


def requisitos(sesion: Session, cooperativa: Cooperativa, hoy: date | None = None):
    """Los requisitos de la organización (sección 3), sin el de aduanas, que es de cada lote."""
    from app.services import diligencia  # evita importación circular

    hoy = hoy or hoy_lima()
    return [
        *requisitos_documentales(casillas(sesion, cooperativa.id, hoy)),
        diligencia.requisito_integridad(sesion, cooperativa),
        diligencia.requisito_actuaciones(sesion, cooperativa.id, hoy),
    ]


def _salida_casilla(tipo, c, docs, nombres, *, anterior: bool = False) -> CasillaOrganizacion:
    from app.services.productores import documento_salida  # evita importación circular

    return CasillaOrganizacion(
        codigo=tipo.codigo,
        nombre=tipo.nombre,
        grupo=tipo.grupo,
        tenencia=False,
        registro_consultable=tipo.registro_consultable,
        admite_exencion=False,
        estado=c.estado if c else "no_aplica",
        nivel=c.nivel if c else None,
        vence_en=c.documento.fecha_vencimiento if c and c.documento else None,
        documentos=[documento_salida(d, nombres.get(d.subido_por)) for d in docs],
        exencion=None,
        identidad=tipo.identidad,
        frena_lote=tipo.identidad and not anterior,
        anterior=anterior,
        vence_solo=tipo.codigo == "renta_anual",
    )


def expediente(contexto: Contexto) -> ExpedienteCooperativa:
    sesion = contexto.sesion
    cooperativa_id = cooperativa_del_contexto(contexto)
    cooperativa = sesion.get(Cooperativa, cooperativa_id)
    hoy = hoy_lima()
    cas = casillas(sesion, cooperativa_id, hoy)
    # Los anulados también se listan, como historial de la casilla.
    todos: dict[str, list[Documento]] = {}
    for d in sesion.scalars(
        select(Documento)
        .where(
            Documento.entidad == "cooperativa",
            Documento.entidad_id == cooperativa_id,
            Documento.tipo.in_(catalogo.TODOS_COOPERATIVA),
        )
        .order_by(Documento.creado_en.desc())
    ):
        todos.setdefault(d.tipo, []).append(d)
    personas = {d.subido_por for docs in todos.values() for d in docs}
    nombres = dict(
        sesion.execute(
            select(Perfil.id, func.concat(Perfil.nombres, " ", Perfil.apellidos)).where(
                Perfil.id.in_(personas)
            )
        ).all()
    )
    salida = [
        _salida_casilla(tipo, cas[tipo.codigo], todos.get(tipo.codigo, []), nombres)
        for tipo in catalogo.TIPOS_COOPERATIVA
        if tipo.codigo in cas
    ]
    # Sección 4, reglas 4 y 5: los que ya no se cargan, y el rnca de una organización que no es cooperativa
    # agraria, se ven como documentos anteriores si se cargaron. No cuentan para nada.
    anteriores = [
        _salida_casilla(tipo, None, todos[tipo.codigo], nombres, anterior=True)
        for tipo in (*catalogo.TIPOS_COOPERATIVA, *catalogo.TIPOS_COOPERATIVA_ANTERIORES)
        if tipo.codigo not in cas and todos.get(tipo.codigo)
    ]
    faltan = faltan_identidad(cas)
    return ExpedienteCooperativa(
        estado="incompleto" if faltan else "completo",
        faltan=faltan,
        tipo_organizacion=cooperativa.tipo_organizacion,
        casillas=salida,
        requisitos=requisitos(sesion, cooperativa, hoy),
        anteriores=anteriores,
        consulta_ruc=CONSULTA_RUC,
    )


def cargar_documento(contexto: Contexto, storage, tipo: str, archivo, **datos):
    """Un documento legal de la organización, con número, entidad emisora y fechas. Sección 4, regla 5: el
    registro de cooperativas solo lo carga una cooperativa agraria."""
    cooperativa = contexto.sesion.get(Cooperativa, cooperativa_del_contexto(contexto))
    legal = catalogo.POR_CODIGO_COOPERATIVA[tipo]
    datos_legales = servicio_expediente.validar_datos_legales(tipo, **datos)
    if not legal.aplica(cooperativa.tipo_organizacion):
        raise error_api(422, "tipo_no_aplica", f"{legal.nombre} solo se carga en una cooperativa agraria.")
    return documentos.cargar(
        contexto,
        storage,
        entidad="cooperativa",
        entidad_id=cooperativa.id,
        tipo=tipo,
        archivo=archivo,
        datos_legales=datos_legales,
    )


def documentos_por_vencer(sesion: Session, cooperativa_id: uuid.UUID) -> list[servicio_expediente.Casilla]:
    """Casillas por vencer o vencidas, ordenadas por fecha de vencimiento."""
    return sorted(
        (c for c in casillas(sesion, cooperativa_id).values() if c.estado in ("por_vencer", "vencido")),
        key=lambda c: c.documento.fecha_vencimiento,
    )

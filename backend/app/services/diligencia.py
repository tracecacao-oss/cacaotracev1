"""Política de la organización, actuaciones de diligencia, cuadro de señales y lista de productos buscados en
el registro del SENASA (adenda 6, secciones 5 y 6).

El sistema no concluye: dice qué temas cubre la política que la organización cargó (los marca quien la
carga; el sistema no lee el archivo), qué actuaciones registró y dónde hace falta una según lo que declaran
sus productores y lo que se sabe de sus parcelas, con el estado de hoy. Nada de esto frena un lote: se
muestra y llega al informe de hallazgos. Una política o una actuación no se edita ni se borra: se anula con
motivo. Cada acción audita en la misma transacción.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app import textos, ubigeo
from app.catalogos import actuaciones as catalogo
from app.catalogos import declaracion_productor as cuestionario
from app.catalogos import requisitos_organizacion
from app.config import get_settings
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import LIMA, ahora, hoy_lima
from app.models import (
    ActuacionDiligencia,
    ActuacionProductor,
    Afiliacion,
    Cooperativa,
    DeclaracionProducto,
    DeclaracionProductor,
    Documento,
    Parcela,
    ParcelaIncidencia,
    Perfil,
    PoliticaOrganizacion,
    Productor,
)
from app.schemas.cooperativa import RequisitoOrganizacionSalida
from app.schemas.diligencia import (
    ActuacionDetalle,
    ActuacionNueva,
    ActuacionSalida,
    DiligenciaSalida,
    FuenteSugeridaSalida,
    PoliticaSalida,
    PoliticasSalida,
    ProductorAlcanzado,
    ProductoRevisado,
    ProductosRevisadosSalida,
    SenalSalida,
    TemaPoliticaSalida,
    TipoActuacionSalida,
)
from app.services import declaracion_productor, documentos
from app.services.auditoria import registrar_auditoria
from app.services.documentos import Archivo
from app.services.legalidad import legalidades, sumar_meses
from app.storage import ClienteStorage

TEMAS_POLITICA = requisitos_organizacion.TEMAS_POLITICA
MESES_INCIDENCIAS = 12


def _nombres(sesion: Session, ids: set) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(
        sesion.execute(
            select(Perfil.id, func.concat(Perfil.nombres, " ", Perfil.apellidos)).where(Perfil.id.in_(ids))
        ).all()
    )


def _requisito(
    codigo: str, estado: str, motivo: str, falta: list[str], falta_codigos: list[str]
) -> RequisitoOrganizacionSalida:
    from app.services.cooperativa import requisito_salida  # evita importación circular

    return requisito_salida(codigo, estado, motivo, falta, falta_codigos)


# ---------- Política (sección 5) ----------


def politicas_vigentes(sesion: Session, cooperativa_id: uuid.UUID) -> list[PoliticaOrganizacion]:
    """Las no anuladas, con su archivo sin anular, de la más reciente a la más antigua."""
    return list(
        sesion.scalars(
            select(PoliticaOrganizacion)
            .join(Documento, Documento.id == PoliticaOrganizacion.documento_id)
            .where(
                PoliticaOrganizacion.cooperativa_id == cooperativa_id,
                PoliticaOrganizacion.anulada_en.is_(None),
                Documento.anulado_en.is_(None),
            )
            .order_by(PoliticaOrganizacion.adoptada_en.desc(), PoliticaOrganizacion.registrada_en.desc())
        )
    )


def temas(sesion: Session, cooperativa: Cooperativa) -> list[TemaPoliticaSalida]:
    """Sección 5, reglas 1 y 2: un tema está sustentado cuando una política vigente lo cubre; el canal de
    denuncias necesita además el contacto escrito en los datos de la organización."""
    vigentes = politicas_vigentes(sesion, cooperativa.id)
    salida = []
    for tema in TEMAS_POLITICA:
        cubren = [p for p in vigentes if tema.codigo in p.temas]
        falta = None
        if not cubren:
            falta = "Una política vigente que lo cubra."
        elif tema.codigo == "canal_denuncias" and not cooperativa.canal_denuncias_contacto:
            falta = "El contacto del canal en los datos de la organización."
        salida.append(
            TemaPoliticaSalida(
                codigo=tema.codigo,
                nombre=tema.nombre,
                que_dice=tema.que_dice,
                referencias=list(tema.referencias),
                estado="sin_sustento" if falta else "sustentado",
                adoptada_en=max((p.adoptada_en for p in cubren), default=None),
                politicas=len(cubren),
                falta=falta,
            )
        )
    return salida


def requisito_integridad(sesion: Session, cooperativa: Cooperativa) -> RequisitoOrganizacionSalida:
    """Sección 5, regla 3: sustentado cuando los cinco temas lo están."""
    faltan = [t for t in temas(sesion, cooperativa) if t.estado != "sustentado"]
    return _requisito(
        "integridad",
        "sin_sustento" if faltan else "sustentado",
        "Siempre: una política que cubra los cinco temas.",
        [t.nombre for t in faltan],
        [t.codigo for t in faltan],
    )


def _politica_salida(p: PoliticaOrganizacion, doc: Documento | None, nombres: dict) -> PoliticaSalida:
    from app.services.productores import documento_salida  # evita importación circular

    return PoliticaSalida(
        id=p.id,
        temas=[t.codigo for t in TEMAS_POLITICA if t.codigo in p.temas],
        adoptada_en=p.adoptada_en,
        organo=p.organo,
        version_plantilla=p.version_plantilla,
        documento=documento_salida(doc, nombres.get(doc.subido_por)) if doc else None,
        registrada_por_nombre=nombres.get(p.registrada_por),
        registrada_en=p.registrada_en,
        vigente=p.anulada_en is None and doc is not None and doc.anulado_en is None,
        anulada_en=p.anulada_en,
        anulada_por_nombre=nombres.get(p.anulada_por),
        motivo_anulacion=p.motivo_anulacion,
    )


def politicas(contexto: Contexto) -> PoliticasSalida:
    from app.pdf.politica_organizacion import version  # evita cargar fpdf2 al importar

    sesion = contexto.sesion
    cooperativa = sesion.get(Cooperativa, cooperativa_del_contexto(contexto))
    filas = list(
        sesion.scalars(
            select(PoliticaOrganizacion)
            .where(PoliticaOrganizacion.cooperativa_id == cooperativa.id)
            .order_by(PoliticaOrganizacion.adoptada_en.desc(), PoliticaOrganizacion.registrada_en.desc())
        )
    )
    docs = {
        d.id: d
        for d in sesion.scalars(select(Documento).where(Documento.id.in_({p.documento_id for p in filas})))
    }
    nombres = _nombres(
        sesion,
        {p.registrada_por for p in filas}
        | {p.anulada_por for p in filas}
        | {d.subido_por for d in docs.values()},
    )
    return PoliticasSalida(
        temas=temas(sesion, cooperativa),
        requisito=requisito_integridad(sesion, cooperativa),
        politicas=[_politica_salida(p, docs.get(p.documento_id), nombres) for p in filas],
        canal_denuncias_contacto=cooperativa.canal_denuncias_contacto,
        organo_sugerido=requisitos_organizacion.ORGANO_SUGERIDO.get(cooperativa.tipo_organizacion, ""),
        version_plantilla=version(),
    )


def cargar_politica(
    contexto: Contexto,
    storage: ClienteStorage,
    archivo: Archivo,
    temas_marcados: list[str],
    adoptada_en: date,
    organo: str,
    version_plantilla: int | None,
) -> PoliticasSalida:
    """Sección 5, regla 5: quien carga la política marca los temas que cubre; el sistema no lee el archivo."""
    from app.pdf.politica_organizacion import version  # evita cargar fpdf2 al importar

    marcados = [t.codigo for t in TEMAS_POLITICA if t.codigo in set(temas_marcados)]
    if not marcados or len(set(temas_marcados)) != len(marcados):
        raise error_api(422, "temas_invalidos", "Marca uno o más de los cinco temas de la política.")
    if adoptada_en > hoy_lima():
        raise error_api(422, "fecha_futura", "La fecha de adopción no puede ser futura.")
    organo = (organo or "").strip()
    if not 2 <= len(organo) <= 200:
        raise error_api(422, "organo_requerido", "Indica qué órgano de la organización adoptó la política.")
    if version_plantilla is not None and not 1 <= version_plantilla <= version():
        raise error_api(422, "version_invalida", "Esa versión de la plantilla no existe.")
    cooperativa_id = cooperativa_del_contexto(contexto)
    documento, ruta = documentos.guardar(
        contexto,
        storage,
        entidad="cooperativa",
        entidad_id=cooperativa_id,
        tipo="politica_organizacion",
        archivo=archivo,
        datos_legales={"fecha_emision": adoptada_en},
    )
    try:
        politica = PoliticaOrganizacion(
            cooperativa_id=cooperativa_id,
            documento_id=documento.id,
            temas=marcados,
            adoptada_en=adoptada_en,
            organo=organo,
            version_plantilla=version_plantilla,
            registrada_por=contexto.usuario_id,
        )
        contexto.sesion.add(politica)
        contexto.sesion.flush()
        registrar_auditoria(
            contexto,
            "politica.cargar",
            "politica_organizacion",
            politica.id,
            {
                "temas": marcados,
                "adoptada_en": adoptada_en,
                "organo": organo,
                "version_plantilla": version_plantilla,
                "documento_id": documento.id,
            },
        )
        contexto.sesion.commit()
    except Exception:
        contexto.sesion.rollback()
        documentos.descartar(storage, ruta)
        raise
    return politicas(contexto)


def anular_politica(contexto: Contexto, politica_id: uuid.UUID, motivo: str) -> PoliticasSalida:
    """Sección 5: la política no se borra; se anula con motivo y sus temas dejan de contar."""
    politica = contexto.sesion.get(PoliticaOrganizacion, politica_id)
    if politica is None or politica.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("La política no existe.")
    if politica.anulada_en is not None:
        raise error_api(400, "politica_anulada", "La política ya estaba anulada.")
    politica.anulada_en = ahora()
    politica.anulada_por = contexto.usuario_id
    politica.motivo_anulacion = motivo
    registrar_auditoria(
        contexto,
        "politica.anular",
        "politica_organizacion",
        politica.id,
        {"temas": politica.temas, "motivo": motivo},
    )
    contexto.sesion.commit()
    return politicas(contexto)


def datos_politica(cooperativa: Cooperativa) -> dict[str, Any]:
    """Lo que la plantilla trae escrito: razón social, RUC, tipo, órgano sugerido y contacto del canal."""
    return {
        "organizacion": cooperativa.razon_social,
        "ruc": cooperativa.ruc,
        "tipo_organizacion": requisitos_organizacion.NOMBRE_TIPO_ORGANIZACION.get(
            cooperativa.tipo_organizacion, cooperativa.tipo_organizacion
        ),
        "organo": requisitos_organizacion.ORGANO_SUGERIDO.get(cooperativa.tipo_organizacion),
        "canal": cooperativa.canal_denuncias_contacto,
    }


def hoja_politica(contexto: Contexto) -> tuple[bytes, str]:
    """Plantilla para firmar: el texto del Anexo A con los datos de la organización ya escritos."""
    from app.pdf import politica_organizacion as pdf  # evita cargar fpdf2 al importar

    cooperativa = contexto.sesion.get(Cooperativa, cooperativa_del_contexto(contexto))
    contenido = pdf.generar(datos_politica(cooperativa), es_demo=bool(cooperativa.es_demo))
    return contenido, f"politica-para-firmar-{cooperativa.ruc}.pdf"


# ---------- Actuaciones (sección 6) ----------


def vigencia_meses() -> int:
    return get_settings().actuacion_vigencia_meses


def vigente_hasta(actuacion: ActuacionDiligencia) -> date:
    return sumar_meses(actuacion.fecha, vigencia_meses())


def es_vigente(actuacion: ActuacionDiligencia, hoy: date) -> bool:
    """Sección 6.2, regla 3: cuenta para sus temas durante ACTUACION_VIGENCIA_MESES desde su fecha."""
    return actuacion.anulada_en is None and vigente_hasta(actuacion) >= hoy


def actuaciones_vigentes(
    sesion: Session, cooperativa_id: uuid.UUID, hoy: date | None = None
) -> list[ActuacionDiligencia]:
    hoy = hoy or hoy_lima()
    # Un margen de un mes evita perder la del último día; la vigencia exacta la decide es_vigente.
    desde = hoy - timedelta(days=31 * (vigencia_meses() + 1))
    filas = sesion.scalars(
        select(ActuacionDiligencia)
        .where(
            ActuacionDiligencia.cooperativa_id == cooperativa_id,
            ActuacionDiligencia.anulada_en.is_(None),
            ActuacionDiligencia.fecha >= desde,
        )
        .order_by(ActuacionDiligencia.fecha.desc(), ActuacionDiligencia.registrada_en.desc())
    )
    return [a for a in filas if es_vigente(a, hoy)]


def actuacion_visible(contexto: Contexto, actuacion_id: uuid.UUID) -> ActuacionDiligencia:
    """Otra organización recibe 404."""
    actuacion = contexto.sesion.get(ActuacionDiligencia, actuacion_id)
    if actuacion is None or actuacion.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("La actuación no existe.")
    return actuacion


def _productores_afiliados(contexto: Contexto, ids: list[uuid.UUID]) -> list[uuid.UUID]:
    unicos = list(dict.fromkeys(ids))
    if not unicos:
        return []
    afiliados = set(
        contexto.sesion.scalars(
            select(Afiliacion.productor_id).where(
                Afiliacion.productor_id.in_(unicos),
                Afiliacion.cooperativa_id == cooperativa_del_contexto(contexto),
                Afiliacion.estado == "activa",
            )
        )
    )
    if len(afiliados) != len(unicos):
        raise error_api(
            422, "productor_no_afiliado", "Algún productor marcado no está afiliado a la cooperativa."
        )
    return unicos


def registrar(contexto: Contexto, datos: ActuacionNueva) -> ActuacionDetalle:
    """Sección 6.5: el formulario pide tipo, temas, fecha, descripción y resultado y, según el tipo, la fuente
    o la contraparte. Lo demás es opcional."""
    tipo = catalogo.TIPOS_POR_CODIGO[datos.tipo]
    if datos.fecha > hoy_lima():
        raise error_api(422, "fecha_futura", "La fecha de la actuación no puede ser futura.")
    contraparte = (datos.contraparte or "").strip() or None
    if tipo.pide_contraparte and contraparte is None:
        que = "la fuente revisada" if datos.tipo == "revision_de_fuente_publica" else "con quién se habló"
        raise error_api(422, "contraparte_requerida", f"Indica {que}.")
    lugar = {c: (getattr(datos, c) or "").strip() or None for c in ubigeo.CAMPOS}
    if any(lugar.values()):
        if not all(lugar.values()):
            raise error_api(
                422, "ubicacion_incompleta", "Indica el departamento, la provincia y el distrito, o ninguno."
            )
        ubigeo.normalizar(lugar)
    productor_ids = _productores_afiliados(contexto, datos.productor_ids)
    temas_marcados = [t.codigo for t in catalogo.TEMAS if t.codigo in set(datos.temas)]
    actuacion = ActuacionDiligencia(
        cooperativa_id=cooperativa_del_contexto(contexto),
        tipo=datos.tipo,
        temas=temas_marcados,
        fecha=datos.fecha,
        descripcion=datos.descripcion,
        contraparte=contraparte,
        resultado=datos.resultado,
        participantes=datos.participantes,
        registrada_por=contexto.usuario_id,
        **lugar,
    )
    contexto.sesion.add(actuacion)
    contexto.sesion.flush()
    for productor_id in productor_ids:
        contexto.sesion.add(ActuacionProductor(actuacion_id=actuacion.id, productor_id=productor_id))
    registrar_auditoria(
        contexto,
        "actuacion.registrar",
        "actuacion",
        actuacion.id,
        {
            "tipo": datos.tipo,
            "temas": temas_marcados,
            "fecha": datos.fecha,
            "contraparte": contraparte,
            "participantes": datos.participantes,
            "productores": len(productor_ids),
            **lugar,
        },
    )
    contexto.sesion.commit()
    return ficha(contexto, actuacion.id)


def cargar_evidencia(
    contexto: Contexto, storage: ClienteStorage, actuacion_id: uuid.UUID, archivo: Archivo
) -> ActuacionDetalle:
    """Sección 6.5, regla 2: lista de asistencia, foto, captura o informe. Se puede agregar después."""
    actuacion = actuacion_visible(contexto, actuacion_id)
    if actuacion.anulada_en is not None:
        raise error_api(400, "actuacion_anulada", "La actuación está anulada: no recibe evidencia.")
    documentos.cargar(
        contexto,
        storage,
        entidad="actuacion",
        entidad_id=actuacion.id,
        tipo="evidencia_actuacion",
        archivo=archivo,
    )
    return ficha(contexto, actuacion.id)


def anular(contexto: Contexto, actuacion_id: uuid.UUID, motivo: str) -> ActuacionDetalle:
    actuacion = actuacion_visible(contexto, actuacion_id)
    if actuacion.anulada_en is not None:
        raise error_api(400, "actuacion_anulada", "La actuación ya estaba anulada.")
    actuacion.anulada_en = ahora()
    actuacion.anulada_por = contexto.usuario_id
    actuacion.motivo_anulacion = motivo
    registrar_auditoria(
        contexto, "actuacion.anular", "actuacion", actuacion.id, {"tipo": actuacion.tipo, "motivo": motivo}
    )
    contexto.sesion.commit()
    return ficha(contexto, actuacion.id)


def _conteos(sesion: Session, ids: list[uuid.UUID]) -> tuple[dict, dict]:
    if not ids:
        return {}, {}
    productores = dict(
        sesion.execute(
            select(ActuacionProductor.actuacion_id, func.count())
            .where(ActuacionProductor.actuacion_id.in_(ids))
            .group_by(ActuacionProductor.actuacion_id)
        ).all()
    )
    evidencias = dict(
        sesion.execute(
            select(Documento.entidad_id, func.count())
            .where(
                Documento.entidad == "actuacion",
                Documento.entidad_id.in_(ids),
                Documento.anulado_en.is_(None),
            )
            .group_by(Documento.entidad_id)
        ).all()
    )
    return productores, evidencias


def _salida(a: ActuacionDiligencia, productores: int, evidencias: int, nombres: dict, hoy: date) -> dict:
    return {
        "id": a.id,
        "tipo": a.tipo,
        "tipo_nombre": catalogo.TIPOS_POR_CODIGO[a.tipo].nombre,
        "temas": [t.codigo for t in catalogo.TEMAS if t.codigo in a.temas],
        "fecha": a.fecha,
        "descripcion": a.descripcion,
        "contraparte": a.contraparte,
        "resultado": a.resultado,
        "participantes": a.participantes,
        "departamento": a.departamento,
        "provincia": a.provincia,
        "distrito": a.distrito,
        "nivel": "documentado" if evidencias else "declarado",
        "vigente": es_vigente(a, hoy),
        "vigente_hasta": vigente_hasta(a),
        "productores": productores,
        "evidencias": evidencias,
        "registrada_por_nombre": nombres.get(a.registrada_por),
        "registrada_en": a.registrada_en,
        "anulada_en": a.anulada_en,
        "anulada_por_nombre": nombres.get(a.anulada_por),
        "motivo_anulacion": a.motivo_anulacion,
    }


def listar(
    contexto: Contexto,
    *,
    tipo: str | None = None,
    tema: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    productor_id: uuid.UUID | None = None,
) -> list[ActuacionSalida]:
    """Sección 9: lista con filtros por tipo, tema y fechas; con `productor_id`, las que alcanzaron a ese
    productor (su ficha). Las anuladas se listan, marcadas."""
    sesion = contexto.sesion
    consulta = select(ActuacionDiligencia).where(
        ActuacionDiligencia.cooperativa_id == cooperativa_del_contexto(contexto)
    )
    if tipo:
        consulta = consulta.where(ActuacionDiligencia.tipo == tipo)
    if tema:
        consulta = consulta.where(ActuacionDiligencia.temas.any(tema))
    if desde:
        consulta = consulta.where(ActuacionDiligencia.fecha >= desde)
    if hasta:
        consulta = consulta.where(ActuacionDiligencia.fecha <= hasta)
    if productor_id:
        consulta = consulta.join(
            ActuacionProductor,
            and_(
                ActuacionProductor.actuacion_id == ActuacionDiligencia.id,
                ActuacionProductor.productor_id == productor_id,
            ),
        )
    filas = list(
        sesion.scalars(
            consulta.order_by(
                ActuacionDiligencia.fecha.desc(), ActuacionDiligencia.registrada_en.desc()
            ).limit(500)
        )
    )
    productores, evidencias = _conteos(sesion, [a.id for a in filas])
    nombres = _nombres(sesion, {a.registrada_por for a in filas} | {a.anulada_por for a in filas})
    hoy = hoy_lima()
    return [
        ActuacionSalida(**_salida(a, productores.get(a.id, 0), evidencias.get(a.id, 0), nombres, hoy))
        for a in filas
    ]


def ficha(contexto: Contexto, actuacion_id: uuid.UUID) -> ActuacionDetalle:
    from app.services.productores import documento_salida  # evita importación circular

    sesion = contexto.sesion
    a = actuacion_visible(contexto, actuacion_id)
    alcanzados = list(
        sesion.execute(
            select(Productor)
            .join(ActuacionProductor, ActuacionProductor.productor_id == Productor.id)
            .where(ActuacionProductor.actuacion_id == a.id)
            .order_by(Productor.apellidos, Productor.nombres)
        ).scalars()
    )
    docs = list(
        sesion.scalars(
            select(Documento)
            .where(Documento.entidad == "actuacion", Documento.entidad_id == a.id)
            .order_by(Documento.creado_en.desc())
        )
    )
    nombres = _nombres(sesion, {a.registrada_por, a.anulada_por} | {d.subido_por for d in docs})
    vigentes = sum(1 for d in docs if d.anulado_en is None)
    return ActuacionDetalle(
        **_salida(a, len(alcanzados), vigentes, nombres, hoy_lima()),
        productores_alcanzados=[
            ProductorAlcanzado(id=p.id, nombre=f"{p.nombres} {p.apellidos}".strip(), dni=p.dni)
            for p in alcanzados
        ],
        documentos=[documento_salida(d, nombres.get(d.subido_por)) for d in docs],
    )


def de_productores(
    sesion: Session, productor_ids: set[uuid.UUID], cooperativa_id: uuid.UUID, hoy: date | None = None
) -> dict[uuid.UUID, list[ActuacionDiligencia]]:
    """Las actuaciones vigentes que alcanzaron a cada productor, de la más reciente a la más antigua."""
    hoy = hoy or hoy_lima()
    salida: dict[uuid.UUID, list[ActuacionDiligencia]] = {p: [] for p in productor_ids}
    if not productor_ids:
        return salida
    for productor_id, actuacion in sesion.execute(
        select(ActuacionProductor.productor_id, ActuacionDiligencia)
        .join(ActuacionDiligencia, ActuacionDiligencia.id == ActuacionProductor.actuacion_id)
        .where(
            ActuacionProductor.productor_id.in_(productor_ids),
            ActuacionDiligencia.cooperativa_id == cooperativa_id,
            ActuacionDiligencia.anulada_en.is_(None),
        )
        .order_by(ActuacionDiligencia.fecha.desc(), ActuacionDiligencia.registrada_en.desc())
    ):
        if es_vigente(actuacion, hoy):
            salida[productor_id].append(actuacion)
    return salida


def de_productor(
    sesion: Session, productor_id: uuid.UUID, cooperativa_id: uuid.UUID, hoy: date | None = None
):
    """Sección 11, regla 2: las actuaciones vigentes que alcanzaron al productor, de la más reciente a la más
    antigua."""
    hoy = hoy or hoy_lima()
    filas = sesion.scalars(
        select(ActuacionDiligencia)
        .join(ActuacionProductor, ActuacionProductor.actuacion_id == ActuacionDiligencia.id)
        .where(
            ActuacionProductor.productor_id == productor_id,
            ActuacionDiligencia.cooperativa_id == cooperativa_id,
            ActuacionDiligencia.anulada_en.is_(None),
        )
        .order_by(ActuacionDiligencia.fecha.desc())
    )
    return [a for a in filas if es_vigente(a, hoy)]


# ---------- Cuadro de señales (secciones 6.2 y 6.3) ----------


@dataclass
class Senal:
    codigo: str
    cuenta: int | None  # None: integridad, que se espera siempre
    esperada: bool
    actuaciones: list[ActuacionDiligencia] = field(default_factory=list)

    @property
    def tema(self) -> catalogo.TemaDiligencia:
        return catalogo.TEMAS_POR_CODIGO[self.codigo]

    @property
    def estado(self) -> str:
        if self.actuaciones:
            return "sustentado"
        return "sin_sustento" if self.esperada else "no_se_espera"

    @property
    def ultima(self) -> date | None:
        return max((a.fecha for a in self.actuaciones), default=None)

    def texto_en(self, idioma: str) -> str:
        """La cuenta dice lo que hay detrás: "5 parcelas en tierra forestal" (sección 6.3)."""
        if self.cuenta is None:
            return textos.obtener(idioma, f"organizacion.senales.{self.codigo}")
        forma = "uno" if self.cuenta == 1 else "varios"
        return textos.t(idioma, f"organizacion.senales.{self.codigo}_{forma}", n=self.cuenta)

    @property
    def texto(self) -> str:
        return self.texto_en("es")


def _cuentas(sesion: Session, cooperativa_id: uuid.UUID, hoy: date) -> dict[str, int]:
    """La cuenta de cada señal, sobre los productores afiliados y las parcelas activas de la organización,
    con el estado de hoy (sección 6.2, regla 2)."""
    productor_ids = set(
        sesion.scalars(
            select(Afiliacion.productor_id).where(
                Afiliacion.cooperativa_id == cooperativa_id, Afiliacion.estado == "activa"
            )
        )
    )
    estados = declaracion_productor.estados(sesion, {(p, cooperativa_id) for p in productor_ids}, hoy)
    respuestas = [e.vigente.respuestas for e in estados.values() if e.valida]
    parcelas = list(
        sesion.scalars(
            select(Parcela).where(Parcela.productor_id.in_(productor_ids), Parcela.estado == "activa")
        )
    )
    leg = legalidades(sesion, parcelas, hoy)
    desde = datetime.combine(sumar_meses(hoy, -MESES_INCIDENCIAS), time(), tzinfo=LIMA)
    incidencias = sesion.scalar(
        select(func.count())
        .select_from(ParcelaIncidencia)
        .where(
            ParcelaIncidencia.parcela_id.in_([p.id for p in parcelas]),
            ParcelaIncidencia.tipo == "tenencia",
            ParcelaIncidencia.registrada_en >= desde,
        )
    )
    return {
        "tierra_forestal": sum(1 for p in parcelas if leg[p.id].valor("en_tierra_forestal") == "si"),
        "agroquimicos_y_envases": sum(1 for r in respuestas if r.get("usa_agroquimicos") == "si"),
        "trabajo": sum(1 for r in respuestas if cuestionario.contrata(r)),
        "tenencia": incidencias or 0,
        "areas_protegidas": sum(1 for p in parcelas if leg[p.id].valor("en_anp") not in (None, "no")),
        "agua": sum(
            1
            for p in parcelas
            if leg[p.id].requisitos["agua_de_riego"].estado in ("sin_sustento", "vencido")
            or leg[p.id].valor("junto_a_cuerpo_de_agua") == "si"
        ),
        "derechos_humanos": sum(
            1
            for e in estados.values()
            if e.valida
            and any(e.requisitos[c].estado == "por_atender" for c in ("menores_de_edad", "trabajo_libre"))
        ),
    }


def senales(sesion: Session, cooperativa_id: uuid.UUID, hoy: date | None = None) -> list[Senal]:
    """Sección 6.2, regla 1: con diligencia estándar se espera actuar siempre que la organización esté
    expuesta; con diligencia aligerada, solo cuando salta un caso. En los dos, eso es una cuenta mayor que
    cero; la integridad se espera siempre."""
    hoy = hoy or hoy_lima()
    cuentas = _cuentas(sesion, cooperativa_id, hoy)
    vigentes = actuaciones_vigentes(sesion, cooperativa_id, hoy)
    salida = []
    for tema in catalogo.TEMAS:
        cuenta = cuentas.get(tema.codigo)
        esperada = cuenta is None or cuenta > 0
        salida.append(Senal(tema.codigo, cuenta, esperada, [a for a in vigentes if tema.codigo in a.temas]))
    return salida


def requisito_actuaciones(
    sesion: Session, cooperativa_id: uuid.UUID, hoy: date | None = None, cuadro: list[Senal] | None = None
) -> RequisitoOrganizacionSalida:
    """Sección 6.2, regla 4: sustentado cuando cada tema esperado tiene al menos una actuación vigente."""
    cuadro = cuadro if cuadro is not None else senales(sesion, cooperativa_id, hoy)
    faltan = [s for s in cuadro if s.estado == "sin_sustento"]
    return _requisito(
        "actuaciones",
        "sin_sustento" if faltan else "sustentado",
        "Una actuación vigente por cada tema en que se espera.",
        [s.tema.nombre for s in faltan],
        [s.codigo for s in faltan],
    )


def _senal_salida(s: Senal) -> SenalSalida:
    return SenalSalida(
        codigo=s.codigo,
        nombre=s.tema.nombre,
        referencias=list(s.tema.referencias),
        diligencia=s.tema.diligencia,
        regla=s.tema.senal,
        cuenta=s.cuenta,
        texto=s.texto,
        esperada=s.esperada,
        actuaciones_vigentes=len(s.actuaciones),
        ultima=s.ultima,
        estado=s.estado,
    )


def cuadro(contexto: Contexto) -> DiligenciaSalida:
    sesion = contexto.sesion
    cooperativa_id = cooperativa_del_contexto(contexto)
    hoy = hoy_lima()
    lista = senales(sesion, cooperativa_id, hoy)
    return DiligenciaSalida(
        senales=[_senal_salida(s) for s in lista],
        requisito=requisito_actuaciones(sesion, cooperativa_id, hoy, lista),
        tipos=[
            TipoActuacionSalida(
                codigo=t.codigo,
                nombre=t.nombre,
                que_es=t.que_es,
                ejemplos=t.ejemplos,
                pide_contraparte=t.pide_contraparte,
            )
            for t in catalogo.TIPOS
        ],
        fuentes=[
            FuenteSugeridaSalida(nombre=f.nombre, temas=list(f.temas), enlace=f.enlace)
            for f in catalogo.FUENTES
        ],
        vigencia_meses=vigencia_meses(),
    )


# ---------- Lista de productos (sección 6.6) ----------


def productos_revisados(
    sesion: Session, cooperativa_id: uuid.UUID, hoy: date | None = None
) -> list[ProductoRevisado]:
    """Cada producto declarado en una declaración vigente, una vez (por su nombre, sin tildes, mayúsculas ni
    espacios de más), con su revisión más reciente, su fecha, su número de registro y cuántos productores lo
    declaran."""
    hoy = hoy or hoy_lima()
    filas = sesion.execute(
        select(DeclaracionProducto, DeclaracionProductor.productor_id, DeclaracionProductor.registrada_en)
        .join(DeclaracionProductor, DeclaracionProductor.id == DeclaracionProducto.declaracion_id)
        .where(
            DeclaracionProductor.cooperativa_id == cooperativa_id,
            DeclaracionProductor.estado == "vigente",
            DeclaracionProductor.vigente_hasta >= hoy,
        )
        .order_by(DeclaracionProductor.registrada_en)
    ).all()
    grupos: dict[str, dict[str, Any]] = {}
    for producto, productor_id, _ in filas:
        clave = cuestionario.normalizar_nombre(producto.nombre)
        g = grupos.setdefault(clave, {"nombre": producto.nombre, "productores": set(), "productos": []})
        g["productores"].add(productor_id)
        g["productos"].append(producto)
    salida = []
    for g in grupos.values():
        revisados = [p for p in g["productos"] if p.revision != "sin_revisar" and p.revisado_en is not None]
        ultimo = max(revisados, key=lambda p: p.revisado_en) if revisados else g["productos"][-1]
        salida.append(
            ProductoRevisado(
                nombre=g["nombre"],
                tipo=ultimo.tipo,
                revision=ultimo.revision if revisados else "sin_revisar",
                registro=ultimo.registro if revisados else None,
                revisado_en=ultimo.revisado_en if revisados else None,
                productores=len(g["productores"]),
            )
        )
    return sorted(salida, key=lambda p: cuestionario.normalizar_nombre(p.nombre))


def productos(contexto: Contexto) -> ProductosRevisadosSalida:
    from app.schemas.cooperativa import ConsultaPublica

    return ProductosRevisadosSalida(
        productos=productos_revisados(contexto.sesion, cooperativa_del_contexto(contexto)),
        consultas=[ConsultaPublica(url=u, nombre=n) for u, n in declaracion_productor.CONSULTAS_SENASA],
    )


def hoja_productos(contexto: Contexto) -> tuple[bytes, str]:
    """El PDF para repartir: los que figuran y los que no figuran en el registro del SENASA. Los productos
    que nadie buscó todavía no van."""
    from app.pdf import politica_organizacion as pdf  # evita cargar fpdf2 al importar

    cooperativa = contexto.sesion.get(Cooperativa, cooperativa_del_contexto(contexto))
    hoy = hoy_lima()
    lista = productos_revisados(contexto.sesion, cooperativa.id, hoy)

    def fila(p: ProductoRevisado) -> dict[str, Any]:
        return {
            "nombre": p.nombre,
            "tipo": cuestionario.ETIQUETAS_TIPO_PRODUCTO.get(p.tipo, p.tipo),
            "registro": p.registro,
            "fecha": p.revisado_en.astimezone(LIMA).strftime("%d/%m/%Y") if p.revisado_en else None,
            "productores": p.productores,
        }

    contenido = pdf.generar_productos(
        cooperativa.razon_social,
        hoy,
        [fila(p) for p in lista if p.revision == "figura"],
        [fila(p) for p in lista if p.revision == "no_figura"],
        declaracion_productor.CONSULTAS_SENASA,
        es_demo=bool(cooperativa.es_demo),
    )
    return contenido, f"productos-senasa-{hoy.isoformat()}.pdf"


# ---------- Bloque del DEX (sección 11) ----------


def bloque(sesion: Session, cooperativa: Cooperativa, hoy: date | None = None) -> dict[str, Any]:
    """Lo que el DEX sella de la organización: los documentos del expediente con su estado y su nivel, los
    requisitos, los cinco temas de la política con su fecha de adopción, si hay contacto del canal, el
    cuadro de señales y las actuaciones vigentes. La evidencia no sale del sistema: el DEX dice si existe.
    Tampoco van los nombres de los productores alcanzados."""
    from app.catalogos import documentos_legales
    from app.services import cooperativa as servicio_cooperativa  # evita importación circular

    hoy = hoy or hoy_lima()
    cas = servicio_cooperativa.casillas(sesion, cooperativa.id, hoy)
    lista = senales(sesion, cooperativa.id, hoy)
    vigentes = actuaciones_vigentes(sesion, cooperativa.id, hoy)
    _, evidencias = _conteos(sesion, [a.id for a in vigentes])
    return {
        "tipo_organizacion": cooperativa.tipo_organizacion,
        "documentos": [
            {
                "codigo": codigo,
                "identidad": documentos_legales.POR_CODIGO_COOPERATIVA[codigo].identidad,
                "estado": c.estado,
                "nivel": c.nivel,
            }
            for codigo, c in cas.items()
        ],
        "requisitos": [
            {"codigo": r.codigo, "estado": r.estado, "falta": r.falta_codigos}
            for r in servicio_cooperativa.requisitos(sesion, cooperativa, hoy)
        ],
        "politica": [
            {"tema": t.codigo, "estado": t.estado, "adoptada_en": t.adoptada_en}
            for t in temas(sesion, cooperativa)
        ],
        "canal_denuncias": bool(cooperativa.canal_denuncias_contacto),
        "senales": [
            {
                "tema": s.codigo,
                "cuenta": s.cuenta,
                "texto": {i: s.texto_en(i) for i in textos.IDIOMAS},
                "esperada": s.esperada,
                "actuaciones_vigentes": len(s.actuaciones),
                "estado": s.estado,
            }
            for s in lista
        ],
        "actuaciones": [
            {
                "fecha": a.fecha,
                "tipo": a.tipo,
                "temas": [t.codigo for t in catalogo.TEMAS if t.codigo in a.temas],
                "descripcion": a.descripcion,
                "resultado": a.resultado,
                "nivel": "documentado" if evidencias.get(a.id) else "declarado",
            }
            for a in vigentes
        ],
    }

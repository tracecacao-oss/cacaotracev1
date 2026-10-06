"""Expediente legal de la parcela: 7 casillas, exenciones y cotejo en fuente (Parte 4).

El estado de cada casilla y del expediente se calcula al consultar, con la fecha del día. Nada se
guarda en columnas que puedan quedar desactualizadas.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogos import documentos_legales as catalogo
from app.config import get_settings
from app.contexto import Contexto
from app.errores import error_api, no_encontrado
from app.fechas import ahora, hoy_lima
from app.models import Documento, ExencionDocumento, Parcela
from app.services.auditoria import registrar_auditoria

ORDEN = {"vigente": 0, "por_vencer": 1, "vencido": 2}


@dataclass
class Casilla:
    codigo: str
    estado: str  # vigente, por_vencer, vencido, no_aplica o faltante
    documento: Documento | None = None  # el que cubre la casilla
    documentos: list[Documento] = field(default_factory=list)
    exencion: ExencionDocumento | None = None

    @property
    def nivel(self) -> str | None:
        if self.documento is None or self.estado not in ("vigente", "por_vencer"):
            return None
        return "verificado_en_fuente" if self.documento.cotejado_en else "documentado"


@dataclass
class Expediente:
    casillas: dict[str, Casilla]

    @property
    def tenencia_cumplida(self) -> bool:
        return any(self.casillas[c].estado in ("vigente", "por_vencer") for c in catalogo.TENENCIA)

    @property
    def faltan(self) -> list[str]:
        faltan = [] if self.tenencia_cumplida else ["tenencia"]
        faltan += [
            c
            for c in catalogo.CON_EXENCION
            if self.casillas[c].estado not in ("vigente", "por_vencer", "no_aplica")
        ]
        return faltan

    @property
    def completo(self) -> bool:
        return not self.faltan

    @property
    def tenencia_solo_posesion(self) -> bool:
        cubre = lambda c: self.casillas[c].estado in ("vigente", "por_vencer")  # noqa: E731
        return cubre("constancia_posesion") and not cubre("titulo_sunarp")

    def alertas(self) -> list[str]:
        estados = {c.estado for c in self.casillas.values()}
        alertas = []
        if not self.completo:
            alertas.append("expediente_incompleto")
        if "por_vencer" in estados:
            alertas.append("documento_por_vencer")
        if "vencido" in estados:
            alertas.append("documento_vencido")
        if self.tenencia_solo_posesion:
            alertas.append("tenencia_solo_posesion")
        return alertas


def estado_documento(documento: Documento, hoy: date, aviso_dias: int) -> str:
    vence = documento.fecha_vencimiento
    if vence is None or vence > hoy + timedelta(days=aviso_dias):
        return "vigente"
    return "por_vencer" if vence >= hoy else "vencido"


def _casilla(codigo: str, docs: list[Documento], exencion, hoy: date, aviso_dias: int) -> Casilla:
    if docs:
        # Cuenta el documento con el mejor estado y, entre esos, el de vencimiento más lejano.
        lejano = date.max
        mejor = min(
            docs,
            key=lambda d: (
                ORDEN[estado_documento(d, hoy, aviso_dias)],
                -(d.fecha_vencimiento or lejano).toordinal(),
            ),
        )
        return Casilla(codigo, estado_documento(mejor, hoy, aviso_dias), mejor, docs, exencion)
    if exencion is not None:
        return Casilla(codigo, "no_aplica", None, [], exencion)
    return Casilla(codigo, "faltante")


def expedientes(
    sesion: Session, parcela_ids: list[uuid.UUID], hoy: date | None = None
) -> dict[uuid.UUID, Expediente]:
    """Expediente de varias parcelas con dos consultas."""
    hoy = hoy or hoy_lima()
    aviso = get_settings().aviso_vencimiento_dias
    if not parcela_ids:
        return {}
    docs: dict[tuple, list[Documento]] = {}
    for d in sesion.scalars(
        select(Documento).where(
            Documento.entidad == "parcela",
            Documento.entidad_id.in_(parcela_ids),
            Documento.tipo.in_(catalogo.CODIGOS),
            Documento.anulado_en.is_(None),
        )
    ):
        docs.setdefault((d.entidad_id, d.tipo), []).append(d)
    exenciones = {
        (e.parcela_id, e.tipo): e
        for e in sesion.scalars(
            select(ExencionDocumento).where(
                ExencionDocumento.parcela_id.in_(parcela_ids), ExencionDocumento.retirada_en.is_(None)
            )
        )
    }
    return {
        pid: Expediente(
            {
                c: _casilla(c, docs.get((pid, c), []), exenciones.get((pid, c)), hoy, aviso)
                for c in catalogo.CODIGOS
            }
        )
        for pid in parcela_ids
    }


def expediente(sesion: Session, parcela_id: uuid.UUID) -> Expediente:
    return expedientes(sesion, [parcela_id])[parcela_id]


def documentos_por_vencer(sesion: Session, parcela_ids: list[uuid.UUID]) -> list[tuple[uuid.UUID, Casilla]]:
    """Casillas por vencer o vencidas de esas parcelas, ordenadas por fecha de vencimiento."""
    resultado = [
        (pid, c)
        for pid, exp in expedientes(sesion, parcela_ids).items()
        for c in exp.casillas.values()
        if c.estado in ("por_vencer", "vencido")
    ]
    return sorted(resultado, key=lambda x: x[1].documento.fecha_vencimiento)


# ---------- Reglas de carga ----------


def no_excluida(parcela: Parcela) -> None:
    """Una parcela excluida no se edita, no se habilita ni recibe documentos. Tampoco para el superadmin."""
    if parcela.habilitacion_estado == "excluida":
        raise error_api(
            400, "parcela_excluida", "La parcela está excluida: no admite cambios, documentos ni decisiones."
        )


def validar_datos_legales(tipo: str, numero, entidad_emisora, fecha_emision, fecha_vencimiento) -> dict:
    """Un documento legal (de la parcela o, desde la Parte 8, de la cooperativa) exige número, entidad emisora
    y fecha de emisión."""
    if catalogo.tipo_legal(tipo) is None:
        return {}
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
        raise error_api(422, "datos_legales_requeridos", f"Falta: {', '.join(faltan)}.")
    if fecha_emision > hoy_lima():
        raise error_api(422, "fecha_futura", "La fecha de emisión no puede ser futura.")
    if fecha_vencimiento is not None and fecha_vencimiento <= fecha_emision:
        raise error_api(422, "vencimiento_invalido", "El vencimiento debe ser posterior a la emisión.")
    return {
        "numero": numero.strip(),
        "entidad_emisora": entidad_emisora.strip(),
        "fecha_emision": fecha_emision,
        "fecha_vencimiento": fecha_vencimiento,
    }


# ---------- Exenciones ----------


def declarar_exencion(contexto: Contexto, parcela: Parcela, tipo: str, motivo: str) -> ExencionDocumento:
    no_excluida(parcela)
    if tipo in catalogo.TENENCIA:
        raise error_api(
            422,
            "tenencia_sin_exencion",
            "La tenencia no admite exención: carga el título o la constancia de posesión.",
        )
    if tipo not in catalogo.CON_EXENCION:
        raise error_api(422, "tipo_invalido", "Ese tipo de documento no existe en el expediente.")
    existente = contexto.sesion.scalar(
        select(ExencionDocumento).where(
            ExencionDocumento.parcela_id == parcela.id,
            ExencionDocumento.tipo == tipo,
            ExencionDocumento.retirada_en.is_(None),
        )
    )
    if existente:
        raise error_api(409, "exencion_existente", "Ya hay una exención vigente para ese documento.")
    exencion = ExencionDocumento(
        parcela_id=parcela.id, tipo=tipo, motivo=motivo, declarada_por=contexto.usuario_id
    )
    contexto.sesion.add(exencion)
    contexto.sesion.flush()
    registrar_auditoria(
        contexto,
        "exencion.declarar",
        "parcela",
        parcela.id,
        {"exencion_id": exencion.id, "tipo": tipo, "motivo": motivo},
    )
    contexto.sesion.commit()
    return exencion


def exencion_visible(contexto: Contexto, exencion_id: uuid.UUID) -> ExencionDocumento:
    from app.services.parcelas import parcela_visible  # evita importación circular

    exencion = contexto.sesion.get(ExencionDocumento, exencion_id)
    if exencion is None:
        raise no_encontrado("La exención no existe.")
    parcela_visible(contexto, exencion.parcela_id)
    return exencion


def retirar_exencion(contexto: Contexto, exencion_id: uuid.UUID) -> ExencionDocumento:
    exencion = exencion_visible(contexto, exencion_id)
    no_excluida(contexto.sesion.get(Parcela, exencion.parcela_id))
    if exencion.retirada_en is not None:
        raise error_api(400, "exencion_retirada", "La exención ya estaba retirada.")
    exencion.retirada_en = ahora()
    exencion.retirada_por = contexto.usuario_id
    registrar_auditoria(
        contexto,
        "exencion.retirar",
        "parcela",
        exencion.parcela_id,
        {"exencion_id": exencion.id, "tipo": exencion.tipo},
    )
    contexto.sesion.commit()
    return exencion


# ---------- Cotejo en fuente ----------


def cotejar(contexto: Contexto, documento: Documento, nota: str) -> Documento:
    """Documentos del expediente de la parcela (Parte 4) o de la cooperativa (Parte 8)."""
    tipo = catalogo.tipo_legal(documento.tipo)
    if tipo is None:
        raise error_api(400, "no_es_documento_legal", "Solo se cotejan documentos del expediente legal.")
    if documento.entidad == "parcela":
        no_excluida(contexto.sesion.get(Parcela, documento.entidad_id))
    if not tipo.registro_consultable:
        raise error_api(
            400,
            "sin_registro_consultable",
            f"{tipo.nombre} no tiene un registro público contra el cual cotejarlo: queda como documentado.",
        )
    if documento.anulado_en is not None:
        raise error_api(400, "documento_anulado", "El documento está anulado.")
    if documento.cotejado_en is not None:
        raise error_api(400, "documento_cotejado", "El documento ya tiene un cotejo registrado.")
    documento.cotejado_en = ahora()
    documento.cotejado_por = contexto.usuario_id
    documento.cotejo_nota = nota
    registrar_auditoria(
        contexto,
        "documento.cotejar",
        "documento",
        documento.id,
        {"tipo": documento.tipo, "entidad_id": documento.entidad_id, "nota": nota},
    )
    contexto.sesion.commit()
    return documento


# ---------- Salida ----------


def salida(sesion: Session, parcela: Parcela):
    """Las 7 casillas con su estado, sus documentos y su exención."""
    from sqlalchemy import func

    from app.models import Perfil
    from app.schemas.habilitacion import CasillaSalida, ExencionSalida, ExpedienteSalida
    from app.services.productores import documento_salida  # evita importación circular

    exp = expediente(sesion, parcela.id)
    personas = {d.subido_por for c in exp.casillas.values() for d in c.documentos} | {
        c.exencion.declarada_por for c in exp.casillas.values() if c.exencion
    }
    nombres = dict(
        sesion.execute(
            select(Perfil.id, func.concat(Perfil.nombres, " ", Perfil.apellidos)).where(
                Perfil.id.in_(personas)
            )
        ).all()
    )
    casillas = []
    for tipo in catalogo.TIPOS:
        c = exp.casillas[tipo.codigo]
        documentos = sorted(c.documentos, key=lambda d: d.creado_en, reverse=True)
        casillas.append(
            CasillaSalida(
                codigo=tipo.codigo,
                nombre=tipo.nombre,
                grupo=tipo.grupo,
                tenencia=tipo.tenencia,
                registro_consultable=tipo.registro_consultable,
                admite_exencion=not tipo.tenencia,
                estado=c.estado,
                nivel=c.nivel,
                vence_en=c.documento.fecha_vencimiento if c.documento else None,
                documentos=[documento_salida(d, nombres.get(d.subido_por)) for d in documentos],
                exencion=ExencionSalida(
                    id=c.exencion.id,
                    tipo=c.exencion.tipo,
                    motivo=c.exencion.motivo,
                    declarada_en=c.exencion.declarada_en,
                    declarada_por_nombre=nombres.get(c.exencion.declarada_por),
                    retirada_en=c.exencion.retirada_en,
                )
                if c.exencion
                else None,
            )
        )
    return ExpedienteSalida(
        estado="completo" if exp.completo else "incompleto",
        faltan=exp.faltan,
        tenencia_solo_posesion=exp.tenencia_solo_posesion,
        casillas=casillas,
    )

"""Declaración anual del productor (adenda 5).

El productor responde un cuestionario una vez al año (app/catalogos/declaracion_productor.py) ante la
organización a la que entrega. Lo declara él mismo desde su cuenta, o lo registra el personal y vale desde
que se carga la hoja firmada. De sus respuestas salen los siete requisitos del productor
(app/catalogos/requisitos_productor.py): ninguno bloquea. Solo bloquea, en `productor_listo`, que no tenga una
declaración vigente.

El sistema no concluye: dice qué declaró el productor, quién lo registró y qué falta. Nunca dice que un
productor cumple la ley laboral, tributaria o sanitaria, ni que un producto está permitido.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.catalogos import declaracion_productor as cuestionario
from app.catalogos import requisitos_productor as catalogo
from app.config import get_settings
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import LIMA, ahora, dia_lima, hoy_lima
from app.models import (
    Afiliacion,
    Cooperativa,
    DeclaracionProducto,
    DeclaracionProductor,
    Documento,
    Parcela,
    Perfil,
    Productor,
    Tanda,
)
from app.services import configuracion_plataforma
from app.services.auditoria import registrar_auditoria
from app.services.legalidad import sumar_meses

DIAS_POR_VENCER = 30
MESES_REVISION_COPIADA = 12
PAPELES = ("relacion_trabajadores", "declaracion_renta")
CONSULTAS_SENASA = (
    ("https://servicios.senasa.gob.pe/SIGIAWeb/sigia_consulta_producto.html", "Registro de plaguicidas"),
    ("https://servicios.senasa.gob.pe/SIGIAWeb/ip_productoprincipal.html", "Registro de insumos"),
)
# Respuestas que dejan un requisito por atender (sección 6). El jornal se compara aparte, con la referencia.
POR_ATENDER = {
    "seguro_salud": ("algunos", "ninguno"),
    "equipo_proteccion": ("no",),
    "mismo_pago": ("no",),
    "descanso_maternidad_paternidad": ("no",),
    "pueden_dejar_el_trabajo": ("no",),
    "menores_trabajan": ("si_de_la_familia", "si_contratados"),
    "destino_envases": ("quema", "entierra", "bota_o_reutiliza"),
}
HORAS_JORNADA = 8
TEXTO_FALTA = {
    "relacion_trabajadores": "la relación de trabajadores permanentes",
    "declaracion_renta": "la declaración anual del impuesto a la renta",
    "ruc": "el RUC en la ficha del productor",
    "ventas_no_sabe": "saber si las ventas pasan de 75 UIT",
    "productos_sin_revisar": "buscar en el registro de SENASA los productos sin revisar",
}


def lista_es(elementos: list[str]) -> str:
    """A, B y C."""
    return elementos[0] if len(elementos) == 1 else f"{', '.join(elementos[:-1])} y {elementos[-1]}"


def vigencia_meses() -> int:
    return get_settings().declaracion_productor_vigencia_meses


def version_texto() -> int:
    from app.pdf.declaracion_tenencia import textos  # el texto versionado del Anexo A

    return textos()["declaracion_productor"]["version"]


# ---------- Lo que el sistema calcula (sección 3.2) ----------


AREA_PARCELA = case(
    (Parcela.tipo_geometria == "poligono", Parcela.area_calculada_ha), else_=Parcela.area_declarada_ha
)


def _kilos_12_meses(sesion: Session, productor_id: uuid.UUID, cooperativa_id: uuid.UUID) -> Decimal:
    """Peso seco equivalente de sus tandas validadas en la organización en los últimos 12 meses, sin las de
    DOP anulado (decisión del equipo del 2026-10-09: el mismo dato que usa el tope por hectárea)."""
    from app.services import configuracion, tandas  # evita importación circular

    desde = datetime.combine(sumar_meses(hoy_lima(), -12), time.min, LIMA)
    filas = list(
        sesion.scalars(
            select(Tanda).where(
                Tanda.productor_id == productor_id,
                Tanda.cooperativa_id == cooperativa_id,
                Tanda.estado == "validada",
                Tanda.recibida_en >= desde,
            )
        )
    )
    if not filas:
        return Decimal(0)
    anuladas = tandas._dop_anulado(sesion, [t.id for t in filas])
    factor = configuracion.de_cooperativa(sesion, cooperativa_id).factor_baba_a_seco
    return sum((tandas._peso_seco_de(sesion, t, factor) for t in filas if t.id not in anuladas), Decimal(0))


def calculados(sesion: Session, productor: Productor, cooperativa_id: uuid.UUID) -> dict[str, Any]:
    """Los datos de la sección 3.2 y los valores de referencia de la sección 9, como están hoy. El área es
    la de todas sus parcelas activas, como la calcula services/productores.py."""
    parcelas = sesion.execute(
        select(Parcela.codigo, AREA_PARCELA)
        .where(Parcela.productor_id == productor.id, Parcela.estado == "activa")
        .order_by(Parcela.codigo)
    ).all()
    area = sum((Decimal(a or 0) for _, a in parcelas), Decimal(0))
    kilos = _kilos_12_meses(sesion, productor.id, cooperativa_id)
    return {
        "area_total_ha": float(area.quantize(Decimal("0.01"))),
        "parcelas_activas": len(parcelas),
        "parcelas_codigos": [c for c, _ in parcelas],
        "tiene_ruc": bool(productor.ruc),
        "kilos_12_meses": float(kilos.quantize(Decimal("0.01"))),
        **configuracion_plataforma.referencias(sesion),
    }


# ---------- Requisitos (sección 6) ----------


@dataclass
class Hecho:
    pregunta: str
    valor: Any
    referencia: float | None = None  # el jornal de referencia, si se comparó con él

    @property
    def texto(self) -> str:
        p = cuestionario.POR_CODIGO[self.pregunta]
        return p.texto_personal

    @property
    def etiqueta(self) -> str:
        texto = cuestionario.POR_CODIGO[self.pregunta].etiqueta(self.valor)
        if self.pregunta == "horas_por_dia":
            return f"{self.valor:g} horas"
        if self.referencia is not None:
            return f"{texto} (referencia: S/ {self.referencia:,.2f})"
        return texto


@dataclass
class EstadoRequisito:
    codigo: str
    estado: str
    motivo: str
    hechos: list[Hecho] = field(default_factory=list)
    # Lo que falta para sustentarlo, aunque el estado sea por_atender: un productor con permanentes sin
    # seguro y sin relación cargada deja dos hallazgos (sección 6).
    falta: list[str] = field(default_factory=list)
    documentos: list[Documento] = field(default_factory=list)
    no_figuran: list[DeclaracionProducto] = field(default_factory=list)
    sin_revisar: list[DeclaracionProducto] = field(default_factory=list)

    @property
    def requisito(self) -> catalogo.RequisitoProductor:
        return catalogo.POR_CODIGO[self.codigo]

    @property
    def nivel_verificacion(self) -> str | None:
        if self.estado in ("sin_dato", "no_aplica"):
            return None
        return "documentado" if self.documentos else "declarado"

    @property
    def siguiente(self) -> str | None:
        if self.estado == "sin_dato":
            return "Registrar la declaración anual."
        if self.estado == "por_atender":
            return (
                "Informar al productor, capacitarlo o visitarlo, y dejar una nota de seguimiento con lo que "
                "se hizo."
            )
        if self.estado == "sin_sustento":
            return f"Falta {lista_es([TEXTO_FALTA[f] for f in self.falta])}."
        return None


@dataclass
class EstadoProductor:
    """La declaración de un productor ante una organización, con la fecha del día."""

    productor: Productor
    cooperativa_id: uuid.UUID
    vigente: DeclaracionProductor | None  # la guardada como vigente, aunque haya vencido
    por_firmar: DeclaracionProductor | None
    productos: list[DeclaracionProducto]  # los de la vigente
    documentos: list[Documento]  # los de la vigente, sin anular
    hoy: date
    area_actual: Decimal = Decimal(0)  # la de hoy, para avisar si cruzó las 5 ha después de declarar
    requisitos: dict[str, EstadoRequisito] = field(init=False)

    def __post_init__(self):
        self.requisitos = {r.codigo: r for r in self._evaluar()}

    @property
    def valida(self) -> bool:
        return self.vigente is not None and self.vigente.vigente_hasta >= self.hoy

    @property
    def estado(self) -> str:
        if self.valida:
            dias = (self.vigente.vigente_hasta - self.hoy).days
            return "por_vencer" if dias <= DIAS_POR_VENCER else "vigente"
        if self.por_firmar is not None:
            return "por_firmar"
        return "vencida" if self.vigente is not None else "sin_declaracion"

    @property
    def falta(self) -> str | None:
        """Lo que le falta a `productor_listo` por la declaración (sección 8, regla 1)."""
        if self.valida:
            return None
        if self.por_firmar is not None:
            return "hoja firmada de la declaración"
        return "declaración anual vencida" if self.vigente is not None else "declaración anual"

    @property
    def pendientes(self) -> list[str]:
        if self.por_firmar is not None:
            return ["declaracion_por_firmar"]
        if not self.valida:
            return ["sin_declaracion_anual"]
        return ["declaracion_por_vencer"] if self.estado == "por_vencer" else []

    @property
    def alertas(self) -> list[str]:
        """Sección 8, regla 3: cada requisito por atender o sin sustento es una alerta de sus parcelas."""
        estados = {r.estado for r in self.requisitos.values()}
        return [
            a
            for a, e in (("productor_por_atender", "por_atender"), ("productor_sin_sustento", "sin_sustento"))
            if e in estados
        ]

    @property
    def aviso_area(self) -> str | None:
        """Sección 5.3, regla 3: el área cruzó las 5 ha después de declarar. Avisa, no bloquea."""
        if not self.valida:
            return None
        antes = cuestionario.cinco_ha_o_mas(self.vigente.contexto)
        ahora_ = self.area_actual >= cuestionario.AREA_AGRICULTURA_FAMILIAR_HA
        if antes == ahora_:
            return None
        sentido = "subió a 5 ha o más" if ahora_ else "bajó de 5 ha"
        return (
            f"Después de declarar, el área de sus parcelas {sentido}: algunas preguntas cambian. Conviene "
            "registrar una declaración nueva."
        )

    def _docs(self, tipo: str) -> list[Documento]:
        return [d for d in self.documentos if d.tipo == tipo]

    def _evaluar(self) -> list[EstadoRequisito]:
        if not self.valida:
            motivo = "Falta la declaración anual vigente."
            return [EstadoRequisito(c, "sin_dato", motivo) for c in catalogo.CODIGOS]
        r = self.vigente.respuestas
        ctx = self.vigente.contexto
        return [
            self._condiciones(r, ctx),
            self._igualdad(r, ctx),
            self._trabajo_libre(r),
            self._menores(r),
            self._agroquimicos(r),
            self._envases(r),
            self._tributos(r),
        ]

    @staticmethod
    def _hechos(r: dict, preguntas: tuple[str, ...]) -> list[Hecho]:
        return [Hecho(p, r[p]) for p in preguntas if p in r and r[p] in POR_ATENDER.get(p, ())]

    def _condiciones(self, r: dict, ctx: dict) -> EstadoRequisito:
        codigo = "condiciones_de_trabajo"
        if not cuestionario.contrata(r):
            return EstadoRequisito(codigo, "no_aplica", "Trabaja solo con su familia.")
        tipo = "todo el año" if r["quien_trabaja"] == "permanentes" else "por días o por temporada"
        motivo = f"Contrata trabajadores {tipo}."
        hechos = []
        if r.get("horas_por_dia") is not None and r["horas_por_dia"] > HORAS_JORNADA:
            hechos.append(Hecho("horas_por_dia", r["horas_por_dia"]))
        # Sección 9: sin jornal de referencia registrado, el jornal no se compara con nada.
        referencia = ctx.get("jornal_minimo_referencia")
        if referencia is not None and r.get("jornal_soles") is not None and r["jornal_soles"] < referencia:
            hechos.append(Hecho("jornal_soles", r["jornal_soles"], referencia))
        hechos += self._hechos(r, ("seguro_salud", "equipo_proteccion"))
        falta, docs = [], []
        if r["quien_trabaja"] == "permanentes":
            docs = self._docs("relacion_trabajadores")
            if not docs:
                falta.append("relacion_trabajadores")
        if hechos:
            estado = "por_atender"
        elif r["quien_trabaja"] == "permanentes":
            estado = "sin_sustento" if falta else "sustentado"
        else:
            estado = "declarado"
        return EstadoRequisito(codigo, estado, motivo, hechos, falta, docs)

    def _igualdad(self, r: dict, ctx: dict) -> EstadoRequisito:
        codigo = "igualdad_y_maternidad"
        if not cuestionario.contrata(r):
            return EstadoRequisito(codigo, "no_aplica", "Trabaja solo con su familia.")
        if not cuestionario.cinco_ha_o_mas(ctx):
            return EstadoRequisito(
                codigo, "no_aplica", "Sus parcelas suman menos de 5 ha: se presume agricultura familiar."
            )
        hechos = self._hechos(r, ("mismo_pago", "descanso_maternidad_paternidad"))
        return EstadoRequisito(
            codigo,
            "por_atender" if hechos else "declarado",
            "Contrata trabajadores y sus parcelas suman 5 ha o más.",
            hechos,
        )

    def _trabajo_libre(self, r: dict) -> EstadoRequisito:
        codigo = "trabajo_libre"
        if not cuestionario.contrata(r):
            return EstadoRequisito(codigo, "no_aplica", "Trabaja solo con su familia.")
        hechos = self._hechos(r, ("pueden_dejar_el_trabajo",))
        estado = "por_atender" if hechos else "declarado"
        return EstadoRequisito(codigo, estado, "Contrata trabajadores.", hechos)

    def _menores(self, r: dict) -> EstadoRequisito:
        hechos = self._hechos(r, ("menores_trabajan",))
        if hechos:
            hechos += [Hecho(p, r[p]) for p in ("menor_edad_minima", "menores_van_a_la_escuela") if p in r]
        return EstadoRequisito(
            "menores_de_edad",
            "por_atender" if hechos else "declarado",
            "Se pregunta a todos los productores.",
            hechos,
        )

    def _agroquimicos(self, r: dict) -> EstadoRequisito:
        codigo, motivo = "agroquimicos", "Se pregunta a todos los productores."
        if r.get("usa_agroquimicos") != "si":
            return EstadoRequisito(codigo, "declarado", motivo)
        no_figuran = [p for p in self.productos if p.revision == "no_figura"]
        sin_revisar = [p for p in self.productos if p.revision == "sin_revisar"]
        estado = "por_atender" if no_figuran else "sin_sustento" if sin_revisar else "sustentado"
        return EstadoRequisito(
            codigo,
            estado,
            motivo,
            falta=["productos_sin_revisar"] if sin_revisar else [],
            no_figuran=no_figuran,
            sin_revisar=sin_revisar,
        )

    def _envases(self, r: dict) -> EstadoRequisito:
        codigo = "envases"
        if r.get("usa_agroquimicos") != "si":
            return EstadoRequisito(codigo, "no_aplica", "No usa agroquímicos.")
        hechos = self._hechos(r, ("destino_envases",))
        return EstadoRequisito(codigo, "por_atender" if hechos else "declarado", "Usa agroquímicos.", hechos)

    def _tributos(self, r: dict) -> EstadoRequisito:
        codigo, ventas = "tributos", r.get("ventas_superan_75_uit")
        if ventas == "no":
            return EstadoRequisito(codigo, "no_aplica", "Declara que sus ventas del año no pasan de 75 UIT.")
        if ventas == "no_sabe":
            motivo = "No sabe si sus ventas del año pasan de 75 UIT."
            return EstadoRequisito(codigo, "sin_sustento", motivo, falta=["ventas_no_sabe"])
        docs = self._docs("declaracion_renta")
        sustentos = (("ruc", bool(self.productor.ruc)), ("declaracion_renta", bool(docs)))
        falta = [f for f, ok in sustentos if not ok]
        return EstadoRequisito(
            codigo,
            "sin_sustento" if falta else "sustentado",
            "Declara que sus ventas del año pasan de 75 UIT.",
            falta=falta,
            documentos=docs,
        )


def estados(
    sesion: Session, pares: set[tuple[uuid.UUID, uuid.UUID]], hoy: date | None = None
) -> dict[tuple[uuid.UUID, uuid.UUID], EstadoProductor]:
    """La declaración de varios productores, cada uno ante su organización: {(productor, cooperativa)}."""
    hoy = hoy or hoy_lima()
    if not pares:
        return {}
    productor_ids = {p for p, _ in pares}
    productores = {p.id: p for p in sesion.scalars(select(Productor).where(Productor.id.in_(productor_ids)))}
    vigentes: dict[tuple, DeclaracionProductor] = {}
    por_firmar: dict[tuple, DeclaracionProductor] = {}
    for d in sesion.scalars(
        select(DeclaracionProductor).where(
            DeclaracionProductor.productor_id.in_(productor_ids),
            DeclaracionProductor.estado.in_(("vigente", "por_firmar")),
        )
    ):
        clave = (d.productor_id, d.cooperativa_id)
        (vigentes if d.estado == "vigente" else por_firmar)[clave] = d
    ids = [d.id for d in vigentes.values()]
    productos: dict[uuid.UUID, list[DeclaracionProducto]] = {i: [] for i in ids}
    documentos: dict[uuid.UUID, list[Documento]] = {i: [] for i in ids}
    if ids:
        for p in sesion.scalars(
            select(DeclaracionProducto)
            .where(DeclaracionProducto.declaracion_id.in_(ids))
            .order_by(DeclaracionProducto.nombre)
        ):
            productos[p.declaracion_id].append(p)
        for doc in sesion.scalars(
            select(Documento).where(
                Documento.entidad == "declaracion_productor",
                Documento.entidad_id.in_(ids),
                Documento.anulado_en.is_(None),
            )
        ):
            documentos[doc.entidad_id].append(doc)
    areas = dict(
        sesion.execute(
            select(Parcela.productor_id, func.coalesce(func.sum(AREA_PARCELA), 0))
            .where(Parcela.productor_id.in_(productor_ids), Parcela.estado == "activa")
            .group_by(Parcela.productor_id)
        ).all()
    )
    resultado = {}
    for productor_id, cooperativa_id in pares:
        clave = (productor_id, cooperativa_id)
        vigente = vigentes.get(clave)
        resultado[clave] = EstadoProductor(
            productores[productor_id],
            cooperativa_id,
            vigente,
            por_firmar.get(clave),
            productos[vigente.id] if vigente else [],
            documentos[vigente.id] if vigente else [],
            hoy,
            Decimal(areas.get(productor_id) or 0),
        )
    return resultado


def estado_de(sesion: Session, productor_id: uuid.UUID, cooperativa_id: uuid.UUID) -> EstadoProductor:
    return estados(sesion, {(productor_id, cooperativa_id)})[(productor_id, cooperativa_id)]


# ---------- Escritura ----------


def productor_afiliado(contexto: Contexto, productor_id: uuid.UUID) -> Productor:
    """Otra organización recibe 404 (sección 5.8)."""
    cooperativa_id = cooperativa_del_contexto(contexto)
    afiliacion = contexto.sesion.scalar(
        select(Afiliacion).where(
            Afiliacion.productor_id == productor_id,
            Afiliacion.cooperativa_id == cooperativa_id,
            Afiliacion.estado == "activa",
        )
    )
    if afiliacion is None:
        raise no_encontrado("El productor no existe.")
    return afiliacion.productor


def declaracion_visible(
    contexto: Contexto, productor_id: uuid.UUID, declaracion_id: uuid.UUID
) -> tuple[Productor, DeclaracionProductor]:
    productor = productor_afiliado(contexto, productor_id)
    declaracion = contexto.sesion.get(DeclaracionProductor, declaracion_id)
    if (
        declaracion is None
        or declaracion.productor_id != productor.id
        or declaracion.cooperativa_id != contexto.cooperativa_id
    ):
        raise no_encontrado("La declaración no existe.")
    return productor, declaracion


def _validar(respuestas: dict, contexto_calculado: dict) -> dict:
    try:
        return cuestionario.validar(respuestas, contexto_calculado)
    except cuestionario.ErrorDeclaracion as exc:
        raise error_api(422, "respuestas_invalidas", str(exc)) from exc


def _revision_anterior(
    sesion: Session, cooperativa_id: uuid.UUID, nombre: str, tipo: str
) -> DeclaracionProducto | None:
    """Sección 5.6, regla 4: una revisión del mismo nombre y tipo en la organización, de menos de 12 meses."""
    desde = datetime.combine(sumar_meses(hoy_lima(), -MESES_REVISION_COPIADA), time.min, LIMA)
    buscado = cuestionario.normalizar_nombre(nombre)
    candidatos = sesion.scalars(
        select(DeclaracionProducto)
        .join(DeclaracionProductor, DeclaracionProductor.id == DeclaracionProducto.declaracion_id)
        .where(
            DeclaracionProductor.cooperativa_id == cooperativa_id,
            DeclaracionProducto.tipo == tipo,
            DeclaracionProducto.revision != "sin_revisar",
            DeclaracionProducto.revisado_en >= desde,
        )
        .order_by(DeclaracionProducto.revisado_en.desc())
    )
    return next((c for c in candidatos if cuestionario.normalizar_nombre(c.nombre) == buscado), None)


def _guardar(
    contexto: Contexto, productor: Productor, respuestas: dict, origen: str, accion: str
) -> DeclaracionProductor:
    sesion = contexto.sesion
    cooperativa_id = contexto.cooperativa_id
    datos = calculados(sesion, productor, cooperativa_id)
    limpias = _validar(respuestas, datos)
    hoy = hoy_lima()
    anteriores = list(
        sesion.scalars(
            select(DeclaracionProductor).where(
                DeclaracionProductor.productor_id == productor.id,
                DeclaracionProductor.cooperativa_id == cooperativa_id,
                DeclaracionProductor.estado.in_(("vigente", "por_firmar")),
            )
        )
    )
    # Sección 5.2, regla 3: la vigente reemplaza a la vigente anterior y a la por firmar; una por firmar
    # reemplaza solo a la por firmar anterior.
    reemplazadas = [d for d in anteriores if origen == "productor" or d.estado == "por_firmar"]
    for d in reemplazadas:
        d.estado = "reemplazada"
    sesion.flush()
    declaracion = DeclaracionProductor(
        cooperativa_id=cooperativa_id,
        productor_id=productor.id,
        version_cuestionario=cuestionario.VERSION,
        version_texto=version_texto(),
        respuestas=limpias,
        contexto=datos,
        origen=origen,
        estado="vigente" if origen == "productor" else "por_firmar",
        registrada_por=contexto.usuario_id,
        registrada_en=ahora(),
        declarada_en=hoy if origen == "productor" else None,
        vigente_hasta=sumar_meses(hoy, vigencia_meses()) if origen == "productor" else None,
    )
    sesion.add(declaracion)
    sesion.flush()
    copiadas = []
    for p in limpias.get("productos", []):
        anterior = _revision_anterior(sesion, cooperativa_id, p["nombre"], p["tipo"])
        producto = DeclaracionProducto(declaracion_id=declaracion.id, nombre=p["nombre"], tipo=p["tipo"])
        if anterior is not None:
            producto.revision = anterior.revision
            producto.registro = anterior.registro
            producto.revisado_por = anterior.revisado_por
            producto.revisado_en = anterior.revisado_en
            producto.copiada_de = anterior.id
            copiadas.append(p["nombre"])
        sesion.add(producto)
    registrar_auditoria(
        contexto,
        accion,
        "declaracion_productor",
        declaracion.id,
        {
            "productor_id": productor.id,
            "origen": origen,
            "version_cuestionario": cuestionario.VERSION,
            "respuestas": limpias,
            "reemplaza": [d.id for d in reemplazadas],
            "revisiones_copiadas": copiadas,
        },
    )
    sesion.flush()
    return declaracion


def registrar(contexto: Contexto, productor_id: uuid.UUID, respuestas: dict) -> DeclaracionProductor:
    """El personal registra las respuestas en nombre del productor. Queda por firmar (sección 5.1)."""
    productor = productor_afiliado(contexto, productor_id)
    declaracion = _guardar(contexto, productor, respuestas, "personal", "declaracion_productor.registrar")
    contexto.sesion.commit()
    return declaracion


def declarar(contexto: Contexto, respuestas: dict, declaro: bool) -> DeclaracionProductor:
    """El productor responde y toca "Declaro": vale al instante y reemplaza a la por firmar."""
    if not declaro:
        raise error_api(422, "falta_declaro", 'Para que tu declaración valga, toca "Declaro".')
    productor = productor_afiliado(contexto, contexto.productor_id)
    declaracion = _guardar(contexto, productor, respuestas, "productor", "declaracion_productor.declarar")
    contexto.sesion.commit()
    return declaracion


def cargar_hoja_firmada(
    contexto: Contexto,
    storage,
    productor_id: uuid.UUID,
    declaracion_id: uuid.UUID,
    archivo,
    fecha_firma: date,
) -> DeclaracionProductor:
    """La hoja firmada hace vigente la declaración por firmar (sección 5.1, regla 3, y 5.2, regla 3)."""
    from app.services import documentos  # evita importación circular

    sesion = contexto.sesion
    _, declaracion = declaracion_visible(contexto, productor_id, declaracion_id)
    if declaracion.estado != "por_firmar":
        raise error_api(400, "declaracion_no_por_firmar", "Esta declaración ya no espera su hoja firmada.")
    if fecha_firma > hoy_lima():
        raise error_api(422, "fecha_futura", "La fecha de firma no puede ser futura.")
    if fecha_firma < dia_lima(declaracion.registrada_en):
        raise error_api(
            422,
            "fecha_anterior_al_registro",
            "La fecha de firma no puede ser anterior al día en que se registraron las respuestas.",
        )
    documento, ruta = documentos.guardar(
        contexto,
        storage,
        entidad="declaracion_productor",
        entidad_id=declaracion.id,
        tipo="hoja_declaracion_productor",
        archivo=archivo,
    )
    try:
        anteriores = list(
            sesion.scalars(
                select(DeclaracionProductor).where(
                    DeclaracionProductor.productor_id == declaracion.productor_id,
                    DeclaracionProductor.cooperativa_id == declaracion.cooperativa_id,
                    DeclaracionProductor.estado == "vigente",
                )
            )
        )
        for d in anteriores:
            d.estado = "reemplazada"
        sesion.flush()
        declaracion.estado = "vigente"
        declaracion.declarada_en = fecha_firma
        declaracion.vigente_hasta = sumar_meses(fecha_firma, vigencia_meses())
        registrar_auditoria(
            contexto,
            "declaracion_productor.hoja_firmada",
            "declaracion_productor",
            declaracion.id,
            {
                "productor_id": declaracion.productor_id,
                "documento_id": documento.id,
                "fecha_firma": fecha_firma,
                "reemplaza": [d.id for d in anteriores],
            },
        )
        sesion.commit()
    except Exception:
        sesion.rollback()
        documentos.descartar(storage, ruta)
        raise
    return declaracion


def _declaracion_actual(contexto: Contexto, productor_id: uuid.UUID, declaracion_id: uuid.UUID | None):
    """La declaración vigente o por firmar a la que se cargan papeles o se revisan productos."""
    if declaracion_id is None:
        estado = estado_de(contexto.sesion, productor_id, contexto.cooperativa_id)
        declaracion = estado.vigente if estado.valida else estado.por_firmar
        if declaracion is None:
            raise error_api(400, "sin_declaracion", "Primero responde tu declaración anual.")
        return declaracion
    _, declaracion = declaracion_visible(contexto, productor_id, declaracion_id)
    if declaracion.estado == "reemplazada":
        raise error_api(400, "declaracion_reemplazada", "Esta declaración ya fue reemplazada por otra.")
    return declaracion


def cargar_papel(
    contexto: Contexto,
    storage,
    productor_id: uuid.UUID,
    declaracion_id: uuid.UUID | None,
    tipo: str,
    archivo,
) -> Documento:
    """Sección 3.3: la relación de trabajadores o la declaración de renta, solo si una respuesta la pide."""
    from app.services import documentos  # evita importación circular

    if contexto.rol == "productor":
        productor_afiliado(contexto, productor_id)
    declaracion = _declaracion_actual(contexto, productor_id, declaracion_id)
    r = declaracion.respuestas
    if tipo == "relacion_trabajadores" and r.get("quien_trabaja") != "permanentes":
        raise error_api(
            400, "papel_no_pedido", "La relación de trabajadores se pide solo con trabajadores todo el año."
        )
    if tipo == "declaracion_renta" and r.get("ventas_superan_75_uit") == "no":
        raise error_api(
            400, "papel_no_pedido", "La declaración de renta se pide solo con ventas de más de 75 UIT."
        )
    return documentos.cargar(
        contexto,
        storage,
        entidad="declaracion_productor",
        entidad_id=declaracion.id,
        tipo=tipo,
        archivo=archivo,
    )


def revisar_producto(
    contexto: Contexto,
    productor_id: uuid.UUID,
    declaracion_id: uuid.UUID,
    producto_id: uuid.UUID,
    revision: str,
    registro: str | None,
) -> DeclaracionProducto:
    """Sección 5.6: el personal busca el producto en SENASA y marca si figura. Se puede cambiar."""
    declaracion = _declaracion_actual(contexto, productor_id, declaracion_id)
    producto = contexto.sesion.get(DeclaracionProducto, producto_id)
    if producto is None or producto.declaracion_id != declaracion.id:
        raise no_encontrado("El producto no existe.")
    antes = {"revision": producto.revision, "registro": producto.registro, "copiada_de": producto.copiada_de}
    producto.revision = revision
    producto.registro = registro if revision == "figura" else None
    producto.revisado_por = contexto.usuario_id
    producto.revisado_en = ahora()
    producto.copiada_de = None
    registrar_auditoria(
        contexto,
        "declaracion_productor.revisar_producto",
        "declaracion_producto",
        producto.id,
        {
            "declaracion_id": declaracion.id,
            "nombre": producto.nombre,
            "antes": antes,
            "despues": {"revision": producto.revision, "registro": producto.registro},
        },
    )
    contexto.sesion.commit()
    return producto


def escribir_seguimiento(
    contexto: Contexto, productor_id: uuid.UUID, declaracion_id: uuid.UUID, nota: str
) -> DeclaracionProductor:
    """Sección 5.7: lo que la organización hizo ante una señal. Solo el administrador; se puede reemplazar."""
    _, declaracion = declaracion_visible(contexto, productor_id, declaracion_id)
    if declaracion.estado != "vigente":
        raise error_api(
            400, "declaracion_no_vigente", "La nota de seguimiento va sobre la declaración vigente."
        )
    antes = declaracion.seguimiento_nota
    declaracion.seguimiento_nota = nota
    declaracion.seguimiento_por = contexto.usuario_id
    declaracion.seguimiento_en = ahora()
    registrar_auditoria(
        contexto,
        "declaracion_productor.seguimiento",
        "declaracion_productor",
        declaracion.id,
        {"productor_id": declaracion.productor_id, "antes": antes, "despues": nota},
    )
    contexto.sesion.commit()
    return declaracion


# ---------- Lectura ----------


def respuestas_salida(declaracion: DeclaracionProductor, personal: bool = True) -> list[dict]:
    """Cada pregunta mostrada con su respuesta, en el orden del cuestionario."""
    salida = []
    for codigo, valor in declaracion.respuestas.items():
        pregunta = cuestionario.POR_CODIGO.get(codigo)
        if pregunta is None:
            continue
        salida.append(
            {
                "codigo": codigo,
                "pregunta": pregunta.texto_personal if personal else pregunta.texto,
                "valor": valor,
                "etiqueta": pregunta.etiqueta(valor),
            }
        )
    orden = {c: i for i, c in enumerate(cuestionario.CODIGOS)}
    return sorted(salida, key=lambda x: orden[x["codigo"]])


def estado_guardado(declaracion: DeclaracionProductor, hoy: date | None = None) -> str:
    if declaracion.estado == "vigente" and declaracion.vigente_hasta < (hoy or hoy_lima()):
        return "vencida"
    return declaracion.estado


def _nombres(sesion: Session, ids: set) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    perfiles = sesion.scalars(select(Perfil).where(Perfil.id.in_(ids)))
    return {p.id: f"{p.nombres} {p.apellidos}".strip() for p in perfiles}


def requisitos_salida(estado: EstadoProductor) -> list[dict]:
    salida = []
    for r in estado.requisitos.values():
        req = r.requisito
        salida.append(
            {
                "codigo": r.codigo,
                "nombre": req.nombre,
                "referencias": list(req.referencias),
                "nivel": req.nivel,
                "diligencia": req.diligencia,
                "nivel_texto": req.nivel_texto,
                "estado": r.estado,
                "etiqueta": catalogo.ETIQUETAS_ESTADO[r.estado],
                "motivo": r.motivo,
                "siguiente": r.siguiente,
                "hechos": [{"pregunta": h.pregunta, "texto": h.texto, "valor": h.etiqueta} for h in r.hechos]
                + [
                    {
                        "pregunta": "productos",
                        "texto": "Producto que no figura en el registro de SENASA consultado",
                        "valor": f"{p.nombre} ({p.revisado_en.astimezone(LIMA):%d/%m/%Y})",
                    }
                    for p in r.no_figuran
                ],
                "falta": [TEXTO_FALTA[f] for f in r.falta],
                "nivel_verificacion": r.nivel_verificacion,
            }
        )
    # Los que no aplican van al final (sección 10).
    return sorted(salida, key=lambda x: x["estado"] == "no_aplica")


def sugerencias(sesion: Session, cooperativa_id: uuid.UUID) -> list[str]:
    """Sección 5.6, regla 5: los nombres ya declarados en la organización. De las grafías de un mismo
    nombre (sin tildes, mayúsculas ni espacios de más) se sugiere la que se declaró primero."""
    primera = func.min(DeclaracionProductor.registrada_en)
    nombres = sesion.scalars(
        select(DeclaracionProducto.nombre)
        .join(DeclaracionProductor, DeclaracionProductor.id == DeclaracionProducto.declaracion_id)
        .where(DeclaracionProductor.cooperativa_id == cooperativa_id)
        .group_by(DeclaracionProducto.nombre)
        .order_by(primera, DeclaracionProducto.nombre)
        .limit(500)
    )
    vistos: dict[str, str] = {}
    for n in nombres:
        vistos.setdefault(cuestionario.normalizar_nombre(n), n)
    return sorted(vistos.values(), key=cuestionario.normalizar_nombre)


def salida(sesion: Session, productor_id: uuid.UUID, cooperativa_id: uuid.UUID, *, personal: bool = True):
    """La declaración del productor ante la organización. El productor no ve la nota de seguimiento."""
    from app.schemas.declaracion import DeclaracionProductorSalida
    from app.services import documentos as servicio_documentos
    from app.services.productores import documento_salida  # evita importación circular

    estado = estado_de(sesion, productor_id, cooperativa_id)
    historial = list(
        sesion.scalars(
            select(DeclaracionProductor)
            .where(
                DeclaracionProductor.productor_id == productor_id,
                DeclaracionProductor.cooperativa_id == cooperativa_id,
            )
            .order_by(DeclaracionProductor.registrada_en.desc())
        )
    )
    detalladas = [d for d in (estado.vigente, estado.por_firmar) if d is not None]
    productos = {
        d.id: list(
            sesion.scalars(
                select(DeclaracionProducto)
                .where(DeclaracionProducto.declaracion_id == d.id)
                .order_by(DeclaracionProducto.nombre)
            )
        )
        for d in detalladas
    }
    nombres = _nombres(
        sesion,
        {d.registrada_por for d in historial}
        | {d.seguimiento_por for d in detalladas}
        | {p.revisado_por for ps in productos.values() for p in ps},
    )

    def detalle(d: DeclaracionProductor | None) -> dict | None:
        if d is None:
            return None
        docs = [
            documento_salida(doc, n)
            for doc, n in servicio_documentos.documentos_de(sesion, "declaracion_productor", d.id)
        ]
        seguimiento = (
            {"nota": d.seguimiento_nota, "por_nombre": nombres.get(d.seguimiento_por), "en": d.seguimiento_en}
            if personal and d.seguimiento_nota
            else None
        )
        return {
            **resumen(d),
            "version_cuestionario": d.version_cuestionario,
            "version_texto": d.version_texto,
            "respuestas": respuestas_salida(d, personal),
            "contexto": d.contexto,
            "productos": [
                {
                    "id": p.id,
                    "nombre": p.nombre,
                    "tipo": p.tipo,
                    "revision": p.revision,
                    "registro": p.registro,
                    "revisado_por_nombre": nombres.get(p.revisado_por),
                    "revisado_en": p.revisado_en,
                    "copiada": p.copiada_de is not None,
                }
                for p in productos[d.id]
            ],
            "documentos": docs,
            "seguimiento": seguimiento,
        }

    def resumen(d: DeclaracionProductor) -> dict:
        return {
            "id": d.id,
            "origen": d.origen,
            "estado": estado_guardado(d, estado.hoy),
            "registrada_por_nombre": nombres.get(d.registrada_por),
            "registrada_en": d.registrada_en,
            "declarada_en": d.declarada_en,
            "vigente_hasta": d.vigente_hasta,
        }

    productor = estado.productor
    return DeclaracionProductorSalida(
        estado=estado.estado,
        vigente=detalle(estado.vigente),
        por_firmar=detalle(estado.por_firmar),
        historial=[resumen(d) for d in historial],
        calculados=calculados(sesion, productor, cooperativa_id),
        requisitos=requisitos_salida(estado),
        aviso_area=estado.aviso_area,
        pendientes=estado.pendientes,
        falta=estado.falta,
        sugerencias_productos=sugerencias(sesion, cooperativa_id),
    )


def cuestionario_salida(sesion: Session):
    from app.pdf.declaracion_tenencia import textos
    from app.schemas.declaracion import CuestionarioSalida

    anexo = textos()["declaracion_productor"]
    return CuestionarioSalida(
        version=cuestionario.VERSION,
        version_texto=anexo["version"],
        preguntas=[
            {
                "codigo": p.codigo,
                "texto": p.texto,
                "texto_personal": p.texto_personal,
                "ayuda": p.ayuda,
                "ayuda_personal": p.ayuda_personal or p.ayuda,
                "tipo": p.tipo,
                "valores": [{"valor": v, "etiqueta": e} for v, e in p.valores],
                "minimo": float(p.minimo) if p.minimo is not None else None,
                "maximo": float(p.maximo) if p.maximo is not None else None,
                "referencias": list(p.referencias),
                "cuando": list(p.cuando),
            }
            for p in cuestionario.PREGUNTAS
        ],
        tipos_producto=[{"valor": v, "etiqueta": e} for v, e in cuestionario.ETIQUETAS_TIPO_PRODUCTO.items()],
        maximo_productos=cuestionario.MAXIMO_PRODUCTOS,
        area_agricultura_familiar_ha=float(cuestionario.AREA_AGRICULTURA_FAMILIAR_HA),
        **configuracion_plataforma.referencias(sesion),
        consultas_senasa=[{"valor": url, "etiqueta": nombre} for url, nombre in CONSULTAS_SENASA],
        anexo=[
            {"tipo": b["tipo"], "texto": b["texto"], "en_pantalla": bool(b.get("en_pantalla"))}
            for b in anexo["bloques"]
        ],
    )


# ---------- Hoja para firmar y copia (sección 5.4) ----------


def hoja(sesion: Session, declaracion: DeclaracionProductor) -> tuple[bytes, str]:
    """La hoja para firmar de una declaración por firmar; de una ya declarada, su copia."""
    from app.pdf import declaracion_productor as pdf

    productor = sesion.get(Productor, declaracion.productor_id)
    cooperativa = sesion.get(Cooperativa, declaracion.cooperativa_id)
    ctx = declaracion.contexto
    codigos = ctx.get("parcelas_codigos") or []
    datos = {
        "productor": f"{productor.nombres} {productor.apellidos}",
        "dni": productor.dni,
        "direccion": productor.direccion_postal,
        "organizacion": cooperativa.razon_social,
        "ruc": cooperativa.ruc,
        "numero": ctx.get("parcelas_activas"),
        "codigos": ", ".join(codigos) if codigos else None,
        "area": f"{Decimal(str(ctx.get('area_total_ha') or 0)):.2f}".replace(".", ","),
    }
    copia = None
    if declaracion.declarada_en is not None:
        registro = _nombres(sesion, {declaracion.registrada_por}).get(declaracion.registrada_por)
        if declaracion.origen == "productor":
            quien = f"La declaró {datos['productor']} desde su cuenta el {declaracion.declarada_en:%d/%m/%Y}."
        else:
            quien = (
                f"La registró {registro or 'el personal de la organización'} el "
                f"{dia_lima(declaracion.registrada_en):%d/%m/%Y} y el productor la firmó el "
                f"{declaracion.declarada_en:%d/%m/%Y}."
            )
        copia = f"Copia de la declaración. {quien} Vale hasta el {declaracion.vigente_hasta:%d/%m/%Y}."
    contenido = pdf.generar(
        datos,
        respuestas_salida(declaracion),
        copia=copia,
        version_cuestionario=declaracion.version_cuestionario,
        es_demo=bool(cooperativa.es_demo or productor.es_demo),
    )
    sufijo = "copia" if copia else "para-firmar"
    return contenido, f"declaracion-anual-{productor.dni}-{sufijo}.pdf"


# ---------- Bloque del DOP y del DEX (sección 11) ----------


def bloque(sesion: Session, productor_id: uuid.UUID, cooperativa_id: uuid.UUID) -> dict[str, Any]:
    """Lo que se sella en el DOP (dentro del productor) y en el DEX (con el estado de ese día). Sin la nota de
    seguimiento: el DOP lo ve el productor."""
    estado = estado_de(sesion, productor_id, cooperativa_id)
    d = estado.vigente if estado.valida else None
    productos = estado.productos if d else []
    return {
        "estado": estado.estado,
        "declarada_en": d.declarada_en.isoformat() if d else None,
        "origen": d.origen if d else None,
        "vigente_hasta": d.vigente_hasta.isoformat() if d else None,
        "version_cuestionario": d.version_cuestionario if d else None,
        "version_texto": d.version_texto if d else None,
        "contexto": d.contexto if d else None,
        "respuestas": respuestas_salida(d) if d else [],
        "productos": [
            {
                "nombre": p.nombre,
                "tipo": p.tipo,
                "revision": p.revision,
                "registro": p.registro,
                "revisado_en": p.revisado_en.isoformat() if p.revisado_en else None,
            }
            for p in productos
        ],
        "documentos": [
            {"tipo": doc.tipo, "nombre_original": doc.nombre_original, "sha256": doc.sha256}
            for doc in sorted(estado.documentos if d else [], key=lambda x: x.creado_en)
        ],
        "requisitos": [
            {
                "codigo": r["codigo"],
                "nombre": r["nombre"],
                "referencias": r["referencias"],
                "nivel": r["nivel"],
                "diligencia": r["diligencia"],
                "estado": r["estado"],
                "etiqueta": r["etiqueta"],
                "hechos": r["hechos"],
                "falta": r["falta"],
                "nivel_verificacion": r["nivel_verificacion"],
            }
            for r in requisitos_salida(estado)
        ],
    }

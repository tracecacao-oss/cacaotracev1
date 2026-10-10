"""Legalidad de la parcela por requisito (adenda 4).

El perfil legal son nueve datos (app/catalogos/perfil_legal.py): cinco los calcula el cruce con capas
oficiales y cuatro los declara una persona. De ese perfil sale qué requisitos aplican
(app/catalogos/requisitos_legales.py) y cada requisito queda en un estado, calculado al consultar con la
fecha del día. Solo bloquean la habilitación cuatro cosas (sección 8): el perfil incompleto, la tenencia sin
sustento, un permiso obligatorio sin sustento y una incidencia de tenencia abierta.

El sistema no concluye: ningún texto dice que una parcela "cumple" la legalidad. Dice qué requisitos le
aplican y con qué se sustentan.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.catalogos import documentos_legales, perfil_legal
from app.catalogos import requisitos_legales as catalogo
from app.config import get_settings
from app.contexto import Contexto
from app.errores import error_api, no_encontrado
from app.fechas import ahora, hoy_lima
from app.models import Documento, ExencionDocumento, Parcela, ParcelaIncidencia, ParcelaVariable, Perfil
from app.schemas.habilitacion import Requisito
from app.services import cruce
from app.services.auditoria import registrar_auditoria
from app.services.expediente import estado_documento, no_excluida

ORDEN_ESTADO = {"vigente": 0, "por_vencer": 1, "vencido": 2}
ORDEN_NIVEL = {"verificado_en_fuente": 0, "documentado": 1, "declarado": 2}
CORTE_LEY_31973 = date.fromisoformat(catalogo.CORTE_LEY_31973)


# ---------- Documentos ----------


def nivel_documento(documento: Documento) -> str:
    """Una declaración jurada es la palabra del productor: su nivel es declarado (sección 5.1)."""
    if documento.tipo == "declaracion_jurada_tenencia":
        return "declarado"
    return "verificado_en_fuente" if documento.cotejado_en else "documentado"


def sumar_meses(dia: date, meses: int) -> date:
    mes = dia.month - 1 + meses
    anio, mes = dia.year + mes // 12, mes % 12 + 1
    for d in (dia.day, 30, 29, 28):
        try:
            return date(anio, mes, d)
        except ValueError:
            continue
    raise ValueError("fecha inválida")


def vencimiento_declaracion(fecha_firma: date) -> date:
    """La declaración jurada de tenencia vence sola a los DECLARACION_VIGENCIA_MESES de su firma."""
    return sumar_meses(fecha_firma, get_settings().declaracion_vigencia_meses)


def _mejor(docs: list[Documento], hoy: date, aviso: int) -> Documento | None:
    """El sustento que cuenta: entre los vigentes o por vencer, el de mejor nivel; después, el de mejor estado
    y vencimiento más lejano."""
    utiles = [d for d in docs if estado_documento(d, hoy, aviso) != "vencido"]
    if not utiles:
        return None
    lejano = date.max
    return min(
        utiles,
        key=lambda d: (
            ORDEN_NIVEL[nivel_documento(d)],
            ORDEN_ESTADO[estado_documento(d, hoy, aviso)],
            -(d.fecha_vencimiento or lejano).toordinal(),
        ),
    )


# ---------- Perfil ----------


@dataclass
class ValorVariable:
    codigo: str
    cruce: ParcelaVariable | None = None
    declarado: ParcelaVariable | None = None

    @property
    def valor(self) -> str | None:
        """Entre un cruce y una declaración vigentes manda el más exigente (sección 4, regla 4)."""
        if self.codigo in perfil_legal.CRUZABLES:
            return perfil_legal.mas_exigente(
                self.codigo,
                self.cruce.valor if self.cruce else None,
                self.declarado.valor if self.declarado else None,
            )
        return self.declarado.valor if self.declarado else None

    @property
    def manda(self) -> ParcelaVariable | None:
        """La fila de la que sale el valor; con empate, el cruce."""
        if self.cruce is not None and self.cruce.valor == self.valor:
            return self.cruce
        return self.declarado

    @property
    def origen(self) -> str | None:
        fila = self.manda
        return fila.origen if fila else None

    @property
    def nivel(self) -> str | None:
        fila = self.manda
        if fila is None:
            return None
        return "verificado_en_fuente" if fila.origen == "cruce" else "declarado"

    @property
    def declarado_sin_cruce(self) -> bool:
        """Una variable con capa oficial que quedó declarada: el cruce falló, o una persona declaró `si`
        sobre un cruce `no` (hallazgo perfil_declarado_sin_cruce)."""
        return self.codigo in perfil_legal.CRUZABLES and self.origen == "declarado"

    @property
    def nota(self) -> str | None:
        return (self.declarado.detalle or {}).get("nota") if self.declarado else None


# ---------- Requisitos ----------


@dataclass
class EstadoRequisito:
    codigo: str
    estado: str  # sin_dato, no_aplica, sustentado, por_vencer, vencido o sin_sustento
    motivo: str  # por qué aplica, por qué no aplica o qué dato falta
    sustento: Documento | None = None
    nivel: str | None = None  # declarado, documentado o verificado_en_fuente
    nota: str | None = None  # cuando se sustenta con una nota
    por_excepcion: bool = False  # tierra forestal por la Ley N.º 31973 o la Ley N.º 31145
    aceptados: tuple[str, ...] = ()  # los tipos de documento que lo sustentan
    vencido: Documento | None = None  # con estado vencido: el sustento que venció último

    @property
    def requisito(self) -> catalogo.RequisitoLegal:
        return catalogo.POR_CODIGO[self.codigo]

    @property
    def cubierto(self) -> bool:
        return self.estado in ("no_aplica", "sustentado", "por_vencer")


def area_total(parcela: Parcela) -> Decimal | None:
    """En un polígono, el área calculada; en un punto, la declarada (sección 4, nota 5)."""
    return parcela.area_calculada_ha if parcela.tipo_geometria == "poligono" else parcela.area_declarada_ha


@dataclass
class Legalidad:
    parcela: Parcela
    perfil: dict[str, ValorVariable]
    documentos: list[Documento]  # legales vigentes (sin anular), también los anteriores
    incidencias: list[ParcelaIncidencia]
    exenciones: list[ExencionDocumento]  # historial: ya no cubren nada
    hoy: date
    aviso: int
    requisitos: dict[str, EstadoRequisito] = field(default_factory=dict)

    def __post_init__(self):
        self.requisitos = {c: self._evaluar(c) for c in catalogo.CODIGOS}

    # --- datos ---

    def valor(self, variable: str) -> str | None:
        return self.perfil[variable].valor

    def _docs(self, tipos) -> list[Documento]:
        return [d for d in self.documentos if d.tipo in tipos]

    def _vigentes(self, tipos) -> list[Documento]:
        return [d for d in self._docs(tipos) if estado_documento(d, self.hoy, self.aviso) != "vencido"]

    def _con_documento(self, codigo: str, aceptados: tuple[str, ...], motivo: str) -> EstadoRequisito:
        docs = self._docs(aceptados)
        mejor = _mejor(docs, self.hoy, self.aviso)
        if mejor is not None:
            return EstadoRequisito(
                codigo,
                "sustentado" if estado_documento(mejor, self.hoy, self.aviso) == "vigente" else "por_vencer",
                motivo,
                sustento=mejor,
                nivel=nivel_documento(mejor),
                aceptados=aceptados,
            )
        if docs:
            ultimo = max(docs, key=lambda d: d.fecha_vencimiento or date.min)
            return EstadoRequisito(codigo, "vencido", motivo, aceptados=aceptados, vencido=ultimo)
        return EstadoRequisito(codigo, "sin_sustento", motivo, aceptados=aceptados)

    def _con_nota(self, codigo: str, variable: str, motivo: str) -> EstadoRequisito:
        nota = self.perfil[variable].nota
        if nota:
            return EstadoRequisito(codigo, "sustentado", motivo, nivel="declarado", nota=nota)
        return EstadoRequisito(codigo, "sin_sustento", motivo)

    def _sin_dato(self, codigo: str, variable: str) -> EstadoRequisito:
        pregunta = perfil_legal.POR_CODIGO[variable].pregunta
        return EstadoRequisito(codigo, "sin_dato", f"Falta responder: {pregunta}")

    # --- estado de cada requisito ---

    def _evaluar(self, codigo: str) -> EstadoRequisito:
        return getattr(self, f"_{codigo}")()

    def _tenencia(self) -> EstadoRequisito:
        tipo = self.valor("tenencia_tipo")
        if tipo is None:
            return self._sin_dato("tenencia", "tenencia_tipo")
        etiqueta = perfil_legal.etiqueta("tenencia_tipo", tipo)
        return self._con_documento(
            "tenencia", catalogo.SUSTENTOS_TENENCIA[tipo], f"Siempre aplica. El productor es: {etiqueta}."
        )

    def _acuerdo_comunal(self) -> EstadoRequisito:
        comunal = self.valor("en_tierra_comunal")
        if comunal is None:
            return self._sin_dato("acuerdo_comunal", "en_tierra_comunal")
        if comunal == "no":
            return EstadoRequisito(
                "acuerdo_comunal", "no_aplica", "La parcela no está en tierra de una comunidad."
            )
        aceptados = ("constancia_comunal", "acta_comunal", "contrato_de_uso")
        # El orientador no exige documento formal al miembro de la comunidad.
        if self.valor("tenencia_tipo") == "comunal_miembro":
            aceptados += ("declaracion_jurada_tenencia",)
        return self._con_documento(
            "acuerdo_comunal", aceptados, "La parcela está en tierra de una comunidad."
        )

    def _area_protegida(self) -> EstadoRequisito:
        anp = self.valor("en_anp")
        if anp is None:
            return self._sin_dato("area_protegida", "en_anp")
        if anp != "dentro":
            motivo = (
                "La parcela está en la zona de amortiguamiento de un área protegida: no pide documento."
                if anp == "zona_de_amortiguamiento"
                else "La parcela no está en un área natural protegida."
            )
            return EstadoRequisito("area_protegida", "no_aplica", motivo)
        return self._con_documento(
            "area_protegida",
            ("acuerdo_conservacion",),
            "La parcela está dentro de un área natural protegida.",
        )

    def documentos_excepcion_forestal(self) -> list[Documento]:
        """Sección 5.2 y decisiones del 2026-10-09: un título o una constancia vigentes emitidos por la
        autoridad antes de que rigiera la Ley N.º 31973, o la constancia de saneamiento de la Ley
        N.º 31145."""
        con_fecha = [
            d
            for d in self._vigentes(catalogo.EXCEPCION_FORESTAL_CON_FECHA)
            if d.fecha_emision is not None
            and d.fecha_emision < CORTE_LEY_31973
            and (d.tipo != "titulo_no_inscrito" or d.clase == catalogo.CLASE_TITULO_QUE_VALE)
        ]
        return con_fecha + self._vigentes(catalogo.EXCEPCION_FORESTAL_SIN_FECHA)

    def _tierra_forestal(self) -> EstadoRequisito:
        forestal = self.valor("en_tierra_forestal")
        if forestal is None:
            return self._sin_dato("tierra_forestal", "en_tierra_forestal")
        if forestal == "no":
            return EstadoRequisito("tierra_forestal", "no_aplica", "La parcela no está en tierra forestal.")
        if forestal == "sin_zonificacion":
            return EstadoRequisito(
                "tierra_forestal",
                "no_aplica",
                "La capa de SERFOR no tiene zonificación forestal del departamento: no se sabe si es tierra "
                "forestal.",
            )
        motivo = "La parcela está en tierra de aptitud forestal o de protección."
        con_titulo = self._con_documento(
            "tierra_forestal", catalogo.POR_CODIGO["tierra_forestal"].sustentos, motivo
        )
        if con_titulo.cubierto:
            return con_titulo
        excepcion = _mejor(self.documentos_excepcion_forestal(), self.hoy, self.aviso)
        if excepcion is not None:
            return EstadoRequisito(
                "tierra_forestal",
                "sustentado"
                if estado_documento(excepcion, self.hoy, self.aviso) == "vigente"
                else "por_vencer",
                motivo + " Se sustenta por la excepción de la Ley N.º 31973.",
                sustento=excepcion,
                nivel=nivel_documento(excepcion),
                por_excepcion=True,
                aceptados=con_titulo.aceptados,
            )
        return con_titulo

    def _agua_de_riego(self) -> EstadoRequisito:
        riego = self.valor("usa_riego")
        if riego is None:
            return self._sin_dato("agua_de_riego", "usa_riego")
        if riego == "no":
            return EstadoRequisito("agua_de_riego", "no_aplica", "El cultivo depende solo de la lluvia.")
        return self._con_documento("agua_de_riego", ("licencia_agua",), "El cultivo se riega.")

    def _instrumento_ambiental(self) -> EstadoRequisito:
        area = area_total(self.parcela)
        texto = f"{Decimal(area):.2f}".replace(".", ",") if area is not None else "—"
        if area is None or area < catalogo.UMBRAL_INSTRUMENTO_HA:
            return EstadoRequisito(
                "instrumento_ambiental", "no_aplica", f"La parcela tiene {texto} ha: menos de 10 ha."
            )
        if area > catalogo.UMBRAL_INSTRUMENTO_MAYOR_HA:
            return self._con_documento(
                "instrumento_ambiental",
                ("instrumento_ambiental",),
                f"La parcela tiene {texto} ha: más de 50 ha piden DIA, EIA-sd, EIA-d o PAMA.",
            )
        return self._con_documento(
            "instrumento_ambiental",
            ("ficha_tecnica_ambiental", "instrumento_ambiental"),
            f"La parcela tiene {texto} ha: de 10 a 50 ha piden la Ficha Técnica Ambiental.",
        )

    def _faja_marginal(self) -> EstadoRequisito:
        agua = self.valor("junto_a_cuerpo_de_agua")
        if agua is None:
            return self._sin_dato("faja_marginal", "junto_a_cuerpo_de_agua")
        if agua == "no":
            return EstadoRequisito(
                "faja_marginal", "no_aplica", "La parcela no colinda con un río ni un lago."
            )
        return self._con_nota(
            "faja_marginal",
            "junto_a_cuerpo_de_agua",
            "La parcela colinda con un río, quebrada, lago o laguna.",
        )

    def _patrimonio_cultural(self) -> EstadoRequisito:
        patrimonio = self.valor("en_patrimonio_cultural")
        if patrimonio is None:
            return self._sin_dato("patrimonio_cultural", "en_patrimonio_cultural")
        if patrimonio == "no":
            return EstadoRequisito(
                "patrimonio_cultural",
                "no_aplica",
                "La parcela no se superpone con un sitio de patrimonio cultural.",
            )
        if self._vigentes(("cusaf",)):
            return EstadoRequisito(
                "patrimonio_cultural",
                "no_aplica",
                "Se superpone con un sitio de patrimonio cultural, pero tiene un CCUSAF vigente.",
            )
        return self._con_nota(
            "patrimonio_cultural",
            "en_patrimonio_cultural",
            "La parcela se superpone con un sitio arqueológico o de patrimonio cultural.",
        )

    # --- perfil y compuerta ---

    @property
    def pide_reserva(self) -> bool:
        """reserva_bosque_30 solo se pregunta cuando la tierra forestal se sustenta por la excepción."""
        return self.requisitos["tierra_forestal"].por_excepcion

    @property
    def faltan_variables(self) -> list[str]:
        codigos = list(perfil_legal.BASE) + (["reserva_bosque_30"] if self.pide_reserva else [])
        return [c for c in codigos if self.valor(c) is None]

    @property
    def perfil_completo(self) -> bool:
        return not self.faltan_variables

    @property
    def tenencia_sustentada(self) -> bool:
        return self.requisitos["tenencia"].estado in ("sustentado", "por_vencer")

    @property
    def permisos_sin_cubrir(self) -> list[str]:
        return [c for c in catalogo.PERMISOS_OBLIGATORIOS if not self.requisitos[c].cubierto]

    @property
    def incidencias_tenencia_abiertas(self) -> list[ParcelaIncidencia]:
        return [i for i in self.incidencias if i.tipo == "tenencia" and i.estado == "abierta"]

    @property
    def tenencia_sin_documento_formal(self) -> bool:
        s = self.requisitos["tenencia"].sustento
        return s is not None and s.tipo == "declaracion_jurada_tenencia"

    @property
    def tenencia_solo_posesion(self) -> bool:
        s = self.requisitos["tenencia"].sustento
        return s is not None and s.tipo == "constancia_posesion"

    def compuerta(self) -> list[Requisito]:
        """Los cuatro requisitos que reemplazan a expediente_completo (sección 8)."""
        nombres = [perfil_legal.POR_CODIGO[c].pregunta for c in self.faltan_variables]
        permisos = [catalogo.POR_CODIGO[c].nombre.lower() for c in self.permisos_sin_cubrir]
        abiertas = len(self.incidencias_tenencia_abiertas)
        tenencia = self.requisitos["tenencia"]
        return [
            Requisito(
                codigo="perfil_legal_completo",
                cumple=self.perfil_completo,
                detalle="El perfil legal está completo."
                if self.perfil_completo
                else f"Falta en el perfil legal: {' '.join(nombres)}",
            ),
            Requisito(
                codigo="tenencia_sustentada",
                cumple=self.tenencia_sustentada,
                detalle="La tenencia tiene un sustento vigente."
                if self.tenencia_sustentada
                else "Falta el dato del derecho del productor sobre la tierra."
                if tenencia.estado == "sin_dato"
                else "El sustento de la tenencia está vencido."
                if tenencia.estado == "vencido"
                else "La tenencia no tiene un sustento.",
            ),
            Requisito(
                codigo="permisos_obligatorios",
                cumple=not self.permisos_sin_cubrir,
                detalle="Los permisos obligatorios no aplican o tienen sustento."
                if not self.permisos_sin_cubrir
                else f"Falta el sustento de: {', '.join(permisos)}.",
            ),
            Requisito(
                codigo="sin_conflicto_de_tenencia",
                cumple=abiertas == 0,
                detalle="No hay incidencias de tenencia abiertas."
                if abiertas == 0
                else "Hay una incidencia de tenencia abierta."
                if abiertas == 1
                else f"Hay {abiertas} incidencias de tenencia abiertas.",
            ),
        ]

    def alertas(self) -> list[str]:
        alertas = []
        estados = {r.estado for r in self.requisitos.values()}
        if self.tenencia_sin_documento_formal:
            alertas.append("tenencia_sin_documento_formal")
        if self.tenencia_solo_posesion:
            alertas.append("tenencia_solo_posesion")
        if self.requisitos["tierra_forestal"].por_excepcion:
            alertas.append("tierra_forestal_por_excepcion")
        if self.valor("en_tierra_forestal") == "sin_zonificacion":
            alertas.append("zonificacion_forestal_desconocida")
        if self.valor("en_anp") == "zona_de_amortiguamiento":
            alertas.append("en_zona_de_amortiguamiento")
        if any(
            r.estado in ("sin_sustento", "vencido") and not r.requisito.bloquea
            for r in self.requisitos.values()
        ):
            alertas.append("requisito_sin_sustento")
        if any(i.estado == "abierta" for i in self.incidencias):
            alertas.append("incidencia_abierta")
        if "por_vencer" in estados:
            alertas.append("documento_por_vencer")
        if "vencido" in estados:
            alertas.append("documento_vencido")
        return alertas


def legalidades(
    sesion: Session, parcelas: list[Parcela], hoy: date | None = None
) -> dict[uuid.UUID, Legalidad]:
    """La legalidad de varias parcelas con cuatro consultas."""
    hoy = hoy or hoy_lima()
    aviso = get_settings().aviso_vencimiento_dias
    ids = [p.id for p in parcelas]
    if not ids:
        return {}
    perfiles = {pid: {c: ValorVariable(c) for c in perfil_legal.CODIGOS} for pid in ids}
    for fila in sesion.scalars(
        select(ParcelaVariable).where(ParcelaVariable.parcela_id.in_(ids), ParcelaVariable.vigente)
    ):
        valor = perfiles[fila.parcela_id][fila.variable]
        if fila.origen == "cruce":
            valor.cruce = fila
        else:
            valor.declarado = fila
    docs: dict[uuid.UUID, list[Documento]] = {pid: [] for pid in ids}
    for d in sesion.scalars(
        select(Documento).where(
            Documento.entidad == "parcela",
            Documento.entidad_id.in_(ids),
            Documento.tipo.in_(documentos_legales.TODOS),
            Documento.anulado_en.is_(None),
        )
    ):
        docs[d.entidad_id].append(d)
    incidencias: dict[uuid.UUID, list[ParcelaIncidencia]] = {pid: [] for pid in ids}
    for i in sesion.scalars(
        select(ParcelaIncidencia)
        .where(ParcelaIncidencia.parcela_id.in_(ids))
        .order_by(ParcelaIncidencia.registrada_en.desc())
    ):
        incidencias[i.parcela_id].append(i)
    exenciones: dict[uuid.UUID, list[ExencionDocumento]] = {pid: [] for pid in ids}
    for e in sesion.scalars(select(ExencionDocumento).where(ExencionDocumento.parcela_id.in_(ids))):
        exenciones[e.parcela_id].append(e)
    return {
        p.id: Legalidad(p, perfiles[p.id], docs[p.id], incidencias[p.id], exenciones[p.id], hoy, aviso)
        for p in parcelas
    }


def legalidad(sesion: Session, parcela: Parcela) -> Legalidad:
    return legalidades(sesion, [parcela])[parcela.id]


def sustentos_por_vencer(
    sesion: Session, parcelas: list[Parcela]
) -> list[tuple[Parcela, EstadoRequisito, Documento]]:
    """Requisitos con su sustento por vencer o vencido, ordenados por fecha de vencimiento."""
    resultado, vistos = [], set()
    por_id = {p.id: p for p in parcelas}
    for pid, leg in legalidades(sesion, parcelas).items():
        for r in leg.requisitos.values():
            documento = (
                r.sustento if r.estado == "por_vencer" else r.vencido if r.estado == "vencido" else None
            )
            # Un mismo documento puede sustentar dos requisitos (un CCUSAF, la tenencia y la tierra forestal).
            if documento is None or documento.fecha_vencimiento is None or documento.id in vistos:
                continue
            vistos.add(documento.id)
            resultado.append((por_id[pid], r, documento))
    return sorted(resultado, key=lambda x: x[2].fecha_vencimiento)


# ---------- Escritura ----------


def _reevaluar(sesion: Session, parcela: Parcela) -> None:
    """La compuerta se evalúa otra vez: una parcela habilitada que dejó de cumplir pasa a observada."""
    from app.services import habilitacion  # evita importación circular

    habilitacion.evaluar(sesion, [parcela])


def _validar_valor(variable: str, valor: str) -> str:
    v = perfil_legal.POR_CODIGO.get(variable)
    if v is None:
        raise error_api(422, "variable_invalida", "Esa variable no existe en el perfil legal.")
    valor = (valor or "").strip()
    if variable == "anio_instalacion_cultivo":
        if not (valor.isdigit() and len(valor) == 4 and 1900 <= int(valor) <= hoy_lima().year):
            raise error_api(
                422, "anio_invalido", f"Escribe un año de 4 dígitos entre 1900 y {hoy_lima().year}."
            )
        return valor
    if valor not in v.valores:
        raise error_api(422, "valor_invalido", f"«{valor}» no es una respuesta válida para esa pregunta.")
    return valor


def _detalle_declarado(variable: str, detalle: dict | None) -> dict:
    """Solo los datos adicionales que declara una persona; el resto lo trae la capa."""
    detalle = dict(detalle or {})
    limpio = {}
    if variable == "en_tierra_comunal":
        if detalle.get("comunidad_nombre"):
            limpio["comunidad_nombre"] = str(detalle["comunidad_nombre"]).strip()[:200]
        if detalle.get("comunidad_tipo"):
            if detalle["comunidad_tipo"] not in perfil_legal.TIPOS_COMUNIDAD:
                raise error_api(422, "tipo_comunidad_invalido", "El tipo de comunidad es campesina o nativa.")
            limpio["comunidad_tipo"] = detalle["comunidad_tipo"]
        if detalle.get("inscrita"):
            if detalle["inscrita"] not in perfil_legal.COMUNIDAD_INSCRITA:
                raise error_api(
                    422, "inscrita_invalida", "Responde si la comunidad está inscrita: sí, no o no se sabe."
                )
            limpio["inscrita"] = detalle["inscrita"]
    if variable == "en_anp" and detalle.get("area_nombre"):
        limpio["area_nombre"] = str(detalle["area_nombre"]).strip()[:200]
    return limpio


def declarar(
    contexto: Contexto,
    parcela: Parcela,
    variable: str,
    valor: str,
    *,
    detalle: dict | None = None,
    nota: str | None = None,
) -> ParcelaVariable:
    """Una persona responde una pregunta del perfil (sección 4). Guarda una fila nueva y conserva la
    anterior."""
    no_excluida(parcela)
    valor = _validar_valor(variable, valor)
    actual = legalidad(contexto.sesion, parcela)
    if variable == "reserva_bosque_30" and not actual.pide_reserva:
        raise error_api(
            422,
            "reserva_no_aplica",
            "La reserva de 30 % de bosque solo se pregunta cuando la tierra forestal se sustenta por la "
            "excepción de la Ley N.º 31973.",
        )
    cruce = actual.perfil[variable].cruce
    nota = (nota or "").strip() or None
    if cruce is not None and variable in perfil_legal.CRUZABLES:
        orden = perfil_legal.POR_CODIGO[variable].exigencia
        if orden.index(valor) < orden.index(cruce.valor):
            capa = cruce.fuente or "la capa oficial"
            raise error_api(
                422,
                "valor_bajo_el_cruce",
                f"El cruce con {capa} dice «{perfil_legal.etiqueta(variable, cruce.valor)}». No se puede "
                "declarar un valor menos exigente: si crees que el mapa se equivoca, registra una incidencia "
                "de tipo «otra».",
            )
        if valor != cruce.valor and not nota:
            raise error_api(
                422,
                "nota_requerida",
                "El cruce con la capa oficial dice otra cosa: explica en una nota por qué declaras este "
                "valor.",
            )
    datos = _detalle_declarado(variable, detalle)
    if variable in VARIABLE_DE_NOTA.values() and valor == "si" and actual.perfil[variable].nota and not nota:
        # Una declaración nueva sin nota conserva la nota con que se sustentó el requisito.
        nota = actual.perfil[variable].nota
    if nota:
        datos["nota"] = nota[:4000]
    contexto.sesion.execute(
        update(ParcelaVariable)
        .where(
            ParcelaVariable.parcela_id == parcela.id,
            ParcelaVariable.variable == variable,
            ParcelaVariable.origen == "declarado",
            ParcelaVariable.vigente,
        )
        .values(vigente=False)
    )
    fila = ParcelaVariable(
        parcela_id=parcela.id,
        variable=variable,
        valor=valor,
        detalle=datos or None,
        origen="declarado",
        registrada_por=contexto.usuario_id,
        registrada_en=ahora(),
    )
    contexto.sesion.add(fila)
    contexto.sesion.flush()
    registrar_auditoria(
        contexto,
        "parcela.perfil_declarar",
        "parcela",
        parcela.id,
        {"variable": variable, "valor": valor, "detalle": datos or None},
    )
    contexto.sesion.commit()
    _reevaluar(contexto.sesion, parcela)
    return fila


VARIABLE_DE_NOTA = {
    "faja_marginal": "junto_a_cuerpo_de_agua",
    "patrimonio_cultural": "en_patrimonio_cultural",
}


def registrar_nota(contexto: Contexto, parcela: Parcela, requisito: str, nota: str) -> ParcelaVariable:
    """Los requisitos sin documento (faja marginal y patrimonio cultural) se sustentan con una nota: se guarda
    como una declaración del mismo valor vigente, con la nota en su detalle."""
    variable = VARIABLE_DE_NOTA.get(requisito)
    if variable is None:
        raise error_api(422, "requisito_sin_nota", "Ese requisito no se sustenta con una nota.")
    actual = legalidad(contexto.sesion, parcela)
    if actual.requisitos[requisito].estado in ("sin_dato", "no_aplica"):
        raise error_api(400, "requisito_no_aplica", "Ese requisito no aplica a la parcela.")
    detalle = dict(
        (actual.perfil[variable].declarado.detalle or {}) if actual.perfil[variable].declarado else {}
    )
    detalle.pop("nota", None)
    return declarar(contexto, parcela, variable, "si", detalle=detalle, nota=nota)


def registrar_cruce(
    sesion: Session, parcela: Parcela, variable: str, valor: str, detalle: dict, fuente: str
) -> ParcelaVariable:
    """El resultado del cruce con una capa oficial (sección 10). No confirma."""
    sesion.execute(
        update(ParcelaVariable)
        .where(
            ParcelaVariable.parcela_id == parcela.id,
            ParcelaVariable.variable == variable,
            ParcelaVariable.origen == "cruce",
            ParcelaVariable.vigente,
        )
        .values(vigente=False)
    )
    fila = ParcelaVariable(
        parcela_id=parcela.id,
        variable=variable,
        valor=valor,
        detalle=detalle,
        origen="cruce",
        fuente=fuente,
        registrada_en=ahora(),
    )
    sesion.add(fila)
    sesion.flush()
    return fila


def volver_a_cruzar(contexto: Contexto, parcela: Parcela) -> None:
    """El botón "Volver a cruzar" (sección 10, regla 3)."""
    no_excluida(parcela)
    if parcela.estado != "activa":
        raise error_api(400, "parcela_inactiva", "La parcela está inactiva.")
    cruce.solicitar(contexto.sesion, parcela)
    registrar_auditoria(contexto, "parcela.cruce_solicitar", "parcela", parcela.id, {})
    contexto.sesion.commit()


# ---------- Incidencias ----------


def registrar_incidencia(
    contexto: Contexto, parcela: Parcela, tipo: str, descripcion: str, fuente: str
) -> ParcelaIncidencia:
    no_excluida(parcela)
    incidencia = ParcelaIncidencia(
        parcela_id=parcela.id,
        tipo=tipo,
        descripcion=descripcion.strip(),
        fuente=fuente.strip(),
        registrada_por=contexto.usuario_id,
        registrada_en=ahora(),
    )
    contexto.sesion.add(incidencia)
    contexto.sesion.flush()
    registrar_auditoria(
        contexto,
        "parcela.incidencia_registrar",
        "parcela",
        parcela.id,
        {"incidencia_id": incidencia.id, "tipo": tipo, "descripcion": descripcion, "fuente": fuente},
    )
    contexto.sesion.commit()
    _reevaluar(contexto.sesion, parcela)
    return incidencia


def incidencia_visible(contexto: Contexto, incidencia_id: uuid.UUID) -> tuple[ParcelaIncidencia, Parcela]:
    from app.services.parcelas import parcela_visible  # evita importación circular

    incidencia = contexto.sesion.get(ParcelaIncidencia, incidencia_id)
    if incidencia is None:
        raise no_encontrado("La incidencia no existe.")
    return incidencia, parcela_visible(contexto, incidencia.parcela_id)


def cerrar_incidencia(contexto: Contexto, incidencia_id: uuid.UUID, nota: str) -> ParcelaIncidencia:
    incidencia, parcela = incidencia_visible(contexto, incidencia_id)
    if incidencia.estado == "cerrada":
        raise error_api(400, "incidencia_cerrada", "La incidencia ya estaba cerrada.")
    incidencia.estado = "cerrada"
    incidencia.cierre_nota = nota.strip()
    incidencia.cerrada_por = contexto.usuario_id
    incidencia.cerrada_en = ahora()
    registrar_auditoria(
        contexto,
        "parcela.incidencia_cerrar",
        "parcela",
        parcela.id,
        {"incidencia_id": incidencia.id, "tipo": incidencia.tipo, "nota": nota},
    )
    contexto.sesion.commit()
    _reevaluar(contexto.sesion, parcela)
    return incidencia


# ---------- Nombres ----------


def nombres_de(sesion: Session, ids: set) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(
        sesion.execute(
            select(Perfil.id, func.concat(Perfil.nombres, " ", Perfil.apellidos)).where(Perfil.id.in_(ids))
        ).all()
    )


# ---------- Salida ----------


def plantillas(leg: Legalidad) -> list[str]:
    """Las plantillas para firmar que se ofrecen (sección 7)."""
    disponibles = []
    if leg.valor("tenencia_tipo") in catalogo.CON_PLANTILLA_DECLARACION:
        disponibles.append("declaracion-jurada-tenencia")
    if leg.valor("en_tierra_comunal") == "si":
        disponibles.append("constancia-comunal")
    return disponibles


def _aviso(leg: Legalidad, variable: str) -> str | None:
    """Sección 4, nota 4: avisa, no impide."""
    if variable != "tenencia_tipo" or leg.valor("tenencia_tipo") in (None, "titulo_habilitante"):
        return None
    if leg.valor("en_anp") == "dentro" or leg.valor("en_tierra_forestal") == "si":
        return (
            "La parcela está dentro de un área protegida o en tierra forestal: lo usual es que la tierra sea "
            "pública y que el productor la use con una cesión en uso o un acuerdo de conservación."
        )
    return None


def salida(sesion: Session, parcela: Parcela):
    from app.schemas.habilitacion import ExencionSalida
    from app.schemas.legalidad import (
        CapaSalida,
        CruceSalida,
        IncidenciaSalida,
        LegalidadSalida,
        Opcion,
        RequisitoLegalSalida,
        TipoAceptado,
        ValorSalida,
        VariableSalida,
    )
    from app.services.productores import documento_salida  # evita importación circular

    leg = legalidad(sesion, parcela)
    # Los anulados también se listan, como historial de cada requisito.
    todos = list(
        sesion.scalars(
            select(Documento)
            .where(
                Documento.entidad == "parcela",
                Documento.entidad_id == parcela.id,
                Documento.tipo.in_(documentos_legales.TODOS),
            )
            .order_by(Documento.creado_en.desc())
        )
    )
    filas = [v.cruce for v in leg.perfil.values() if v.cruce] + [
        v.declarado for v in leg.perfil.values() if v.declarado
    ]
    nombres = nombres_de(
        sesion,
        {d.subido_por for d in todos}
        | {f.registrada_por for f in filas}
        | {i.registrada_por for i in leg.incidencias}
        | {i.cerrada_por for i in leg.incidencias}
        | {e.declarada_por for e in leg.exenciones},
    )

    def valor_salida(fila: ParcelaVariable | None) -> ValorSalida | None:
        if fila is None:
            return None
        return ValorSalida(
            valor=fila.valor,
            etiqueta=perfil_legal.etiqueta(fila.variable, fila.valor),
            origen=fila.origen,
            fuente=fila.fuente,
            detalle=fila.detalle,
            registrada_en=fila.registrada_en,
            registrada_por_nombre=nombres.get(fila.registrada_por),
        )

    perfil = []
    for v in perfil_legal.VARIABLES:
        valor = leg.perfil[v.codigo]
        perfil.append(
            VariableSalida(
                codigo=v.codigo,
                pregunta=v.pregunta,
                ayuda=v.ayuda,
                fuente_orientador=v.fuente,
                cruzable=v.cruzable,
                opciones=[Opcion(valor=o, etiqueta=perfil_legal.etiqueta(v.codigo, o)) for o in v.valores],
                se_pregunta=v.codigo != "reserva_bosque_30" or leg.pide_reserva,
                valor=valor.valor,
                etiqueta=perfil_legal.etiqueta(v.codigo, valor.valor),
                origen=valor.origen,
                nivel=valor.nivel,
                cruce=valor_salida(valor.cruce),
                declarado=valor_salida(valor.declarado),
                declarado_sin_cruce=valor.declarado_sin_cruce,
                aviso=_aviso(leg, v.codigo),
            )
        )

    ofrecidas = plantillas(leg)
    requisitos = []
    # En el orden del catálogo: primero la tenencia y los permisos que bloquean. La interfaz pliega al final
    # los que no aplican.
    for r in leg.requisitos.values():
        req = r.requisito
        plantilla = None
        if r.codigo == "tenencia" and "declaracion-jurada-tenencia" in ofrecidas:
            formal = r.sustento is not None and r.sustento.tipo != "declaracion_jurada_tenencia"
            plantilla = None if formal else "declaracion-jurada-tenencia"
        elif r.codigo == "acuerdo_comunal" and "constancia-comunal" in ofrecidas and not r.cubierto:
            plantilla = "constancia-comunal"
        registro_oficial = []
        if r.codigo == "tierra_forestal" and leg.perfil["en_tierra_forestal"].cruce:
            detalle = leg.perfil["en_tierra_forestal"].cruce.detalle or {}
            registro_oficial = [{"tipo": "cesion_en_uso", **c} for c in detalle.get("cesiones") or []] + [
                {"tipo": "cambio_de_uso", **c} for c in detalle.get("cambios_de_uso") or []
            ]
        aceptados = r.aceptados or req.sustentos
        requisitos.append(
            RequisitoLegalSalida(
                codigo=r.codigo,
                nombre=req.nombre,
                referencias=list(req.referencias),
                nivel_orientador=req.nivel,
                diligencia=req.diligencia,
                bloquea=req.bloquea,
                que_pide=req.que_pide,
                estado=r.estado,
                motivo=r.motivo,
                sustento=documento_salida(r.sustento, nombres.get(r.sustento.subido_por))
                if r.sustento
                else None,
                sustento_nivel=r.nivel,
                nota=r.nota,
                pide_nota=req.pide_nota,
                por_excepcion=r.por_excepcion,
                aceptados=[
                    TipoAceptado(codigo=t, nombre=documentos_legales.POR_CODIGO[t].nombre) for t in aceptados
                ],
                documentos=[
                    documento_salida(d, nombres.get(d.subido_por)) for d in todos if d.tipo in aceptados
                ],
                plantilla=plantilla,
                registro_oficial=registro_oficial,
            )
        )

    estado_cruce = parcela.cruce_estado or {}
    area = area_total(parcela)
    return LegalidadSalida(
        parcela_id=parcela.id,
        orientador=catalogo.ORIENTADOR,
        perfil=perfil,
        perfil_completo=leg.perfil_completo,
        requisitos=requisitos,
        compuerta=leg.compuerta(),
        alertas=leg.alertas(),
        incidencias=[
            IncidenciaSalida(
                id=i.id,
                tipo=i.tipo,
                descripcion=i.descripcion,
                fuente=i.fuente,
                estado=i.estado,
                registrada_en=i.registrada_en,
                registrada_por_nombre=nombres.get(i.registrada_por),
                cierre_nota=i.cierre_nota,
                cerrada_en=i.cerrada_en,
                cerrada_por_nombre=nombres.get(i.cerrada_por),
            )
            for i in leg.incidencias
        ],
        cruce=CruceSalida(
            en_cola=cruce.en_cola(parcela),
            solicitado_en=parcela.cruce_solicitado_en,
            aproximacion=bool(estado_cruce.get("aproximacion")),
            capas=[CapaSalida(**c) for c in cruce.estado_por_capa(parcela)],
        ),
        plantillas=ofrecidas,
        documentos_anteriores=[
            documento_salida(d, nombres.get(d.subido_por))
            for d in todos
            if d.tipo in documentos_legales.CODIGOS_ANTERIORES
        ],
        exenciones=[
            ExencionSalida(
                id=e.id,
                tipo=e.tipo,
                motivo=e.motivo,
                declarada_en=e.declarada_en,
                declarada_por_nombre=nombres.get(e.declarada_por),
                retirada_en=e.retirada_en,
            )
            for e in leg.exenciones
        ],
        area_total_ha=float(area) if area is not None else None,
    )


# ---------- Bloque sellado en el DOP (versión 5) y en el respaldo del DEX ----------

AVISO_ORIENTADOR = "El propio documento dice que no es jurídicamente vinculante ni asesoría legal."


def _encontrados(codigo: str, detalle: dict) -> list[str]:
    """Lo que una capa encontró, en una línea por elemento."""

    def nombre(e: dict, *extra: str) -> str:
        partes = [str(e[k]) for k in extra if e.get(k)]
        base = e.get("nombre") or "sin nombre en la capa"
        return f"{base} ({', '.join(partes)})" if partes else base

    if codigo == "sernanp_anp":
        return [nombre(e, "categoria") for e in detalle.get("areas") or []]
    if codigo == "sernanp_amortiguamiento":
        return [nombre(e) for e in detalle.get("zonas_de_amortiguamiento") or []]
    if codigo == "serfor_zonificacion":
        return [
            " · ".join(str(x) for x in (e.get("categoria_nombre"), e.get("subcategoria_nombre")) if x)
            + (f" ({e['resolucion']})" if e.get("resolucion") else "")
            for e in detalle.get("zonas") or []
        ]
    if codigo == "idep_comunidades":
        return [
            f"{e.get('nombre') or 'sin nombre en la capa'} (comunidad {e.get('tipo')})"
            for e in detalle.get("comunidades") or []
        ]
    if codigo == "ign_hidrografia":
        return [
            f"{e.get('nombre') or 'sin nombre en la capa'} ({e.get('tipo')}, a {e.get('distancia_m')} m)"
            for e in detalle.get("cuerpos") or []
        ]
    if codigo == "sigda_monumentos":
        return [nombre(e, "clase") for e in detalle.get("monumentos") or []]
    return []


def capas_consultadas(leg: Legalidad) -> list[dict]:
    """Las capas activas con su fecha y su resultado, también cuando la parcela no figura en ellas (sección
    12, regla 5)."""
    from app.catalogos import capas_legales

    estados = {c["codigo"]: c for c in cruce.estado_por_capa(leg.parcela)}
    salida = []
    for codigo, estado in estados.items():
        capa = capas_legales.POR_CODIGO[codigo]
        fila = leg.perfil[capa.variable].cruce
        detalle = (
            (fila.detalle or {})
            if fila is not None and codigo in (fila.detalle or {}).get("capas", [])
            else {}
        )
        # Sin estado de la cola (una fila de cruce anterior a él), la fila del cruce dice cuándo se consultó.
        hecho, consultada_en = estado["estado"], estado["consultada_en"]
        if hecho == "pendiente" and detalle:
            hecho, consultada_en = "hecho", fila.registrada_en
        dato = {
            "codigo": codigo,
            "nombre": capa.nombre,
            "entidad": capa.entidad,
            "variable": capa.variable,
            "estado": hecho,
            "consultada_en": consultada_en,
            "encontrados": _encontrados(codigo, detalle) if hecho == "hecho" else [],
        }
        if codigo == "serfor_zonificacion" and hecho == "hecho" and detalle:
            dato["otras"] = [
                " · ".join(str(x) for x in (o.get("categoria_nombre"), o.get("subcategoria_nombre")) if x)
                for o in detalle.get("otras") or []
            ]
            dato["sin_zonificacion"] = fila.valor == "sin_zonificacion"
        salida.append(dato)
    return salida


def bloque(sesion: Session, parcela: Parcela) -> dict:
    """La legalidad de la parcela tal como está hoy: el perfil con el origen de cada variable, los requisitos
    con su estado, su sustento y su nivel, las incidencias y las capas consultadas."""
    leg = legalidad(sesion, parcela)
    perfil = []
    for v in perfil_legal.VARIABLES:
        if v.codigo == "reserva_bosque_30" and not leg.pide_reserva:
            continue
        valor = leg.perfil[v.codigo]
        fila = valor.manda
        perfil.append(
            {
                "codigo": v.codigo,
                "pregunta": v.pregunta,
                "valor": valor.valor,
                "etiqueta": perfil_legal.etiqueta(v.codigo, valor.valor),
                "origen": valor.origen,
                "nivel": valor.nivel,
                "fuente": fila.fuente if fila else None,
                "registrada_en": fila.registrada_en if fila else None,
                "declarado_sin_cruce": valor.declarado_sin_cruce,
                "aproximacion": bool((fila.detalle or {}).get("aproximacion")) if fila else False,
            }
        )
    requisitos = []
    for r in leg.requisitos.values():
        req, doc = r.requisito, r.sustento
        requisitos.append(
            {
                "codigo": r.codigo,
                "nombre": req.nombre,
                "referencias": list(req.referencias),
                "nivel_orientador": req.nivel,
                "diligencia": req.diligencia,
                "bloquea": req.bloquea,
                "estado": r.estado,
                "motivo": r.motivo,
                "nivel": r.nivel,
                "nota": r.nota,
                "por_excepcion": r.por_excepcion,
                "documento": {
                    "tipo": doc.tipo,
                    "nombre": documentos_legales.POR_CODIGO[doc.tipo].nombre,
                    "clase": doc.clase,
                    "numero": doc.numero,
                    "entidad_emisora": doc.entidad_emisora,
                    "fecha_emision": doc.fecha_emision,
                    "fecha_vencimiento": doc.fecha_vencimiento,
                    "cotejado_en": doc.cotejado_en,
                    "sha256": doc.sha256,
                    "registro_consultable": documentos_legales.POR_CODIGO[doc.tipo].registro_consultable,
                }
                if doc
                else None,
            }
        )
    return {
        "orientador": catalogo.ORIENTADOR,
        "aviso_orientador": AVISO_ORIENTADOR,
        "perfil_completo": leg.perfil_completo,
        "perfil": perfil,
        "requisitos": requisitos,
        "incidencias": [
            {
                "tipo": i.tipo,
                "descripcion": i.descripcion,
                "fuente": i.fuente,
                "estado": i.estado,
                "registrada_en": i.registrada_en,
                "cierre_nota": i.cierre_nota,
                "cerrada_en": i.cerrada_en,
            }
            for i in sorted(leg.incidencias, key=lambda x: x.registrada_en)
        ],
        "capas": capas_consultadas(leg),
        "aproximacion": bool((parcela.cruce_estado or {}).get("aproximacion")),
    }


# ---------- Plantillas para firmar ----------

CLAVE_PLANTILLA = {
    "declaracion-jurada-tenencia": "declaracion_jurada_tenencia",
    "constancia-comunal": "constancia_comunal",
}


def plantilla(sesion: Session, parcela: Parcela, nombre: str) -> tuple[bytes, str]:
    """El PDF para firmar con los datos que el sistema conoce (sección 7). No se guarda."""
    from app.models import Cooperativa, Productor
    from app.pdf import declaracion_tenencia
    from app.services.analisis import _cooperativa_de  # evita importación circular
    from app.ubigeo import mostrar

    leg = legalidad(sesion, parcela)
    if nombre not in CLAVE_PLANTILLA or nombre not in plantillas(leg):
        raise error_api(
            400,
            "plantilla_no_aplica",
            "La declaración jurada se ofrece para propietarios, poseedores, usos por acuerdo y miembros de "
            "la comunidad; la constancia comunal, cuando la parcela está en tierra de una comunidad.",
        )
    productor = sesion.get(Productor, parcela.productor_id)
    cooperativa = sesion.get(Cooperativa, _cooperativa_de(sesion, parcela))
    area = area_total(parcela)
    datos = {
        "productor": f"{productor.nombres} {productor.apellidos}",
        "dni": productor.dni,
        "parcela": parcela.nombre,
        "codigo": parcela.codigo,
        "centro_poblado": parcela.centro_poblado,
        "distrito": mostrar(parcela.distrito),
        "provincia": mostrar(parcela.provincia),
        "departamento": mostrar(parcela.departamento),
        "area": f"{Decimal(area):.2f}".replace(".", ",") if area is not None else None,
        "organizacion": cooperativa.razon_social,
        "ruc": cooperativa.ruc,
    }
    contenido = declaracion_tenencia.generar(
        CLAVE_PLANTILLA[nombre],
        datos,
        leg.valor("tenencia_tipo"),
        es_demo=bool(cooperativa.es_demo or productor.es_demo),
    )
    return contenido, f"{nombre}-{parcela.codigo}.pdf"

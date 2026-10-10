"""Requisitos legales de la parcela (adenda 4, secciones 3 y 5).

Fuente: "Documento orientador para la diligencia debida de la legalidad del café y cacao en el marco del
EUDR" (MIDAGRI, MINCETUR y ADEX; European Forest Institute, 2026), Anexo 2. El propio documento dice que no
es jurídicamente vinculante ni asesoría legal.

`nivel` es el nivel de implementación en el Perú que le da el orientador y `diligencia` lo que pide: con
nivel alto, diligencia aligerada; con nivel bajo, estándar. Solo bloquean la habilitación los que tienen
`bloquea`. `sustentos` son los tipos de documento que lo sustentan; vacío si pide solo una nota.
"""

from dataclasses import dataclass

ORIENTADOR = (
    "Documento orientador para la diligencia debida de la legalidad del café y cacao en el marco del EUDR "
    "(MIDAGRI, MINCETUR y ADEX; European Forest Institute, 2026)"
)


@dataclass(frozen=True)
class RequisitoLegal:
    codigo: str
    nombre: str
    referencias: tuple[str, ...]
    nivel: str  # alto o bajo
    diligencia: str  # aligerada o estandar
    bloquea: bool
    que_pide: str  # "Qué pide el orientador", en una línea
    sustentos: tuple[str, ...] = ()
    pide_nota: bool = False  # sin documento: se sustenta con una nota


REQUISITOS: tuple[RequisitoLegal, ...] = (
    RequisitoLegal(
        "tenencia",
        "Tenencia de la tierra",
        ("1.1", "1.2"),
        "alto",
        "aligerada",
        True,
        "Que el productor tenga un derecho sobre la tierra por propiedad, posesión o un acuerdo escrito o "
        "verbal con su dueño.",
    ),
    RequisitoLegal(
        "acuerdo_comunal",
        "Acuerdo con la comunidad",
        ("1.3", "1.4"),
        "alto",
        "aligerada",
        True,
        "En tierra de una comunidad, que el uso esté acordado con ella: la constancia de la comunidad para "
        "un "
        "miembro, o el acta de asamblea o el contrato para quien no lo es.",
        ("constancia_comunal", "acta_comunal", "contrato_de_uso", "declaracion_jurada_tenencia"),
    ),
    RequisitoLegal(
        "area_protegida",
        "Acuerdo de conservación en el área protegida",
        ("2.1", "2.13"),
        "alto",
        "aligerada",
        True,
        "Dentro de un área natural protegida, un acuerdo de conservación firmado por la jefatura del área, y "
        "no afectar especies amenazadas ni la biodiversidad.",
        ("acuerdo_conservacion",),
    ),
    RequisitoLegal(
        "tierra_forestal",
        "Título habilitante en tierra forestal o de protección",
        ("2.2", "2.10", "2.11"),
        "bajo",
        "estandar",
        True,
        "En tierra de aptitud forestal o de protección, un contrato de cesión en uso (CCUSAF) o una "
        "autorización de cambio de uso; o la excepción de la Ley N.º 31973 para predios con título o "
        "constancia anteriores a la ley.",
        ("cusaf", "autorizacion_cambio_uso"),
    ),
    RequisitoLegal(
        "agua_de_riego",
        "Licencia de agua para riego",
        ("2.4",),
        "alto",
        "aligerada",
        False,
        "Si se riega, la licencia o el permiso de uso de agua, o el "
        "certificado de la organización de usuarios.",
        ("licencia_agua",),
    ),
    RequisitoLegal(
        "instrumento_ambiental",
        "Instrumento de gestión ambiental",
        ("2.12", "3.3"),
        "alto",
        "aligerada",
        False,
        "Con 10 ha o más, el instrumento ambiental que pide la ley: Ficha Técnica Ambiental hasta 50 ha; "
        "DIA, "
        "EIA-sd, EIA-d o PAMA sobre 50 ha. El instrumento es público.",
        ("ficha_tecnica_ambiental", "instrumento_ambiental"),
    ),
    RequisitoLegal(
        "faja_marginal",
        "Faja marginal de ríos y lagos",
        ("2.5",),
        "alto",
        "aligerada",
        False,
        "No cultivar en la faja marginal de un río, quebrada, lago o laguna. Se registra una nota con la "
        "distancia del cultivo al agua.",
        pide_nota=True,
    ),
    RequisitoLegal(
        "patrimonio_cultural",
        "Patrimonio cultural",
        ("3.1",),
        "alto",
        "aligerada",
        False,
        "Respetar los sitios arqueológicos y de patrimonio cultural. Se registra una nota de cómo se "
        "respeta.",
        pide_nota=True,
    ),
)
POR_CODIGO = {r.codigo: r for r in REQUISITOS}
CODIGOS = tuple(POR_CODIGO)
BLOQUEAN = tuple(r.codigo for r in REQUISITOS if r.bloquea)
PERMISOS_OBLIGATORIOS = ("acuerdo_comunal", "area_protegida", "tierra_forestal")

# Sección 5.1: sustentos de tenencia según `tenencia_tipo`.
SUSTENTOS_TENENCIA: dict[str, tuple[str, ...]] = {
    "propietario": (
        "titulo_sunarp",
        "titulo_no_inscrito",
        "certificado_catastral",
        "declaracion_jurada_tenencia",
    ),
    "poseedor": ("constancia_posesion", "certificado_catastral", "declaracion_jurada_tenencia"),
    "uso_por_acuerdo": ("contrato_de_uso", "declaracion_jurada_tenencia"),
    "comunal_miembro": ("constancia_comunal", "declaracion_jurada_tenencia"),
    "comunal_tercero": ("acta_comunal", "contrato_de_uso"),
    "titulo_habilitante": ("cusaf", "acuerdo_conservacion"),
}
# Sección 7: la plantilla de la declaración jurada solo se ofrece para estos tipos de tenencia.
CON_PLANTILLA_DECLARACION = ("propietario", "poseedor", "uso_por_acuerdo", "comunal_miembro")

# Sección 5.2 y decisiones del equipo del 2026-10-09: la excepción de la Ley N.º 31973.
# La ley se publicó el 11/01/2024 y rige desde el 12/01/2024: valen los documentos emitidos antes.
CORTE_LEY_31973 = "2024-01-12"
# Títulos o constancias "emitidas por la autoridad competente" (un título no inscrito solo si es de
# formalización), más la constancia de saneamiento de la Ley N.º 31145, sin fecha.
EXCEPCION_FORESTAL_CON_FECHA = ("titulo_sunarp", "constancia_posesion", "titulo_no_inscrito")
EXCEPCION_FORESTAL_SIN_FECHA = ("constancia_saneamiento_31145",)
CLASE_TITULO_QUE_VALE = "titulo_formalizacion"

# Sección 5, instrumento ambiental: hasta 50 ha la ficha técnica; sobre 50 ha, el instrumento mayor.
UMBRAL_INSTRUMENTO_HA = 10
UMBRAL_INSTRUMENTO_MAYOR_HA = 50

ETIQUETAS_NIVEL = {"alto": "Alto", "bajo": "Bajo"}
ETIQUETAS_DILIGENCIA = {"aligerada": "Aligerada", "estandar": "Estándar"}

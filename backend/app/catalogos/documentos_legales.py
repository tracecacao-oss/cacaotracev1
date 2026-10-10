"""Documentos legales de la parcela (adenda 4, sección 6) y de la cooperativa (Parte 8).

`registro_consultable` dice si el documento tiene un registro público en línea contra el cual cotejarlo.
Confirmado con fuentes oficiales (ver la especificación, "Los 7 documentos", y la adenda 4, sección 6):
- titulo_sunarp: "Conoce Aquí" de SUNARP, con el número de partida (2026-10-05).
- cusaf: GeoSERFOR, capa "Cesiones en uso" de Modalidad_Acceso, con número, inicio, término y situación del
  contrato; el 2026-10-09 publicaba 1179 cesiones.
Sin registro en línea (2026-10-09): la autorización de cambio de uso (GeoSERFOR publicaba solo 2 en su capa
"Autorización de cambio de uso actual de las tierras a fines agropecuarios"); el acuerdo de conservación (la
capa "Acuerdo" de SERNANP estaba vacía); la licencia de agua (la ANA no publica un buscador del Registro
Administrativo de Derechos de Uso de Agua; sus resoluciones solo se autentican con su clave en sisged); la
constancia de posesión (registro administrativo de quien la emite, RM 0029-2020-MINAGRI); y los demás, que
emiten notarías, comunidades, gobiernos regionales o el propio productor.
Cambiar un valor aquí no exige migración.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TipoLegal:
    codigo: str
    nombre: str
    grupo: str
    tenencia: bool  # sustenta la tenencia de la parcela
    registro_consultable: bool
    requiere_numero: bool = True  # la declaración jurada y lo que firma la comunidad no llevan número
    anterior: bool = False  # adenda 4: ya no se cargan; los cargados se ven como "documentos anteriores"


# Adenda 4, sección 6: los documentos de la parcela.
TIPOS = (
    TipoLegal("titulo_sunarp", "Título de propiedad inscrito en SUNARP", "Tenencia", True, True),
    TipoLegal(
        "titulo_no_inscrito",
        "Título de propiedad no inscrito: escritura, minuta o título de formalización",
        "Tenencia",
        True,
        False,
    ),
    TipoLegal("constancia_posesion", "Constancia de posesión", "Tenencia", True, False),
    TipoLegal(
        "certificado_catastral",
        "Certificado de información catastral del ente de formalización regional",
        "Tenencia",
        True,
        False,
    ),
    TipoLegal(
        "contrato_de_uso", "Contrato de arrendamiento, comodato o cesión en uso", "Tenencia", True, False
    ),
    TipoLegal(
        "declaracion_jurada_tenencia",
        "Declaración jurada de tenencia firmada por el productor",
        "Tenencia",
        True,
        False,
        requiere_numero=False,
    ),
    TipoLegal(
        "constancia_comunal",
        "Constancia de la comunidad sobre el uso de su tierra",
        "Comunidad",
        True,
        False,
        requiere_numero=False,
    ),
    TipoLegal(
        "acta_comunal",
        "Acta de asamblea comunal que autoriza el uso",
        "Comunidad",
        True,
        False,
        requiere_numero=False,
    ),
    TipoLegal(
        "acuerdo_conservacion",
        "Acuerdo de conservación con la jefatura del área protegida",
        "Área protegida",
        True,
        False,
    ),
    TipoLegal(
        "cusaf",
        "Contrato de cesión en uso para sistemas agroforestales (CCUSAF)",
        "Uso forestal",
        True,
        True,
    ),
    TipoLegal(
        "autorizacion_cambio_uso",
        "Autorización de cambio de uso o de desbosque",
        "Uso forestal",
        False,
        False,
    ),
    # Decisión del equipo del 2026-10-09 (adenda 4, sección 5.2): la vía de la Ley N.º 31145.
    TipoLegal(
        "constancia_saneamiento_31145",
        "Constancia del gobierno regional de saneamiento del predio por la Ley N.º 31145",
        "Uso forestal",
        False,
        False,
    ),
    TipoLegal(
        "licencia_agua",
        "Licencia o permiso de uso de agua, o certificado de la organización de usuarios",
        "Agua",
        False,
        False,
    ),
    TipoLegal("ficha_tecnica_ambiental", "Ficha Técnica Ambiental", "Ambiental", False, False),
    TipoLegal(
        "instrumento_ambiental", "Instrumento ambiental: DIA, EIA-sd, EIA-d o PAMA", "Ambiental", False, False
    ),
)
# Antes de la adenda 4: se conservan y se ven, pero no sustentan nada y no se cargan nuevos.
TIPOS_ANTERIORES = (
    TipoLegal("sunafil", "Sustento laboral ante SUNAFIL", "Anterior", False, True, anterior=True),
    TipoLegal("sunat", "Ficha RUC u otro sustento de SUNAT", "Anterior", False, True, anterior=True),
    TipoLegal(
        "zonificacion",
        "Sustento de la zonificación forestal de la parcela",
        "Anterior",
        False,
        True,
        anterior=True,
    ),
)
POR_CODIGO = {t.codigo: t for t in (*TIPOS, *TIPOS_ANTERIORES)}
CODIGOS = tuple(t.codigo for t in TIPOS)  # los que se cargan
CODIGOS_ANTERIORES = tuple(t.codigo for t in TIPOS_ANTERIORES)
TODOS = (*CODIGOS, *CODIGOS_ANTERIORES)
# El título no inscrito guarda su clase: solo el de formalización sustenta la excepción de la Ley N.º 31973.
CLASES_TITULO_NO_INSCRITO = ("titulo_formalizacion", "escritura_publica", "minuta")
ETIQUETAS_CLASE = {
    "titulo_formalizacion": "Título de formalización",
    "escritura_publica": "Escritura pública",
    "minuta": "Minuta",
}

# ---------- Parte 8: expediente legal de la cooperativa ----------
# Seis casillas sin exenciones: las seis deben estar vigentes. `registro_consultable` trae los valores
# iniciales de la especificación ("Los 6 documentos"), que el equipo debe confirmar.

TIPOS_COOPERATIVA = (
    TipoLegal(
        "rnca", "Registro Nacional de Cooperativas Agrarias (MIDAGRI)", "Registro agrario", False, False
    ),
    TipoLegal(
        "partida_sunarp", "Partida registral de la cooperativa en SUNARP", "Identificación legal", False, True
    ),
    TipoLegal("ficha_ruc", "Ficha RUC de SUNAT", "Identificación legal", False, True),
    TipoLegal(
        "vigencia_poderes",
        "Vigencia de poderes del representante legal (SUNARP)",
        "Representación legal",
        False,
        True,
    ),
    TipoLegal(
        "ruc_comercio_exterior",
        "Sustento del RUC habilitado para comercio exterior",
        "Capacidad exportadora",
        False,
        True,
    ),
    TipoLegal(
        "registro_aduanas",
        "Registro como exportador ante SUNAT Aduanas",
        "Capacidad exportadora",
        False,
        False,
    ),
)
POR_CODIGO_COOPERATIVA = {t.codigo: t for t in TIPOS_COOPERATIVA}
CODIGOS_COOPERATIVA = tuple(POR_CODIGO_COOPERATIVA)


def tipo_legal(codigo: str) -> TipoLegal | None:
    """Un tipo legal de la parcela (adenda 4, también los anteriores) o de la cooperativa (Parte 8)."""
    return POR_CODIGO.get(codigo) or POR_CODIGO_COOPERATIVA.get(codigo)

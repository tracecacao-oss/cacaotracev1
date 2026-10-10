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
    # Adenda 6, sección 4: el documento de la organización que frena un lote si falta (su identidad), y los
    # tipos de organización a los que aplica (vacío: a todas).
    identidad: bool = False
    aplica_a: tuple[str, ...] = ()

    def aplica(self, tipo_organizacion: str) -> bool:
        return not self.aplica_a or tipo_organizacion in self.aplica_a


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

# ---------- Expediente legal de la organización (Parte 8; desde la adenda 6, sección 4) ----------
# Cada organización ve lo que le toca según su `tipo_organizacion`. Solo la identidad frena un lote: ficha
# RUC, partida registral y vigencia de poderes. La declaración de renta vence sola a los RENTA_VIGENCIA_MESES
# de su presentación. `rnca` es la "Constancia de Inscripción" del Decreto Supremo N.º 023-2021-MIDAGRI
# (art. 13.4): solo para la cooperativa agraria, no frena (decisión del equipo del 2026-10-09) y no tiene una
# consulta en línea, aunque el reglamento la prevé (art. 5).
TIPOS_COOPERATIVA = (
    TipoLegal("ficha_ruc", "Ficha RUC de SUNAT", "Identidad", False, True, identidad=True),
    TipoLegal(
        "partida_sunarp",
        "Partida registral de la organización en SUNARP",
        "Identidad",
        False,
        True,
        identidad=True,
    ),
    TipoLegal(
        "vigencia_poderes",
        "Vigencia de poderes del representante legal (SUNARP)",
        "Identidad",
        False,
        True,
        identidad=True,
    ),
    TipoLegal(
        "renta_anual",
        "Declaración jurada anual del impuesto a la renta, o constancia de haberla presentado",
        "Tributos y registro",
        False,
        False,
    ),
    TipoLegal(
        "rnca",
        "Constancia de inscripción en el Registro Nacional de Cooperativas Agrarias (MIDAGRI)",
        "Tributos y registro",
        False,
        False,
        aplica_a=("cooperativa_agraria",),
    ),
)
# Adenda 6, sección 4, regla 4: SUNAT pide para exportar el RUC sin la condición de no habido; no hay un
# registro aparte de exportadores. Los cargados se conservan como "documentos anteriores".
TIPOS_COOPERATIVA_ANTERIORES = (
    TipoLegal(
        "ruc_comercio_exterior",
        "Sustento del RUC habilitado para comercio exterior",
        "Anterior",
        False,
        True,
        anterior=True,
    ),
    TipoLegal(
        "registro_aduanas",
        "Registro como exportador ante SUNAT Aduanas",
        "Anterior",
        False,
        False,
        anterior=True,
    ),
)
POR_CODIGO_COOPERATIVA = {t.codigo: t for t in (*TIPOS_COOPERATIVA, *TIPOS_COOPERATIVA_ANTERIORES)}
CODIGOS_COOPERATIVA = tuple(t.codigo for t in TIPOS_COOPERATIVA)  # los que se cargan
TODOS_COOPERATIVA = tuple(POR_CODIGO_COOPERATIVA)
IDENTIDAD = tuple(t.codigo for t in TIPOS_COOPERATIVA if t.identidad)


def tipos_de_organizacion(tipo_organizacion: str) -> tuple[TipoLegal, ...]:
    """Los documentos que le tocan a una organización según su tipo (adenda 6, sección 4)."""
    return tuple(t for t in TIPOS_COOPERATIVA if t.aplica(tipo_organizacion))


def tipo_legal(codigo: str) -> TipoLegal | None:
    """Un tipo legal de la parcela (adenda 4) o de la organización (Parte 8 y adenda 6), también los
    anteriores."""
    return POR_CODIGO.get(codigo) or POR_CODIGO_COOPERATIVA.get(codigo)

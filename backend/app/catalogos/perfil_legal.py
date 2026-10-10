"""Perfil legal de la parcela (adenda 4, sección 4): nueve datos de los que sale qué requisitos aplican.

Cinco los responde el sistema cruzando la geometría con capas oficiales (`cruzable`); los otros cuatro los
declara una persona. Entre un cruce y una declaración vigentes manda el valor más exigente: `exigencia`
ordena los valores de menos a más exigente. Una declaración no puede quedar por debajo del cruce vigente.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Variable:
    codigo: str
    pregunta: str
    ayuda: str
    valores: tuple[str, ...]  # vacío: un año de 4 dígitos
    cruzable: bool
    exigencia: tuple[str, ...] = ()  # de menos a más exigente, solo en las cruzables
    fuente: str = ""  # la que nombra el orientador


VARIABLES: tuple[Variable, ...] = (
    Variable(
        "tenencia_tipo",
        "¿Qué derecho tiene el productor sobre esta tierra?",
        "Lo que el productor tiene sobre la tierra, aunque no tenga un documento formal.",
        (
            "propietario",
            "poseedor",
            "uso_por_acuerdo",
            "comunal_miembro",
            "comunal_tercero",
            "titulo_habilitante",
        ),
        False,
        fuente="Se declara",
    ),
    Variable(
        "en_anp",
        "¿La parcela está en un área natural protegida?",
        "Dentro de un área natural protegida nacional o una zona reservada, o en su zona de amortiguamiento.",
        ("no", "zona_de_amortiguamiento", "dentro"),
        True,
        ("no", "zona_de_amortiguamiento", "dentro"),
        "Visor de SERNANP",
    ),
    Variable(
        "en_tierra_forestal",
        "¿Está en tierra de aptitud forestal o de protección?",
        "Según la zonificación forestal del departamento en la capa de SERFOR. Donde la capa no lo "
        "clasifica, no se sabe.",
        ("no", "si", "sin_zonificacion"),
        True,
        ("no", "sin_zonificacion", "si"),
        "GeoSERFOR e IDE-i de SERFOR",
    ),
    Variable(
        "en_tierra_comunal",
        "¿Está en tierra de una comunidad campesina o nativa?",
        "Hay comunidades que no figuran en los mapas: si la tierra es de una comunidad, decláralo.",
        ("no", "si"),
        True,
        ("no", "si"),
        "Sistema de Catastro Rural y Base de Datos de Pueblos Indígenas",
    ),
    Variable(
        "junto_a_cuerpo_de_agua",
        "¿Colinda con un río, quebrada, lago o laguna?",
        "Si el cultivo llega hasta la orilla de un río, una quebrada, un lago o una laguna.",
        ("no", "si"),
        True,
        ("no", "si"),
        "Mapa de fajas marginales de la ANA",
    ),
    Variable(
        "en_patrimonio_cultural",
        "¿Se superpone con un sitio arqueológico o de patrimonio cultural?",
        "Restos arqueológicos, caminos prehispánicos u otros sitios declarados patrimonio cultural.",
        ("no", "si"),
        True,
        ("no", "si"),
        "SIGDA, del Ministerio de Cultura",
    ),
    Variable(
        "usa_riego",
        "¿Riega el cultivo o depende solo de la lluvia?",
        "Riego es tomar agua de un río, una quebrada, un canal o un pozo para el cultivo.",
        ("no", "si"),
        False,
        fuente="Encuesta",
    ),
    Variable(
        "anio_instalacion_cultivo",
        "¿En qué año se instaló el cacao en esta parcela?",
        "El año en que se sembró el cacao que hoy produce, aunque sea aproximado.",
        (),
        False,
        fuente="Evaluar el año de antigüedad de las parcelas",
    ),
    Variable(
        "reserva_bosque_30",
        "¿Mantiene con bosque al menos 30 % del área?",
        "La Ley N.º 31973 exige reservar 30 % de bosque en el predio; si no lo tiene, se compensa de a "
        "pocos.",
        ("si", "no", "sin_bosque"),
        False,
        fuente="Ley N.º 31973",
    ),
)
POR_CODIGO = {v.codigo: v for v in VARIABLES}
CODIGOS = tuple(POR_CODIGO)
# Las ocho que siempre se piden; reserva_bosque_30 solo con la excepción de la Ley N.º 31973 (sección 5.2).
BASE = tuple(c for c in CODIGOS if c != "reserva_bosque_30")
CRUZABLES = tuple(v.codigo for v in VARIABLES if v.cruzable)

# Datos adicionales que una persona puede declarar en `detalle`.
COMUNIDAD_INSCRITA = ("si", "no", "no_se_sabe")
TIPOS_COMUNIDAD = ("campesina", "nativa")

ETIQUETAS = {
    "tenencia_tipo": {
        "propietario": "Propietario",
        "poseedor": "Poseedor",
        "uso_por_acuerdo": "Usa la tierra de otro por acuerdo",
        "comunal_miembro": "Miembro de la comunidad dueña de la tierra",
        "comunal_tercero": "Usa tierra de una comunidad sin ser miembro",
        "titulo_habilitante": "Tierra pública con cesión en uso o acuerdo de conservación",
    },
    "en_anp": {"no": "No", "zona_de_amortiguamiento": "En zona de amortiguamiento", "dentro": "Dentro"},
    "en_tierra_forestal": {
        "no": "No",
        "si": "Sí",
        "sin_zonificacion": "Sin zonificación forestal en la capa",
    },
    "reserva_bosque_30": {"si": "Sí", "no": "No", "sin_bosque": "No tiene bosque"},
}


def etiqueta(variable: str, valor: str | None) -> str | None:
    if valor is None:
        return None
    if variable == "anio_instalacion_cultivo":
        return valor
    return ETIQUETAS.get(variable, {"no": "No", "si": "Sí"}).get(valor, valor)


def mas_exigente(variable: str, a: str | None, b: str | None) -> str | None:
    """El valor más exigente entre dos (un cruce y una declaración)."""
    if a is None or b is None:
        return a or b
    orden = POR_CODIGO[variable].exigencia
    return a if orden.index(a) >= orden.index(b) else b

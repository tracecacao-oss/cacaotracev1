"""Actuaciones de diligencia de la organización (adenda 6, sección 6): sus tipos, sus temas con la señal que
hace esperar una actuación, y las fuentes públicas que el formulario sugiere. El orientador agrupa lo que
recomienda en cinco familias; tres son trabajo de la organización (consultas con partes interesadas,
procedimientos y verificación en campo), y pide anotarlas en un "registro de actuaciones de diligencia
debida". La regla de los temas sigue al orientador: con diligencia estándar se espera actuar siempre que la
organización esté expuesta; con diligencia aligerada, solo cuando salta un caso. Las señales las calcula
`services/diligencia.py`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TipoActuacion:
    codigo: str
    nombre: str
    que_es: str
    ejemplos: str
    pide_contraparte: bool  # la fuente revisada o con quién se habló (sección 6.5)


TIPOS: tuple[TipoActuacion, ...] = (
    TipoActuacion(
        "revision_de_fuente_publica",
        "Revisión de una fuente pública",
        "Revisar una fuente pública.",
        "La lista de sancionados de OEFA; los reportes de conflictos de la Defensoría del Pueblo; la Base de "
        "Datos de Pueblos Indígenas.",
        True,
    ),
    TipoActuacion(
        "consulta_a_partes_interesadas",
        "Consulta a partes interesadas",
        "Preguntar a alguien de la zona.",
        "Municipalidad, agencia agraria, autoridades de una comunidad, vendedores de agroquímicos, "
        "organizaciones locales.",
        True,
    ),
    TipoActuacion(
        "capacitacion",
        "Capacitación o campaña",
        "Capacitación o campaña a productores o al personal.",
        "Equipo de protección y envases; derechos básicos de los trabajadores; ética y revisión de "
        "documentos.",
        False,
    ),
    TipoActuacion(
        "verificacion_en_campo",
        "Verificación en campo",
        "Visita a una muestra de productores.",
        "Qué productos usan, dónde dejan los envases, quiénes trabajan.",
        False,
    ),
    TipoActuacion(
        "apoyo_a_productores",
        "Apoyo a productores",
        "Ayuda para regularizar algo.",
        "Tramitar una constancia de posesión, un CCUSAF, un acuerdo de conservación o una licencia de agua.",
        False,
    ),
)
TIPOS_POR_CODIGO = {t.codigo: t for t in TIPOS}
CODIGOS_TIPOS = tuple(TIPOS_POR_CODIGO)


@dataclass(frozen=True)
class TemaDiligencia:
    codigo: str
    nombre: str
    referencias: tuple[str, ...]
    diligencia: str  # estandar o aligerada
    senal: str  # la señal que hace esperar una actuación (sección 6.2)


TEMAS: tuple[TemaDiligencia, ...] = (
    TemaDiligencia("integridad", "Integridad", ("7.3",), "estandar", "Siempre"),
    TemaDiligencia(
        "tierra_forestal",
        "Tierra forestal",
        ("2.2", "2.10", "2.11"),
        "estandar",
        "Alguna parcela activa en tierra de aptitud forestal o de protección",
    ),
    TemaDiligencia(
        "agroquimicos_y_envases",
        "Agroquímicos y envases",
        ("2.3", "2.7"),
        "estandar",
        "Algún productor que declara usar agroquímicos",
    ),
    TemaDiligencia(
        "trabajo",
        "Trabajo",
        ("4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7"),
        "estandar",
        "Algún productor que contrata trabajadores",
    ),
    TemaDiligencia(
        "tenencia",
        "Tenencia",
        ("1.1", "1.2", "1.3", "1.4"),
        "aligerada",
        "Alguna incidencia de tenencia registrada en los últimos 12 meses",
    ),
    TemaDiligencia(
        "areas_protegidas",
        "Áreas protegidas",
        ("2.1", "2.13"),
        "aligerada",
        "Alguna parcela activa dentro de un área protegida o en su zona de amortiguamiento",
    ),
    TemaDiligencia(
        "agua",
        "Agua",
        ("2.4", "2.5"),
        "aligerada",
        "Alguna parcela activa que riega sin licencia de agua o que colinda con un cuerpo de agua",
    ),
    TemaDiligencia(
        "derechos_humanos",
        "Derechos humanos",
        ("5.2", "5.3", "5.4", "5.5"),
        "aligerada",
        "Algún productor con menores de 18 años o trabajo no libre por atender",
    ),
)
TEMAS_POR_CODIGO = {t.codigo: t for t in TEMAS}
CODIGOS_TEMAS = tuple(TEMAS_POR_CODIGO)


@dataclass(frozen=True)
class FuenteSugerida:
    nombre: str
    temas: tuple[str, ...]  # vacío: todos
    enlace: str | None  # solo las que el orientador da con dirección


FUENTES: tuple[FuenteSugerida, ...] = (
    FuenteSugerida(
        "OEFA, administrados sancionados",
        ("agroquimicos_y_envases", "agua"),
        "https://publico.oefa.gob.pe/administrados-sancionados/#/",
    ),
    FuenteSugerida(
        "Base de Datos de Pueblos Indígenas u Originarios, Ministerio de Cultura",
        ("tenencia",),
        "https://bdpi.cultura.gob.pe/buscador-de-localidades-de-pueblos-indigenas",
    ),
    FuenteSugerida(
        "Defensoría del Pueblo, reportes de conflictos sociales", ("tenencia", "areas_protegidas"), None
    ),
    FuenteSugerida(
        "SUNAFIL, información pública de inspecciones y sanciones", ("trabajo", "derechos_humanos"), None
    ),
    FuenteSugerida(
        "Ministerio de la Mujer y Poblaciones Vulnerables, Programa Aurora", ("derechos_humanos",), None
    ),
    FuenteSugerida("Prensa y organizaciones de la sociedad civil", (), None),
)

LARGO_DESCRIPCION = 50
LARGO_RESULTADO = 20

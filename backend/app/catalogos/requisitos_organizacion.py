"""Requisitos de la organización y del lote (adenda 6, sección 3), los cinco temas de su política (sección 5)
y el órgano de dirección que adopta la política según el tipo de organización. Fuente: el "Documento
orientador para la diligencia debida de la legalidad del café y cacao en el marco del EUDR" (MIDAGRI, MINCETUR
y ADEX; European Forest Institute, 2026), Anexo 2. Solo la identidad frena un lote: lo demás se muestra y
llega al informe de hallazgos.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RequisitoOrganizacion:
    codigo: str
    nombre: str
    referencias: tuple[str, ...]
    nivel: str | None  # alto o bajo, el del orientador; None en la identidad y en las actuaciones
    diligencia: str | None  # aligerada o estandar
    bloquea: bool
    que_pide: str
    aplica_a: tuple[str, ...] = ()  # tipos de organización; vacío, a todas


REQUISITOS: tuple[RequisitoOrganizacion, ...] = (
    RequisitoOrganizacion(
        "identidad",
        "Identidad de la organización",
        (),
        None,
        None,
        True,
        "Ficha RUC, partida registral y vigencia de poderes del representante: el DEX nombra al exportador "
        "y a su representante.",
    ),
    RequisitoOrganizacion(
        "tributos",
        "Tributos de su régimen",
        ("7.1",),
        "alto",
        "aligerada",
        False,
        "La declaración jurada del impuesto a la renta, revisada con la consulta del RUC.",
    ),
    RequisitoOrganizacion(
        "registro_cooperativas",
        "Inscripción en el Registro Nacional de Cooperativas Agrarias",
        ("7.1",),
        "alto",
        "aligerada",
        False,
        "De esa inscripción dependen los beneficios tributarios de la Ley N.º 31335, que el orientador cita "
        "al explicar los tributos.",
        aplica_a=("cooperativa_agraria",),
    ),
    RequisitoOrganizacion(
        "integridad",
        "Política de integridad, trabajo digno y canal de denuncias",
        ("7.3", "5.5"),
        "bajo",
        "estandar",
        False,
        "Políticas de integridad y de no fraude, verificación de la autenticidad de los documentos y un "
        "canal confidencial de denuncias.",
    ),
    RequisitoOrganizacion(
        "actuaciones",
        "Actuaciones de diligencia",
        (),
        None,
        None,
        False,
        "Un registro de lo que la organización hace en su zona: consultas, capacitaciones, visitas y apoyo "
        "a los productores.",
    ),
    RequisitoOrganizacion(
        "aduanas",
        "Formalidades aduaneras del lote",
        ("7.2",),
        "alto",
        "aligerada",
        False,
        "La Declaración Aduanera de Mercancías, o su consulta pública por número.",
    ),
)
POR_CODIGO = {r.codigo: r for r in REQUISITOS}
DE_LA_ORGANIZACION = tuple(r.codigo for r in REQUISITOS if r.codigo != "aduanas")


@dataclass(frozen=True)
class TemaPolitica:
    codigo: str
    nombre: str
    que_dice: str
    referencias: tuple[str, ...]


TEMAS_POLITICA: tuple[TemaPolitica, ...] = (
    TemaPolitica(
        "integridad",
        "Integridad",
        "Que nadie da ni recibe pagos indebidos, y cómo se manejan los conflictos de interés.",
        ("7.3",),
    ),
    TemaPolitica(
        "no_fraude",
        "No fraude",
        "Que no se alteran pesos, calidades, orígenes ni documentos, y que no se mezcla cacao de origen "
        "desconocido.",
        ("7.3",),
    ),
    TemaPolitica(
        "canal_denuncias",
        "Canal de quejas y denuncias",
        "Cómo se presenta una queja o una denuncia, quién la recibe, que es confidencial y que no hay "
        "represalias.",
        ("7.3", "5.3", "5.4", "5.5"),
    ),
    TemaPolitica(
        "trabajo_digno",
        "Trabajo digno",
        "Sin menores de 18 años, trabajo libre, igualdad, sin acoso, y seguridad en el trabajo.",
        ("4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "5.2", "5.3", "5.4", "5.5"),
    ),
    TemaPolitica(
        "revision_de_documentos",
        "Revisión de documentos",
        "Cómo comprueba la organización que los documentos que recibe son auténticos.",
        ("7.3",),
    ),
)
TEMAS_POR_CODIGO = {t.codigo: t for t in TEMAS_POLITICA}
CODIGOS_TEMAS = tuple(TEMAS_POR_CODIGO)
LARGO_CONTACTO_CANAL = 200

# Sección 5, plantilla, regla 3: el órgano de dirección que sugiere el PDF.
ORGANO_SUGERIDO = {
    "cooperativa_agraria": "el Consejo de Administración",
    "asociacion": "el Consejo Directivo",
    "empresa": "el Directorio o la Gerencia General",
}
NOMBRE_TIPO_ORGANIZACION = {
    "cooperativa_agraria": "Cooperativa agraria",
    "asociacion": "Asociación",
    "empresa": "Empresa",
}

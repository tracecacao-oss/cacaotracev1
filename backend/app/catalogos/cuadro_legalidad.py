"""Cuadro de legalidad por requisito del lote (adenda 7, sección 5): el orden y la composición de sus 21 filas
y los nueve requisitos del orientador que no se piden.

Cada fila toma su estado de un requisito ya definido: de la parcela (adenda 4), del productor (adenda 5), de
la organización (adenda 6) o del lote (la declaración aduanera de la adenda 7). Su referencia, su nivel y su
diligencia son los del orientador, leídos del catálogo de ese requisito; las dos filas que no tienen uno
propio (daños ambientales y aduanas) los traen aquí. Entre todas las filas nombran los 31 requisitos que el
orientador considera pertinentes para el cacao.
"""

from dataclasses import dataclass

from app.catalogos import requisitos_legales, requisitos_organizacion, requisitos_productor

SUJETOS = ("parcela", "productor", "organizacion", "lote")


@dataclass(frozen=True)
class Fila:
    codigo: str
    nombre: str
    de: str  # parcela, productor, organizacion o lote
    fuente: str  # el requisito del que toma su estado
    referencias: tuple[str, ...]
    nivel: str | None  # alto o bajo, el del orientador
    diligencia: str | None  # aligerada o estandar
    nivel_texto: str = ""  # cuando el orientador da niveles distintos a sus referencias


def _parcela(codigo: str, nombre: str) -> Fila:
    r = requisitos_legales.POR_CODIGO[codigo]
    return Fila(codigo, nombre, "parcela", codigo, r.referencias, r.nivel, r.diligencia)


def _productor(codigo: str, nombre: str, fuente: str | None = None) -> Fila:
    r = requisitos_productor.POR_CODIGO[fuente or codigo]
    return Fila(codigo, nombre, "productor", r.codigo, r.referencias, r.nivel, r.diligencia, r.nivel_texto)


def _organizacion(codigo: str, nombre: str, fuente: str | None = None) -> Fila:
    r = requisitos_organizacion.POR_CODIGO[fuente or codigo]
    return Fila(codigo, nombre, "organizacion", r.codigo, r.referencias, r.nivel, r.diligencia)


FILAS: tuple[Fila, ...] = (
    _parcela("tenencia", "Tenencia"),
    _parcela("acuerdo_comunal", "Acuerdo con la comunidad"),
    _parcela("area_protegida", "Área protegida"),
    _parcela("tierra_forestal", "Tierra forestal"),
    _parcela("agua_de_riego", "Agua de riego"),
    _parcela("faja_marginal", "Faja marginal"),
    _parcela("instrumento_ambiental", "Instrumento ambiental"),
    _parcela("patrimonio_cultural", "Patrimonio cultural"),
    # Sección 5.2, regla 2: aplica con alguna incidencia ambiental; cerrada, con sustento; abierta, por
    # atender.
    Fila(
        "danos_ambientales",
        "Daños ambientales",
        "parcela",
        "incidencia_ambiental",
        ("3.4",),
        "alto",
        "aligerada",
    ),
    _productor("agroquimicos", "Agroquímicos"),
    _productor("envases", "Envases"),
    _productor("condiciones_de_trabajo", "Condiciones de trabajo"),
    _productor("igualdad_y_maternidad", "Igualdad y maternidad"),
    _productor("menores_de_edad", "Menores de edad"),
    _productor("trabajo_libre", "Trabajo libre"),
    _productor("tributos_productor", "Tributos del productor", "tributos"),
    _organizacion("tributos_organizacion", "Tributos de la organización", "tributos"),
    _organizacion("registro_cooperativas", "Registro de cooperativas"),
    _organizacion("integridad", "Integridad"),
    _organizacion("actuaciones", "Actuaciones de diligencia"),
    Fila("aduanas", "Aduanas", "lote", "dam", ("7.2",), "alto", "aligerada"),
)
POR_CODIGO = {f.codigo: f for f in FILAS}
CODIGOS = tuple(POR_CODIGO)


# Sección 5.2, regla 3: los requisitos de la tabla 3.3 de la adenda 4. Su nombre y su motivo, en español y en
# inglés, están en `cuadro.no_se_piden` de app/textos.
NO_SE_PIDEN = ("1.5", "2.6", "2.8", "2.9", "3.2", "3.4 bis", "4.8", "5.1", "6.1")

# Sección 5.3: en qué columna cuenta cada estado.
CON_SUSTENTO = ("sustentado", "por_vencer", "declarado")
POR_ATENDER = ("por_atender",)
SIN_SUSTENTO = ("sin_sustento", "vencido", "sin_dato")
NIVELES = ("declarado", "documentado", "verificado_en_fuente")

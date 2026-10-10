"""Requisitos del productor (adenda 5, sección 6). Ninguno bloquea.

Fuente: el "Documento orientador para la diligencia debida de la legalidad del café y cacao en el marco del
EUDR" (MIDAGRI, MINCETUR y ADEX; European Forest Institute, 2026), Anexo 2, como en la adenda 4. El
orientador advierte que se debate si lo laboral y los derechos humanos entran en el ámbito del Reglamento:
por eso aquí van como declaración del productor.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RequisitoProductor:
    codigo: str
    nombre: str
    referencias: tuple[str, ...]
    nivel: str  # alto o bajo, el del orientador
    diligencia: str  # aligerada o estandar
    que_pide: str
    nivel_texto: str = ""  # cuando el orientador da niveles distintos a sus referencias


REQUISITOS: tuple[RequisitoProductor, ...] = (
    RequisitoProductor(
        "condiciones_de_trabajo",
        "Condiciones de trabajo",
        ("4.1", "4.2", "4.3", "4.4", "4.5"),
        "bajo",
        "estandar",
        "Una encuesta a todos los productores para saber si tienen trabajadores, sus horas, su pago, su "
        "seguro de salud y su equipo de protección. Contratos solo si hay trabajadores permanentes.",
        "Bajo, estándar. El 4.1 es alto, aligerada",
    ),
    RequisitoProductor(
        "igualdad_y_maternidad",
        "Igualdad de pago y descanso por maternidad y paternidad",
        ("4.6", "4.7"),
        "bajo",
        "estandar",
        "Con 5 ha o más, preguntar si se paga lo mismo a hombres y mujeres y, con trabajadores permanentes, "
        "si se respeta el descanso pre y postnatal.",
    ),
    RequisitoProductor(
        "trabajo_libre",
        "Trabajo libre",
        ("5.3", "5.4"),
        "alto",
        "aligerada",
        "Una declaración voluntaria de que los trabajadores pueden renunciar y de que no hay trabajo "
        "forzoso.",
    ),
    RequisitoProductor(
        "menores_de_edad",
        "Sin trabajo de menores de 18 años",
        ("5.2",),
        "alto",
        "aligerada",
        "Recoger por encuesta quiénes trabajan y sus edades, y mirar si los menores van a la escuela.",
    ),
    RequisitoProductor(
        "agroquimicos",
        "Agroquímicos registrados",
        ("2.3",),
        "bajo",
        "estandar",
        "Tener la lista de plaguicidas y fertilizantes registrados por SENASA y comprobar que los productos "
        "usados figuran en ella.",
    ),
    RequisitoProductor(
        "envases",
        "Manejo de envases y residuos",
        ("2.7",),
        "bajo",
        "estandar",
        "Preguntar con un cuestionario periódico cómo se aplican los productos, cuáles son y qué se hace "
        "con los envases.",
    ),
    RequisitoProductor(
        "tributos",
        "Tributos de su régimen",
        ("7.1",),
        "alto",
        "aligerada",
        "Ver si vende menos de 75 UIT al año. Sobre ese monto, pedir la declaración del impuesto a la renta "
        "y revisar el RUC.",
    ),
)
POR_CODIGO = {r.codigo: r for r in REQUISITOS}
CODIGOS = tuple(POR_CODIGO)

ESTADOS = ("sin_dato", "no_aplica", "declarado", "por_atender", "sin_sustento", "sustentado")
ETIQUETAS_ESTADO = {
    "sin_dato": "Falta la declaración",
    "no_aplica": "No aplica",
    "declarado": "Declarado",
    "por_atender": "Por atender",
    "sin_sustento": "Sin sustento",
    "sustentado": "Sustentado",
}

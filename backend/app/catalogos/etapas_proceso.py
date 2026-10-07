"""Las 23 etapas del proceso (Parte 6), en cinco fases. El catálogo es fijo: una cooperativa no agrega ni
quita etapas. La etapa 11, "Traslado a zona de secado", es la que el equipo no tenía en su primer diagrama.

Cada etapa tiene un tipo del diagrama de análisis de proceso (operación, inspección, transporte, espera o
almacenamiento), la fase en que se ve en el tablero, si aplica en la ruta `seco` y su dato propio.
"""

from dataclasses import dataclass, field

TIPOS = ("operacion", "inspeccion", "transporte", "espera", "almacenamiento")
NOMBRE_TIPO = {
    "operacion": "Operación",
    "inspeccion": "Inspección",
    "transporte": "Transporte",
    "espera": "Espera",
    "almacenamiento": "Almacenamiento",
}
FASES = (
    ("ingreso", "Ingreso"),
    ("fermentacion", "Fermentación"),
    ("secado", "Secado"),
    ("seleccion", "Selección"),
    ("envasado", "Envasado y almacén"),
)
NOMBRE_FASE = dict(FASES)


@dataclass(frozen=True)
class Dato:
    """El dato propio de una etapa. tipo: texto, numero, entero, fechas o calidad."""

    clave: str
    etiqueta: str
    tipo: str
    minimo: float | None = None
    maximo: float | None = None
    unidad: str | None = None


@dataclass(frozen=True)
class Etapa:
    numero: int
    nombre: str
    tipo: str
    fase: str
    en_ruta_seco: bool
    # Las etapas 1, 3 y 4 no se digitan: el sistema las llena con las tandas y sus DOP.
    automatica: bool = False
    # Las etapas 7 y 14 pueden marcarse como "no ocurrió".
    opcional: bool = False
    datos: tuple[Dato, ...] = field(default_factory=tuple)

    @property
    def transporte(self) -> bool:
        return self.tipo == "transporte"


ETAPAS = (
    Etapa(1, "Recepción y pesaje en cancha de acopio", "operacion", "ingreso", True, automatica=True),
    Etapa(
        2,
        "Control de calidad del cacao recibido",
        "inspeccion",
        "ingreso",
        True,
        datos=(Dato("observacion_calidad", "Observación de calidad", "texto"),),
    ),
    Etapa(3, "Registro y codificación del lote", "operacion", "ingreso", True, automatica=True),
    Etapa(4, "Control de trazabilidad y legalidad de origen", "inspeccion", "ingreso", True, automatica=True),
    # Su dato, el tipo de manejo, se llena con el elegido al crear la corrida.
    Etapa(5, "Segregación o rechazo", "operacion", "ingreso", True),
    Etapa(6, "Traslado a cajones de fermentación", "transporte", "fermentacion", False),
    Etapa(7, "Espera de cajón de fermentación disponible", "espera", "fermentacion", False, opcional=True),
    Etapa(8, "Descarga y llenado del cajón", "operacion", "fermentacion", False),
    Etapa(
        9,
        "Fermentación con volteos",
        "operacion",
        "fermentacion",
        False,
        datos=(Dato("fechas_volteo", "Fechas de volteo", "fechas"),),
    ),
    Etapa(
        10,
        "Prueba de corte",
        "inspeccion",
        "fermentacion",
        False,
        datos=(Dato("pct_bien_fermentados", "Granos bien fermentados", "numero", 0, 100, "%"),),
    ),
    Etapa(11, "Traslado a zona de secado", "transporte", "secado", False),
    Etapa(12, "Secado solar con volteos periódicos", "operacion", "secado", False),
    Etapa(
        13,
        "Control de humedad",
        "inspeccion",
        "secado",
        False,
        datos=(Dato("humedad_pct", "Humedad", "numero", 0, 100, "%"),),
    ),
    Etapa(14, "Espera bajo cobertizo por lluvia", "espera", "secado", False, opcional=True),
    Etapa(15, "Traslado a zona de zarandeo", "transporte", "seleccion", True),
    Etapa(16, "Zarandeo y limpieza de impurezas", "operacion", "seleccion", True),
    Etapa(
        17,
        "Clasificación por calibre y calidad",
        "operacion",
        "seleccion",
        True,
        datos=(Dato("calidad_id", "Calidad asignada", "calidad"),),
    ),
    Etapa(
        18,
        "Selección manual de granos defectuosos",
        "operacion",
        "seleccion",
        True,
        datos=(Dato("kg_descartados", "Kilos descartados", "numero", 0, 1_000_000, "kg"),),
    ),
    Etapa(
        19,
        "Pesado del cacao clasificado",
        "operacion",
        "seleccion",
        True,
        datos=(Dato("peso_final_kg", "Peso final", "numero", 0.01, 10_000_000, "kg"),),
    ),
    Etapa(20, "Traslado a zona de envasado", "transporte", "envasado", True),
    Etapa(
        21,
        "Envasado en sacos de yute",
        "operacion",
        "envasado",
        True,
        datos=(Dato("numero_sacos", "Número de sacos", "entero", 1, 1_000_000),),
    ),
    Etapa(22, "Traslado a almacén", "transporte", "envasado", True),
    Etapa(23, "Almacenamiento hasta consolidar el lote de exportación", "almacenamiento", "envasado", True),
)
POR_NUMERO = {e.numero: e for e in ETAPAS}
NUMEROS = tuple(POR_NUMERO)
# Etapas fijas: la cooperativa no las desactiva en su plantilla (decisión del equipo del 2026-10-06). Las
# llena el sistema (1, 3 y 4) o guardan lo que se usa al consolidar (13, 17, 19 y 21). La base lo impide.
FIJAS = (1, 3, 4, 13, 17, 19, 21)

# Métodos sugeridos de cada etapa (decisión del equipo del 2026-10-06: lista fija más "Otro"). La plantilla
# y el registro de la etapa los ofrecen para elegir; si el de la cooperativa no está, se escribe. El primero
# es el que propone la plantilla sugerida. Las etapas 1, 3 y 4 no tienen: su método lo pone el sistema.
# Propuesta de Claude Code, por revisar con el equipo.
_PESAJE = ("Balanza de plataforma", "Balanza electrónica", "Balanza colgante (romana)")
_TRASLADO = ("Carretilla", "Sacos al hombro", "Motocarguero", "Camión")
METODOS: dict[int, tuple[str, ...]] = {
    2: ("Revisión visual de una muestra", "Revisión visual de cada saco"),
    5: ("Separación según el tipo de manejo", "Separación por productor", "Rechazo del cacao que no cumple"),
    6: _TRASLADO,
    7: ("Baldes o tinas tapadas", "Sacos en patio techado"),
    8: ("Llenado manual con baldes", "Descarga directa desde los sacos"),
    9: (
        "Cajones de madera escalonados",
        "Cajones de madera en una fila",
        "Sacos de yute",
        "Montón cubierto con hojas de plátano",
    ),
    10: ("Corte de 100 granos", "Corte de 50 granos", "Guillotina de 50 granos"),
    11: _TRASLADO,
    12: (
        "Tendal solar de cemento",
        "Secador solar con techo (marquesina)",
        "Camas o parihuelas de madera",
        "Secador mecánico",
    ),
    13: ("Medidor electrónico de humedad", "Prueba manual (crujido del grano)"),
    14: ("Cobertizo techado", "Cubierto con plástico"),
    15: _TRASLADO,
    16: ("Zaranda manual", "Zarandeadora mecánica"),
    17: ("Clasificación manual por tamaño y aspecto", "Clasificadora mecánica por mallas"),
    18: ("Selección manual en mesa", "Selección manual en faja"),
    19: _PESAJE,
    20: _TRASLADO,
    21: ("Sacos de yute nuevos, cosidos a mano", "Sacos de yute nuevos, cosidos a máquina"),
    22: _TRASLADO,
    23: ("Sacos sobre parihuelas en almacén ventilado", "Sacos sobre parihuelas, separados de la pared"),
}

# Plantilla sugerida: el tipo de lugar de la cooperativa que toma cada etapa (un traslado toma el de su
# destino) y su duración habitual en horas. Sin duración, la etapa no tiene una habitual: las automáticas,
# las que pueden no ocurrir y el almacenamiento, que dura hasta que el grano sale en un lote.
LUGAR_SUGERIDO = {n: "cancha_acopio" if n <= 5 else "almacen" if n >= 22 else "planta" for n in NUMEROS}
HORAS_SUGERIDAS = {
    2: "0.5",
    5: "0.5",
    6: "0.5",
    8: "1",
    9: "144",  # 6 días
    10: "0.5",
    11: "0.5",
    12: "120",  # 5 días
    13: "0.5",
    15: "0.5",
    16: "2",
    17: "2",
    18: "4",
    19: "0.5",
    20: "0.5",
    21: "1",
    22: "0.5",
}
AUTOMATICAS = tuple(e.numero for e in ETAPAS if e.automatica)
# Datos que deben estar para consolidar (comprobación al consolidar, regla 3), por ruta.
OBLIGATORIOS_AL_CONSOLIDAR = {
    "completa": ((19, "peso_final_kg"), (13, "humedad_pct"), (17, "calidad_id"), (21, "numero_sacos")),
    "seco": ((19, "peso_final_kg"), (17, "calidad_id"), (21, "numero_sacos")),
}


def aplica(etapa: Etapa, ruta: str) -> bool:
    return ruta == "completa" or etapa.en_ruta_seco

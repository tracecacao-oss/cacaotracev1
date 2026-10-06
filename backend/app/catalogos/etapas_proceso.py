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
AUTOMATICAS = tuple(e.numero for e in ETAPAS if e.automatica)
# Datos que deben estar para consolidar (comprobación al consolidar, regla 3), por ruta.
OBLIGATORIOS_AL_CONSOLIDAR = {
    "completa": ((19, "peso_final_kg"), (13, "humedad_pct"), (17, "calidad_id"), (21, "numero_sacos")),
    "seco": ((19, "peso_final_kg"), (17, "calidad_id"), (21, "numero_sacos")),
}


def aplica(etapa: Etapa, ruta: str) -> bool:
    return ruta == "completa" or etapa.en_ruta_seco

"""Tabla de convergencia (adenda de la Parte 4, refuerzo D).

Una fila por conjunto de datos, no por API: si el mismo conjunto llega por Whisp y por GFW, se cuenta
una vez y la fila dice por dónde se consultó. Columnas: "Al 31 de diciembre de 2020" y "Después de
2020"; una celda queda vacía si ese conjunto no mide esa pregunta. Debajo, una frase de conteo hecha por
plantilla. No hay puntaje, semáforo ni conclusión: solo se cuenta.

Un conjunto "registra bosque en 2020" si alguna de sus medidas de bosque alcanza
UMBRAL_BOSQUE_2020_PCT del área de la parcela; "registra cambios" si alguna de sus medidas de cambio es
mayor que cero. Se usa el último análisis completado de cada fuente sobre la geometría actual.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.catalogos.conjuntos_datos import CONJUNTOS
from app.models import AnalisisCobertura

VIA = {"whisp": "Whisp", "gfw": "GFW", "mapbiomas": "MapBiomas"}
# Indicadores de GFW y MapBiomas: (clave, conjunto, pregunta, unidad, mide_bosque)
INDICADORES = {
    "gfw": (
        ("bosque_natural_2020_ha", "sbtn_natural_lands", "estado_2020", "ha", True),
        ("alertas_desde_2021", "gfw_integrated_alerts", "cambio_posterior", "alertas", False),
        ("perdida_ha_total", "umd_gfc", "cambio_posterior", "ha", False),
        ("alertas_dist_desde_2021", "umd_glad_dist", "cambio_posterior", "alertas", False),
    ),
    "mapbiomas": (
        ("bosque_2020_ha", "mapbiomas_peru_c3", "estado_2020", "ha", True),
        ("cambio_bosque_a_no_bosque_ha", "mapbiomas_peru_c3", "cambio_posterior", "ha", False),
    ),
}
FRASE = (
    "Conjuntos de datos consultados: {n}. Registran bosque en 2020: {a} de {b} que lo miden. "
    "Registran cambios después de 2020: {c} de {d} que lo miden."
)


@dataclass
class Medida:
    via: str
    nombre: str
    valor: Any
    unidad: str | None
    mide_bosque: bool = False
    serie: bool = False


@dataclass
class Fila:
    conjunto: str
    nombre: str
    fechas: dict[str, datetime] = field(default_factory=dict)
    al_2020: list[Medida] = field(default_factory=list)
    despues_2020: list[Medida] = field(default_factory=list)
    registra_bosque_2020: bool | None = None
    registra_cambio: bool | None = None

    @property
    def vias(self) -> list[str]:
        return list(self.fechas)


# Decisión del equipo del 2026-10-05 (adenda, 7.2 reglas 1 y 3): hubo bosque en la parcela el 31/12/2020
# cuando al menos 3 conjuntos de datos lo registran. Un mapa solo puede ver árboles sueltos (sombra,
# frutales, cercos vivos): se muestra como dato, pero no pide visita.
MAPAS_MINIMOS_BOSQUE_2020 = 3


@dataclass
class Convergencia:
    filas: list[Fila]
    umbral_pct: float
    area_ha: float | None

    def _conteo(self, atributo: str) -> tuple[int, int]:
        medidas = [getattr(f, atributo) for f in self.filas if getattr(f, atributo) is not None]
        return sum(medidas), len(medidas)

    @property
    def conteos(self) -> dict[str, int]:
        a, b = self._conteo("registra_bosque_2020")
        c, d = self._conteo("registra_cambio")
        return {
            "consultados": len(self.filas),
            "bosque_registran": a,
            "bosque_miden": b,
            "cambio_registran": c,
            "cambio_miden": d,
        }

    @property
    def frase(self) -> str:
        k = self.conteos
        return FRASE.format(
            n=k["consultados"],
            a=k["bosque_registran"],
            b=k["bosque_miden"],
            c=k["cambio_registran"],
            d=k["cambio_miden"],
        )

    @property
    def registran_bosque_2020(self) -> list[str]:
        return [f.nombre for f in self.filas if f.registra_bosque_2020]

    @property
    def hubo_bosque_2020(self) -> bool:
        return len(self.registran_bosque_2020) >= MAPAS_MINIMOS_BOSQUE_2020

    @property
    def discrepan(self) -> dict[str, bool]:
        """Dos conjuntos responden distinto a la misma pregunta (para el hallazgo `conjuntos_discrepan`)."""
        bosque = {f.registra_bosque_2020 for f in self.filas if f.registra_bosque_2020 is not None}
        cambio = {f.registra_cambio for f in self.filas if f.registra_cambio is not None}
        return {"estado_2020": len(bosque) > 1, "cambio_posterior": len(cambio) > 1}


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return None
    return float(valor)


def _medidas(analisis: AnalisisCobertura) -> list[tuple[str, str, Medida]]:
    """(conjunto, pregunta, medida) de un análisis completado."""
    via = VIA.get(analisis.fuente, analisis.fuente)
    indicadores = analisis.indicadores or {}
    salida = []
    if analisis.fuente == "whisp":
        for capa in indicadores.get("capas", []):
            if capa.get("conjunto_de_datos") and capa.get("pregunta") in ("estado_2020", "cambio_posterior"):
                salida.append(
                    (
                        capa["conjunto_de_datos"],
                        capa["pregunta"],
                        Medida(
                            via,
                            capa["nombre"],
                            capa["valor"],
                            capa.get("unidad"),
                            bool(capa.get("mide_bosque")),
                            bool(capa.get("serie")),
                        ),
                    )
                )
    for clave, conjunto, pregunta, unidad, mide_bosque in INDICADORES.get(analisis.fuente, ()):
        if clave in indicadores:
            salida.append((conjunto, pregunta, Medida(via, clave, indicadores[clave], unidad, mide_bosque)))
    return salida


def calcular(
    analisis: list[AnalisisCobertura], area_ha: float | None, umbral_pct: float, *, es_punto: bool = False
) -> Convergencia:
    """`analisis`: el último completado de cada fuente sobre la geometría actual."""
    filas: dict[str, Fila] = {}
    for a in analisis:
        for conjunto, pregunta, medida in _medidas(a):
            fila = filas.setdefault(conjunto, Fila(conjunto, CONJUNTOS.get(conjunto, conjunto)))
            fila.fechas.setdefault(medida.via, a.completado_en)
            (fila.al_2020 if pregunta == "estado_2020" else fila.despues_2020).append(medida)
            # Whisp analiza el punto tal cual: para un punto, cualquier valor distinto de cero cuenta.
            punto = es_punto and not a.es_aproximacion

            if pregunta == "estado_2020" and medida.mide_bosque:
                valor = _numero(medida.valor)
                if valor is not None:
                    if punto:
                        alcanza = valor > 0
                    elif medida.unidad == "percent":
                        alcanza = valor >= umbral_pct
                    else:
                        alcanza = bool(area_ha) and valor >= area_ha * umbral_pct / 100
                    fila.registra_bosque_2020 = bool(fila.registra_bosque_2020) or alcanza
            elif pregunta == "cambio_posterior":
                valor = _numero(medida.valor)
                if valor is not None:
                    fila.registra_cambio = bool(fila.registra_cambio) or valor > 0
    return Convergencia(sorted(filas.values(), key=lambda f: f.nombre), umbral_pct, area_ha)

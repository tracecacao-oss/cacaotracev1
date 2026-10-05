"""Fuentes del análisis de cobertura forestal. Cada una vive en su módulo con la misma interfaz:
agregar una fuente no toca el resto del sistema.

A las fuentes solo se envía la geometría y un identificador opaco: nunca DNI, nombres ni datos de
la cooperativa. La cola guarda la respuesta completa (`consultar`) antes de interpretarla
(`interpretar`).
"""

from typing import Any, Protocol


class ErrorFuente(Exception):
    """La fuente falló. `espera` (segundos) la pide la propia fuente, por ejemplo con Retry-After."""

    def __init__(self, detalle: str, *, espera: float | None = None):
        super().__init__(detalle)
        self.detalle = detalle
        self.espera = espera


class Fuente(Protocol):
    codigo: str  # "whisp", "gfw" o "mapbiomas"
    nombre: str
    # True si la fuente solo analiza polígonos: un punto se le envía como círculo con el área declarada.
    requiere_poligono: bool

    @property
    def configurada(self) -> bool: ...

    def consultar(self, geometria: dict, identificador: str) -> bytes:
        """La respuesta completa de la fuente, tal cual, en JSON. Lanza ErrorFuente si falla."""

    def interpretar(self, contenido: bytes) -> tuple[str | None, dict[str, Any], str | None]:
        """(resultado_fuente sin traducir, indicadores, versión informada por la fuente)."""

    def requiere_revision(
        self, resultado: str | None, indicadores: dict[str, Any], *, hubo_bosque_2020: bool = True
    ) -> bool:
        """True si lo que dice la fuente pide que una persona mire la parcela. `hubo_bosque_2020`: algún
        conjunto de datos registra bosque en la parcela el 31/12/2020 (sin ese dato se supone que sí)."""

    def texto(self, resultado: str | None, indicadores: dict[str, Any]) -> str | None:
        """Resultado para mostrar, siempre precedido por el nombre de la fuente."""

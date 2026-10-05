"""Fuentes en uso. crear_app las fija al arrancar; las pruebas fijan las suyas, con HTTP simulado."""

from app.services.fuentes import Fuente

_fuentes: dict[str, Fuente] = {}


def fijar(fuentes: dict[str, Fuente]) -> None:
    _fuentes.clear()
    _fuentes.update(fuentes)


def actuales() -> dict[str, Fuente]:
    return _fuentes


def construir(settings) -> dict[str, Fuente]:
    """Las fuentes reales, con las claves de las variables de entorno."""
    from app.services.fuentes.gfw import GFW
    from app.services.fuentes.whisp import Whisp

    def clave(valor):
        return valor.get_secret_value() if valor else None

    return {"whisp": Whisp(clave(settings.whisp_api_key)), "gfw": GFW(clave(settings.gfw_api_key))}

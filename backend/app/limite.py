"""Límite de peticiones por dirección IP para los endpoints públicos (Parte 5): 30 por minuto.

Vive en la memoria del proceso: Render corre una sola instancia de la API. Cada aplicación tiene su
propio limitador (app.state.limite_publico), así las pruebas no se pisan entre sí.

La IP sale de CF-Connecting-IP, que Cloudflare (delante de Render) escribe con la dirección que se conectó.
X-Forwarded-For no sirve para limitar: Cloudflare agrega su valor al final de lo que mande quien llama,
así que el primero se puede inventar (developers.cloudflare.com/fundamentals/reference/http-headers,
consultado el 2026-10-05). Sin esa cabecera, como en local, se usa la misma IP que la auditoría.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.contexto import _ip
from app.errores import error_api

MAXIMO_POR_MINUTO = 30
VENTANA = 60.0


class LimitePorIp:
    def __init__(self, maximo: int = MAXIMO_POR_MINUTO, ventana: float = VENTANA, reloj=time.monotonic):
        self.maximo, self.ventana, self.reloj = maximo, ventana, reloj
        self._pedidos: dict[str, deque[float]] = defaultdict(deque)
        self._cerrojo = threading.Lock()

    def comprobar(self, ip: str | None) -> None:
        clave = ip or "desconocida"
        ahora = self.reloj()
        with self._cerrojo:
            pedidos = self._pedidos[clave]
            while pedidos and ahora - pedidos[0] >= self.ventana:
                pedidos.popleft()
            if len(pedidos) >= self.maximo:
                raise error_api(
                    429,
                    "demasiadas_peticiones",
                    "Demasiadas consultas seguidas. Espera un minuto y vuelve a intentar.",
                )
            pedidos.append(ahora)
            if len(self._pedidos) > 10_000:  # no crece sin fin con direcciones distintas
                for vieja in [k for k, v in self._pedidos.items() if not v or ahora - v[-1] >= self.ventana]:
                    del self._pedidos[vieja]


def ip_del_cliente(request: Request) -> str | None:
    return request.headers.get("cf-connecting-ip") or _ip(request)


def limite_publico(request: Request) -> None:
    request.app.state.limite_publico.comprobar(ip_del_cliente(request))

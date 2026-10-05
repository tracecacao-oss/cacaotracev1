"""MapBiomas Perú, Colección 3: uso del suelo de la parcela, año por año (adenda de la Parte 4, refuerzo C).

Un GeoTIFF de 30 m por año, en storage.googleapis.com (público, sin clave). Se lee solo la ventana de la
parcela con peticiones por rango (app/services/fuentes/cog.py). Se cuentan los píxeles cuyo centro cae
dentro de la parcela y el área de cada uno se calcula según su latitud.

No entrega un valor de riesgo: `resultado_fuente` queda nulo. Lo ocurrido después del último año cubierto
no lo ve esta fuente.
"""

import json
import math
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import httpx
import numpy as np
import shapely
from shapely.geometry import shape

from app.catalogos import mapbiomas_peru_c3 as leyenda
from app.services.fuentes import ErrorFuente
from app.services.fuentes.cog import Cabecera, ErrorCog, LectorCog

URL = (
    "https://storage.googleapis.com/mapbiomas-public/initiatives/peru/collection_3/LULC/"
    "peru_collection3_integration_v1-classification_{anio}.tif"
)
COLECCION = "MapBiomas Perú, Colección 3"
TIEMPO_MAXIMO = 60
POCOS_PIXELES = 10
RADIO_TIERRA_M = 6_371_007.181  # radio de la esfera de igual área del elipsoide WGS 84


def _area_pixeles_ha(cab: Cabecera, fila0: int, filas: int) -> np.ndarray:
    """Área de un píxel de cada fila, en hectáreas, según su latitud."""
    bordes = cab.y0 - (fila0 + np.arange(filas + 1)) * cab.dy
    seno = np.sin(np.radians(bordes))
    return RADIO_TIERRA_M**2 * math.radians(cab.dx) * (seno[:-1] - seno[1:]) / 10_000


class MapBiomas:
    codigo = "mapbiomas"
    nombre = "MapBiomas Perú"
    requiere_poligono = True

    def __init__(self, activa: bool, anio_inicial: int, anio_final: int, cliente: httpx.Client | None = None):
        self._activa = activa
        self.anio_inicial, self.anio_final = anio_inicial, anio_final
        self._cliente_propio = cliente

    @property
    def _cliente(self) -> httpx.Client:
        if self._cliente_propio is None:
            self._cliente_propio = httpx.Client(timeout=TIEMPO_MAXIMO)
        return self._cliente_propio

    @property
    def configurada(self) -> bool:
        return self._activa

    @property
    def anios(self) -> list[int]:
        # 2020 siempre: la adenda pide el estado al 31 de diciembre de 2020.
        return sorted(set(range(self.anio_inicial, self.anio_final + 1)) | {2020})

    def consultar(self, geometria: dict, identificador: str) -> bytes:
        # MapBiomas no recibe nada: se leen sus archivos públicos. El identificador no sale del sistema.
        parcela = shape(geometria)
        lector = LectorCog(self._cliente)
        evidencia: dict[str, Any] = {
            "consultado_en": datetime.now(UTC).isoformat(timespec="seconds"),
            "coleccion": COLECCION,
            "anios": {},
        }
        mascara = None
        valores_por_anio: dict[int, np.ndarray] = {}
        try:
            for anio in self.anios:
                url = URL.format(anio=anio)
                cab = lector.cabecera(url)
                minx, miny, maxx, maxy = parcela.bounds
                col0 = math.floor((minx - cab.x0) / cab.dx)
                col1 = math.floor((maxx - cab.x0) / cab.dx) + 1
                fila0 = math.floor((cab.y0 - maxy) / cab.dy)
                fila1 = math.floor((cab.y0 - miny) / cab.dy) + 1
                ventana = lector.ventana(cab, col0, fila0, col1, fila1)
                if mascara is None:
                    filas, cols = ventana.shape
                    lon = cab.x0 + (max(col0, 0) + np.arange(cols) + 0.5) * cab.dx
                    lat = cab.y0 - (max(fila0, 0) + np.arange(filas) + 0.5) * cab.dy
                    x, y = np.meshgrid(lon, lat)
                    mascara = shapely.contains_xy(parcela, x, y)
                    area_fila = _area_pixeles_ha(cab, max(fila0, 0), filas)
                    area = np.broadcast_to(area_fila[:, None], ventana.shape)[mascara]
                    rejilla = (cab.x0, cab.y0, cab.dx, cab.dy)
                elif (cab.x0, cab.y0, cab.dx, cab.dy) != rejilla or ventana.shape != mascara.shape:
                    raise ErrorFuente(
                        f"El mapa de MapBiomas de {anio} no usa la misma rejilla que los demás."
                    )
                valores = ventana[mascara]
                valores_por_anio[anio] = valores
                hectareas = Counter()
                for clase, a in zip(valores.tolist(), area.tolist(), strict=True):
                    hectareas[clase] += a
                evidencia["anios"][str(anio)] = {
                    "url": url,
                    "cabeceras": cab.version,
                    "pixeles": {str(k): int(v) for k, v in sorted(Counter(valores.tolist()).items())},
                    "hectareas": {str(k): round(v, 6) for k, v in sorted(hectareas.items())},
                }
        except ErrorCog as exc:
            raise ErrorFuente(f"MapBiomas: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ErrorFuente("MapBiomas no respondió en 60 segundos.") from exc
        except httpx.HTTPError as exc:
            raise ErrorFuente(f"No se pudo conectar con MapBiomas ({type(exc).__name__}).") from exc

        ultimo = max(self.anios)
        evidencia["pixeles_en_parcela"] = int(mascara.sum()) if mascara is not None else 0
        evidencia["peticiones"] = lector.peticiones
        evidencia["bytes_leidos"] = lector.bytes_leidos
        # Transición píxel a píxel de 2020 al último año: de ahí sale el paso de bosque a otra clase.
        transicion: Counter = Counter()
        area_transicion: Counter = Counter()
        for de, a, ha in zip(
            valores_por_anio[2020].tolist(), valores_por_anio[ultimo].tolist(), area.tolist(), strict=True
        ):
            transicion[f"{de}->{a}"] += 1
            area_transicion[f"{de}->{a}"] += ha
        evidencia["transicion"] = {
            "desde": 2020,
            "hasta": ultimo,
            "pixeles": dict(sorted(transicion.items())),
            "hectareas": {k: round(v, 6) for k, v in sorted(area_transicion.items())},
        }
        return json.dumps(evidencia, ensure_ascii=False).encode()

    def interpretar(self, contenido: bytes) -> tuple[str | None, dict[str, Any], str | None]:
        evidencia = json.loads(contenido)
        anios = {
            anio: {int(k): v for k, v in datos["hectareas"].items()}
            for anio, datos in evidencia["anios"].items()
        }
        en_2020 = anios["2020"]
        ultimo = max(anios, key=int)
        predominante = max(en_2020, key=en_2020.get) if en_2020 else None
        cambio = sum(
            ha
            for clave, ha in evidencia["transicion"]["hectareas"].items()
            if int(clave.split("->")[0]) in leyenda.BOSQUE and int(clave.split("->")[1]) not in leyenda.BOSQUE
        )
        pixeles = evidencia["pixeles_en_parcela"]
        codigos = sorted({c for por_clase in anios.values() for c in por_clase})
        indicadores = {
            "clase_predominante_2020": leyenda.nombre(predominante) if predominante is not None else None,
            "bosque_2020_ha": round(sum(ha for c, ha in en_2020.items() if c in leyenda.BOSQUE), 4),
            "cambio_bosque_a_no_bosque_ha": round(cambio, 4),
            "anios": {
                a: {str(c): round(ha, 4) for c, ha in sorted(por_clase.items())}
                for a, por_clase in anios.items()
            },
            "clases": {str(c): leyenda.nombre(c) for c in codigos},
            "clases_bosque": [str(c) for c in codigos if c in leyenda.BOSQUE],
            "ultimo_anio": int(ultimo),
            "pixeles": pixeles,
            "pocos_pixeles": pixeles < POCOS_PIXELES,
        }
        return None, indicadores, f"{evidencia['coleccion']} · hasta {ultimo}"

    def requiere_revision(
        self, resultado: str | None, indicadores: dict[str, Any], *, hubo_bosque_2020: bool = True
    ) -> bool:
        cambio = indicadores.get("cambio_bosque_a_no_bosque_ha")
        return cambio is None or cambio > 0

    def texto(self, resultado: str | None, indicadores: dict[str, Any]) -> str | None:
        clase = indicadores.get("clase_predominante_2020")
        bosque = indicadores.get("bosque_2020_ha")
        cambio = indicadores.get("cambio_bosque_a_no_bosque_ha")
        if clase is None or bosque is None or cambio is None:
            return "MapBiomas Perú: sin resultado"
        return (
            f"MapBiomas Perú: en 2020, clase predominante {clase}; {bosque:g} ha de bosque en 2020; "
            f"{cambio:g} ha pasaron de bosque a otra clase entre 2020 y {indicadores['ultimo_anio']}"
        )

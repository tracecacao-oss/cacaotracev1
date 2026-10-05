"""Global Forest Watch (GFW) Data API: segunda fuente del análisis de cobertura forestal.

Confirmado en su documentación oficial (https://data-api.globalforestwatch.org/openapi.json y la guía
"Query data for a custom geometry", consultadas el 2026-10-05):
- POST /dataset/{conjunto}/{versión}/query/json con {"sql", "geometry"} y el encabezado x-api-key.
- La versión "latest" responde 307 hacia la versión concreta: la versión consultada sale de ahí.
- Las consultas de ráster solo aceptan Polygon o MultiPolygon: un punto se envía como círculo.
- Respuesta: {"data": [...], "status": "success"}.
- gfw_integrated_alerts: alertas integradas de deforestación, campo gfw_integrated_alerts__date.
- umd_tree_cover_loss: pérdida de cobertura arbórea, campos umd_tree_cover_loss__year y area__ha.
  La API no aplica un umbral de densidad por su cuenta; se usa el 30 % de la plataforma de GFW y se
  registra en los indicadores.
"""

import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.services.fuentes import ErrorFuente

BASE = "https://data-api.globalforestwatch.org"
TIEMPO_MAXIMO = 60
DESDE = "2021-01-01"
UMBRAL_DENSIDAD = 30
# Consultas fijas: no llevan ningún dato de entrada; la geometría va aparte, en el cuerpo.
CONSULTAS = {
    "alertas": (
        "gfw_integrated_alerts",
        "SELECT COUNT(*) FROM results WHERE gfw_integrated_alerts__date >= '2021-01-01'",
    ),
    "perdida": (
        "umd_tree_cover_loss",
        "SELECT umd_tree_cover_loss__year, SUM(area__ha) FROM results "
        "WHERE umd_tree_cover_loss__year >= 2021 AND umd_tree_cover_density_2000__percent > 30 "
        "GROUP BY umd_tree_cover_loss__year",
    ),
}


def _version(respuesta: httpx.Response) -> str | None:
    """La versión concreta a la que redirigió "latest"."""
    m = re.search(r"/dataset/[^/]+/([^/]+)/query", str(respuesta.url))
    return m.group(1) if m else None


class GFW:
    codigo = "gfw"
    nombre = "Global Forest Watch"
    requiere_poligono = True

    def __init__(self, clave: str | None, cliente: httpx.Client | None = None):
        self._clave = clave
        self._cliente_propio = cliente

    @property
    def _cliente(self) -> httpx.Client:
        # Se crea al primer uso: armar el contexto TLS cuesta y la mayoría de instancias no consulta nada.
        if self._cliente_propio is None:
            self._cliente_propio = httpx.Client(timeout=TIEMPO_MAXIMO)
        return self._cliente_propio

    @property
    def configurada(self) -> bool:
        return bool(self._clave)

    def _consulta(self, conjunto: str, sql: str, geometria: dict) -> tuple[dict, str | None]:
        try:
            r = self._cliente.post(
                f"{BASE}/dataset/{conjunto}/latest/query/json",
                json={"sql": sql, "geometry": geometria},
                headers={"x-api-key": self._clave},
                timeout=TIEMPO_MAXIMO,
                follow_redirects=True,
            )
        except httpx.TimeoutException as exc:
            raise ErrorFuente("GFW no respondió en 60 segundos.") from exc
        except httpx.HTTPError as exc:
            raise ErrorFuente(f"No se pudo conectar con GFW ({type(exc).__name__}).") from exc
        try:
            datos = r.json()
        except ValueError:
            datos = {}
        if r.status_code == 429:
            raise ErrorFuente("GFW pidió esperar: se alcanzó su límite de peticiones.")
        if r.status_code in (401, 403):
            raise ErrorFuente(f"GFW rechazó la clave ({r.status_code}). Revisa GFW_API_KEY.")
        if r.status_code != 200 or datos.get("status") != "success":
            raise ErrorFuente(
                f"GFW respondió {r.status_code} en {conjunto}: {datos.get('message') or 'sin detalle'}."
            )
        return datos, _version(r)

    def consultar(self, geometria: dict, identificador: str) -> bytes:
        # GFW no recibe identificadores: solo la geometría.
        evidencia: dict[str, Any] = {
            "consultado_en": datetime.now(UTC).isoformat(timespec="seconds"),
            "desde": DESDE,
            "umbral_densidad_2000_porcentaje": UMBRAL_DENSIDAD,
        }
        for clave, (conjunto, sql) in CONSULTAS.items():
            datos, version = self._consulta(conjunto, sql, geometria)
            evidencia[clave] = {"conjunto": conjunto, "version": version, "sql": sql, "respuesta": datos}
        return json.dumps(evidencia, ensure_ascii=False).encode()

    def interpretar(self, contenido: bytes) -> tuple[str | None, dict[str, Any], str | None]:
        evidencia = json.loads(contenido)
        # Estricto a propósito: si una columna no viene con el nombre esperado, la interpretación falla y
        # la parcela pide revisión, en vez de leerse como "cero alertas".
        (fila_alertas,) = evidencia["alertas"]["respuesta"]["data"]
        alertas = int(fila_alertas["count"])
        perdida = {
            str(f["umd_tree_cover_loss__year"]): float(
                Decimal(str(f["area__ha"] or 0)).quantize(Decimal("0.0001"))
            )
            for f in evidencia["perdida"]["respuesta"]["data"]
        }
        indicadores = {
            "alertas_desde_2021": alertas,
            "perdida_ha_por_anio": perdida,
            "perdida_ha_total": round(sum(perdida.values()), 4),
            "desde": evidencia["desde"],
            "hasta": evidencia["consultado_en"][:10],
            "umbral_densidad_2000_porcentaje": evidencia["umbral_densidad_2000_porcentaje"],
        }
        version = " · ".join(
            f"{evidencia[c]['conjunto']} {evidencia[c]['version']}"
            for c in ("alertas", "perdida")
            if evidencia[c]["version"]
        )
        # GFW entrega cifras, no un veredicto: no hay "resultado de la fuente".
        return None, indicadores, version or None

    def requiere_revision(self, resultado: str | None, indicadores: dict[str, Any]) -> bool:
        # Sin cifras (respuesta que no se pudo interpretar) también pide que una persona mire la parcela.
        alertas = indicadores.get("alertas_desde_2021")
        perdida = indicadores.get("perdida_ha_total")
        return alertas is None or perdida is None or alertas > 0 or perdida > 0

    def texto(self, resultado: str | None, indicadores: dict[str, Any]) -> str | None:
        alertas = indicadores.get("alertas_desde_2021")
        perdida = indicadores.get("perdida_ha_total")
        if alertas is None or perdida is None:
            return "GFW: sin resultado"
        if alertas == 0 and perdida == 0:
            return "GFW: sin alertas ni pérdida registrada desde 2021"
        return f"GFW: {alertas} alertas y {perdida:g} ha de pérdida desde 2021"

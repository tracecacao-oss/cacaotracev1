"""Whisp, de FAO: fuente principal del análisis de cobertura forestal.

Confirmado en su documentación oficial (OpenAPI 2.3.0 en https://whisp.openforis.org/api/openapi.json,
consultada el 2026-10-05):
- POST /api/submit/geojson con el encabezado x-api-key; el cuerpo es el FeatureCollection, con
  analysisOptions opcional. Acepta puntos y polígonos.
- Sin "async", la respuesta llega en la misma petición (hasta 60 s): 200 con code
  "analysis_completed" y el FeatureCollection de resultados en "data".
- El riesgo para cultivos permanentes, que incluye cacao, es risk_pcrop: "low", "more_info_needed"
  o "high". Lo sustentan Ind_01_treecover, Ind_02_commodities, Ind_03_disturbance_before_2020 e
  Ind_04_disturbance_after_2020 ("yes" o "no").
- La versión viene en properties.whisp_processing_metadata.whisp_version.
- 429 trae los segundos de espera en el mensaje; no hay encabezado Retry-After.
"""

import json
import re
from typing import Any

import httpx

from app.catalogos import capas_whisp
from app.services.fuentes import ErrorFuente

URL = "https://whisp.openforis.org/api/submit/geojson"
TIEMPO_MAXIMO = 60
# Lo que se guarda como indicadores, con los nombres de campo de Whisp.
CAMPOS = (
    "risk_pcrop",
    "Ind_01_treecover",
    "Ind_02_commodities",
    "Ind_03_disturbance_before_2020",
    "Ind_04_disturbance_after_2020",
    "EUFO_2020",
    "GLAD_Primary",
    "TMF_undist",
    "Cocoa_ETH",
    "Cocoa_FDaP",
    "Cocoa_2024_FDaP",
    "Area",
    "Unit",
    "Country",
    "In_waterbody",
)
TEXTOS = {
    "low": "Whisp: riesgo bajo",
    "more_info_needed": "Whisp: requiere más información",
    "high": "Whisp: riesgo alto",
}


class Whisp:
    codigo = "whisp"
    nombre = "Whisp (FAO)"
    requiere_poligono = False

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

    def consultar(self, geometria: dict, identificador: str) -> bytes:
        cuerpo = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"id": identificador}, "geometry": geometria}],
            "analysisOptions": {"externalIdColumn": "id", "unitType": "ha"},
        }
        try:
            r = self._cliente.post(
                URL, json=cuerpo, headers={"x-api-key": self._clave}, timeout=TIEMPO_MAXIMO
            )
        except httpx.TimeoutException as exc:
            raise ErrorFuente("Whisp no respondió en 60 segundos.") from exc
        except httpx.HTTPError as exc:
            raise ErrorFuente(f"No se pudo conectar con Whisp ({type(exc).__name__}).") from exc

        try:
            datos = r.json()
        except ValueError:
            datos = {}
        mensaje = datos.get("message") if isinstance(datos, dict) else None
        if r.status_code == 429:
            segundos = re.search(r"(\d+)\s*seconds", mensaje or "")
            raise ErrorFuente(
                "Whisp pidió esperar: se alcanzó su límite de peticiones.",
                espera=float(segundos.group(1)) + 1 if segundos else None,
            )
        if r.status_code == 401:
            raise ErrorFuente("Whisp rechazó la clave (401). Revisa WHISP_API_KEY.")
        if r.status_code != 200 or datos.get("code") != "analysis_completed" or "data" not in datos:
            raise ErrorFuente(
                f"Whisp respondió {r.status_code}: {datos.get('code') or mensaje or 'sin detalle'}."
            )
        return r.content

    def interpretar(self, contenido: bytes) -> tuple[str | None, dict[str, Any], str | None]:
        datos = json.loads(contenido)["data"]
        propiedades = datos["features"][0]["properties"]
        indicadores = {campo: propiedades[campo] for campo in CAMPOS if campo in propiedades}
        # Detalle por capa (adenda de la Parte 4, refuerzo A): qué conjuntos vieron bosque en 2020 y cuáles
        # vieron cambios después.
        indicadores["capas"] = capas_whisp.capas(propiedades)
        metadatos = propiedades.get("whisp_processing_metadata") or {}
        return propiedades.get("risk_pcrop"), indicadores, metadatos.get("whisp_version")

    def requiere_revision(
        self, resultado: str | None, indicadores: dict[str, Any], *, hubo_bosque_2020: bool = True
    ) -> bool:
        # Todo valor distinto de riesgo bajo pide que una persona mire la parcela; también la falta de valor.
        return resultado != "low"

    def texto(self, resultado: str | None, indicadores: dict[str, Any]) -> str | None:
        if resultado is None:
            return "Whisp: sin resultado"
        return TEXTOS.get(resultado, f"Whisp: {resultado}")

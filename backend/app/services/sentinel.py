"""Cliente de Sentinel-2 L2A por Copernicus Data Space (adenda 2 de la Parte 4).

Usa las APIs de Sentinel Hub de Copernicus (documentación revisada el 2026-10-05, la misma con que corrió
backend/scripts/check_imagenes.py):
- token OAuth2 de credenciales de cliente; se reutiliza hasta poco antes de vencer, porque pedir tokens
  tiene límite;
- Statistical API: por cada día con escena, la fracción de la parcela (con su margen) cubierta por nube o
  sombra según la clasificación de escena (SCL), a 10 m;
- Catalog API: el identificador y el satélite de la escena elegida;
- Process API: la imagen en color natural y en falso color infrarrojo, en PNG.

Cada respuesta trae en `x-processingunits-spent` las unidades de procesamiento (PU) que consumió; el
cliente las suma para la cuota del mes. Solo se envía la geometría: ningún dato de la parcela ni del
productor.
"""

import math
import time
from dataclasses import dataclass, field
from datetime import date

import httpx

IDENTIDAD = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOGO = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
ESTADISTICA = "https://sh.dataspace.copernicus.eu/statistics/v1"
PROCESO = "https://sh.dataspace.copernicus.eu/process/v1"
CRS_4326 = "http://www.opengis.net/def/crs/EPSG/0/4326"
COLECCION = "sentinel-2-l2a"
RESOLUCION_M = 10
CABECERA_PU = "x-processingunits-spent"
# Atribución que exige el aviso legal de los datos Sentinel para productos modificados.
ATRIBUCION = "Contains modified Copernicus Sentinel data {anio}"

# Nubes (3 sombra, 8 y 9 nube de probabilidad media y alta, 10 cirro); 0 sin dato y 1 defectuoso no cuentan.
EVALSCRIPT_NUBES = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["SCL", "dataMask"] }],
    output: [{ id: "nubes", bands: 1 }, { id: "dataMask", bands: 1 }]
  };
}
function evaluatePixel(s) {
  const valido = s.dataMask === 1 && s.SCL !== 0 && s.SCL !== 1 ? 1 : 0;
  return { nubes: [[3, 8, 9, 10].includes(s.SCL) ? 1 : 0], dataMask: [valido] };
}"""

EVALSCRIPTS = {
    "natural": """//VERSION=3
function setup() { return { input: ["B02", "B03", "B04"], output: { bands: 3 } }; }
function evaluatePixel(s) { return [2.5 * s.B04, 2.5 * s.B03, 2.5 * s.B02]; }""",
    "infrarrojo": """//VERSION=3
function setup() { return { input: ["B03", "B04", "B08"], output: { bands: 3 } }; }
function evaluatePixel(s) { return [2.5 * s.B08, 2.5 * s.B04, 2.5 * s.B03]; }""",
}


class ErrorSentinel(Exception):
    """La consulta a Copernicus falló. `detalle` se guarda en la imagen para mostrarlo."""

    def __init__(self, detalle: str):
        super().__init__(detalle)
        self.detalle = detalle


@dataclass
class Medida:
    """Nubosidad de un día sobre la parcela con su margen."""

    nubes_pct: float | None
    sin_dato: int  # píxeles sin dato: más que el mínimo indica que la parcela no está completa en la escena


@dataclass
class Escena:
    identificador: str
    satelite: str | None


@dataclass
class Consumo:
    pu: float = 0.0
    peticiones: int = 0
    detalle: list[float] = field(default_factory=list)


class Sentinel:
    def __init__(self, client_id: str | None, client_secret: str | None, http: httpx.Client | None = None):
        self.client_id, self.client_secret = client_id, client_secret
        self.http = http or httpx.Client(timeout=httpx.Timeout(120, connect=20))
        self._token: str | None = None
        self._vence = 0.0

    @property
    def configurada(self) -> bool:
        return bool(self.client_id and self.client_secret)

    # ---------- HTTP ----------

    def _token_vigente(self) -> str:
        if self._token and time.monotonic() < self._vence:
            return self._token
        try:
            r = self.http.post(
                IDENTIDAD,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
        except httpx.HTTPError as exc:
            raise ErrorSentinel(f"No se pudo conectar con Copernicus: {type(exc).__name__}") from exc
        if r.status_code != 200:
            raise ErrorSentinel(f"Copernicus no entregó el token (HTTP {r.status_code}).")
        datos = r.json()
        self._token = datos["access_token"]
        self._vence = time.monotonic() + max(60, int(datos.get("expires_in", 300)) - 60)
        return self._token

    def _post(self, url: str, cuerpo: dict, consumo: Consumo) -> httpx.Response:
        for _ in range(5):
            try:
                r = self.http.post(
                    url, json=cuerpo, headers={"Authorization": f"Bearer {self._token_vigente()}"}
                )
            except httpx.HTTPError as exc:
                raise ErrorSentinel(f"No se pudo conectar con Copernicus: {type(exc).__name__}") from exc
            if r.status_code == 429:  # Retry-After viene en milisegundos
                time.sleep(min(60.0, int(r.headers.get("retry-after", "2000")) / 1000))
                continue
            if r.status_code == 401:  # token vencido antes de lo previsto
                self._token = None
                continue
            break
        consumo.peticiones += 1
        if r.status_code // 100 == 2:
            try:
                pu = float(r.headers.get(CABECERA_PU, "0"))
            except ValueError:
                pu = 0.0
            consumo.pu += pu
            consumo.detalle.append(pu)
        return r

    # ---------- Consultas ----------

    def nubes(
        self, geometria: dict, desde: date, hasta: date, lat0: float, consumo: Consumo
    ) -> dict[date, Medida]:
        """Por cada día con escena: fracción de la parcela con su margen cubierta por nube o sombra."""
        cuerpo = {
            "input": {
                "bounds": {"geometry": geometria, "properties": {"crs": CRS_4326}},
                "data": [{"type": COLECCION, "dataFilter": {"mosaickingOrder": "leastRecent"}}],
            },
            "aggregation": {
                "timeRange": {"from": f"{desde}T00:00:00Z", "to": f"{hasta}T23:59:59Z"},
                "aggregationInterval": {"of": "P1D"},
                "evalscript": EVALSCRIPT_NUBES,
                "resx": RESOLUCION_M / (111_320 * math.cos(math.radians(lat0))),
                "resy": RESOLUCION_M / 111_320,
            },
        }
        r = self._post(ESTADISTICA, cuerpo, consumo)
        if r.status_code != 200:
            raise ErrorSentinel(f"Copernicus no midió la nubosidad (HTTP {r.status_code}).")
        medidas: dict[date, Medida] = {}
        for intervalo in r.json().get("data", []):
            if intervalo.get("error"):
                continue
            stats = intervalo["outputs"]["nubes"]["bands"]["B0"]["stats"]
            if not stats.get("sampleCount"):
                continue
            media = stats.get("mean")
            medidas[date.fromisoformat(intervalo["interval"]["from"][:10])] = Medida(
                nubes_pct=None if media in (None, "NaN") else round(100 * float(media), 2),
                sin_dato=int(stats.get("noDataCount") or 0),
            )
        return medidas

    def escena(self, geometria: dict, dia: date, consumo: Consumo) -> Escena:
        """Identificador y satélite de la escena de ese día (la parcela cae en una sola pasada)."""
        cuerpo = {
            "collections": [COLECCION],
            "datetime": f"{dia}T00:00:00Z/{dia}T23:59:59Z",
            "intersects": geometria,
            "limit": 5,
            "fields": {"include": ["id", "properties.platform"]},
        }
        r = self._post(CATALOGO, cuerpo, consumo)
        if r.status_code == 200 and r.json().get("features"):
            item = r.json()["features"][0]
            plataforma = (item.get("properties") or {}).get("platform")
            return Escena(item["id"], _satelite(plataforma))
        return Escena(f"{COLECCION}/{dia}", None)

    def imagen(
        self,
        bbox: tuple[float, float, float, float],
        dia: date,
        version: str,
        tamano: tuple[int, int],
        consumo: Consumo,
    ) -> bytes:
        ancho, alto = tamano
        cuerpo = {
            "input": {
                "bounds": {"bbox": list(bbox), "properties": {"crs": CRS_4326}},
                "data": [
                    {
                        "type": COLECCION,
                        "dataFilter": {
                            "timeRange": {"from": f"{dia}T00:00:00Z", "to": f"{dia}T23:59:59Z"},
                            "mosaickingOrder": "mostRecent",
                        },
                    }
                ],
            },
            "output": {
                "width": ancho,
                "height": alto,
                "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
            },
            "evalscript": EVALSCRIPTS[version],
        }
        r = self._post(PROCESO, cuerpo, consumo)
        if r.status_code != 200 or not r.content.startswith(b"\x89PNG"):
            raise ErrorSentinel(f"Copernicus no entregó la imagen del {dia:%d/%m/%Y} (HTTP {r.status_code}).")
        return r.content


def _satelite(plataforma: str | None) -> str | None:
    """ "sentinel-2b" del catálogo se muestra como "Sentinel-2B"."""
    if not plataforma:
        return None
    if plataforma.lower().startswith("sentinel-"):
        return "Sentinel-" + plataforma[len("sentinel-") :].upper()
    return plataforma

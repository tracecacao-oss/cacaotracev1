"""Comprobación de viabilidad de las imágenes satelitales (adenda 2 de la Parte 4, sección 4).

Contra los servicios reales y con la parcela ficticia de tests/datos/whisp_respuesta_real.json:
1. Que la cuenta de Copernicus entrega una imagen de Sentinel-2 de 2020 para esa parcela.
2. Cuántas unidades de procesamiento (PU) consume el juego completo de una parcela.
3. Que la nubosidad se puede medir sobre la parcela (con un margen), no solo sobre la escena completa.
4. Que Esri World Imagery Wayback devuelve versiones y fechas de captura para ese lugar.

Si fallan el 1 o el 3, hay que detenerse e informar al equipo. Si falla el 4, se construye sin Wayback.

Las credenciales se leen de COPERNICUS_CLIENT_ID y COPERNICUS_CLIENT_SECRET o, si faltan, se piden por
teclado sin mostrarse. Nunca se escriben en ningún archivo ni se imprimen. Las imágenes de muestra se
guardan fuera del repositorio, en una carpeta temporal que el script indica al final. Desde backend/:

    .venv\\Scripts\\python scripts\\check_imagenes.py

Con --solo-wayback comprueba solo el punto 4, sin pedir credenciales. Consume unas pocas decenas de PU de
la cuota del mes (se informan al final): genera el juego completo de una parcela para medirlo.

Servicios consultados (documentación revisada el 2026-10-05):
- Copernicus Data Space, Sentinel Hub: token OAuth2 de credenciales de cliente, Catalog API, Statistical
  API y Process API (documentation.dataspace.copernicus.eu/APIs/SentinelHub).
- Esri World Imagery Wayback: configuración pública de versiones, metadatos por punto y "tilemap" para
  saber qué versiones cambiaron en un lugar (la lógica de github.com/Esri/wayback-core).
"""

import getpass
import io
import json
import math
import os
import sys
import tempfile
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from PIL import Image, ImageDraw
from shapely.geometry import mapping, shape
from shapely.ops import transform

RAIZ = Path(__file__).resolve().parents[1]
PARCELA = RAIZ / "tests/datos/whisp_respuesta_real.json"

# Copernicus Data Space (Sentinel Hub)
IDENTIDAD = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOGO = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
ESTADISTICA = "https://sh.dataspace.copernicus.eu/statistics/v1"
PROCESO = "https://sh.dataspace.copernicus.eu/process/v1"
CRS_4326 = "http://www.opengis.net/def/crs/EPSG/0/4326"
COLECCION = "sentinel-2-l2a"

# Valores iniciales de la adenda 2 (sección 11) y cuota que informó el equipo.
NUBES_MAX_PCT = 5.0
MARGEN_M = 150
CUOTA_MENSUAL_PU = 30_000
CORTE = date(2020, 12, 31)
LADO_MINIMO_PX = 512

# Esri World Imagery Wayback
WAYBACK_CONFIG = "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json"
WAYBACK_TILEMAP = (
    "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tilemap/"
    "{version}/{z}/{fila}/{columna}"
)
ZOOM_WAYBACK = 17  # capa de metadatos 23 - 17 = 6 ("1.2m"), como en wayback-core

# Nubes (3 sombra, 8 y 9 nube de probabilidad media y alta, 10 cirro) y píxeles sin dato o defectuosos
# (0 y 1) según la clasificación de escena (SCL) de Sentinel-2 L2A.
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

EVALSCRIPT_NATURAL = """//VERSION=3
function setup() { return { input: ["B02", "B03", "B04"], output: { bands: 3 } }; }
function evaluatePixel(s) { return [2.5 * s.B04, 2.5 * s.B03, 2.5 * s.B02]; }"""

EVALSCRIPT_INFRARROJO = """//VERSION=3
function setup() { return { input: ["B03", "B04", "B08"], output: { bands: 3 } }; }
function evaluatePixel(s) { return [2.5 * s.B08, 2.5 * s.B04, 2.5 * s.B03]; }"""


# ---------- Geometría ----------


def _a_metros(lat0: float):
    k = 111_320.0
    return lambda x, y, z=None: (x * k * math.cos(math.radians(lat0)), y * k)


def _a_grados(lat0: float):
    k = 111_320.0
    return lambda x, y, z=None: (x / (k * math.cos(math.radians(lat0))), y / k)


def parcela_y_margen() -> tuple[dict, dict, tuple[float, float, float, float], float]:
    """La parcela, la parcela con su margen y el rectángulo del recorte, en grados (EPSG:4326)."""
    geometria = json.loads(PARCELA.read_bytes())["data"]["features"][0]["geometry"]
    poligono = shape(geometria)
    lat0 = poligono.centroid.y
    en_metros = transform(_a_metros(lat0), poligono)
    con_margen = transform(_a_grados(lat0), en_metros.buffer(MARGEN_M))
    return mapping(poligono), mapping(con_margen), con_margen.bounds, lat0


def tamano_imagen(bbox, lat0) -> tuple[int, int]:
    """El lado menor mide 512 px; el mayor, en proporción (máximo 2500, lo que acepta Process API)."""
    ancho_m = (bbox[2] - bbox[0]) * 111_320 * math.cos(math.radians(lat0))
    alto_m = (bbox[3] - bbox[1]) * 111_320
    escala = LADO_MINIMO_PX / min(ancho_m, alto_m)
    return min(2500, round(ancho_m * escala)), min(2500, round(alto_m * escala))


# ---------- Copernicus ----------


class Copernicus:
    def __init__(self, cliente: httpx.Client, client_id: str, client_secret: str):
        self.cliente = cliente
        self.id, self.secreto = client_id, client_secret
        self.token = None
        self.pu_por_cabecera: list[float] = []
        self.pu_estimadas = 0.0
        self.peticiones = 0
        self.cabecera_pu = None  # nombre de la cabecera con las PU, si la API la manda

    def autenticar(self) -> None:
        r = self.cliente.post(
            IDENTIDAD,
            data={"grant_type": "client_credentials", "client_id": self.id, "client_secret": self.secreto},
        )
        if r.status_code != 200:
            raise RuntimeError(f"el token respondió {r.status_code}: {r.text[:200]}")
        self.token = r.json()["access_token"]

    def post(self, url: str, cuerpo: dict, *, pu_estimadas: float) -> httpx.Response:
        for _ in range(5):
            r = self.cliente.post(url, json=cuerpo, headers={"Authorization": f"Bearer {self.token}"})
            if r.status_code == 429:  # Retry-After viene en milisegundos
                time.sleep(int(r.headers.get("retry-after", "2000")) / 1000)
                continue
            break
        self.peticiones += 1
        if r.status_code // 100 == 2:
            self.pu_estimadas += pu_estimadas
            for nombre, valor in r.headers.items():
                if "processingunits" in nombre.lower():
                    self.cabecera_pu = nombre
                    try:
                        self.pu_por_cabecera.append(float(valor))
                    except ValueError:
                        pass
        return r

    def escenas(self, geometria: dict, desde: date, hasta: date) -> dict[str, float]:
        """Fechas de Sentinel-2 L2A sobre la parcela, con la nubosidad de la escena completa (tile)."""
        fechas: dict[str, float] = {}
        cuerpo = {
            "collections": [COLECCION],
            "datetime": f"{desde}T00:00:00Z/{hasta}T23:59:59Z",
            "intersects": geometria,
            "limit": 100,
            "fields": {"include": ["properties.datetime", "properties.eo:cloud_cover"]},
        }
        while True:
            r = self.post(CATALOGO, cuerpo, pu_estimadas=0.01)
            r.raise_for_status()
            datos = r.json()
            for item in datos.get("features", []):
                dia = item["properties"]["datetime"][:10]
                fechas[dia] = min(
                    fechas.get(dia, 100.0), float(item["properties"].get("eo:cloud_cover", 100))
                )
            siguiente = datos.get("context", {}).get("next")
            if siguiente is None:
                return fechas
            cuerpo["next"] = siguiente

    def nubes_sobre_la_parcela(
        self, geometria: dict, desde: date, hasta: date, lat0: float
    ) -> dict[str, dict]:
        """Por fecha: fracción de la parcela con su margen cubierta por nube o sombra, a 10 m."""
        res_y = 10 / 111_320
        res_x = 10 / (111_320 * math.cos(math.radians(lat0)))
        cuerpo = {
            "input": {
                "bounds": {"geometry": geometria, "properties": {"crs": CRS_4326}},
                "data": [{"type": COLECCION, "dataFilter": {"mosaickingOrder": "leastRecent"}}],
            },
            "aggregation": {
                "timeRange": {"from": f"{desde}T00:00:00Z", "to": f"{hasta}T23:59:59Z"},
                "aggregationInterval": {"of": "P1D"},
                "evalscript": EVALSCRIPT_NUBES,
                "resx": res_x,
                "resy": res_y,
            },
        }
        dias = (hasta - desde).days + 1
        r = self.post(ESTADISTICA, cuerpo, pu_estimadas=max(0.01, 0.01 * dias / 5))
        if r.status_code != 200:
            raise RuntimeError(f"Statistical API respondió {r.status_code}: {r.text[:300]}")
        salida = {}
        for intervalo in r.json().get("data", []):
            if intervalo.get("error"):
                continue
            stats = intervalo["outputs"]["nubes"]["bands"]["B0"]["stats"]
            if not stats.get("sampleCount"):
                continue
            salida[intervalo["interval"]["from"][:10]] = {
                "nubes_pct": None
                if stats.get("mean") in (None, "NaN")
                else round(100 * float(stats["mean"]), 2),
                "muestras": stats["sampleCount"],
                "sin_dato": stats["noDataCount"],
            }
        return salida

    def imagen(self, bbox, dia: str, evalscript: str, tamano: tuple[int, int]) -> bytes:
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
            "evalscript": evalscript,
        }
        r = self.post(PROCESO, cuerpo, pu_estimadas=max(0.005, ancho * alto / 512**2))
        if r.status_code != 200 or not r.content.startswith(b"\x89PNG"):
            raise RuntimeError(f"Process API respondió {r.status_code}: {r.text[:300]}")
        return r.content


def utilizables(nubes: dict[str, dict]) -> dict[str, dict]:
    """Escenas con menos del máximo de nubes y la parcela completa (sin píxeles sin dato de más)."""
    if not nubes:
        return {}
    minimo = min(v["sin_dato"] for v in nubes.values())
    return {
        dia: v
        for dia, v in nubes.items()
        if v["nubes_pct"] is not None and v["nubes_pct"] < NUBES_MAX_PCT and v["sin_dato"] <= minimo
    }


def dibujar_lindero(png: bytes, parcela: dict, bbox) -> bytes:
    imagen = Image.open(io.BytesIO(png)).convert("RGB")
    ancho, alto = imagen.size
    lienzo = ImageDraw.Draw(imagen)
    for anillo in parcela["coordinates"]:
        puntos = [
            ((x - bbox[0]) / (bbox[2] - bbox[0]) * ancho, (bbox[3] - y) / (bbox[3] - bbox[1]) * alto)
            for x, y in anillo
        ]
        lienzo.line(puntos, fill=(255, 220, 0), width=3)
    salida = io.BytesIO()
    imagen.save(salida, format="PNG")
    return salida.getvalue()


# ---------- Wayback ----------


def _tile(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2**z
    columna = int((lon + 180) / 360 * n)
    fila = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return columna, fila


def wayback(cliente: httpx.Client, lat: float, lon: float) -> list[dict]:
    """Versiones de Wayback que cambiaron la imagen en el punto, con su fecha de captura real."""
    config = cliente.get(WAYBACK_CONFIG).raise_for_status().json()
    versiones = sorted(
        ((int(numero), datos) for numero, datos in config.items()),
        key=lambda par: par[1]["itemTitle"].split("Wayback ")[-1].rstrip(")"),
        reverse=True,
    )
    orden = [numero for numero, _ in versiones]
    por_numero = dict(versiones)
    columna, fila = _tile(lat, lon, ZOOM_WAYBACK)
    cambios, actual = [], orden[0]
    while actual is not None and len(cambios) < 60:
        r = cliente.get(WAYBACK_TILEMAP.format(version=actual, z=ZOOM_WAYBACK, fila=fila, columna=columna))
        datos = r.json() if r.status_code == 200 else {}
        if not datos.get("data") or not datos["data"][0]:
            break
        elegida = datos["select"][0]
        if elegida in cambios:
            break
        cambios.append(elegida)
        posicion = orden.index(elegida) if elegida in orden else len(orden)
        actual = orden[posicion + 1] if posicion + 1 < len(orden) else None
    salida = []
    for numero in cambios:
        datos = por_numero[numero]
        consulta = cliente.get(
            f"{datos['metadataLayerUrl']}/{23 - ZOOM_WAYBACK}/query",
            params={
                "f": "json",
                "where": "1=1",
                "outFields": "SRC_DATE2,NICE_DESC,SRC_DESC,SAMP_RES,SRC_RES",
                "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
                "geometryType": "esriGeometryPoint",
                "spatialRel": "esriSpatialRelIntersects",
                "returnGeometry": "false",
            },
        ).json()
        atributos = (consulta.get("features") or [{}])[0].get("attributes", {})
        captura = atributos.get("SRC_DATE2")
        salida.append(
            {
                "version": numero,
                "publicada": datos["itemTitle"].split("Wayback ")[-1].rstrip(")"),
                "captura": datetime.fromtimestamp(captura / 1000, UTC).date() if captura else None,
                "proveedor": atributos.get("NICE_DESC"),
                "sensor": atributos.get("SRC_DESC"),
                "resolucion_m": atributos.get("SRC_RES"),
                "tile": datos["itemURL"]
                .replace("{level}", str(ZOOM_WAYBACK))
                .replace("{row}", str(fila))
                .replace("{col}", str(columna)),
            }
        )
    return salida


# ---------- Programa ----------


def _credencial(variable: str, texto: str) -> str:
    valor = os.environ.get(variable, "").strip()
    if not valor:
        valor = getpass.getpass(f"{texto} (no se mostrará; Enter para saltar Copernicus): ").strip()
    return valor


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parcela, con_margen, bbox, lat0 = parcela_y_margen()
    centro = shape(parcela).centroid
    carpeta = Path(tempfile.gettempdir()) / "cacaotrace_check_imagenes"
    carpeta.mkdir(exist_ok=True)
    hoy = datetime.now(UTC).date()
    resultado: dict[str, str] = {}
    print(
        f"Parcela: {PARCELA.relative_to(RAIZ)} (centro {centro.y:.5f}, {centro.x:.5f}); margen {MARGEN_M} m"
    )

    # Con --solo-wayback no se piden credenciales: comprueba solo el punto 4.
    solo_wayback = "--solo-wayback" in sys.argv
    client_id = "" if solo_wayback else _credencial("COPERNICUS_CLIENT_ID", "Pega el COPERNICUS_CLIENT_ID")
    client_secret = (
        _credencial("COPERNICUS_CLIENT_SECRET", "Pega el COPERNICUS_CLIENT_SECRET") if client_id else ""
    )

    # Wayback rechaza (403) el identificador por defecto de httpx; se identifica a CacaoTrace tal cual.
    cabeceras = {"User-Agent": "CacaoTrace/1.0 (comprobacion de viabilidad; https://cacaotrace.pages.dev)"}
    with httpx.Client(timeout=120, headers=cabeceras, follow_redirects=True) as cliente:
        if client_id and client_secret:
            resultado.update(
                _copernicus(cliente, client_id, client_secret, parcela, con_margen, bbox, lat0, hoy, carpeta)
            )
        else:
            for punto in ("1", "2", "3"):
                resultado[punto] = "NO CORRIDO: faltan las credenciales de Copernicus"

        print("\n4. Esri World Imagery Wayback")
        try:
            versiones = wayback(cliente, centro.y, centro.x)
            if not versiones:
                raise RuntimeError("ninguna versión con imagen para ese lugar")
            print(f"  {len(versiones)} versiones cambiaron la imagen en el punto (zoom {ZOOM_WAYBACK}):")
            for v in versiones:
                print(
                    f"   - publicada {v['publicada']}: captura {v['captura'] or 'sin fecha'}, "
                    f"{v['proveedor']} ({v['sensor']}), {v['resolucion_m']} m"
                )
            tile = cliente.get(versiones[0]["tile"].replace("{s}", "wayback"))
            print(
                f"  Una tesela de la última versión, sin clave: HTTP {tile.status_code} "
                f"({tile.headers.get('content-type')})"
            )
            previas = [v for v in versiones if v["captura"] and v["captura"] <= CORTE]
            print(
                f"  Captura anterior al {CORTE:%d/%m/%Y}: "
                + (
                    f"sí, la más cercana es del {max(v['captura'] for v in previas):%d/%m/%Y}"
                    if previas
                    else "no hay"
                )
            )
            ok = all(v["captura"] for v in versiones) and tile.status_code == 200
            resultado["4"] = "PASA" if ok else "FALLA: faltan fechas de captura o la tesela no respondió"
        except Exception as exc:  # noqa: BLE001 — la comprobación informa cualquier falla
            resultado["4"] = f"FALLA: {exc}"

    print("\nResultado")
    for punto in ("1", "2", "3", "4"):
        print(f"  {punto}. {resultado[punto]}")
    print(f"\nImágenes de muestra (fuera del repositorio): {carpeta}")
    if resultado["1"].startswith("FALLA") or resultado["3"].startswith("FALLA"):
        print("Falló el punto 1 o el 3: hay que detenerse e informar al equipo (adenda 2, sección 4).")
        return 1
    if resultado["4"].startswith("FALLA"):
        print("Falló el punto 4: se construye sin Wayback (adenda 2, sección 4).")
    return 0


def _copernicus(
    cliente, client_id, client_secret, parcela, con_margen, bbox, lat0, hoy, carpeta
) -> dict[str, str]:
    resultado: dict[str, str] = {}
    cop = Copernicus(cliente, client_id, client_secret)
    print("\n1. Imagen de Sentinel-2 de 2020")
    try:
        cop.autenticar()
        print("  Token de Copernicus: obtenido")
        escenas_2020 = cop.escenas(con_margen, date(2020, 1, 1), date(2020, 12, 31))
        print(f"  Escenas de 2020 sobre la parcela (Catalog API): {len(escenas_2020)}")
    except Exception as exc:  # noqa: BLE001
        return {"1": f"FALLA: {exc}", "2": "NO CORRIDO", "3": "NO CORRIDO"}

    print("\n3. Nubosidad sobre la parcela con su margen (Statistical API, clasificación SCL)")
    nubes: dict[str, dict] = {}
    try:
        for anio in range(2019, hoy.year + 1):
            desde, hasta = date(anio, 1, 1), min(date(anio, 12, 31), hoy)
            nubes.update(cop.nubes_sobre_la_parcela(con_margen, desde, hasta, lat0))
        de_2020 = {d: v for d, v in nubes.items() if d.startswith("2020")}
        if not de_2020:
            raise RuntimeError("la API no devolvió nubosidad para 2020")
        print(f"  Fechas medidas desde 2019: {len(nubes)} (2020: {len(de_2020)})")
        print("  Muestra de 2020, nubes sobre la parcela frente a nubes de la escena completa:")
        for dia in sorted(de_2020)[:12]:
            print(f"   - {dia}: parcela {de_2020[dia]['nubes_pct']} %, escena {escenas_2020.get(dia, '—')} %")
        resultado["3"] = "PASA: la nubosidad se mide sobre la parcela con su margen, fecha por fecha"
    except Exception as exc:  # noqa: BLE001
        resultado["3"] = f"FALLA: {exc}"

    usables = utilizables(nubes)
    juego: list[tuple[str, str]] = []
    previas = sorted(d for d in usables if date.fromisoformat(d) <= CORTE)
    if previas:
        juego.append(("anterior_al_corte", previas[-1]))
    for anio in range(2021, hoy.year):
        del_anio = {d: v for d, v in usables.items() if d.startswith(str(anio))}
        if del_anio:
            juego.append((f"anual {anio}", min(del_anio, key=lambda d: (del_anio[d]["nubes_pct"], d))))
        else:
            juego.append((f"anual {anio}", ""))
    recientes = sorted(d for d in usables if date.fromisoformat(d) >= hoy - timedelta(days=365))
    juego.append(("reciente", recientes[-1] if recientes else ""))
    print(
        f"\n  Escenas utilizables (menos de {NUBES_MAX_PCT:g} % de nubes y parcela completa): {len(usables)}"
    )
    for papel, dia in juego:
        if dia:
            dias = (date.fromisoformat(dia) - CORTE).days
            print(
                f"   - {papel}: {dia} ({dias:+d} días respecto al corte), nubes {usables[dia]['nubes_pct']} %"
            )
        else:
            print(f"   - {papel}: sin imagen utilizable")

    print("\n1-2. Imágenes del juego completo (Process API: color natural e infrarrojo, con el lindero)")
    tamano = tamano_imagen(bbox, lat0)
    print(f"  Tamaño de cada imagen: {tamano[0]} x {tamano[1]} px; resolución real 10 m")
    try:
        generadas = 0
        for papel, dia in juego:
            if not dia:
                continue
            for version, script in (("natural", EVALSCRIPT_NATURAL), ("infrarrojo", EVALSCRIPT_INFRARROJO)):
                png = dibujar_lindero(cop.imagen(bbox, dia, script, tamano), parcela, bbox)
                (carpeta / f"{dia}_{papel.replace(' ', '_')}_{version}.png").write_bytes(png)
                generadas += 1
        hay_2020 = any(p == "anterior_al_corte" and d.startswith("2020") for p, d in juego)
        resultado["1"] = (
            "PASA: imagen de 2020 generada"
            if hay_2020
            else "FALLA: no hubo escena utilizable de 2020 para la parcela"
        )
        print(f"  Imágenes generadas: {generadas}")
    except Exception as exc:  # noqa: BLE001
        resultado["1"] = f"FALLA: {exc}"

    if cop.pu_por_cabecera:
        total, origen = sum(cop.pu_por_cabecera), f"cabecera {cop.cabecera_pu}"
    else:
        total, origen = (
            cop.pu_estimadas,
            "estimadas con la fórmula de la documentación (la API no mandó cabecera)",
        )
    juegos = int(CUOTA_MENSUAL_PU * 0.8 // total) if total else 0
    print(
        f"\n2. Unidades de procesamiento del juego completo: {total:.2f} PU en {cop.peticiones} "
        f"peticiones ({origen})"
    )
    print(
        f"  Con {CUOTA_MENSUAL_PU:,} PU al mes y el corte al 80 %, alcanzan para unos {juegos:,} "
        "juegos al mes"
    )
    resultado["2"] = f"{total:.2f} PU por parcela ({origen})"
    return resultado


if __name__ == "__main__":
    sys.exit(main())

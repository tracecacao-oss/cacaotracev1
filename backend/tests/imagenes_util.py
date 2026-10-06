"""Ayudas para las pruebas de la adenda 2: Copernicus y Esri Wayback simulados (nada sale a internet) y
registros de imágenes y revisiones listos para la compuerta de habilitación."""

import io
import json
import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
from PIL import Image

from app.fechas import ahora, hoy_lima
from app.models import Documento, ImagenParcela, Parcela, Perfil, RevisionImagenes
from app.services import imagenes as servicio
from app.services import sentinel, wayback
from app.services.imagenes import Proveedores
from app.services.sentinel import Sentinel
from app.services.wayback import Wayback
from app.storage import construir_ruta, sha256

DESCRIPCION = (
    "En la imagen de diciembre de 2020 se ve cacao bajo sombra en toda la parcela; en la reciente, lo mismo."
)


def png(ancho: int = 8, alto: int = 8, color=(40, 90, 50)) -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (ancho, alto), color).save(salida, format="PNG")
    return salida.getvalue()


def _epoch_ms(dia: date) -> int:
    return int(datetime(dia.year, dia.month, dia.day, 12, tzinfo=UTC).timestamp() * 1000)


class ServiciosFalsos:
    """Responde como Copernicus (token, Statistical, Catalog y Process) y como Esri Wayback.

    `nubes`: día -> porcentaje de la parcela con nubes. `sin_dato`: día -> píxeles sin dato (la parcela no
    entra entera en la escena). `capturas`: versiones de Wayback (número, publicación, captura, proveedor).
    """

    def __init__(self, nubes=None, sin_dato=None, capturas=None, pu: float = 2.0, falla_proceso=False):
        self.nubes: dict[date, float] = nubes or {}
        self.sin_dato: dict[date, int] = sin_dato or {}
        self.capturas = capturas or []
        self.pu = pu
        self.falla_proceso = falla_proceso
        self.peticiones: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.peticiones.append(request)
        url = f"{request.url.scheme}://{request.url.host}{request.url.path}"
        cabecera = {sentinel.CABECERA_PU: str(self.pu)}
        if url == sentinel.IDENTIDAD:
            return httpx.Response(200, json={"access_token": "token-de-prueba", "expires_in": 600})
        if url == sentinel.ESTADISTICA:
            rango = json.loads(request.content)["aggregation"]["timeRange"]
            desde, hasta = date.fromisoformat(rango["from"][:10]), date.fromisoformat(rango["to"][:10])
            datos = [
                {
                    "interval": {"from": f"{dia}T00:00:00Z", "to": f"{dia + timedelta(days=1)}T00:00:00Z"},
                    "outputs": {
                        "nubes": {
                            "bands": {
                                "B0": {
                                    "stats": {
                                        "sampleCount": 900,
                                        "noDataCount": self.sin_dato.get(dia, 0),
                                        "mean": pct / 100,
                                    }
                                }
                            }
                        }
                    },
                }
                for dia, pct in sorted(self.nubes.items())
                if desde <= dia <= hasta
            ]
            return httpx.Response(200, json={"data": datos}, headers=cabecera)
        if url == sentinel.CATALOGO:
            dia = json.loads(request.content)["datetime"][:10]
            item = {"id": f"S2B_MSIL2A_{dia.replace('-', '')}", "properties": {"platform": "sentinel-2b"}}
            return httpx.Response(200, json={"type": "FeatureCollection", "features": [item]})
        if url == sentinel.PROCESO:
            if self.falla_proceso:
                return httpx.Response(500, json={"error": "falla simulada"})
            cuerpo = json.loads(request.content)
            salida = cuerpo["output"]
            # Color natural verde; falso color infrarrojo, la vegetación en rojo. Cada fecha, un tono.
            tono = int(cuerpo["input"]["data"][0]["dataFilter"]["timeRange"]["from"][8:10])
            natural = cuerpo["evalscript"] == sentinel.EVALSCRIPTS["natural"]
            color = (40, 90 + tono, 50) if natural else (190, 40 + tono, 50)
            contenido = png(salida["width"], salida["height"], color)
            return httpx.Response(200, content=contenido, headers=cabecera)
        if url == wayback.CONFIG:
            return httpx.Response(
                200,
                json={
                    str(c["version"]): {
                        "itemTitle": f"World Imagery (Wayback {c['publicada']})",
                        "metadataLayerUrl": f"https://metadatos.prueba/{c['version']}/MapServer",
                    }
                    for c in self.capturas
                },
            )
        if request.url.host == "wayback.maptiles.arcgis.com" and "/tilemap/" in request.url.path:
            version = int(request.url.path.split("/tilemap/")[1].split("/")[0])
            return httpx.Response(200, json={"valid": True, "select": [version], "data": [1]})
        if request.url.host == "metadatos.prueba":
            version = int(request.url.path.split("/")[1])
            c = next(c for c in self.capturas if c["version"] == version)
            atributos = {
                "SRC_DATE2": _epoch_ms(c["captura"]),
                "NICE_DESC": c.get("proveedor", "Maxar"),
                "SRC_DESC": c.get("sensor", "WV02"),
                "SRC_RES": c.get("resolucion_m", 0.5),
            }
            return httpx.Response(200, json={"features": [{"attributes": atributos}]})
        raise AssertionError(f"Petición no simulada: {request.url}")

    def de(self, url: str) -> list[httpx.Request]:
        return [p for p in self.peticiones if str(p.url).startswith(url)]


def proveedores(servicios: ServiciosFalsos, cuota_mensual_pu: float = 30_000) -> Proveedores:
    cliente = httpx.Client(transport=httpx.MockTransport(servicios))
    return Proveedores(
        sentinel=Sentinel("cliente-prueba", "secreto-prueba", http=cliente),
        wayback=Wayback(http=cliente),
        nubes_max_pct=5,
        margen_m=150,
        cuota_mensual_pu=cuota_mensual_pu,
    )


def procesar(sesion, storage) -> int:
    """Lo que hace el hilo en segundo plano, hasta que no quede trabajo."""
    vueltas = 0
    while servicio.procesar_siguiente(sesion, storage):
        vueltas += 1
        assert vueltas < 20
    return vueltas


# ---------- Registros directos (para las pruebas de la compuerta) ----------


def imagen(
    sesion, parcela: Parcela, dia: date, *, papel: str | None = None, fuente: str = "sentinel2"
) -> ImagenParcela:
    """Una imagen ya generada del juego actual, con su PNG registrado."""
    fila = ImagenParcela(
        id=uuid.uuid4(),
        parcela_id=parcela.id,
        cooperativa_id=parcela.cooperativa_registro_id,
        fuente=fuente,
        papel=papel or ("anterior_al_corte" if dia <= servicio.CORTE else "reciente"),
        fecha_captura=dia,
        dias_respecto_al_corte=(dia - servicio.CORTE).days,
        resolucion_m=10,
        nubes_parcela_pct=1,
        identificador_fuente=f"S2B_MSIL2A_{dia:%Y%m%d}",
        proveedor="Sentinel-2B",
        geometria_sha256=servicio.huella(parcela),
        estado="generada",
    )
    sesion.add(fila)
    sesion.flush()
    contenido = png()
    documento = Documento(
        cooperativa_id=fila.cooperativa_id,
        entidad="imagen",
        entidad_id=fila.id,
        tipo="imagen_satelital",
        ruta=construir_ruta(fila.cooperativa_id, "imagen", fila.id, "png"),
        nombre_original=f"{parcela.codigo}-{dia}-natural.png",
        tipo_mime="image/png",
        tamano_bytes=len(contenido),
        sha256=sha256(contenido),
    )
    sesion.add(documento)
    sesion.flush()
    fila.documento_natural_id = documento.id
    sesion.flush()
    return fila


def juego(sesion, parcela: Parcela) -> list[ImagenParcela]:
    """La anterior al corte y la reciente: lo mínimo para registrar una revisión."""
    return [
        imagen(sesion, parcela, date(2020, 12, 19)),
        imagen(sesion, parcela, hoy_lima() - timedelta(days=9)),
    ]


def revision(
    sesion,
    parcela: Parcela,
    perfil: Perfil,
    *,
    observacion_2020: str = "cultivo_o_uso_agricola",
    observacion_cambio: str = "sin_cambio_visible",
    revisada_en: datetime | None = None,
) -> RevisionImagenes:
    filas = servicio.juego_actual(sesion, parcela) or juego(sesion, parcela)
    r = RevisionImagenes(
        id=uuid.uuid4(),
        parcela_id=parcela.id,
        cooperativa_id=perfil.cooperativa_id,
        revisada_por=perfil.id,
        revisada_en=revisada_en or ahora(),
        imagenes=[str(f.id) for f in filas],
        observacion_2020=observacion_2020,
        observacion_cambio=observacion_cambio,
        descripcion=DESCRIPCION,
        geometria_sha256=servicio.huella(parcela),
    )
    sesion.add(r)
    sesion.flush()
    return r

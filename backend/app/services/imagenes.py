"""Imágenes satelitales de la parcela (adenda 2 de la Parte 4).

Cuando una parcela tiene la alerta `analisis_requiere_revision`, el sistema genera su juego de imágenes:
de Sentinel-2 (la anterior al 31/12/2020, una por año desde 2021 y la reciente, en color natural y en
falso color infrarrojo, con el lindero dibujado) y los datos de las versiones de alta resolución de Esri
Wayback. Una parcela sin esa alerta no genera imágenes. El administrador las revisa y registra lo que
observa (services/revisiones_imagenes.py).

La generación usa el mismo hilo en segundo plano que los análisis: una fila `pendiente` por cada imagen
esperada; el hilo toma las de una parcela y las resuelve juntas. Las unidades de procesamiento de
Copernicus se suman por mes; al 80 % de la cuota no se generan imágenes nuevas.
"""

import io
import json
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from geoalchemy2.shape import to_shape
from PIL import Image, ImageDraw
from shapely.geometry import mapping, shape
from shapely.ops import transform
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.contexto import Contexto
from app.errores import error_api
from app.fechas import ahora, hoy_lima
from app.models import ConsumoImagenes, Documento, ImagenParcela, Parcela
from app.schemas.imagenes import ConsumoSalida, ImagenesSalida, ImagenSalida
from app.services import geometria
from app.services.auditoria import registrar_auditoria
from app.services.sentinel import (
    ATRIBUCION as ATRIBUCION_SENTINEL,
)
from app.services.sentinel import (
    RESOLUCION_M,
    Consumo,
    ErrorSentinel,
    Medida,
    Sentinel,
)
from app.services.wayback import ATRIBUCION as ATRIBUCION_WAYBACK
from app.services.wayback import SUBDOMINIOS, TESELAS, ErrorWayback, Wayback
from app.storage import ClienteStorage, ErrorStorage, construir_ruta, detectar_tipo, sha256

log = logging.getLogger(__name__)

CORTE = date(2020, 12, 31)
# Imagen anterior al corte: se busca en 2020 y, si no hay, se retrocede hasta el 1 de enero de 2019.
INICIO_PREVIA = date(2019, 1, 1)
# "Buscar más imágenes" (decisión del equipo, adenda 2, 17): hasta 3 escenas más cercanas al corte.
MAS_PREVIAS = 3
UMBRAL_CUOTA = 0.8
LADO_MINIMO_PX = 512
LADO_MAXIMO_PX = 2500  # lo que acepta Process API
LINDERO = (255, 220, 0)


# ---------- Proveedores ----------


@dataclass
class Proveedores:
    sentinel: Sentinel | None
    wayback: Wayback | None
    nubes_max_pct: float
    margen_m: int
    cuota_mensual_pu: float

    @property
    def configurada(self) -> bool:
        return self.sentinel is not None and self.sentinel.configurada


_actual: Proveedores | None = None


def fijar(proveedores: Proveedores) -> None:
    global _actual
    _actual = proveedores


def actual() -> Proveedores:
    if _actual is None:
        from app.config import get_settings

        fijar(construir(get_settings()))
    return _actual


def construir(settings) -> Proveedores:
    def clave(valor):
        return valor.get_secret_value() if valor else None

    return Proveedores(
        sentinel=Sentinel(clave(settings.copernicus_client_id), clave(settings.copernicus_client_secret)),
        wayback=Wayback(),
        nubes_max_pct=settings.imagenes_nubes_max_pct,
        margen_m=settings.imagenes_margen_m,
        cuota_mensual_pu=settings.imagenes_cuota_mensual_pu,
    )


# ---------- Selección de escenas (5.1 y 5.2) ----------


def utilizables(medidas: dict[date, Medida], nubes_max_pct: float) -> dict[date, Medida]:
    """Menos del máximo de nubes sobre la parcela con su margen, y la parcela completa en la escena: una
    escena que no la cubre entera tiene más píxeles sin dato que el mínimo de todas las fechas."""
    if not medidas:
        return {}
    minimo = min(m.sin_dato for m in medidas.values())
    return {
        dia: m
        for dia, m in medidas.items()
        if m.nubes_pct is not None and m.nubes_pct < nubes_max_pct and m.sin_dato <= minimo
    }


def elegir_previas(usables: dict[date, Medida], usadas: set[date], cantidad: int) -> list[date]:
    """Las escenas utilizables más cercanas al corte sin pasarse: primero 2020; si no hay, 2019."""
    candidatas = sorted((d for d in usables if INICIO_PREVIA <= d <= CORTE and d not in usadas), reverse=True)
    return candidatas[:cantidad]


def elegir_anual(usables: dict[date, Medida], anio: int) -> date | None:
    """La de menos nubes del año; si empatan, la más cercana a fin de año, la misma estación del corte."""
    del_anio = [d for d in usables if d.year == anio]
    if not del_anio:
        return None
    fin = date(anio, 12, 31)
    return min(del_anio, key=lambda d: (usables[d].nubes_pct, (fin - d).days))


def elegir_reciente(usables: dict[date, Medida], hoy: date) -> date | None:
    recientes = [d for d in usables if d >= hoy - timedelta(days=365)]
    return max(recientes) if recientes else None


# ---------- Geometría del recorte ----------


def _a_metros(lat0: float):
    return lambda x, y, z=None: (x * 111_320 * math.cos(math.radians(lat0)), y * 111_320)


def _a_grados(lat0: float):
    return lambda x, y, z=None: (x / (111_320 * math.cos(math.radians(lat0))), y / 111_320)


def lindero(sesion: Session, parcela: Parcela) -> dict:
    """El polígono de la parcela; para un punto, el círculo con el área declarada (5.3, regla 3)."""
    geo = geometria.a_geojson(to_shape(parcela.geometria))
    if parcela.tipo_geometria != "punto":
        return geo
    radio_m = math.sqrt(float(parcela.area_declarada_ha) * 10_000 / math.pi)
    circulo = sesion.execute(
        text(
            "SELECT ST_AsGeoJSON(ST_Buffer(ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326)::geography, :r, 32)"
            "::geometry, 8)"
        ),
        {"g": json.dumps(geo), "r": radio_m},
    ).scalar_one()
    return json.loads(circulo)


def recorte(contorno: dict, margen_m: int) -> tuple[dict, tuple[float, float, float, float], float]:
    """La parcela con su margen, su rectángulo (EPSG:4326) y la latitud central."""
    figura = shape(contorno)
    lat0 = figura.centroid.y
    con_margen = transform(_a_grados(lat0), transform(_a_metros(lat0), figura).buffer(margen_m))
    return mapping(con_margen), con_margen.bounds, lat0


def tamano_imagen(bbox, lat0: float) -> tuple[int, int]:
    """El lado menor mide 512 px; el mayor, en proporción. La resolución real sigue siendo 10 m."""
    ancho_m = (bbox[2] - bbox[0]) * 111_320 * math.cos(math.radians(lat0))
    alto_m = (bbox[3] - bbox[1]) * 111_320
    escala = LADO_MINIMO_PX / max(1.0, min(ancho_m, alto_m))
    return min(LADO_MAXIMO_PX, round(ancho_m * escala)), min(LADO_MAXIMO_PX, round(alto_m * escala))


def dibujar_lindero(png: bytes, contorno: dict, bbox) -> bytes:
    imagen = Image.open(io.BytesIO(png)).convert("RGB")
    ancho, alto = imagen.size
    lienzo = ImageDraw.Draw(imagen)
    poligonos = [contorno["coordinates"]] if contorno["type"] == "Polygon" else contorno["coordinates"]
    grosor = max(2, round(min(ancho, alto) / 200))
    for poligono in poligonos:
        for anillo in poligono:
            puntos = [
                ((x - bbox[0]) / (bbox[2] - bbox[0]) * ancho, (bbox[3] - y) / (bbox[3] - bbox[1]) * alto)
                for x, y in anillo
            ]
            lienzo.line(puntos, fill=LINDERO, width=grosor, joint="curve")
    salida = io.BytesIO()
    imagen.save(salida, format="PNG", optimize=True)
    return salida.getvalue()


# ---------- Estado ----------


def tiene_alerta(sesion: Session, parcela: Parcela) -> bool:
    from app.services import analisis
    from app.services.fuentes import registro

    estado = analisis.resumen(
        registro.actuales(), parcela, analisis.de_parcelas(sesion, [parcela.id])[parcela.id]
    )
    return "analisis_requiere_revision" in analisis.alertas(estado)


def huella(parcela: Parcela) -> str:
    from app.services.analisis import huella_parcela

    return huella_parcela(parcela)


def juego_actual(sesion: Session, parcela: Parcela) -> list[ImagenParcela]:
    """Las imágenes de la geometría actual que no fueron reemplazadas. Las de otra geometría son obsoletas."""
    return list(
        sesion.scalars(
            select(ImagenParcela)
            .where(
                ImagenParcela.parcela_id == parcela.id,
                ImagenParcela.geometria_sha256 == huella(parcela),
                ImagenParcela.reemplazada_en.is_(None),
            )
            .order_by(ImagenParcela.creado_en)
        )
    )


def _primer_dia_del_mes(momento: datetime | None = None) -> date:
    momento = momento or datetime.now(UTC)
    return date(momento.year, momento.month, 1)


def consumo_del_mes(sesion: Session) -> float:
    total = sesion.scalar(
        select(func.coalesce(func.sum(ConsumoImagenes.pu), 0)).where(
            ConsumoImagenes.mes == _primer_dia_del_mes()
        )
    )
    return float(total or 0)


def en_pausa(sesion: Session, proveedores: Proveedores | None = None) -> bool:
    proveedores = proveedores or actual()
    return consumo_del_mes(sesion) >= UMBRAL_CUOTA * proveedores.cuota_mensual_pu


def consumo_salida(sesion: Session) -> ConsumoSalida:
    proveedores = actual()
    usadas = consumo_del_mes(sesion)
    return ConsumoSalida(
        mes=_primer_dia_del_mes(),
        usadas_pu=round(usadas, 2),
        cuota_pu=proveedores.cuota_mensual_pu,
        umbral_pu=round(UMBRAL_CUOTA * proveedores.cuota_mensual_pu, 2),
        en_pausa=usadas >= UMBRAL_CUOTA * proveedores.cuota_mensual_pu,
        configurada=proveedores.configurada,
        pendientes=sesion.scalar(
            select(func.count()).select_from(ImagenParcela).where(ImagenParcela.estado == "pendiente")
        ),
    )


# ---------- Encolar ----------


def _nueva(parcela: Parcela, huella_actual: str, fuente: str, papel: str, periodo: int | None = None):
    return ImagenParcela(
        parcela_id=parcela.id,
        cooperativa_id=parcela.cooperativa_registro_id,
        fuente=fuente,
        papel=papel,
        periodo=periodo,
        geometria_sha256=huella_actual,
        estado="pendiente",
    )


def encolar(
    sesion: Session,
    parcela: Parcela,
    *,
    origen: str,
    contexto: Contexto | None = None,
    solo_mas: bool = False,
) -> int:
    """Agrega las imágenes pendientes de una parcela. `solo_mas`: las de "Buscar más imágenes"."""
    proveedores = actual()
    huella_actual = huella(parcela)
    filas = []
    if solo_mas:
        filas += [
            _nueva(parcela, huella_actual, "sentinel2", "anterior_al_corte") for _ in range(MAS_PREVIAS)
        ]
        filas.append(_nueva(parcela, huella_actual, "sentinel2", "reciente"))
    else:
        hoy = hoy_lima()
        filas.append(_nueva(parcela, huella_actual, "sentinel2", "anterior_al_corte"))
        filas += [
            _nueva(parcela, huella_actual, "sentinel2", "anual", anio) for anio in range(2021, hoy.year)
        ]
        filas.append(_nueva(parcela, huella_actual, "sentinel2", "reciente"))
        if proveedores.wayback is not None:
            filas.append(_nueva(parcela, huella_actual, "esri_wayback", "alta_resolucion"))
    sesion.add_all(filas)
    sesion.flush()
    registrar_auditoria(
        contexto,
        "imagenes.generar",
        "parcela",
        parcela.id,
        {"origen": origen, "imagenes": len(filas)},
        **({} if contexto else {"cooperativa_id": parcela.cooperativa_registro_id, "sesion": sesion}),
    )
    return len(filas)


def asegurar_juego(sesion: Session, parcela: Parcela) -> bool:
    """Si la parcela tiene la alerta y no tiene juego para su geometría actual, lo encola. Lo llama el hilo
    al terminar un análisis y la tarea diaria. Confirma la transacción si encoló."""
    if parcela.estado != "activa" or parcela.habilitacion_estado == "excluida":
        return False
    if not actual().configurada or not tiene_alerta(sesion, parcela):
        return False
    juego = juego_actual(sesion, parcela)
    # Un juego que falló entero (Copernicus caído, por ejemplo) se vuelve a pedir; queda como historial.
    if juego and not all(f.estado == "error" for f in juego):
        return False
    for fila in juego:
        fila.reemplazada_en = ahora()
    encolar(sesion, parcela, origen="reintento" if juego else "alerta")
    sesion.commit()
    return True


def encolar_pendientes(sesion: Session) -> int:
    """Al arrancar y cada día: toda parcela activa con la alerta y sin juego vigente recibe el suyo."""
    if not actual().configurada:
        return 0
    parcelas = list(
        sesion.scalars(
            select(Parcela).where(Parcela.estado == "activa", Parcela.habilitacion_estado != "excluida")
        )
    )
    return sum(asegurar_juego(sesion, p) for p in parcelas)


# ---------- Generación (hilo en segundo plano) ----------


def _guardar_png(
    sesion: Session, storage: ClienteStorage, fila: ImagenParcela, codigo: str, version: str, png: bytes
) -> Documento:
    ruta = construir_ruta(fila.cooperativa_id, "imagen", fila.id, "png")
    storage.subir(ruta, png, "image/png")
    documento = Documento(
        cooperativa_id=fila.cooperativa_id,
        entidad="imagen",
        entidad_id=fila.id,
        tipo="imagen_satelital",
        ruta=ruta,
        nombre_original=f"{codigo}-{fila.fecha_captura}-{version}.png",
        tipo_mime="image/png",
        tamano_bytes=len(png),
        sha256=sha256(png),
        subido_por=None,
    )
    sesion.add(documento)
    sesion.flush()
    return documento


def _sentinel(
    sesion: Session,
    storage: ClienteStorage,
    proveedores: Proveedores,
    parcela: Parcela,
    filas: list[ImagenParcela],
    consumo: Consumo,
) -> None:
    sentinel = proveedores.sentinel
    contorno = lindero(sesion, parcela)
    con_margen, bbox, lat0 = recorte(contorno, proveedores.margen_m)
    tamano = tamano_imagen(bbox, lat0)
    hoy = datetime.now(UTC).date()

    anios: set[int] = set()
    for fila in filas:
        if fila.papel == "anterior_al_corte":
            anios |= {2019, 2020}
        elif fila.papel == "anual":
            anios.add(fila.periodo)
        elif fila.papel == "reciente":
            anios |= {hoy.year - 1, hoy.year}
    medidas: dict[date, Medida] = {}
    for anio in sorted(anios):
        medidas.update(
            sentinel.nubes(con_margen, date(anio, 1, 1), min(date(anio, 12, 31), hoy), lat0, consumo)
        )
    usables = utilizables(medidas, proveedores.nubes_max_pct)

    actuales = [
        f
        for f in juego_actual(sesion, parcela)
        if f.fuente == "sentinel2" and f.estado in ("generada", "pendiente")
    ]
    propias = {f.id for f in filas}
    usadas = {f.fecha_captura for f in actuales if f.fecha_captura}
    ya_hay_previa = any(f.papel == "anterior_al_corte" and f.id not in propias for f in actuales)
    previas = [f for f in filas if f.papel == "anterior_al_corte"]
    elegidas: list[tuple[ImagenParcela, date | None]] = list(
        zip(previas, elegir_previas(usables, usadas, len(previas)) + [None] * len(previas), strict=False)
    )
    elegidas += [(f, elegir_anual(usables, f.periodo)) for f in filas if f.papel == "anual"]
    for fila in (f for f in filas if f.papel == "reciente"):
        dia = elegir_reciente(usables, hoy)
        viejas = [
            v for v in actuales if v.papel == "reciente" and v.id not in propias and v.estado == "generada"
        ]
        if viejas and (dia is None or any(v.fecha_captura == dia for v in viejas)):
            dia = None  # no hay una más reciente que la del juego: la del juego se queda
            fila.reemplazada_en = ahora()
        elif dia is not None:
            # La reciente nueva reemplaza a la anterior del juego (Buscar más imágenes la renueva).
            for vieja in viejas:
                vieja.reemplazada_en = ahora()
        elegidas.append((fila, dia))

    for fila, dia in elegidas:
        if dia is None:
            fila.estado = "sin_imagen_utilizable"
            # "Buscar más imágenes" que no encontró otra fecha no deja un hueco en la tira.
            if fila.papel == "anterior_al_corte" and ya_hay_previa:
                fila.reemplazada_en = ahora()
            continue
        try:
            escena = sentinel.escena(con_margen, dia, consumo)
            fila.fecha_captura = dia
            fila.dias_respecto_al_corte = (dia - CORTE).days
            fila.resolucion_m = Decimal(RESOLUCION_M)
            fila.nubes_parcela_pct = Decimal(str(usables[dia].nubes_pct))
            fila.identificador_fuente = escena.identificador
            fila.proveedor = escena.satelite or "Sentinel-2"
            natural = None
            for version in ("natural", "infrarrojo"):
                png = dibujar_lindero(sentinel.imagen(bbox, dia, version, tamano, consumo), contorno, bbox)
                if natural is not None and natural.sha256 == sha256(png):
                    # Idénticas (una escena sin datos sobre el recorte): el mismo archivo sirve para las dos.
                    fila.documento_infrarrojo_id = natural.id
                    continue
                documento = _guardar_png(sesion, storage, fila, parcela.codigo, version, png)
                if version == "natural":
                    natural = documento
                    fila.documento_natural_id = documento.id
                else:
                    fila.documento_infrarrojo_id = documento.id
            fila.estado = "generada"
        except (ErrorSentinel, ErrorStorage) as exc:
            fila.estado, fila.error_detalle = "error", getattr(exc, "detalle", None) or str(exc)
            fila.documento_natural_id = fila.documento_infrarrojo_id = None


def _wayback(sesion: Session, proveedores: Proveedores, parcela: Parcela, filas: list[ImagenParcela]) -> None:
    centro = shape(lindero(sesion, parcela)).centroid
    try:
        capturas = proveedores.wayback.capturas(centro.y, centro.x)
    except ErrorWayback as exc:
        for fila in filas:
            fila.estado, fila.error_detalle = "error", exc.detalle
        return
    if not capturas:
        for fila in filas:
            fila.estado = "sin_imagen_utilizable"
        return
    plantilla = filas[0]
    for i, captura in enumerate(capturas):
        fila = (
            plantilla
            if i == 0
            else _nueva(parcela, plantilla.geometria_sha256, "esri_wayback", "alta_resolucion")
        )
        fila.fecha_captura = captura.fecha_captura
        fila.dias_respecto_al_corte = (captura.fecha_captura - CORTE).days
        fila.resolucion_m = Decimal(str(captura.resolucion_m)) if captura.resolucion_m is not None else None
        fila.identificador_fuente = str(captura.version)
        fila.proveedor = " · ".join(x for x in (captura.proveedor, captura.sensor) if x) or None
        fila.estado = "generada"
        if i:
            sesion.add(fila)
    for fila in filas[1:]:
        fila.estado = "sin_imagen_utilizable"


def procesar_siguiente(sesion: Session, storage: ClienteStorage) -> bool:
    """Toma las imágenes pendientes de una parcela y las resuelve juntas. False si no había trabajo."""
    proveedores = actual()
    if not proveedores.configurada or en_pausa(sesion, proveedores):
        return False
    primera = sesion.scalar(
        select(ImagenParcela)
        .where(ImagenParcela.estado == "pendiente")
        .order_by(ImagenParcela.creado_en)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if primera is None:
        return False
    parcela = sesion.get(Parcela, primera.parcela_id)
    filas = list(
        sesion.scalars(
            select(ImagenParcela)
            .where(
                ImagenParcela.parcela_id == parcela.id,
                ImagenParcela.geometria_sha256 == primera.geometria_sha256,
                ImagenParcela.estado == "pendiente",
            )
            .order_by(ImagenParcela.creado_en)
            .with_for_update(skip_locked=True)
        )
    )
    if primera.geometria_sha256 != huella(parcela):
        for fila in filas:
            fila.estado, fila.error_detalle = (
                "error",
                "La geometría de la parcela cambió antes de generar la imagen.",
            )
        sesion.commit()
        return True

    consumo = Consumo()
    try:
        sentinel = [f for f in filas if f.fuente == "sentinel2"]
        if sentinel:
            _sentinel(sesion, storage, proveedores, parcela, sentinel, consumo)
        wayback = [f for f in filas if f.fuente == "esri_wayback"]
        if wayback and proveedores.wayback is not None:
            _wayback(sesion, proveedores, parcela, wayback)
    except ErrorSentinel as exc:
        for fila in filas:
            if fila.estado == "pendiente":
                fila.estado, fila.error_detalle = "error", exc.detalle
    except Exception:
        log.exception("Falló la generación de imágenes de la parcela %s", parcela.id)
        for fila in filas:
            if fila.estado == "pendiente":
                fila.estado, fila.error_detalle = "error", "Falló la generación de la imagen."
    if consumo.peticiones:
        sesion.add(
            ConsumoImagenes(
                mes=_primer_dia_del_mes(),
                parcela_id=parcela.id,
                cooperativa_id=parcela.cooperativa_registro_id,
                pu=Decimal(str(round(consumo.pu, 3))),
                peticiones=consumo.peticiones,
            )
        )
    sesion.commit()
    log.info(
        "Imágenes de la parcela %s: %s filas, %.2f PU en %s peticiones",
        parcela.id,
        len(filas),
        consumo.pu,
        consumo.peticiones,
    )
    return True


# ---------- Lo que ve la interfaz ----------


def _orden(fila: ImagenParcela) -> date:
    if fila.fecha_captura:
        return fila.fecha_captura
    if fila.papel == "anual" and fila.periodo:
        return date(fila.periodo, 7, 1)
    if fila.papel == "anterior_al_corte":
        return CORTE
    return hoy_lima()


def salida(sesion: Session, storage: ClienteStorage | None, parcela: Parcela) -> ImagenesSalida:
    proveedores = actual()
    filas = sorted(juego_actual(sesion, parcela), key=lambda f: (_orden(f), f.fuente))
    alerta = tiene_alerta(sesion, parcela)
    ids = [i for f in filas for i in (f.documento_natural_id, f.documento_infrarrojo_id) if i]
    documentos = (
        {d.id: d for d in sesion.scalars(select(Documento).where(Documento.id.in_(ids)))} if ids else {}
    )

    def url(documento_id):
        if not documento_id or storage is None or documento_id not in documentos:
            return None
        try:
            return storage.url_firmada(documentos[documento_id].ruta)
        except ErrorStorage:
            return None

    pendientes = any(f.estado == "pendiente" for f in filas)
    if pendientes:
        estado = "pausada" if en_pausa(sesion, proveedores) else "pendiente"
    elif filas:
        estado = "generada"
    elif not alerta:
        estado = "sin_alerta"
    elif not proveedores.configurada:
        estado = "no_configurada"
    else:
        estado = "pendiente"  # la tendrá en la próxima vuelta del hilo
    return ImagenesSalida(
        estado=estado,
        tiene_alerta=alerta,
        imagenes=[
            ImagenSalida(
                id=f.id,
                fuente=f.fuente,
                papel=f.papel,
                periodo=f.periodo,
                fecha_captura=f.fecha_captura,
                dias_respecto_al_corte=f.dias_respecto_al_corte,
                resolucion_m=f.resolucion_m,
                nubes_parcela_pct=f.nubes_parcela_pct,
                identificador_fuente=f.identificador_fuente,
                proveedor=f.proveedor,
                estado=f.estado,
                error_detalle=f.error_detalle,
                url_natural=url(f.documento_natural_id),
                url_infrarrojo=url(f.documento_infrarrojo_id),
                sha256_natural=documentos[f.documento_natural_id].sha256
                if f.documento_natural_id in documentos
                else None,
            )
            for f in filas
        ],
        teselas_wayback=TESELAS,
        subdominios_wayback=list(SUBDOMINIOS),
        atribucion_sentinel=ATRIBUCION_SENTINEL,
        atribucion_wayback=ATRIBUCION_WAYBACK,
    )


# ---------- Acciones del personal ----------


def _no_excluida(parcela: Parcela) -> None:
    from app.services.expediente import no_excluida

    no_excluida(parcela)


def regenerar(contexto: Contexto, parcela: Parcela) -> None:
    """Regenera el juego de una parcela con alerta. El juego anterior queda como historial."""
    _no_excluida(parcela)
    if not tiene_alerta(contexto.sesion, parcela):
        raise error_api(
            400, "sin_alerta", "Esta parcela no tiene alertas de análisis; no se generan imágenes."
        )
    if not actual().configurada:
        raise error_api(400, "imagenes_no_configuradas", "La fuente de imágenes no está configurada.")
    actuales = juego_actual(contexto.sesion, parcela)
    if any(f.estado == "pendiente" for f in actuales):
        raise error_api(409, "imagenes_en_proceso", "Las imágenes de esta parcela ya se están generando.")
    for fila in actuales:
        fila.reemplazada_en = ahora()
    encolar(contexto.sesion, parcela, origen="regenerar", contexto=contexto)
    contexto.sesion.commit()


def buscar_mas(contexto: Contexto, parcela: Parcela) -> None:
    """Hasta 3 escenas más cercanas al corte y una reciente nueva (decisión del equipo, adenda 2, 17)."""
    _no_excluida(parcela)
    if not tiene_alerta(contexto.sesion, parcela):
        raise error_api(
            400, "sin_alerta", "Esta parcela no tiene alertas de análisis; no se generan imágenes."
        )
    if not actual().configurada:
        raise error_api(400, "imagenes_no_configuradas", "La fuente de imágenes no está configurada.")
    if any(f.estado == "pendiente" for f in juego_actual(contexto.sesion, parcela)):
        raise error_api(409, "imagenes_en_proceso", "Las imágenes de esta parcela ya se están generando.")
    encolar(contexto.sesion, parcela, origen="buscar_mas", contexto=contexto, solo_mas=True)
    contexto.sesion.commit()


def cargar_externa(
    contexto: Contexto, storage: ClienteStorage, parcela: Parcela, archivo, fuente: str, fecha_captura: date
) -> None:
    """Imagen que carga el administrador, con su fuente y su fecha de captura (7.1, regla 3)."""
    from app.services import documentos

    _no_excluida(parcela)
    if fecha_captura > hoy_lima():
        raise error_api(422, "fecha_futura", "La fecha de captura no puede ser futura.")
    # Se compara junto a las demás: tiene que ser una imagen, no un PDF.
    if detectar_tipo(archivo.contenido) not in ("jpg", "png"):
        raise error_api(422, "formato_no_admitido", "Sube la imagen en JPG o PNG.")
    fila = ImagenParcela(
        id=uuid.uuid4(),
        parcela_id=parcela.id,
        cooperativa_id=parcela.cooperativa_registro_id,
        fuente="externa",
        papel="externa",
        fecha_captura=fecha_captura,
        dias_respecto_al_corte=(fecha_captura - CORTE).days,
        proveedor=fuente,
        identificador_fuente=archivo.nombre,
        geometria_sha256=huella(parcela),
        estado="generada",
        cargada_por=contexto.usuario_id,
    )
    contexto.sesion.add(fila)
    contexto.sesion.flush()
    documento, ruta = documentos.guardar(
        contexto, storage, entidad="imagen", entidad_id=fila.id, tipo="imagen_externa", archivo=archivo
    )
    fila.documento_natural_id = documento.id
    registrar_auditoria(
        contexto,
        "imagenes.cargar_externa",
        "parcela",
        parcela.id,
        {
            "imagen_id": fila.id,
            "fuente": fuente,
            "fecha_captura": fecha_captura.isoformat(),
            "documento_id": documento.id,
        },
    )
    try:
        contexto.sesion.commit()
    except Exception:
        contexto.sesion.rollback()
        documentos.descartar(storage, ruta)
        raise


# ---------- DOP (12) ----------


def para_dop(sesion: Session, parcela: Parcela, revision) -> tuple[dict | None, dict[str, str]]:
    """Solo para una parcela con la alerta: la imagen de Sentinel-2 anterior al corte (la más cercana) y la
    reciente, con sus datos y huellas; las versiones de Wayback como datos; y la revisión vigente.
    Devuelve también las rutas en Storage de las dos imágenes, para dibujarlas en el PDF."""
    if not tiene_alerta(sesion, parcela):
        return None, {}
    filas = [f for f in juego_actual(sesion, parcela) if f.estado == "generada"]
    sentinel = [f for f in filas if f.fuente == "sentinel2" and f.documento_natural_id]
    previas = sorted((f for f in sentinel if f.fecha_captura <= CORTE), key=lambda f: f.fecha_captura)
    recientes = [f for f in sentinel if f.papel == "reciente"]
    elegidas = {
        "anterior_al_corte": previas[-1] if previas else None,
        "reciente": recientes[-1] if recientes else None,
    }
    documentos = {
        d.id: d
        for d in sesion.scalars(
            select(Documento).where(
                Documento.id.in_([f.documento_natural_id for f in elegidas.values() if f])
            )
        )
    }

    def dato(f: ImagenParcela | None) -> dict | None:
        if f is None:
            return None
        return {
            "id": str(f.id),
            "fuente": "Sentinel-2 L2A (Copernicus)",
            "fecha_captura": f.fecha_captura.isoformat(),
            "dias_respecto_al_corte": f.dias_respecto_al_corte,
            "resolucion_m": float(f.resolucion_m) if f.resolucion_m is not None else None,
            "nubes_parcela_pct": float(f.nubes_parcela_pct) if f.nubes_parcela_pct is not None else None,
            "identificador_fuente": f.identificador_fuente,
            "proveedor": f.proveedor,
            "sha256": documentos[f.documento_natural_id].sha256,
            "atribucion": ATRIBUCION_SENTINEL.format(anio=f.fecha_captura.year),
        }

    bloque = {
        "anterior_al_corte": dato(elegidas["anterior_al_corte"]),
        "reciente": dato(elegidas["reciente"]),
        "alta_resolucion": [
            {
                "fecha_captura": f.fecha_captura.isoformat(),
                "proveedor": f.proveedor,
                "resolucion_m": float(f.resolucion_m) if f.resolucion_m is not None else None,
                "version_wayback": f.identificador_fuente,
            }
            for f in sorted((x for x in filas if x.fuente == "esri_wayback"), key=lambda x: x.fecha_captura)
        ],
        "atribucion_alta_resolucion": ATRIBUCION_WAYBACK,
        "revision": revision,
    }
    rutas = {papel: documentos[f.documento_natural_id].ruta for papel, f in elegidas.items() if f}
    return bloque, rutas

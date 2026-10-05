"""Lectura de una ventana de un GeoTIFF en bloques por HTTP con peticiones por rango.

Hecho para los mapas de MapBiomas Perú (adenda de la Parte 4): BigTIFF de un canal de 8 bits, en grados
WGS 84, en bloques de 256 x 256, con compresión LZW y predictor horizontal. También admite TIFF clásico,
sin compresión o Deflate. Solo pide la cabecera, las entradas de la tabla de bloques que necesita y esos
bloques: nunca baja el archivo completo ni escribe en disco. No depende de GDAL ni de otra librería de
rásteres; solo de numpy.
"""

import math
import struct
import zlib
from dataclasses import dataclass, field

import httpx
import numpy as np

CABECERA_INICIAL = 64 * 1024
# tipo TIFF -> (bytes, formato de struct)
TIPOS = {
    1: (1, "B"),
    2: (1, "c"),
    3: (2, "H"),
    4: (4, "I"),
    5: (8, "II"),
    7: (1, "B"),
    11: (4, "f"),
    12: (8, "d"),
    13: (4, "I"),
    16: (8, "Q"),
    17: (8, "q"),
    18: (8, "Q"),
}
ANCHO, ALTO, BITS, COMPRESION, MUESTRAS = 256, 257, 258, 259, 277
PREDICTOR, TILE_ANCHO, TILE_ALTO, TILE_OFFSETS, TILE_BYTES = 317, 322, 323, 324, 325
FORMATO_MUESTRA, ESCALA, PUNTO_ATADO, GEOCLAVES = 339, 33550, 33922, 34735
VERSION = ("etag", "last-modified", "x-goog-generation")


class ErrorCog(Exception):
    pass


@dataclass
class _Tabla:
    posicion: int
    tipo: int
    cantidad: int


@dataclass
class Cabecera:
    url: str
    ancho: int
    alto: int
    tile_ancho: int
    tile_alto: int
    compresion: int
    predictor: int
    x0: float  # longitud del borde izquierdo
    y0: float  # latitud del borde superior
    dx: float  # grados por píxel, en longitud
    dy: float  # grados por píxel, en latitud (positivo)
    orden: str
    offsets: _Tabla
    bytes_bloque: _Tabla
    version: dict[str, str] = field(default_factory=dict)

    @property
    def bloques_por_fila(self) -> int:
        return math.ceil(self.ancho / self.tile_ancho)


class LectorCog:
    def __init__(self, cliente: httpx.Client):
        self._cliente = cliente
        self.peticiones = 0
        self.bytes_leidos = 0

    def _rango(self, url: str, inicio: int, fin: int) -> httpx.Response:
        """Bytes [inicio, fin] (inclusive). Exige 206: un servidor que ignore el rango mandaría el archivo
        entero."""
        r = self._cliente.get(url, headers={"Range": f"bytes={inicio}-{fin}"})
        self.peticiones += 1
        if r.status_code == 404:
            raise ErrorCog(f"No existe el archivo {url}.")
        if r.status_code != 206:
            raise ErrorCog(
                f"El servidor respondió {r.status_code} a una petición por rango; se esperaba 206."
            )
        self.bytes_leidos += len(r.content)
        return r

    def cabecera(self, url: str) -> Cabecera:
        """Lee los primeros 64 KiB y, aparte, solo los valores de la cabecera guardados más adelante (en
        MapBiomas, la georreferencia va después de la tabla de bloques)."""
        r = self._rango(url, 0, CABECERA_INICIAL - 1)
        trozos = {0: r.content}
        for _ in range(4):
            try:
                cab = _leer_cabecera(url, trozos)
            except _FaltanBytes as falta:
                if falta.posicion is None:
                    raise ErrorCog("La cabecera del GeoTIFF no cabe en lo admitido.") from None
                trozos[falta.posicion] = self._rango(
                    url, falta.posicion, falta.posicion + falta.tamano - 1
                ).content
                continue
            cab.version = {k: r.headers[k] for k in VERSION if k in r.headers}
            return cab
        raise ErrorCog("La cabecera del GeoTIFF está demasiado dispersa.")

    def _entradas(self, cab: Cabecera, tabla: _Tabla, desde: int, hasta: int) -> list[int]:
        tam, fmt = TIPOS[tabla.tipo]
        inicio = tabla.posicion + desde * tam
        datos = self._rango(cab.url, inicio, inicio + (hasta - desde + 1) * tam - 1).content
        return list(struct.unpack(f"{cab.orden}{hasta - desde + 1}{fmt}", datos))

    def ventana(self, cab: Cabecera, col0: int, fila0: int, col1: int, fila1: int) -> np.ndarray:
        """Píxeles [fila0, fila1) x [col0, col1) como uint8. Fuera del mapa, 0."""
        col0, fila0 = max(col0, 0), max(fila0, 0)
        col1, fila1 = min(col1, cab.ancho), min(fila1, cab.alto)
        salida = np.zeros((max(fila1 - fila0, 0), max(col1 - col0, 0)), dtype=np.uint8)
        if salida.size == 0:
            return salida
        tw, th = cab.tile_ancho, cab.tile_alto
        for tf in range(fila0 // th, (fila1 - 1) // th + 1):
            tc0, tc1 = col0 // tw, (col1 - 1) // tw
            primero = tf * cab.bloques_por_fila + tc0
            ultimo = tf * cab.bloques_por_fila + tc1
            offsets = self._entradas(cab, cab.offsets, primero, ultimo)
            tamanos = self._entradas(cab, cab.bytes_bloque, primero, ultimo)
            for i, tc in enumerate(range(tc0, tc1 + 1)):
                bloque = self._bloque(cab, offsets[i], tamanos[i])
                # Recorte del bloque que cae en la ventana
                f_a, f_b = max(fila0, tf * th), min(fila1, (tf + 1) * th)
                c_a, c_b = max(col0, tc * tw), min(col1, (tc + 1) * tw)
                salida[f_a - fila0 : f_b - fila0, c_a - col0 : c_b - col0] = bloque[
                    f_a - tf * th : f_b - tf * th, c_a - tc * tw : c_b - tc * tw
                ]
        return salida

    def _bloque(self, cab: Cabecera, offset: int, tamano: int) -> np.ndarray:
        forma = (cab.tile_alto, cab.tile_ancho)
        if tamano == 0:  # bloque vacío: GDAL lo deja sin escribir
            return np.zeros(forma, dtype=np.uint8)
        crudo = self._rango(cab.url, offset, offset + tamano - 1).content
        esperado = forma[0] * forma[1]
        if cab.compresion == 1:
            datos = crudo
        elif cab.compresion == 5:
            datos = lzw(crudo, esperado)
        elif cab.compresion in (8, 32946):
            datos = zlib.decompress(crudo)
        else:
            raise ErrorCog(f"Compresión TIFF {cab.compresion} no admitida.")
        if len(datos) < esperado:
            raise ErrorCog("Un bloque del GeoTIFF vino incompleto.")
        matriz = np.frombuffer(datos[:esperado], dtype=np.uint8).reshape(forma)
        if cab.predictor == 2:
            matriz = np.cumsum(matriz, axis=1, dtype=np.uint8)  # suma con desborde módulo 256
        return matriz


class _FaltanBytes(Exception):
    def __init__(self, posicion: int | None = None, tamano: int = 0):
        super().__init__()
        self.posicion, self.tamano = posicion, tamano


def _bytes_en(trozos: dict[int, bytes], posicion: int, tamano: int) -> bytes:
    for inicio, datos in trozos.items():
        if inicio <= posicion and posicion + tamano <= inicio + len(datos):
            return datos[posicion - inicio : posicion - inicio + tamano]
    # Se pide de una vez un poco más, por si los valores vecinos también están lejos.
    raise _FaltanBytes(posicion, max(tamano, 4096))


def _leer_cabecera(url: str, trozos: dict[int, bytes]) -> Cabecera:
    d = trozos[0]
    if len(d) < 16:
        raise ErrorCog("El archivo no es un TIFF.")
    if d[:2] == b"II":
        o = "<"
    elif d[:2] == b"MM":
        o = ">"
    else:
        raise ErrorCog("El archivo no es un TIFF.")
    magia = struct.unpack(o + "H", d[2:4])[0]
    if magia == 43:
        grande, ifd = True, struct.unpack(o + "Q", d[8:16])[0]
    elif magia == 42:
        grande, ifd = False, struct.unpack(o + "I", d[4:8])[0]
    else:
        raise ErrorCog("El archivo no es un TIFF.")
    tam_n, tam_e = (8, 20) if grande else (2, 12)
    n = struct.unpack(o + ("Q" if grande else "H"), _bytes_en(trozos, ifd, tam_n))[0]
    directorio = _bytes_en(trozos, ifd + tam_n, n * tam_e)
    etiquetas: dict[int, tuple[int, int, int, bytes]] = {}
    for i in range(n):
        e = directorio[i * tam_e : (i + 1) * tam_e]
        tag, tipo = struct.unpack(o + "HH", e[:4])
        cantidad = struct.unpack(o + ("Q" if grande else "I"), e[4:12] if grande else e[4:8])[0]
        valor = e[12:20] if grande else e[8:12]
        etiquetas[tag] = (tipo, cantidad, valor, e)

    def posicion(tag: int) -> int | None:
        tipo, cantidad, valor, _ = etiquetas[tag]
        if TIPOS[tipo][0] * cantidad <= (8 if grande else 4):
            return None
        return struct.unpack(o + ("Q" if grande else "I"), valor)[0]

    def valores(tag: int) -> tuple:
        tipo, cantidad, valor, _ = etiquetas[tag]
        tam, fmt = TIPOS[tipo]
        p = posicion(tag)
        crudo = valor[: tam * cantidad] if p is None else _bytes_en(trozos, p, tam * cantidad)
        return struct.unpack(f"{o}{cantidad * len(fmt)}{fmt[0]}", crudo)

    def uno(tag: int, defecto: int | None = None) -> int:
        if tag not in etiquetas:
            if defecto is None:
                raise ErrorCog(f"Falta la etiqueta TIFF {tag}.")
            return defecto
        return int(valores(tag)[0])

    if TILE_ANCHO not in etiquetas or TILE_OFFSETS not in etiquetas:
        raise ErrorCog("El GeoTIFF no está organizado en bloques (tiles): leer una ventana traería franjas.")
    if uno(BITS) != 8 or uno(MUESTRAS, 1) != 1 or uno(FORMATO_MUESTRA, 1) != 1:
        raise ErrorCog("Se esperaba un canal de 8 bits sin signo.")
    if ESCALA not in etiquetas or PUNTO_ATADO not in etiquetas:
        raise ErrorCog("El GeoTIFF no trae su georreferencia.")
    dx, dy, _ = valores(ESCALA)
    i, j, _, x, y, _ = valores(PUNTO_ATADO)[:6]
    x0, y0 = x - i * dx, y + j * dy
    if GEOCLAVES in etiquetas:
        claves = valores(GEOCLAVES)
        geo = {claves[k]: claves[k + 3] for k in range(4, len(claves), 4)}
        if geo.get(1024) not in (None, 2):  # GTModelTypeGeoKey: 2 = geográfico
            raise ErrorCog("El GeoTIFF no está en coordenadas geográficas.")
        if geo.get(1025) == 2:  # RasterPixelIsPoint: el punto atado es el centro del píxel
            x0, y0 = x0 - dx / 2, y0 + dy / 2
    tabla = {}
    for tag in (TILE_OFFSETS, TILE_BYTES):
        tipo, cantidad, _, _ = etiquetas[tag]
        p = posicion(tag)
        if p is None:
            raise ErrorCog("Tabla de bloques demasiado pequeña.")
        tabla[tag] = _Tabla(p, tipo, cantidad)
    return Cabecera(
        url=url,
        ancho=uno(ANCHO),
        alto=uno(ALTO),
        tile_ancho=uno(TILE_ANCHO),
        tile_alto=uno(TILE_ALTO),
        compresion=uno(COMPRESION, 1),
        predictor=uno(PREDICTOR, 1),
        x0=x0,
        y0=y0,
        dx=dx,
        dy=dy,
        orden=o,
        offsets=tabla[TILE_OFFSETS],
        bytes_bloque=tabla[TILE_BYTES],
    )


def lzw(datos: bytes, esperado: int = 0) -> bytes:
    """Decodificador LZW de TIFF 6.0 (sección 13): códigos de 9 a 12 bits, el bit más significativo
    primero y cambio de ancho anticipado, como libtiff."""
    salida = bytearray()
    tabla: list[bytes] = [bytes([k]) for k in range(256)] + [b"", b""]
    ancho = 9
    pos = 0
    total = len(datos) * 8
    previo: bytes | None = None
    relleno = datos + b"\0\0\0"
    while pos + ancho <= total:
        k = pos >> 3
        trozo = (relleno[k] << 16) | (relleno[k + 1] << 8) | relleno[k + 2]
        codigo = (trozo >> (24 - (pos & 7) - ancho)) & ((1 << ancho) - 1)
        pos += ancho
        if codigo == 257:  # fin de la información
            break
        if codigo == 256:  # limpiar la tabla
            del tabla[258:]
            ancho = 9
            previo = None
            continue
        if previo is None:
            entrada = tabla[codigo]
        else:
            if codigo < len(tabla):
                entrada = tabla[codigo]
                tabla.append(previo + entrada[:1])
            elif codigo == len(tabla):
                entrada = previo + previo[:1]
                tabla.append(entrada)
            else:
                raise ErrorCog("Código LZW inválido en un bloque del GeoTIFF.")
            if len(tabla) >= (1 << ancho) - 1 and ancho < 12:
                ancho += 1
        salida += entrada
        previo = entrada
        if esperado and len(salida) >= esperado:
            break
    return bytes(salida)

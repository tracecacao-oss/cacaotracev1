"""GeoTIFF sintéticos para las pruebas de MapBiomas: se arman en memoria y se sirven por rangos con un
transporte HTTP simulado. Ninguna prueba sale a internet."""

import re
import struct

import httpx
import numpy as np

D = 0.0002694945852358564  # tamaño del píxel de MapBiomas Perú, en grados


def lzw_codificar(datos: bytes) -> bytes:
    """Codificador LZW de TIFF (bit más significativo primero, cambio de ancho anticipado, como libtiff)."""
    bits: list[tuple[int, int]] = []
    tabla = {bytes([i]): i for i in range(256)}
    siguiente, ancho = 258, 9
    bits.append((256, ancho))
    w = b""
    for byte in datos:
        wc = w + bytes([byte])
        if wc in tabla:
            w = wc
            continue
        bits.append((tabla[w], ancho))
        tabla[wc] = siguiente
        siguiente += 1
        if siguiente >= 4094:
            bits.append((256, ancho))
            tabla = {bytes([i]): i for i in range(256)}
            siguiente, ancho = 258, 9
        elif siguiente > (1 << ancho) - 1:
            ancho += 1
        w = bytes([byte])
    if w:
        bits.append((tabla[w], ancho))
        siguiente += 1
        if siguiente > (1 << ancho) - 1 and ancho < 12:
            ancho += 1
    bits.append((257, ancho))
    acumulado, n = 0, 0
    salida = bytearray()
    for codigo, a in bits:
        acumulado = (acumulado << a) | codigo
        n += a
        while n >= 8:
            n -= 8
            salida.append((acumulado >> n) & 0xFF)
    if n:
        salida.append((acumulado << (8 - n)) & 0xFF)
    return bytes(salida)


def geotiff(
    clases: np.ndarray,
    x0: float,
    y0: float,
    *,
    d: float = D,
    bloque: int = 16,
    compresion: int = 5,
    predictor: int = 2,
    relleno: int = 0,
) -> bytes:
    """BigTIFF de un canal uint8 en bloques, en grados WGS 84, como los de MapBiomas. Con `relleno`, la
    georreferencia queda al final del archivo, lejos de la cabecera, como en los archivos reales."""
    alto, ancho = clases.shape
    filas_b, cols_b = -(-alto // bloque), -(-ancho // bloque)
    bloques = []
    for fb in range(filas_b):
        for cb in range(cols_b):
            t = np.zeros((bloque, bloque), dtype=np.uint8)
            parte = clases[fb * bloque : (fb + 1) * bloque, cb * bloque : (cb + 1) * bloque]
            t[: parte.shape[0], : parte.shape[1]] = parte
            if predictor == 2:
                t = np.diff(t.astype(np.int16), axis=1, prepend=0).astype(np.uint8)
            crudo = t.tobytes()
            bloques.append(lzw_codificar(crudo) if compresion == 5 else crudo)

    n_etiquetas = 16
    ifd = 16
    fuera = ifd + 8 + n_etiquetas * 20 + 8  # donde empiezan los valores que no caben en la entrada
    offsets_pos = fuera
    bytes_pos = offsets_pos + 8 * len(bloques)
    datos_pos = bytes_pos + 4 * len(bloques)
    offsets, pos = [], datos_pos
    for b in bloques:
        offsets.append(pos)
        pos += len(b)
    geo_pos = pos + relleno
    escala = struct.pack("<3d", d, d, 0.0)
    atado = struct.pack("<6d", 0.0, 0.0, 0.0, x0, y0, 0.0)
    geoclaves = struct.pack("<16H", 1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 1, 2048, 0, 1, 4326)

    def entrada(tag, tipo, cantidad, valor_o_pos, en_linea=True):
        if en_linea:
            fmt = {3: "<H", 4: "<I", 16: "<Q"}[tipo]
            valor = struct.pack(fmt, valor_o_pos).ljust(8, b"\0")
        else:
            valor = struct.pack("<Q", valor_o_pos)
        return struct.pack("<HHQ", tag, tipo, cantidad) + valor

    entradas = [
        entrada(256, 3, 1, ancho),
        entrada(257, 3, 1, alto),
        entrada(258, 3, 1, 8),
        entrada(259, 3, 1, compresion),
        entrada(262, 3, 1, 1),
        entrada(277, 3, 1, 1),
        entrada(284, 3, 1, 1),
        entrada(317, 3, 1, predictor),
        entrada(322, 3, 1, bloque),
        entrada(323, 3, 1, bloque),
        entrada(324, 16, len(bloques), offsets_pos, en_linea=False),
        entrada(325, 4, len(bloques), bytes_pos, en_linea=False),
        entrada(339, 3, 1, 1),
        entrada(33550, 12, 3, geo_pos, en_linea=False),
        entrada(33922, 12, 6, geo_pos + 24, en_linea=False),
        entrada(34735, 3, 16, geo_pos + 72, en_linea=False),
    ]
    # Con más de dos bloques, las dos tablas quedan fuera de la entrada, como en MapBiomas.
    if len(bloques) <= 2:
        raise ValueError("Usar una imagen de más de dos bloques")
    cuerpo = struct.pack("<2sHHHQ", b"II", 43, 8, 0, ifd)
    cuerpo += struct.pack("<Q", n_etiquetas) + b"".join(entradas) + struct.pack("<Q", 0)
    cuerpo += struct.pack(f"<{len(offsets)}Q", *offsets)
    cuerpo += struct.pack(f"<{len(bloques)}I", *[len(b) for b in bloques])
    cuerpo += b"".join(bloques) + b"\0" * relleno + escala + atado + geoclaves
    return cuerpo


def servidor_por_rangos(archivos: dict[str, bytes]):
    """Transporte simulado: responde 206 con el rango pedido, como Google Cloud Storage. Guarda los
    rangos pedidos para comprobar que nunca se bajó un archivo entero."""
    pedidos: list[tuple[str, int, int]] = []

    def responder(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url not in archivos:
            return httpx.Response(404)
        contenido = archivos[url]
        m = re.fullmatch(r"bytes=(\d+)-(\d+)", request.headers.get("range", ""))
        if not m:
            return httpx.Response(200, content=contenido)
        a, b = int(m.group(1)), min(int(m.group(2)), len(contenido) - 1)
        pedidos.append((url, a, b))
        return httpx.Response(
            206,
            content=contenido[a : b + 1],
            headers={
                "content-range": f"bytes {a}-{b}/{len(contenido)}",
                "accept-ranges": "bytes",
                "etag": '"prueba"',
                "x-goog-generation": "1",
            },
        )

    responder.pedidos = pedidos
    return responder

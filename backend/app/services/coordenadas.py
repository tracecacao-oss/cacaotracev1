"""Listas de coordenadas escritas o copiadas: texto pegado, .txt, .csv o .xlsx.

Cada vértice es una latitud y una longitud en grados: decimales (con punto o con coma) o grados,
minutos y segundos (6°57'12"S). Un vértice solo es un punto; tres o más, un polígono. Las parcelas
se separan con una línea en blanco, con una línea que solo trae el nombre o con una columna de
nombre. UTM no se acepta: se detecta y se pide escribir grados.

Como en el Perú la latitud va de 0 a -18.5 y la longitud de -68.5 a -81.5, los dos rangos no se
cruzan: si no hay encabezados se reconoce cuál es cuál por su tamaño, y si ambas vienen sin signo
se toman como sur y oeste.
"""

import re
import unicodedata

from app.services.tablas import ErrorTabla, leer_tabla

ENCABEZADOS = {
    "lat": {"lat", "latitud", "latitude", "y"},
    "lon": {"lon", "lng", "long", "longitud", "longitude", "x"},
    "nombre": {"nombre", "parcela", "name", "codigo", "id"},
    "utm": {"este", "norte", "east", "north", "easting", "northing", "utm", "zona"},
}
MAXIMO_LINEAS = 20000

MENSAJE_UTM = (
    "Las coordenadas parecen estar en UTM (metros). Escríbelas en grados de latitud y longitud, "
    "por ejemplo -6.9512, -76.5487."
)

# Grados, minutos y segundos con hemisferio antes o después: 6°57'12.5"S, S 6° 57.2', 76º33'W.
_GMS = re.compile(
    r"(?P<h1>\b[NSEOW])?\s*(?P<signo>[-+])?(?P<g>\d{1,3}(?:[.,]\d+)?)\s*[°º˚]\s*"
    r"(?:(?P<m>\d{1,2}(?:[.,]\d+)?)\s*['′’´]\s*)?"
    r"(?:(?P<s>\d{1,2}(?:[.,]\d+)?)\s*(?:\"|″|”|''|’’)\s*)?"
    r"(?P<h2>[NSEOW]\b)?",
    re.IGNORECASE,
)
_DECIMAL = re.compile(r"[-+]?\d{1,3}[.,]\d+")
_DECIMAL_CON_COMA = re.compile(r"[-+]?\d{1,3},\d+")
_METROS = re.compile(r"\d{5,8}(?:[.,]\d+)?")


class ErrorCoordenadas(Exception):
    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def _sin_marcas(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _rol_de_encabezado(celda: str) -> str | None:
    palabras = set(re.findall(r"[a-z]+", _sin_marcas(celda)))
    for rol, nombres in ENCABEZADOS.items():
        if palabras & nombres:
            return rol
    return None


def _numero(texto: str) -> float:
    return float(texto.replace(",", "."))


def _gms(m: re.Match) -> tuple[float, str | None]:
    valor = _numero(m["g"]) + _numero(m["m"] or "0") / 60 + _numero(m["s"] or "0") / 3600
    hemisferio = (m["h1"] or m["h2"] or "").upper()
    if hemisferio in ("S", "W", "O") or m["signo"] == "-":
        valor = -valor
    rol = "lat" if hemisferio in ("N", "S") else "lon" if hemisferio in ("E", "W", "O") else None
    return valor, rol


def _leer_linea(texto: str) -> tuple[list[tuple[float, str | None]], list[str]]:
    """Valores (con su rol si se sabe) y palabras sueltas de una línea."""
    valores: list[tuple[float, str | None]] = []
    for m in _GMS.finditer(texto):
        if m["g"] and ("°" in m[0] or "º" in m[0] or "˚" in m[0]):
            valores.append(_gms(m))
    resto = _GMS.sub(" ; ", texto) if valores else texto
    # Si la línea usa punto decimal, las comas separan; si no, la coma es el decimal.
    con_punto = "." in resto
    if con_punto:
        resto = resto.replace(",", " ")
    palabras = []
    for ficha in re.split(r"[\s;|]+", resto):
        if not ficha:
            continue
        if _DECIMAL.fullmatch(ficha) and (con_punto or "," in ficha):
            valores.append((_numero(ficha), None))
        elif _METROS.fullmatch(ficha):
            raise ErrorCoordenadas("coordenadas_invalidas", MENSAJE_UTM)
        elif not con_punto and len(_DECIMAL_CON_COMA.findall(ficha)) > 1:
            valores.extend((_numero(n), None) for n in _DECIMAL_CON_COMA.findall(ficha))
        elif re.search(r"[^\W\d_]", ficha):
            palabras.append(ficha.strip(",:()[]"))
        # Números enteros cortos (1, 2, 3…) son la numeración de los vértices: se ignoran.
    return valores, palabras


def _parece_lat(v: float) -> bool:
    return abs(v) <= 18.6


def _parece_lon(v: float) -> bool:
    return 68 <= abs(v) <= 82


def _vertice(valores: list[tuple[float, str | None]], *, con_hemisferio: bool) -> list[float]:
    """[lon, lat] a partir de dos valores, por su rol o por su tamaño."""
    (a, rol_a), (b, rol_b) = valores
    if abs(a) > 180 or abs(b) > 180:
        raise ErrorCoordenadas("coordenadas_invalidas", MENSAJE_UTM)
    if rol_a == "lon" or rol_b == "lat":
        a, b = b, a
    elif not (rol_a or rol_b) and _parece_lon(a) and _parece_lat(b):
        a, b = b, a
    # Sin hemisferio escrito y ambas sin signo: en el Perú siempre son sur y oeste.
    if not con_hemisferio and a >= 0 and b >= 0 and _parece_lat(a) and _parece_lon(b):
        a, b = -a, -b
    return [b, a]


def _es_encabezado(palabras: list[str]) -> bool:
    """Una línea de títulos de columna: nombra la latitud o la longitud ("Parcela Norte" no lo es)."""
    nombres = {"lat", "latitud", "latitude", "lon", "lng", "long", "longitud", "longitude"}
    return any(set(re.findall(r"[a-z]+", _sin_marcas(p))) & nombres for p in palabras)


def _geometria(vertices: list[list[float]], nombre: str | None) -> dict:
    if len(vertices) == 1:
        return {"type": "Point", "coordinates": vertices[0]}
    if len(vertices) == 2:
        etiqueta = f"La parcela «{nombre}»" if nombre else "Una parcela"
        raise ErrorCoordenadas(
            "archivo_invalido",
            f"{etiqueta} tiene solo 2 vértices. Un polígono necesita al menos 3; para un punto escribe uno.",
        )
    anillo = vertices if vertices[0] == vertices[-1] else [*vertices, vertices[0]]
    return {"type": "Polygon", "coordinates": [anillo]}


def _agrupar(lineas: list[tuple[int, str | None, list | None]]) -> list[tuple[str | None, dict]]:
    """lineas: (número, nombre, vértice o None para separador). Junta los vértices de cada parcela."""
    grupos: list[tuple[str | None, list]] = []
    actual: list = []
    nombre_actual = None
    pendiente = None
    for _, nombre, vertice in lineas:
        if vertice is None:
            if actual:
                grupos.append((nombre_actual, actual))
                actual, nombre_actual, pendiente = [], None, None
            if nombre:
                pendiente = nombre
            continue
        nombre = nombre or pendiente
        if actual and nombre != nombre_actual:
            grupos.append((nombre_actual, actual))
            actual = []
        nombre_actual = nombre
        actual.append(vertice)
    if actual:
        grupos.append((nombre_actual, actual))
    if not grupos:
        raise ErrorCoordenadas("sin_geometrias", "No se encontró ninguna coordenada.")
    return [(nombre, _geometria(vertices, nombre)) for nombre, vertices in grupos]


def _error_de_linea(numero: int, texto: str) -> ErrorCoordenadas:
    corto = texto if len(texto) <= 60 else texto[:57] + "…"
    return ErrorCoordenadas(
        "archivo_invalido",
        f"No se entiende la línea {numero}: «{corto}». "
        "Escribe latitud y longitud, por ejemplo -6.9512, -76.5487.",
    )


def _lineas_de_texto(filas: list[str], primera_es_encabezado: bool) -> list:
    lineas = []
    for numero, texto in enumerate(filas, start=1):
        if not texto.strip():
            lineas.append((numero, None, None))
            continue
        valores, palabras = _leer_linea(texto)
        nombre = " ".join(palabras) or None
        if not valores and not palabras:
            # Solo números enteros, por ejemplo "-7 -77": no son coordenadas con precisión.
            raise _error_de_linea(numero, texto)
        if not valores:
            # Una línea solo con palabras: encabezado o nombre de la parcela que sigue.
            es_encabezado = (primera_es_encabezado and numero == 1) or _es_encabezado(palabras)
            lineas.append((numero, None if es_encabezado else nombre, None))
        elif len(valores) == 2:
            con_hemisferio = any(rol for _, rol in valores)
            lineas.append((numero, nombre, _vertice(valores, con_hemisferio=con_hemisferio)))
        else:
            raise _error_de_linea(numero, texto)
    return lineas


def _celda(fila: list[str], columnas: dict[str, int], rol: str) -> str:
    i = columnas.get(rol)
    return fila[i] if i is not None and i < len(fila) else ""


def _lineas_de_columnas(filas: list[list[str]], columnas: dict[str, int]) -> list:
    lineas = []
    for numero, fila in enumerate(filas[1:], start=2):
        lat, lon = _celda(fila, columnas, "lat"), _celda(fila, columnas, "lon")
        nombre = _celda(fila, columnas, "nombre") or None
        if not lat and not lon:
            lineas.append((numero, nombre, None))
            continue
        valores_lat, _ = _leer_linea(lat)
        valores_lon, _ = _leer_linea(lon)
        if len(valores_lat) != 1 or len(valores_lon) != 1:
            raise _error_de_linea(numero, f"{lat} {lon}")
        (v_lat, h_lat), (v_lon, h_lon) = valores_lat[0], valores_lon[0]
        vertice = _vertice([(v_lat, "lat"), (v_lon, "lon")], con_hemisferio=bool(h_lat or h_lon))
        lineas.append((numero, nombre, vertice))
    return lineas


def leer_texto(contenido: bytes) -> list[tuple[str | None, dict]]:
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("cp1252", errors="replace")
    filas = texto.splitlines()
    if len(filas) > MAXIMO_LINEAS:
        raise ErrorCoordenadas("archivo_invalido", "La lista tiene demasiadas líneas.")
    return _agrupar(_lineas_de_texto(filas, primera_es_encabezado=False))


def leer_tabla_de_coordenadas(extension: str, contenido: bytes) -> list[tuple[str | None, dict]]:
    try:
        filas = leer_tabla(extension, contenido)
    except ErrorTabla as exc:
        raise ErrorCoordenadas("archivo_invalido", exc.mensaje) from exc
    if len(filas) > MAXIMO_LINEAS:
        raise ErrorCoordenadas("archivo_invalido", "La tabla tiene demasiadas filas.")
    if not filas:
        raise ErrorCoordenadas("sin_geometrias", "No se encontró ninguna coordenada.")

    columnas: dict[str, int] = {}
    for i, celda in enumerate(filas[0]):
        rol = _rol_de_encabezado(celda) if celda else None
        if rol and rol not in columnas:
            columnas[rol] = i
    if "utm" in columnas and not {"lat", "lon"} <= columnas.keys():
        raise ErrorCoordenadas("coordenadas_invalidas", MENSAJE_UTM)
    if {"lat", "lon"} <= columnas.keys():
        return _agrupar(_lineas_de_columnas(filas, columnas))
    # Sin columnas reconocibles: cada fila se lee como una línea de texto.
    return _agrupar(_lineas_de_texto([" ; ".join(f) for f in filas], primera_es_encabezado=True))

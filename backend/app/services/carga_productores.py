"""Carga masiva de productores desde una hoja de cálculo (.csv o .xlsx).

Dos pasos: `analizar` revisa cada fila sin guardar nada; `registrar` vuelve a revisar el mismo
archivo y afilia las filas listas en una sola transacción, con las mismas reglas y la misma
auditoría que el alta de uno en uno. Las filas con problemas se informan y no se guardan.
"""

import re
import unicodedata
from pathlib import PurePath

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.contexto import Contexto
from app.errores import error_api
from app.models import Afiliacion, Cooperativa, Productor
from app.schemas.productores import CargaMasiva, FilaCarga, ProductorNuevo
from app.services import productores
from app.services.auditoria import registrar_auditoria
from app.services.documentos import Archivo
from app.services.tablas import ErrorTabla, leer_tabla

Filas = list[tuple[FilaCarga, ProductorNuevo | None]]

TAMANO_MAXIMO = 2 * 1024 * 1024
MAXIMO_FILAS = 1000

# Columna de la API -> nombres de encabezado aceptados (sin tildes, espacios ni signos).
COLUMNAS = {
    "dni": {"dni", "documento", "nrodni", "numerodni", "numerodedni", "documentodeidentidad"},
    "nombres": {"nombres", "nombre"},
    "apellidos": {"apellidos", "apellido"},
    "direccion_postal": {"direccionpostal", "direccion", "domicilio"},
    "telefono": {"telefono", "celular", "movil"},
    "correo_contacto": {"correo", "correocontacto", "correodecontacto", "email", "correoelectronico"},
    "ruc": {"ruc"},
    "ppa_registrado": {"ppa", "pparegistrado", "registradoppa", "registradoenelppa", "enelppa"},
    "ppa_codigo": {"ppacodigo", "codigoppa", "numeroppa", "nroppa", "registroppa", "numerodeppa"},
    "codigo_agrodigital": {"codigoagrodigital", "agrodigital", "codigoapp", "codigoproductorapp"},
    "codigo_socio": {"codigosocio", "codigodesocio", "socio", "nrosocio", "numerodesocio"},
}
OBLIGATORIAS = ("dni", "nombres", "apellidos", "direccion_postal")
TITULOS = {
    "dni": "DNI",
    "nombres": "nombres",
    "apellidos": "apellidos",
    "direccion_postal": "dirección postal",
}
SI = {"si", "s", "x", "1", "true", "verdadero", "yes"}
NO = {"", "no", "n", "0", "false", "falso"}

MENSAJES_CAMPO = {
    "dni": "El DNI debe tener 8 dígitos.",
    "nombres": "Faltan los nombres.",
    "apellidos": "Faltan los apellidos.",
    "direccion_postal": "Falta la dirección postal.",
    "ruc": "El RUC debe tener 11 dígitos.",
    "correo_contacto": "El correo no es válido.",
    "telefono": "El teléfono es demasiado largo.",
    "ppa_codigo": "El código del PPA es demasiado largo.",
    "codigo_agrodigital": "El código de Agro Digital es demasiado largo.",
    "codigo_socio": "El código de socio es demasiado largo.",
}


def _clave(texto: str) -> str:
    sin_marcas = unicodedata.normalize("NFD", texto.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in sin_marcas if not unicodedata.combining(c)))


def _columnas(encabezados: list[str]) -> tuple[dict[str, int], list[str]]:
    columnas, ignoradas = {}, []
    for i, titulo in enumerate(encabezados):
        clave = _clave(titulo)
        campo = next((c for c, nombres in COLUMNAS.items() if clave in nombres), None)
        if campo and campo not in columnas:
            columnas[campo] = i
        elif titulo.strip():
            ignoradas.append(titulo.strip())
    return columnas, ignoradas


def _dni(texto: str) -> str:
    """Solo dígitos. Excel borra los ceros a la izquierda: un DNI de 6 o 7 cifras se completa."""
    digitos = re.sub(r"[\s.\-]", "", texto)
    if digitos.isdigit() and len(digitos) in (6, 7):
        return digitos.zfill(8)
    return digitos


def _fila(numero: int, celdas: list[str], columnas: dict) -> tuple[FilaCarga, ProductorNuevo | None]:
    valor = {campo: (celdas[i].strip() if i < len(celdas) else "") for campo, i in columnas.items()}
    datos: dict = {campo: v for campo, v in valor.items() if v}
    mensajes = []
    if "dni" in datos:
        datos["dni"] = _dni(datos["dni"])
    ppa = _clave(valor.get("ppa_registrado", ""))
    if ppa in SI:
        datos["ppa_registrado"] = True
    elif ppa in NO:
        # Si trae el número del PPA, está registrado aunque la columna quede vacía.
        datos["ppa_registrado"] = bool(datos.get("ppa_codigo"))
    else:
        mensajes.append("En «PPA» escribe sí o no.")
        datos.pop("ppa_registrado", None)
    try:
        modelo = ProductorNuevo(**datos)
    except ValidationError as exc:
        campos = sorted({str(e["loc"][0]) for e in exc.errors() if e.get("loc")})
        mensajes.extend(MENSAJES_CAMPO.get(c, f"Revisa el campo {c}.") for c in campos)
        modelo = None
    fila = FilaCarga(
        fila=numero,
        dni=datos.get("dni"),
        nombres=datos.get("nombres"),
        apellidos=datos.get("apellidos"),
        estado="error" if mensajes else "lista",
        mensajes=mensajes,
    )
    return fila, None if mensajes else modelo


def _leer(archivo: Archivo) -> tuple[Filas, list[str]]:
    extension = PurePath(archivo.nombre or "").suffix.lower()
    if extension not in (".csv", ".xlsx"):
        raise error_api(422, "formato_no_admitido", "Sube la hoja de cálculo como .xlsx o .csv.")
    if not archivo.contenido:
        raise error_api(400, "archivo_vacio", "El archivo está vacío.")
    if len(archivo.contenido) > TAMANO_MAXIMO:
        raise error_api(422, "archivo_muy_grande", "El archivo supera el máximo de 2 MB.")
    try:
        filas = leer_tabla(extension, archivo.contenido)
    except ErrorTabla as exc:
        raise error_api(422, "archivo_invalido", exc.mensaje) from exc
    con_datos = [i for i, f in enumerate(filas) if any(c.strip() for c in f)]
    if not con_datos:
        raise error_api(400, "archivo_vacio", "La hoja no tiene datos.")
    # Los encabezados son la primera fila que nombra las columnas obligatorias; antes puede
    # haber filas de título, como "Padrón de socios 2026".
    inicio = next(
        (i for i in con_datos[:10] if all(c in _columnas(filas[i])[0] for c in OBLIGATORIAS)), con_datos[0]
    )
    columnas, ignoradas = _columnas(filas[inicio])
    faltan = [TITULOS[c] for c in OBLIGATORIAS if c not in columnas]
    if faltan:
        raise error_api(
            422,
            "columnas_faltantes",
            f"Faltan estas columnas: {', '.join(faltan)}. Usa la plantilla para ver los encabezados.",
        )
    datos = [(i + 1, f) for i, f in enumerate(filas) if i > inicio and any(c.strip() for c in f)]
    if not datos:
        raise error_api(400, "archivo_vacio", "La hoja no tiene productores debajo de los encabezados.")
    if len(datos) > MAXIMO_FILAS:
        raise error_api(422, "demasiadas_filas", f"Sube como máximo {MAXIMO_FILAS} productores por archivo.")
    return [_fila(numero, celdas, columnas) for numero, celdas in datos], ignoradas


def _revisar(contexto: Contexto, archivo: Archivo) -> tuple[Filas, list[str]]:
    filas, ignoradas = _leer(archivo)
    vistos: dict[str, int] = {}
    for fila, _ in filas:
        if fila.estado != "lista":
            continue
        if fila.dni in vistos:
            fila.estado = "repetida"
            fila.mensajes.append(f"El DNI ya aparece en la fila {vistos[fila.dni]}.")
        else:
            vistos[fila.dni] = fila.fila

    # Una sola consulta para saber qué DNI ya tienen una afiliación activa y dónde.
    afiliados = dict(
        contexto.sesion.execute(
            select(Productor.dni, Afiliacion.cooperativa_id)
            .join(Afiliacion, Afiliacion.productor_id == Productor.id)
            .where(
                Productor.dni.in_(list(vistos)),
                Productor.es_demo == _es_demo(contexto),
                Afiliacion.estado == "activa",
            )
        ).all()
    )
    for fila, _ in filas:
        if fila.estado != "lista" or fila.dni not in afiliados:
            continue
        if afiliados[fila.dni] == contexto.cooperativa_id:
            fila.estado = "ya_registrado"
            fila.mensajes.append("Ya está registrado en tu cooperativa.")
        else:
            # Sin revelar cuál es la otra cooperativa, como en el alta de uno en uno.
            fila.estado = "otra_cooperativa"
            fila.mensajes.append("Este DNI ya está afiliado a otra cooperativa.")
    return filas, ignoradas


def _resumen(nombre: str, filas: list[FilaCarga], ignoradas: list[str]) -> CargaMasiva:
    return CargaMasiva(
        archivo=nombre,
        total=len(filas),
        listas=sum(f.estado == "lista" for f in filas),
        creadas=sum(f.estado == "creada" for f in filas),
        con_problemas=sum(f.estado not in ("lista", "creada") for f in filas),
        columnas_ignoradas=ignoradas,
        filas=filas,
    )


def analizar(contexto: Contexto, archivo: Archivo) -> CargaMasiva:
    filas, ignoradas = _revisar(contexto, archivo)
    return _resumen(archivo.nombre, [f for f, _ in filas], ignoradas)


def registrar(contexto: Contexto, archivo: Archivo) -> CargaMasiva:
    filas, ignoradas = _revisar(contexto, archivo)
    listas = [(f, m) for f, m in filas if f.estado == "lista"]
    if not listas:
        raise error_api(400, "nada_que_registrar", "Ninguna fila está lista para registrarse.")
    for fila, modelo in listas:
        fila.productor_id = productores.registrar(contexto, modelo).id
        fila.estado = "creada"
    resumen = _resumen(archivo.nombre, [f for f, _ in filas], ignoradas)
    registrar_auditoria(
        contexto,
        "productor.carga_masiva",
        "cooperativa",
        contexto.cooperativa_id,
        {"archivo": archivo.nombre, "filas": resumen.total, "creados": resumen.creadas},
    )
    try:
        contexto.sesion.commit()
    except IntegrityError as exc:
        contexto.sesion.rollback()
        raise error_api(
            409,
            "carga_en_conflicto",
            "Alguien registró a uno de estos productores mientras tanto. Revisa el archivo de nuevo.",
        ) from exc
    return resumen


def _es_demo(contexto: Contexto) -> bool:
    """Parte 10: los DNI de una cooperativa de demostración solo se comparan con los de demostración."""
    cooperativa = contexto.sesion.get(Cooperativa, contexto.cooperativa_id)
    return bool(cooperativa and cooperativa.es_demo)

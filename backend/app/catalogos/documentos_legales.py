"""Los 7 documentos del expediente legal de la parcela (Parte 4).

`registro_consultable` dice si el documento tiene un registro público en línea contra el cual
cotejarlo. Confirmado con fuentes oficiales el 2026-10-05 (ver la especificación, "Los 7 documentos"):
- titulo_sunarp: "Conoce Aquí" de SUNARP, con el número de partida.
- cusaf: GeoSERFOR, capa "Cesiones en uso" (número, inicio, término y situación del contrato).
- sunafil: buscador de resoluciones del sistema inspectivo de SUNAFIL, por RUC.
- sunat: Consulta RUC de SUNAT.
- zonificacion: GeoSERFOR, capa Zonificación Forestal, con la resolución que la aprueba.
Sin registro en línea: la constancia de posesión (registro administrativo de quien la emite,
RM 0029-2020-MINAGRI) y la autorización forestal (GeoSERFOR casi no las publica).
Cambiar un valor aquí no exige migración.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TipoLegal:
    codigo: str
    nombre: str
    grupo: str
    tenencia: bool  # los dos de tenencia: basta uno y no admiten exención
    registro_consultable: bool


TIPOS = (
    TipoLegal("titulo_sunarp", "Título de propiedad inscrito en SUNARP", "Tenencia", True, True),
    TipoLegal("constancia_posesion", "Constancia de posesión", "Tenencia", True, False),
    TipoLegal(
        "cusaf",
        "Contrato de cesión en uso para sistemas agroforestales (CUSAF)",
        "Uso forestal",
        False,
        True,
    ),
    TipoLegal(
        "autorizacion_serfor",
        "Autorización forestal de SERFOR o de la autoridad regional",
        "Uso forestal",
        False,
        False,
    ),
    TipoLegal("sunafil", "Sustento laboral ante SUNAFIL", "Laboral", False, True),
    TipoLegal("sunat", "Ficha RUC u otro sustento de SUNAT", "Tributario", False, True),
    TipoLegal(
        "zonificacion", "Sustento de la zonificación forestal de la parcela", "Zonificación", False, True
    ),
)
POR_CODIGO = {t.codigo: t for t in TIPOS}
CODIGOS = tuple(POR_CODIGO)
TENENCIA = tuple(t.codigo for t in TIPOS if t.tenencia)
CON_EXENCION = tuple(t.codigo for t in TIPOS if not t.tenencia)

# ---------- Parte 8: expediente legal de la cooperativa ----------
# Seis casillas sin exenciones: las seis deben estar vigentes. `registro_consultable` trae los valores
# iniciales de la especificación ("Los 6 documentos"), que el equipo debe confirmar.

TIPOS_COOPERATIVA = (
    TipoLegal(
        "rnca", "Registro Nacional de Cooperativas Agrarias (MIDAGRI)", "Registro agrario", False, False
    ),
    TipoLegal(
        "partida_sunarp", "Partida registral de la cooperativa en SUNARP", "Identificación legal", False, True
    ),
    TipoLegal("ficha_ruc", "Ficha RUC de SUNAT", "Identificación legal", False, True),
    TipoLegal(
        "vigencia_poderes",
        "Vigencia de poderes del representante legal (SUNARP)",
        "Representación legal",
        False,
        True,
    ),
    TipoLegal(
        "ruc_comercio_exterior",
        "Sustento del RUC habilitado para comercio exterior",
        "Capacidad exportadora",
        False,
        True,
    ),
    TipoLegal(
        "registro_aduanas",
        "Registro como exportador ante SUNAT Aduanas",
        "Capacidad exportadora",
        False,
        False,
    ),
)
POR_CODIGO_COOPERATIVA = {t.codigo: t for t in TIPOS_COOPERATIVA}
CODIGOS_COOPERATIVA = tuple(POR_CODIGO_COOPERATIVA)


def tipo_legal(codigo: str) -> TipoLegal | None:
    """Un tipo legal de la parcela (Parte 4) o de la cooperativa (Parte 8)."""
    return POR_CODIGO.get(codigo) or POR_CODIGO_COOPERATIVA.get(codigo)

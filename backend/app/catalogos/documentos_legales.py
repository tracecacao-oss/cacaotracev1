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

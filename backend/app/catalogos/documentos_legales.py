"""Los 7 documentos del expediente legal de la parcela (Parte 4).

`registro_consultable` dice si el documento tiene un registro público contra el cual cotejarlo.
Son valores iniciales que el equipo debe confirmar; cambiar uno aquí no exige migración.
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
        False,
    ),
    TipoLegal(
        "autorizacion_serfor",
        "Autorización forestal de SERFOR o de la autoridad regional",
        "Uso forestal",
        False,
        False,
    ),
    TipoLegal("sunafil", "Sustento laboral ante SUNAFIL", "Laboral", False, False),
    TipoLegal("sunat", "Ficha RUC u otro sustento de SUNAT", "Tributario", False, True),
    TipoLegal(
        "zonificacion", "Sustento de la zonificación forestal de la parcela", "Zonificación", False, True
    ),
)
POR_CODIGO = {t.codigo: t for t in TIPOS}
CODIGOS = tuple(POR_CODIGO)
TENENCIA = tuple(t.codigo for t in TIPOS if t.tenencia)
CON_EXENCION = tuple(t.codigo for t in TIPOS if not t.tenencia)

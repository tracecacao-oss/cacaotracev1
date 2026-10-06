"""Documento de entrega de la tanda (adenda 3 de la Parte 5): de qué tipos puede ser, quién lo emite, cuándo
corresponde y cómo son su serie y su número, según la documentación de SUNAT.

Guía de remisión (consultada el 2026-10-05):
- RS 000123-2022/SUNAT y sus anexos 12, 13 y 28: la GRE desde el sistema del contribuyente usa una serie
  "T" + 3 alfanuméricos (remitente) o "V" + 3 alfanuméricos (transportista); desde SUNAT, EG02 a EG04 y EG07.
  El correlativo tiene de 1 a 8 dígitos, empieza en 1 y los ceros a la izquierda son opcionales.
- Reglas de validación de SUNAT (actualizadas al 26.08.2026), campo DespatchDocumentReference: aceptan
  T###, V###, EG01 a EG04, EG07, G### y series numéricas de 4 dígitos.
- Reglamento de Comprobantes de Pago, art. 9.4: la guía impresa lleva una serie de 3 dígitos numéricos.
- Una guía de remisión general no tiene registro público consultable: SUNAT solo la muestra, con Clave SOL,
  al remitente, al transportista o al destinatario.

Liquidación de compra (consultada el 2026-10-06):
- Reglamento de Comprobantes de Pago, art. 6, inciso 1.3 (RS 244-2019/SUNAT): la emite quien adquiere
  productos primarios de la actividad agropecuaria a personas naturales que no otorgan comprobante por
  carecer de RUC, mientras sus ventas del año no superen 75 UIT. Se emite en el SEE-SOL o desde el sistema
  del contribuyente; en formato impreso, solo en contingencia o en zonas sin conexión.
- Anexo N.° 27 de la RS 097-2012/SUNAT (texto de la RS 123-2022/SUNAT): la serie electrónica tiene 4
  caracteres alfanuméricos y empieza con "L" (ejemplo L001); el correlativo tiene hasta 8 dígitos y empieza
  en 1. En el SEE-SOL la serie es "E001".
- Reglamento de Comprobantes de Pago, art. 9.4: el comprobante impreso lleva una serie de 3 dígitos y un
  correlativo de 7. Para la contingencia se admiten también series numéricas de 4 dígitos, como en la guía.

El Comprobante de Operaciones de la Ley N.° 29972 que pedía la adenda queda fuera: la Ley N.° 31335
(Segunda Disposición Complementaria Derogatoria, El Peruano, 10/08/2021) derogó la Ley N.° 29972. Decisión
del equipo del 2026-10-06 (adenda 3, sección 12).

Ninguno de los dos se coteja en su fuente: quedan en "documentado".
"""

import re
from dataclasses import dataclass

from app.errores import error_api

NUMERO = re.compile(r"^[0-9]{1,8}$")


@dataclass(frozen=True)
class TipoDocumento:
    codigo: str
    nombre: str
    emisor: str
    cuando: str
    serie: re.Pattern
    ejemplo: str
    # El RUC del emisor debe ser el de la organización que recibe (5, regla 1).
    emite_la_organizacion: bool
    # Fecha de emisión: no posterior a la recepción, o entre la recepción y el plazo de la configuración.
    emitido_despues_de_recibir: bool


TIPOS = {
    t.codigo: t
    for t in (
        TipoDocumento(
            codigo="guia_remision",
            nombre="Guía de remisión",
            emisor="El productor, la organización que recibe o el transportista",
            cuando="Cuando el traslado se hizo con guía",
            serie=re.compile(r"^(?:[TV][A-Z0-9]{3}|EG0[1-4]|EG07|G[0-9]{3}|[0-9]{3,4})$"),
            ejemplo="T001-123 o EG07-45",
            emite_la_organizacion=False,
            emitido_despues_de_recibir=False,
        ),
        TipoDocumento(
            codigo="liquidacion_compra",
            nombre="Liquidación de compra",
            emisor="La organización que recibe",
            cuando="Cuando compra a un productor que no da comprobante por no tener RUC",
            serie=re.compile(r"^(?:L[A-Z0-9]{3}|E001|[0-9]{3,4})$"),
            ejemplo="L001-123 o E001-45",
            emite_la_organizacion=True,
            emitido_despues_de_recibir=True,
        ),
    )
}
CODIGOS = tuple(TIPOS)


def nombre(codigo: str | None) -> str:
    return TIPOS[codigo].nombre if codigo in TIPOS else "Documento de entrega"


def validar_numero(codigo: str, texto: str) -> str:
    """Devuelve la forma comparable SERIE-NÚMERO: serie numérica con 4 dígitos y número sin ceros a la
    izquierda. Responde 422 si no tiene un formato de SUNAT para ese tipo."""
    tipo = TIPOS[codigo]
    limpio = re.sub(r"\s+", "", texto.upper())
    serie, guion, numero = limpio.partition("-")
    error = error_api(
        422,
        "documento_numero_invalido",
        f"Escribe la serie y el número de la {tipo.nombre.lower()} separados por un guion, "
        f"por ejemplo {tipo.ejemplo}.",
    )
    if not guion or not tipo.serie.fullmatch(serie) or not NUMERO.fullmatch(numero) or int(numero) == 0:
        raise error
    if serie.isdigit():
        if int(serie) == 0:
            raise error
        serie = serie.zfill(4)
    return f"{serie}-{int(numero)}"

"""Serie y número de la guía de remisión (Parte 5), según la documentación de SUNAT consultada el
2026-10-05:

- RS 000123-2022/SUNAT y sus anexos 12, 13 y 28: la GRE desde el sistema del contribuyente usa una serie
  "T" + 3 alfanuméricos (remitente) o "V" + 3 alfanuméricos (transportista); desde SUNAT, EG02 a EG04 y EG07.
  El correlativo tiene de 1 a 8 dígitos, empieza en 1 y los ceros a la izquierda son opcionales.
- Reglas de validación de SUNAT (actualizadas al 26.08.2026), campo DespatchDocumentReference: aceptan
  T###, V###, EG01 a EG04, EG07, G### y series numéricas de 4 dígitos.
- Reglamento de Comprobantes de Pago, art. 9.4: la guía impresa lleva una serie de 3 dígitos numéricos.

Una guía de remisión general no tiene registro público consultable: SUNAT solo la muestra, con Clave SOL,
al remitente, al transportista o al destinatario. Por eso no se coteja y queda en "documentado".
"""

import re

from app.errores import error_api

SERIE = re.compile(r"^(?:[TV][A-Z0-9]{3}|EG0[1-4]|EG07|G[0-9]{3}|[0-9]{3,4})$")
NUMERO = re.compile(r"^[0-9]{1,8}$")
REGISTRO_CONSULTABLE = False


def validar_numero(texto: str) -> str:
    """Devuelve la forma comparable SERIE-NÚMERO: serie numérica con 4 dígitos y número sin ceros a la
    izquierda. Responde 422 si no tiene un formato de SUNAT."""
    limpio = re.sub(r"\s+", "", texto.upper())
    serie, guion, numero = limpio.partition("-")
    error = error_api(
        422,
        "guia_numero_invalido",
        "Escribe la serie y el número de la guía separados por un guion, por ejemplo T001-123 o EG07-45.",
    )
    if not guion or not SERIE.fullmatch(serie) or not NUMERO.fullmatch(numero) or int(numero) == 0:
        raise error
    if serie.isdigit():
        if int(serie) == 0:
            raise error
        serie = serie.zfill(4)
    return f"{serie}-{int(numero)}"

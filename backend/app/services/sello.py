"""Sello del DOP (Parte 5): una sola función produce la forma canónica del contenido, y su SHA-256 es la
huella. Cualquiera que tenga el contenido puede recalcularla y compararla con la publicada.

Forma canónica: JSON con las claves ordenadas, en UTF-8 y sin espacios sobrantes.
"""

import hashlib
import json
from typing import Any


def canonico(contenido: dict[str, Any]) -> bytes:
    return json.dumps(contenido, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def huella(contenido: dict[str, Any]) -> str:
    return hashlib.sha256(canonico(contenido)).hexdigest()

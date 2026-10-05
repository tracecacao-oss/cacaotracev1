"""Diagnóstico de Supabase Storage.

Sube un archivo de prueba al bucket, genera una URL firmada, lo descarga, compara el contenido
y lo borra. También comprueba que el bucket sea privado.

Lo corre una persona con las variables reales cargadas en su terminal, desde backend/:

    python scripts/check_storage.py

Variables necesarias: SUPABASE_URL, SUPABASE_SECRET_KEY y STORAGE_BUCKET (por defecto documentos).
"""

import base64
import os
import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.storage import ClienteStorage, ErrorStorage, sha256  # noqa: E402

# PNG de 1x1 píxel: un tipo que el bucket acepta aunque tenga restricción de tipos.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def paso(texto: str) -> None:
    print(f"  · {texto}...", end=" ", flush=True)


def main() -> int:
    faltan = [v for v in ("SUPABASE_URL", "SUPABASE_SECRET_KEY") if not os.environ.get(v)]
    if faltan:
        print(f"Faltan variables de entorno: {', '.join(faltan)}")
        return 2

    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    bucket = os.environ.get("STORAGE_BUCKET", "documentos")
    storage = ClienteStorage(supabase_url, os.environ["SUPABASE_SECRET_KEY"], bucket)
    ruta = f"_diagnostico/{uuid.uuid4()}.png"
    subido = False

    print(f"Diagnóstico de Storage en el bucket '{bucket}'")
    try:
        paso("Subiendo archivo de prueba")
        storage.subir(ruta, PNG_1X1, "image/png")
        subido = True
        print("ok")

        paso("Generando URL firmada de 5 minutos")
        url = storage.url_firmada(ruta)
        print("ok")

        paso("Descargando con la URL firmada")
        descarga = httpx.get(url, timeout=30)
        descarga.raise_for_status()
        print("ok")

        paso("Comparando contenido")
        if sha256(descarga.content) != sha256(PNG_1X1):
            print("FALLA: el contenido descargado no coincide")
            return 1
        print("ok")

        paso("Comprobando que el bucket sea privado")
        publica = httpx.get(f"{supabase_url}/storage/v1/object/public/{bucket}/{ruta}", timeout=30)
        if publica.status_code == 200:
            print("FALLA: el archivo se puede leer sin firma; el bucket es público")
            return 1
        print("ok")

        paso("Borrando archivo de prueba")
        storage.borrar(ruta)
        subido = False
        print("ok")
    except (ErrorStorage, httpx.HTTPError) as exc:
        print(f"FALLA: {exc}")
        return 1
    finally:
        if subido:
            try:
                storage.borrar(ruta)
            except (ErrorStorage, httpx.HTTPError):
                print(f"  ! No se pudo borrar {ruta}; bórralo a mano desde el panel")

    print("Storage funciona: sube, firma, descarga y borra.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

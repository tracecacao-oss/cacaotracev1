"""Cliente de Supabase Storage y reglas de archivos.

Solo la API sube, firma y borra archivos, siempre en el bucket privado. El navegador
recibe URLs firmadas que vencen a los 5 minutos. La base guarda ruta, nombre, tamaño y hash.
"""

import hashlib
import uuid
from urllib.parse import quote

import httpx
from fastapi import Request

from app.config import Settings
from app.errores import error_api

TAMANO_MAXIMO_DOCUMENTO = 10 * 1024 * 1024
VIGENCIA_URL_FIRMADA = 300

# Tipo real del contenido según sus primeros bytes, no según la extensión ni el navegador.
FIRMAS = {
    "pdf": b"%PDF-",
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
}
TIPOS_MIME = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg"}


class ArchivoNoPermitido(Exception):
    pass


class ErrorStorage(Exception):
    pass


def detectar_tipo(contenido: bytes) -> str | None:
    for extension, firma in FIRMAS.items():
        if contenido.startswith(firma):
            return extension
    return None


def validar_documento(contenido: bytes) -> str:
    """Devuelve la extensión real (pdf, jpg o png) o lanza ArchivoNoPermitido."""
    if not contenido:
        raise ArchivoNoPermitido("El archivo está vacío.")
    if len(contenido) > TAMANO_MAXIMO_DOCUMENTO:
        raise ArchivoNoPermitido("El archivo supera el máximo de 10 MB.")
    extension = detectar_tipo(contenido)
    if extension is None:
        raise ArchivoNoPermitido("Solo se aceptan archivos PDF, JPG o PNG.")
    return extension


def sha256(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def construir_ruta(
    cooperativa_id: uuid.UUID | str, entidad: str, entidad_id: uuid.UUID | str, extension: str
) -> str:
    return f"{cooperativa_id}/{entidad}/{entidad_id}/{uuid.uuid4()}.{extension}"


class ClienteStorage:
    def __init__(self, supabase_url: str, clave_secreta: str, bucket: str, http: httpx.Client | None = None):
        self._base = f"{supabase_url.rstrip('/')}/storage/v1"
        self._clave = clave_secreta
        self.bucket = bucket
        self._http = http or httpx.Client(timeout=30)

    def _cabeceras(self) -> dict[str, str]:
        cabeceras = {"apikey": self._clave}
        # Las claves secretas nuevas (sb_secret_...) no son JWT: van solo en apikey.
        # La clave service_role heredada sí es un JWT y además va como Bearer.
        if not self._clave.startswith("sb_secret_"):
            cabeceras["Authorization"] = f"Bearer {self._clave}"
        return cabeceras

    def _url_objeto(self, ruta: str) -> str:
        return f"{self._base}/object/{self.bucket}/{quote(ruta, safe='/')}"

    def _comprobar(self, respuesta: httpx.Response, accion: str) -> None:
        if respuesta.is_error:
            # No se incluye el cuerpo: podría repetir cabeceras o datos sensibles.
            raise ErrorStorage(f"Storage respondió {respuesta.status_code} al {accion}")

    def subir(self, ruta: str, contenido: bytes, tipo_mime: str) -> None:
        cabeceras = self._cabeceras() | {"Content-Type": tipo_mime, "x-upsert": "false"}
        respuesta = self._http.post(self._url_objeto(ruta), content=contenido, headers=cabeceras)
        self._comprobar(respuesta, "subir")

    def url_firmada(self, ruta: str, segundos: int = VIGENCIA_URL_FIRMADA) -> str:
        url = f"{self._base}/object/sign/{self.bucket}/{quote(ruta, safe='/')}"
        respuesta = self._http.post(url, json={"expiresIn": segundos}, headers=self._cabeceras())
        self._comprobar(respuesta, "firmar")
        relativa = respuesta.json()["signedURL"]
        return f"{self._base}{relativa}"

    def borrar(self, ruta: str) -> None:
        url = f"{self._base}/object/{self.bucket}"
        respuesta = self._http.request("DELETE", url, json={"prefixes": [ruta]}, headers=self._cabeceras())
        self._comprobar(respuesta, "borrar")


def crear_storage(settings: Settings) -> ClienteStorage | None:
    if settings.supabase_secret_key is None:
        return None
    return ClienteStorage(
        settings.supabase_url,
        settings.supabase_secret_key.get_secret_value(),
        settings.storage_bucket,
    )


def obtener_storage(request: Request) -> ClienteStorage:
    """Dependencia de FastAPI; las pruebas la reemplazan por un Storage simulado."""
    cliente = request.app.state.storage
    if cliente is None:
        raise error_api(503, "archivos_no_disponibles", "La carga de archivos no está disponible.")
    return cliente

import json
import re

import httpx
import pytest

from app.storage import (
    TAMANO_MAXIMO_DOCUMENTO,
    ArchivoNoPermitido,
    ClienteStorage,
    ErrorStorage,
    construir_ruta,
    detectar_tipo,
    sha256,
    validar_documento,
)

PDF = b"%PDF-1.7\n%prueba\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 20


@pytest.mark.parametrize(("contenido", "esperado"), [(PDF, "pdf"), (PNG, "png"), (JPG, "jpg")])
def test_detecta_tipo_real(contenido, esperado):
    assert detectar_tipo(contenido) == esperado
    assert validar_documento(contenido) == esperado


def test_rechaza_contenido_disfrazado():
    # Un HTML con extensión .pdf sigue siendo HTML.
    with pytest.raises(ArchivoNoPermitido):
        validar_documento(b"<html><script>alert(1)</script></html>")


def test_rechaza_archivo_vacio():
    with pytest.raises(ArchivoNoPermitido):
        validar_documento(b"")


def test_rechaza_archivo_mayor_a_10_mb():
    with pytest.raises(ArchivoNoPermitido):
        validar_documento(PDF + b"0" * TAMANO_MAXIMO_DOCUMENTO)


def test_ruta_sigue_la_convencion():
    ruta = construir_ruta("coop-1", "productor", "prod-9", "pdf")
    assert re.fullmatch(r"coop-1/productor/prod-9/[0-9a-f-]{36}\.pdf", ruta)


def test_sha256():
    # Vector de prueba de FIPS 180-2.
    assert sha256(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


class StorageSimulado:
    def __init__(self, estado: int = 200):
        self.peticiones: list[httpx.Request] = []
        self.estado = estado

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        if self.estado != 200:
            return httpx.Response(self.estado, json={"message": "error"})
        if "/object/sign/" in peticion.url.path:
            return httpx.Response(200, json={"signedURL": "/object/sign/documentos/a/b.pdf?token=t0k3n"})
        return httpx.Response(200, json={"Key": "documentos/a/b.pdf"})


def _cliente(simulado: StorageSimulado, clave: str = "sb_secret_abc") -> ClienteStorage:
    return ClienteStorage(
        "https://proyecto-prueba.supabase.co",
        clave,
        "documentos",
        http=httpx.Client(transport=httpx.MockTransport(simulado)),
    )


def test_subir_al_bucket_privado():
    simulado = StorageSimulado()
    _cliente(simulado).subir("a/b.pdf", PDF, "application/pdf")
    peticion = simulado.peticiones[0]
    assert peticion.method == "POST"
    assert str(peticion.url) == "https://proyecto-prueba.supabase.co/storage/v1/object/documentos/a/b.pdf"
    assert peticion.headers["content-type"] == "application/pdf"
    assert peticion.headers["x-upsert"] == "false"
    assert peticion.content == PDF


def test_clave_secreta_nueva_va_solo_en_apikey():
    simulado = StorageSimulado()
    _cliente(simulado, "sb_secret_abc").subir("a/b.pdf", PDF, "application/pdf")
    cabeceras = simulado.peticiones[0].headers
    assert cabeceras["apikey"] == "sb_secret_abc"
    assert "authorization" not in cabeceras


def test_clave_service_role_heredada_va_tambien_como_bearer():
    simulado = StorageSimulado()
    _cliente(simulado, "eyJ.heredada.jwt").subir("a/b.pdf", PDF, "application/pdf")
    assert simulado.peticiones[0].headers["authorization"] == "Bearer eyJ.heredada.jwt"


def test_url_firmada_vence_a_los_5_minutos():
    simulado = StorageSimulado()
    url = _cliente(simulado).url_firmada("a/b.pdf")
    peticion = simulado.peticiones[0]
    assert (
        str(peticion.url) == "https://proyecto-prueba.supabase.co/storage/v1/object/sign/documentos/a/b.pdf"
    )
    assert json.loads(peticion.content) == {"expiresIn": 300}
    assert url == "https://proyecto-prueba.supabase.co/storage/v1/object/sign/documentos/a/b.pdf?token=t0k3n"


def test_url_firmada_para_descargar_con_nombre():
    url = _cliente(StorageSimulado()).url_firmada("a/b.json", descarga="whisp-PA-00001-20261005-1200.json")
    assert url.endswith("?token=t0k3n&download=whisp-PA-00001-20261005-1200.json")


def test_borrar():
    simulado = StorageSimulado()
    _cliente(simulado).borrar("a/b.pdf")
    peticion = simulado.peticiones[0]
    assert peticion.method == "DELETE"
    assert str(peticion.url) == "https://proyecto-prueba.supabase.co/storage/v1/object/documentos"
    assert json.loads(peticion.content) == {"prefixes": ["a/b.pdf"]}


def test_error_de_storage_no_expone_la_clave():
    with pytest.raises(ErrorStorage) as error:
        _cliente(StorageSimulado(estado=403)).subir("a/b.pdf", PDF, "application/pdf")
    assert "sb_secret" not in str(error.value)

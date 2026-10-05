"""Utilidades de los routers para formularios multipart con archivos."""

import json
from typing import Any

from fastapi import UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError

from app.errores import error_api
from app.services.documentos import Archivo
from app.storage import TAMANO_MAXIMO_DOCUMENTO


def leer_archivo(archivo: UploadFile, maximo: int = TAMANO_MAXIMO_DOCUMENTO) -> Archivo:
    """Lee el archivo subido sin pasar del tope: un byte de más basta para rechazarlo."""
    contenido = archivo.file.read(maximo + 1)
    if len(contenido) > maximo:
        mb = maximo // (1024 * 1024)
        raise error_api(422, "archivo_muy_grande", f"El archivo supera el máximo de {mb} MB.")
    return Archivo(nombre=archivo.filename or "archivo", contenido=contenido)


def modelo_desde_json[M: BaseModel](modelo: type[M], texto: str, campo: str) -> M:
    """Valida el JSON de un campo de formulario y responde 422 con el formato común."""
    try:
        return modelo.model_validate_json(texto)
    except ValidationError as exc:
        errores = [{**e, "loc": ("body", *e.get("loc", ()))} for e in exc.errors()]
        raise RequestValidationError(errores) from exc


def json_desde_formulario(texto: str | None, campo: str) -> Any:
    if not texto:
        return None
    try:
        return json.loads(texto)
    except ValueError as exc:
        raise error_api(422, "datos_invalidos", f"El campo {campo} no es JSON válido.") from exc

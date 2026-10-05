"""Errores de la API con la forma {"error": {"codigo": "...", "mensaje": "..."}}.

400 regla de negocio, 401 token, 403 sin permiso, 404 no existe o es de otra cooperativa,
409 duplicado, 422 datos mal formados.
"""

from fastapi import HTTPException


def error_api(estado: int, codigo: str, mensaje: str) -> HTTPException:
    return HTTPException(status_code=estado, detail={"codigo": codigo, "mensaje": mensaje})


def no_encontrado(mensaje: str = "No encontrado.") -> HTTPException:
    return error_api(404, "no_encontrado", mensaje)


def sin_permiso() -> HTTPException:
    return error_api(403, "sin_permiso", "No tienes permiso para esta acción.")

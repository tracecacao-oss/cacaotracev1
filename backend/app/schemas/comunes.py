"""Tipos comunes de entrada y salida. Nombres de campos en español y snake_case."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Dni = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{8}$")]
Ruc = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{11}$")]
Correo = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
TextoOpcional = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Clave = Annotated[str, StringConstraints(min_length=1, max_length=72)]


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pagina[T](BaseModel):
    items: list[T]
    total: int
    pagina: int
    por_pagina: int


class ClaveTemporal(BaseModel):
    """La contraseña temporal se entrega una sola vez y no se guarda."""

    clave_temporal: str

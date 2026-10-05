import uuid
from datetime import datetime
from typing import Literal

from app.schemas.comunes import Correo, Entrada, Salida, Texto

RolPersonal = Literal["admin_cooperativa", "operador", "lector"]


class UsuarioSalida(Salida):
    id: uuid.UUID
    rol: str
    nombres: str
    apellidos: str
    correo: str | None
    activo: bool
    debe_cambiar_clave: bool
    ultimo_acceso_en: datetime | None
    creado_en: datetime


class UsuarioNuevo(Entrada):
    nombres: Texto
    apellidos: Texto
    correo: Correo
    rol: RolPersonal


class UsuarioCambios(Entrada):
    nombres: Texto | None = None
    apellidos: Texto | None = None
    rol: RolPersonal | None = None
    activo: bool | None = None


class AdministradorNuevo(Entrada):
    nombres: Texto
    apellidos: Texto
    correo: Correo


class CuentaCreada(Salida):
    usuario: UsuarioSalida
    clave_temporal: str

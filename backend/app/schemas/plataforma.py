import uuid
from datetime import datetime
from typing import Literal

from app.schemas.comunes import Entrada, Ruc, Salida, Texto, TextoOpcional
from app.schemas.usuarios import AdministradorNuevo, UsuarioSalida


class CooperativaSalida(Salida):
    id: uuid.UUID
    razon_social: str
    nombre_comercial: str | None
    ruc: str
    departamento: str
    provincia: str
    distrito: str
    estado: str
    es_demo: bool
    creado_en: datetime
    usuarios: int = 0
    productores: int = 0


class CooperativaNueva(Entrada):
    razon_social: Texto
    nombre_comercial: TextoOpcional | None = None
    ruc: Ruc
    departamento: Texto
    provincia: Texto
    distrito: Texto
    # Parte 10: se fija al crear y no cambia después.
    es_demo: bool = False
    administrador: AdministradorNuevo


class CooperativaCambios(Entrada):
    razon_social: Texto | None = None
    nombre_comercial: TextoOpcional | None = None
    ruc: Ruc | None = None
    departamento: Texto | None = None
    provincia: Texto | None = None
    distrito: Texto | None = None
    estado: Literal["activa", "suspendida"] | None = None


class CooperativaCreada(Salida):
    cooperativa: CooperativaSalida
    administrador: UsuarioSalida
    clave_temporal: str

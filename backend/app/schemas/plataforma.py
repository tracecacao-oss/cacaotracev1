import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BeforeValidator, StringConstraints

from app.schemas.comunes import Entrada, Ruc, Salida, Texto, TextoOpcional
from app.schemas.recepcion import TipoOrganizacion
from app.schemas.usuarios import AdministradorNuevo, UsuarioSalida

# Parte 5: de 3 a 6 letras mayúsculas; forma parte del código de cada DOP.
CodigoCooperativa = Annotated[
    str,
    BeforeValidator(lambda v: v.strip().upper() if isinstance(v, str) else v),
    StringConstraints(pattern=r"^[A-Z]{3,6}$"),
]


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
    codigo: str | None = None
    tipo_organizacion: str
    creado_en: datetime
    usuarios: int = 0
    productores: int = 0


class UsoCooperativa(Salida):
    cooperativa_id: uuid.UUID
    cooperativa: str
    es_demo: bool
    archivos: int
    storage_bytes: int
    # Suma del tamaño de sus filas, sin índices: sirve para comparar cooperativas, no para sumar.
    db_bytes_aprox: int


class UsoSalida(Salida):
    """Parte 10: espacio usado contra los límites del plan. La interfaz avisa al pasar de 70 % y de 90 %."""

    archivos: int
    storage_bytes: int
    limite_storage_mb: int
    storage_pct: float
    db_bytes: int
    limite_db_mb: int
    db_pct: float
    analisis_en_cola: int
    por_cooperativa: list[UsoCooperativa]


class CooperativaNueva(Entrada):
    razon_social: Texto
    nombre_comercial: TextoOpcional | None = None
    ruc: Ruc
    departamento: Texto
    provincia: Texto
    distrito: Texto
    # Parte 10: se fija al crear y no cambia después.
    es_demo: bool = False
    # Parte 5: se fija al crear y no cambia después.
    codigo: CodigoCooperativa
    # Adenda 3 de la Parte 5: obligatoria; el superadmin puede corregirla después.
    tipo_organizacion: TipoOrganizacion
    administrador: AdministradorNuevo


class CooperativaCambios(Entrada):
    razon_social: Texto | None = None
    nombre_comercial: TextoOpcional | None = None
    ruc: Ruc | None = None
    departamento: Texto | None = None
    provincia: Texto | None = None
    distrito: Texto | None = None
    estado: Literal["activa", "suspendida"] | None = None
    # Solo para las cooperativas creadas antes de la Parte 5, que todavía no tienen código.
    codigo: CodigoCooperativa | None = None
    tipo_organizacion: TipoOrganizacion | None = None


class CooperativaCreada(Salida):
    cooperativa: CooperativaSalida
    administrador: UsuarioSalida
    clave_temporal: str

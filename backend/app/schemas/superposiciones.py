import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.schemas.comunes import Entrada, Texto


class ParcelaEnSuperposicion(BaseModel):
    id: uuid.UUID
    codigo: str
    nombre: str
    productor_nombre: str
    cooperativa_id: uuid.UUID | None
    cooperativa_nombre: str | None = None
    geometria: dict[str, Any]


class SuperposicionSalida(BaseModel):
    id: uuid.UUID
    tipo: str
    estado: str
    area_ha: Decimal | None
    porcentaje: Decimal | None
    entre_cooperativas: bool
    aviso: str | None
    # Las parcelas que el usuario puede ver; de otra cooperativa solo se ve la propia.
    parcelas: list[ParcelaEnSuperposicion]
    interseccion: dict[str, Any] | None
    nota: str | None
    cerrada_en: datetime | None
    creado_en: datetime


class Aceptacion(Entrada):
    nota: Texto

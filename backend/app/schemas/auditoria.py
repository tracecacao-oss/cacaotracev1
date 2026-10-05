import uuid
from datetime import datetime
from typing import Any

from app.schemas.comunes import Salida


class AuditoriaSalida(Salida):
    id: int
    ocurrido_en: datetime
    usuario_id: uuid.UUID | None
    usuario_nombre: str | None = None
    rol: str | None
    cooperativa_id: uuid.UUID | None
    accion: str
    entidad: str
    entidad_id: str | None
    detalle: dict[str, Any]
    ip: str | None

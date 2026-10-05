import uuid

from pydantic import BaseModel

from app.schemas.comunes import Clave, Entrada, Salida, TextoOpcional


class CooperativaDelUsuario(Salida):
    id: uuid.UUID
    razon_social: str
    nombre_comercial: str | None
    estado: str
    es_demo: bool


class MeRespuesta(BaseModel):
    id: uuid.UUID
    rol: str
    nombres: str
    apellidos: str
    correo: str | None
    dni: str | None
    cooperativa: CooperativaDelUsuario | None
    productor_id: uuid.UUID | None
    debe_cambiar_clave: bool
    consentimiento_pendiente: bool


class CambioClave(Entrada):
    clave_actual: Clave
    clave_nueva: Clave


class Consentimiento(Entrada):
    version_texto: TextoOpcional

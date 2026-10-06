import uuid

from pydantic import BaseModel

from app.schemas.comunes import Clave, Entrada, Salida, TextoOpcional


class CooperativaDelUsuario(Salida):
    id: uuid.UUID
    razon_social: str
    nombre_comercial: str | None
    estado: str
    es_demo: bool
    # La pantalla de consentimiento nombra a la cooperativa como titular del banco de datos, con su RUC y su
    # domicilio (Ley N.° 29733, art. 18).
    ruc: str
    direccion_postal: str | None = None
    distrito: str | None = None
    provincia: str | None = None
    departamento: str | None = None


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
    # Parte 10: la interfaz muestra la franja "Demostración: datos ficticios".
    es_demo: bool = False


class CambioClave(Entrada):
    clave_actual: Clave
    clave_nueva: Clave


class Consentimiento(Entrada):
    version_texto: TextoOpcional

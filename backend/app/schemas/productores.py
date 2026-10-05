import uuid
from datetime import date, datetime

from pydantic import model_validator

from app.schemas.comunes import Dni, Entrada, Salida, Texto, TextoOpcional


class AccesoProductor(Salida):
    existe: bool
    activo: bool
    debe_cambiar_clave: bool
    ultimo_acceso_en: datetime | None


class ProductorSalida(Salida):
    id: uuid.UUID
    dni: str
    nombres: str
    apellidos: str
    telefono: str | None
    codigo_socio: str | None
    afiliado_desde: date
    consentimiento_datos_en: datetime | None
    consentimiento_origen: str | None
    es_demo: bool
    acceso: AccesoProductor


class ProductorNuevo(Entrada):
    dni: Dni
    nombres: Texto
    apellidos: Texto
    telefono: TextoOpcional | None = None
    codigo_socio: TextoOpcional | None = None
    # Casilla "La cooperativa cuenta con el consentimiento firmado del productor".
    consentimiento_cooperativa: bool = False
    version_consentimiento: TextoOpcional | None = None

    @model_validator(mode="after")
    def _version_si_hay_consentimiento(self):
        if self.consentimiento_cooperativa and not self.version_consentimiento:
            raise ValueError("Falta la versión del texto de consentimiento")
        return self

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, model_validator

from app.schemas.comunes import Correo, Dni, Entrada, Ruc, Salida, Texto, TextoOpcional
from app.schemas.parcelas import DocumentoSalida

Nivel = Literal["declarado", "documentado", "verificado_en_fuente"]


class AccesoProductor(Salida):
    existe: bool
    activo: bool
    debe_cambiar_clave: bool
    ultimo_acceso_en: datetime | None


class ResumenParcelas(BaseModel):
    activas: int
    area_total_ha: Decimal


class ProductorSalida(Salida):
    id: uuid.UUID
    dni: str
    nombres: str
    apellidos: str
    ruc: str | None
    direccion_postal: str | None
    correo_contacto: str | None
    telefono: str | None
    ppa_registrado: bool
    ppa_codigo: str | None
    codigo_agrodigital: str | None
    codigo_socio: str | None
    afiliado_desde: date
    consentimiento_datos_en: datetime | None
    consentimiento_origen: str | None
    es_demo: bool
    acceso: AccesoProductor
    # Calculados al responder, nunca guardados: así no quedan desactualizados.
    nivel_identidad: Literal["declarado", "documentado"]
    nivel_ppa: Literal["declarado", "documentado", "no_registrado"]
    pendientes: list[str]
    parcelas: ResumenParcelas


class ProductorDetalle(ProductorSalida):
    documentos: list[DocumentoSalida]


class FichaProductor(Entrada):
    ruc: Ruc | None = None
    correo_contacto: Correo | None = None
    telefono: TextoOpcional | None = None
    ppa_registrado: bool = False
    ppa_codigo: TextoOpcional | None = None
    codigo_agrodigital: TextoOpcional | None = None
    codigo_socio: TextoOpcional | None = None


class ProductorNuevo(FichaProductor):
    dni: Dni
    nombres: Texto
    apellidos: Texto
    direccion_postal: Texto
    # Casilla "La cooperativa cuenta con el consentimiento firmado del productor".
    consentimiento_cooperativa: bool = False
    version_consentimiento: TextoOpcional | None = None

    @model_validator(mode="after")
    def _version_si_hay_consentimiento(self):
        if self.consentimiento_cooperativa and not self.version_consentimiento:
            raise ValueError("Falta la versión del texto de consentimiento")
        return self


class ProductorCambios(Entrada):
    dni: Dni | None = None
    # Obligatorio si cambia el DNI.
    motivo: TextoOpcional | None = None
    nombres: Texto | None = None
    apellidos: Texto | None = None
    direccion_postal: Texto | None = None
    ruc: Ruc | None = None
    correo_contacto: Correo | None = None
    telefono: TextoOpcional | None = None
    ppa_registrado: bool | None = None
    ppa_codigo: TextoOpcional | None = None
    codigo_agrodigital: TextoOpcional | None = None
    codigo_socio: TextoOpcional | None = None


class MisCambios(Entrada):
    """El productor solo edita su teléfono: cualquier otro campo responde 422."""

    telefono: TextoOpcional | None


class CierreAfiliacion(Entrada):
    motivo: TextoOpcional | None = None

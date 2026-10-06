"""Parte 9: informe de hallazgos, DEX, certificaciones y configuración de plataforma."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EstadoDex = Literal["vigente", "anulado"]
ClasificacionPais = Literal["bajo", "estandar", "alto"]


class EmisionDex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # La casilla "Entiendo que el DEX no declara el nivel de riesgo ni reemplaza la DDS".
    entiendo: bool


class ArchivoDex(BaseModel):
    clave: str
    nombre: str
    tamano_bytes: int


class DescargaDex(BaseModel):
    clave: str
    nombre: str
    url: str


class DexSalida(BaseModel):
    id: uuid.UUID
    codigo: str
    estado: str
    lote_id: uuid.UUID
    lote_codigo: str
    orden_codigo: str
    importador_id: uuid.UUID
    importador: str
    masa_neta_kg: Decimal
    emitido_en: datetime
    contenido_sha256: str


class DexDetalle(DexSalida):
    contenido: dict[str, Any]
    url_verificacion: str
    qr: list[str]
    archivos: list[ArchivoDex]
    emitido_por_nombre: str | None
    anulado_en: datetime | None
    anulado_por_nombre: str | None
    motivo_anulacion: str | None


class DexPublico(BaseModel):
    """Lo único que se muestra sin token, más la marca de demostración."""

    codigo: str
    estado: str
    emitido_en: datetime
    contenido_sha256: str
    cooperativa: str
    # Parte 10: la página pública avisa que es un documento de demostración.
    es_demo: bool = False


# ---------- Certificaciones ----------


def _texto(valor: str | None) -> str | None:
    valor = (valor or "").strip()
    return valor or None


class CertificacionNueva(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    entidad_certificadora: str = Field(min_length=2, max_length=200)
    numero: str = Field(min_length=1, max_length=100)
    vigente_desde: date
    vigente_hasta: date

    @field_validator("nombre", "entidad_certificadora", "numero")
    @classmethod
    def _limpio(cls, valor: str) -> str:
        return valor.strip()

    @model_validator(mode="after")
    def _periodo(self):
        if self.vigente_hasta < self.vigente_desde:
            raise ValueError("La fecha de fin de vigencia no puede ser anterior a la de inicio.")
        return self


class CertificacionCambios(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=2, max_length=200)
    entidad_certificadora: str | None = Field(default=None, min_length=2, max_length=200)
    numero: str | None = Field(default=None, min_length=1, max_length=100)
    vigente_desde: date | None = None
    vigente_hasta: date | None = None
    # Anular: con motivo. Una certificación anulada deja de contar y no se edita.
    anular: bool = False
    motivo: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _motivo(self):
        if self.anular and len((self.motivo or "").strip()) < 10:
            raise ValueError("Escribe el motivo de la anulación (mínimo 10 caracteres).")
        return self


class CertificacionSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    entidad_certificadora: str
    numero: str
    vigente_desde: date
    vigente_hasta: date
    estado: Literal["vigente", "por_iniciar", "vencida", "anulada"]
    documento_id: uuid.UUID | None
    registrada_por_nombre: str | None
    creado_en: datetime
    anulada_en: datetime | None
    motivo_anulacion: str | None


# ---------- Configuración de plataforma ----------


class ConfiguracionPlataformaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clasificacion_pais: ClasificacionPais | None
    clasificacion_fecha: date | None = None
    clasificacion_referencia: str | None = Field(default=None, max_length=1000)

    @field_validator("clasificacion_referencia")
    @classmethod
    def _limpia(cls, valor: str | None) -> str | None:
        return _texto(valor)

    @model_validator(mode="after")
    def _completa(self):
        if self.clasificacion_pais and (not self.clasificacion_fecha or not self.clasificacion_referencia):
            raise ValueError(
                "La clasificación del país va con su fecha y con la referencia de la publicación de la "
                "Comisión Europea de donde sale."
            )
        return self


class ConfiguracionPlataformaSalida(BaseModel):
    clasificacion_pais: str | None
    clasificacion_fecha: date | None
    clasificacion_referencia: str | None
    actualizado_en: datetime | None
    actualizado_por_nombre: str | None

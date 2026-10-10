"""Parte 9: informe de hallazgos, DEX, certificaciones y configuración de plataforma."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.cooperativa import ComparacionAduanera

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


class AgregadoDespues(BaseModel):
    """Adenda 6, sección 7, regla 7, y adenda 7, sección 4.4: la declaración aduanera cargada en el lote
    después de emitir el DEX. No forma parte del DEX: su contenido y su huella no cambian. La pestaña DEX
    muestra sus cuatro datos, la comparación con el lote, cuándo se cargó y si tiene cotejo."""

    tipo: str
    nombre: str
    numero: str | None
    fecha_numeracion: date | None
    peso_neto_kg: Decimal | None = None
    subpartida: str | None = None
    comparacion: ComparacionAduanera | None = None
    cargado_en: datetime
    cotejado: bool
    cotejado_en: datetime | None


class AgregadoPublico(BaseModel):
    """Adenda 7, sección 4.4, regla 4: en la verificación pública, solo tres datos. Sin pesos ni archivo."""

    nombre: str
    numero: str | None
    fecha_numeracion: date | None
    agregado_en: datetime


class DexDetalle(DexSalida):
    contenido: dict[str, Any]
    url_verificacion: str
    qr: list[str]
    archivos: list[ArchivoDex]
    emitido_por_nombre: str | None
    anulado_en: datetime | None
    anulado_por_nombre: str | None
    motivo_anulacion: str | None
    agregado: list[AgregadoDespues] = []


class DexPublico(BaseModel):
    """Lo único que se muestra sin token, más la marca de demostración."""

    codigo: str
    estado: str
    emitido_en: datetime
    contenido_sha256: str
    cooperativa: str
    # Parte 10: la página pública avisa que es un documento de demostración.
    es_demo: bool = False
    agregado: list[AgregadoPublico] = []


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

    clasificacion_pais: ClasificacionPais | None = None
    clasificacion_fecha: date | None = None
    clasificacion_referencia: str | None = Field(default=None, max_length=1000)
    # Adenda 5, sección 9: valores de referencia de la declaración del productor.
    uit_soles: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    uit_anio: int | None = Field(default=None, ge=2000, le=2100)
    jornal_minimo_referencia: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    jornal_referencia_nota: str | None = Field(default=None, max_length=1000)

    @field_validator("clasificacion_referencia", "jornal_referencia_nota")
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
        if (self.uit_soles is None) != (self.uit_anio is None):
            raise ValueError("El valor de la UIT va con su año.")
        if (self.jornal_minimo_referencia is None) != (self.jornal_referencia_nota is None):
            raise ValueError("El jornal de referencia va con la nota de dónde sale.")
        return self


class ConfiguracionPlataformaSalida(BaseModel):
    clasificacion_pais: str | None
    clasificacion_fecha: date | None
    clasificacion_referencia: str | None
    uit_soles: Decimal | None = None
    uit_anio: int | None = None
    jornal_minimo_referencia: Decimal | None = None
    jornal_referencia_nota: str | None = None
    actualizado_en: datetime | None
    actualizado_por_nombre: str | None

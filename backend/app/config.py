"""Configuración del backend, leída de variables de entorno (y de backend/.env en local)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # Por defecto producción: si falta la variable, la documentación interactiva queda apagada.
    environment: Literal["production", "development"] = "production"
    database_url: str
    supabase_url: str
    supabase_secret_key: SecretStr | None = None
    supabase_jwt_secret: SecretStr | None = None
    storage_bucket: str = "documentos"
    cors_origins: str = ""
    productor_email_domain: str = "productores.cacaotrace.local"
    git_sha: str = Field("dev", validation_alias=AliasChoices("GIT_SHA", "RENDER_GIT_COMMIT"))

    @field_validator("supabase_secret_key", "supabase_jwt_secret", mode="before")
    @classmethod
    def _vacio_es_nulo(cls, valor):
        # En .env las variables opcionales quedan como "VARIABLE=": vacío equivale a no definida.
        return valor or None

    @field_validator("database_url")
    @classmethod
    def _usar_psycopg3(cls, valor: str) -> str:
        # La cadena que entrega Supabase empieza con postgresql://; SQLAlchemy necesita el driver explícito.
        for prefijo in ("postgresql://", "postgres://"):
            if valor.startswith(prefijo):
                return "postgresql+psycopg://" + valor[len(prefijo) :]
        return valor

    @field_validator("supabase_url")
    @classmethod
    def _sin_barra_final(cls, valor: str) -> str:
        return valor.rstrip("/")

    @field_validator("cors_origins")
    @classmethod
    def _sin_comodin(cls, valor: str) -> str:
        if "*" in valor:
            raise ValueError("CORS_ORIGINS no puede usar '*'")
        return valor

    @property
    def es_produccion(self) -> bool:
        return self.environment == "production"

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

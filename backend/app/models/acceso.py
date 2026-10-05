"""Tablas de la Parte 2: cooperativas, perfiles, productores, afiliaciones y auditoría."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, ConFechas

ROLES = ("superadmin", "admin_cooperativa", "operador", "lector", "productor")
ROLES_PERSONAL = ("admin_cooperativa", "operador", "lector")
ESTADOS_COOPERATIVA = ("activa", "suspendida")
ESTADOS_AFILIACION = ("activa", "inactiva")
ORIGENES_CONSENTIMIENTO = ("productor", "cooperativa")


def _en(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


class Cooperativa(ConFechas, Base):
    __tablename__ = "cooperativas"
    __table_args__ = (
        CheckConstraint("ruc ~ '^[0-9]{11}$'", name="ruc_11_digitos"),
        CheckConstraint(f"estado IN ({_en(ESTADOS_COOPERATIVA)})", name="estado_valido"),
        CheckConstraint("codigo IS NULL OR codigo ~ '^[A-Z]{3,6}$'", name="codigo_3_a_6_letras"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    razon_social: Mapped[str] = mapped_column(Text)
    nombre_comercial: Mapped[str | None] = mapped_column(Text)
    ruc: Mapped[str] = mapped_column(String(11), unique=True)
    departamento: Mapped[str] = mapped_column(Text)
    provincia: Mapped[str] = mapped_column(Text)
    distrito: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, server_default="activa")
    # Parte 10: la fija el superadmin al crear la cooperativa y no cambia después.
    es_demo: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Parte 5: forma parte del código de cada DOP. La fija el superadmin y no cambia después. Las
    # cooperativas creadas antes de la Parte 5 la reciben una sola vez.
    codigo: Mapped[str | None] = mapped_column(String(6), unique=True)


class Productor(ConFechas, Base):
    __tablename__ = "productores"
    __table_args__ = (
        CheckConstraint("dni ~ '^[0-9]{8}$'", name="dni_8_digitos"),
        CheckConstraint(
            f"consentimiento_origen IS NULL OR consentimiento_origen IN ({_en(ORIGENES_CONSENTIMIENTO)})",
            name="consentimiento_origen_valido",
        ),
        CheckConstraint("ruc IS NULL OR ruc ~ '^[0-9]{11}$'", name="ruc_11_digitos"),
        CheckConstraint("ppa_registrado OR ppa_codigo IS NULL", name="ppa_codigo_solo_si_registrado"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    dni: Mapped[str] = mapped_column(String(8), unique=True)
    nombres: Mapped[str] = mapped_column(Text)
    apellidos: Mapped[str] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(Text)
    consentimiento_datos_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consentimiento_origen: Mapped[str | None] = mapped_column(Text)
    es_demo: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Parte 3: ficha completa. La dirección es obligatoria en la API; nula solo en altas de la Parte 2.
    ruc: Mapped[str | None] = mapped_column(String(11))
    direccion_postal: Mapped[str | None] = mapped_column(Text)
    correo_contacto: Mapped[str | None] = mapped_column(Text)
    ppa_registrado: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    ppa_codigo: Mapped[str | None] = mapped_column(Text)
    codigo_agrodigital: Mapped[str | None] = mapped_column(Text)


class Perfil(ConFechas, Base):
    """Una fila por cada usuario que puede iniciar sesión. id = id del usuario en Supabase Auth."""

    __tablename__ = "perfiles"
    __table_args__ = (
        CheckConstraint(f"rol IN ({_en(ROLES)})", name="rol_valido"),
        CheckConstraint("(rol = 'superadmin') = (cooperativa_id IS NULL)", name="cooperativa_segun_rol"),
        CheckConstraint("(rol = 'productor') = (productor_id IS NOT NULL)", name="productor_segun_rol"),
        Index(
            "uq_perfiles_correo",
            text("lower(correo)"),
            unique=True,
            postgresql_where=text("correo IS NOT NULL"),
        ),
    )

    # Sin clave foránea a auth.users: el esquema auth no existe en local.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    rol: Mapped[str] = mapped_column(Text)
    cooperativa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cooperativas.id"), index=True)
    productor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("productores.id"), unique=True)
    nombres: Mapped[str] = mapped_column(Text)
    apellidos: Mapped[str] = mapped_column(Text)
    correo: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    debe_cambiar_clave: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    ultimo_acceso_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))

    cooperativa: Mapped[Cooperativa | None] = relationship(lazy="joined")
    productor: Mapped[Productor | None] = relationship(lazy="joined")


class Afiliacion(ConFechas, Base):
    """Vincula a un productor con una cooperativa. Nada debe asumir que es única por productor."""

    __tablename__ = "afiliaciones"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_en(ESTADOS_AFILIACION)})", name="estado_valido"),
        # Una sola cooperativa activa por productor. Para permitir varias, reemplazar por un
        # índice único sobre (productor_id, cooperativa_id).
        Index(
            "uq_afiliaciones_productor_activa",
            "productor_id",
            unique=True,
            postgresql_where=text("estado = 'activa'"),
        ),
        Index("ix_afiliaciones_cooperativa_estado", "cooperativa_id", "estado"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    productor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productores.id"))
    cooperativa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cooperativas.id"))
    codigo_socio: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, server_default="activa")
    desde: Mapped[date] = mapped_column(Date)
    hasta: Mapped[date | None] = mapped_column(Date)

    productor: Mapped[Productor] = relationship(lazy="joined")


class Auditoria(Base):
    """Solo admite inserciones: un trigger rechaza UPDATE y DELETE."""

    __tablename__ = "auditoria"
    __table_args__ = (
        Index("ix_auditoria_cooperativa_ocurrido", "cooperativa_id", text("ocurrido_en DESC")),
        Index("ix_auditoria_usuario_ocurrido", "usuario_id", text("ocurrido_en DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("perfiles.id"))
    rol: Mapped[str | None] = mapped_column(Text)
    cooperativa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cooperativas.id"))
    accion: Mapped[str] = mapped_column(Text)
    entidad: Mapped[str] = mapped_column(Text)
    entidad_id: Mapped[str | None] = mapped_column(Text)
    detalle: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    ip: Mapped[str | None] = mapped_column(Text)

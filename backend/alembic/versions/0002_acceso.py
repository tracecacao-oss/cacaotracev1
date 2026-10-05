"""Parte 2: cooperativas, perfiles, productores, afiliaciones y auditoría.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04

Regla: toda tabla nueva lleva ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY y ninguna política.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = ("cooperativas", "productores", "perfiles", "afiliaciones", "auditoria")


def _fechas() -> list[sa.Column]:
    return [
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "cooperativas",
        _uuid_pk(),
        sa.Column("razon_social", sa.Text(), nullable=False),
        sa.Column("nombre_comercial", sa.Text(), nullable=True),
        sa.Column("ruc", sa.String(11), nullable=False),
        sa.Column("departamento", sa.Text(), nullable=False),
        sa.Column("provincia", sa.Text(), nullable=False),
        sa.Column("distrito", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), server_default="activa", nullable=False),
        sa.Column("es_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_fechas(),
        sa.CheckConstraint("ruc ~ '^[0-9]{11}$'", name=op.f("ck_cooperativas_ruc_11_digitos")),
        sa.CheckConstraint("estado IN ('activa', 'suspendida')", name=op.f("ck_cooperativas_estado_valido")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cooperativas")),
        sa.UniqueConstraint("ruc", name=op.f("uq_cooperativas_ruc")),
    )

    op.create_table(
        "productores",
        _uuid_pk(),
        sa.Column("dni", sa.String(8), nullable=False),
        sa.Column("nombres", sa.Text(), nullable=False),
        sa.Column("apellidos", sa.Text(), nullable=False),
        sa.Column("telefono", sa.Text(), nullable=True),
        sa.Column("consentimiento_datos_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consentimiento_origen", sa.Text(), nullable=True),
        sa.Column("es_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_fechas(),
        sa.CheckConstraint("dni ~ '^[0-9]{8}$'", name=op.f("ck_productores_dni_8_digitos")),
        sa.CheckConstraint(
            "consentimiento_origen IS NULL OR consentimiento_origen IN ('productor', 'cooperativa')",
            name=op.f("ck_productores_consentimiento_origen_valido"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_productores")),
        sa.UniqueConstraint("dni", name=op.f("uq_productores_dni")),
    )

    op.create_table(
        "perfiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rol", sa.Text(), nullable=False),
        sa.Column("cooperativa_id", sa.Uuid(), nullable=True),
        sa.Column("productor_id", sa.Uuid(), nullable=True),
        sa.Column("nombres", sa.Text(), nullable=False),
        sa.Column("apellidos", sa.Text(), nullable=False),
        sa.Column("correo", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("debe_cambiar_clave", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("ultimo_acceso_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        *_fechas(),
        sa.CheckConstraint(
            "rol IN ('superadmin', 'admin_cooperativa', 'operador', 'lector', 'productor')",
            name=op.f("ck_perfiles_rol_valido"),
        ),
        sa.CheckConstraint(
            "(rol = 'superadmin') = (cooperativa_id IS NULL)", name=op.f("ck_perfiles_cooperativa_segun_rol")
        ),
        sa.CheckConstraint(
            "(rol = 'productor') = (productor_id IS NOT NULL)", name=op.f("ck_perfiles_productor_segun_rol")
        ),
        sa.ForeignKeyConstraint(
            ["cooperativa_id"], ["cooperativas.id"], name=op.f("fk_perfiles_cooperativa_id_cooperativas")
        ),
        sa.ForeignKeyConstraint(
            ["productor_id"], ["productores.id"], name=op.f("fk_perfiles_productor_id_productores")
        ),
        sa.ForeignKeyConstraint(["creado_por"], ["perfiles.id"], name=op.f("fk_perfiles_creado_por_perfiles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_perfiles")),
        sa.UniqueConstraint("productor_id", name=op.f("uq_perfiles_productor_id")),
    )
    op.create_index(op.f("ix_perfiles_cooperativa_id"), "perfiles", ["cooperativa_id"])
    op.create_index(
        "uq_perfiles_correo",
        "perfiles",
        [sa.text("lower(correo)")],
        unique=True,
        postgresql_where=sa.text("correo IS NOT NULL"),
    )

    op.create_table(
        "afiliaciones",
        _uuid_pk(),
        sa.Column("productor_id", sa.Uuid(), nullable=False),
        sa.Column("cooperativa_id", sa.Uuid(), nullable=False),
        sa.Column("codigo_socio", sa.Text(), nullable=True),
        sa.Column("estado", sa.Text(), server_default="activa", nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=True),
        *_fechas(),
        sa.CheckConstraint("estado IN ('activa', 'inactiva')", name=op.f("ck_afiliaciones_estado_valido")),
        sa.ForeignKeyConstraint(
            ["cooperativa_id"], ["cooperativas.id"], name=op.f("fk_afiliaciones_cooperativa_id_cooperativas")
        ),
        sa.ForeignKeyConstraint(
            ["productor_id"], ["productores.id"], name=op.f("fk_afiliaciones_productor_id_productores")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_afiliaciones")),
    )
    # Una sola cooperativa activa por productor. Para permitir varias en el futuro, reemplazar
    # por un índice único sobre (productor_id, cooperativa_id).
    op.create_index(
        "uq_afiliaciones_productor_activa",
        "afiliaciones",
        ["productor_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'activa'"),
    )
    op.create_index("ix_afiliaciones_cooperativa_estado", "afiliaciones", ["cooperativa_id", "estado"])

    op.create_table(
        "auditoria",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ocurrido_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column("rol", sa.Text(), nullable=True),
        sa.Column("cooperativa_id", sa.Uuid(), nullable=True),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("entidad", sa.Text(), nullable=False),
        sa.Column("entidad_id", sa.Text(), nullable=True),
        sa.Column("detalle", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["cooperativa_id"], ["cooperativas.id"], name=op.f("fk_auditoria_cooperativa_id_cooperativas")
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["perfiles.id"], name=op.f("fk_auditoria_usuario_id_perfiles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auditoria")),
    )
    op.create_index(
        "ix_auditoria_cooperativa_ocurrido", "auditoria", ["cooperativa_id", sa.text("ocurrido_en DESC")]
    )
    op.create_index("ix_auditoria_usuario_ocurrido", "auditoria", ["usuario_id", sa.text("ocurrido_en DESC")])

    # La auditoría solo admite inserciones.
    op.execute(
        """
        CREATE FUNCTION auditoria_solo_insercion() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'La auditoría solo admite inserciones (% rechazado)', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER auditoria_solo_insercion
        BEFORE UPDATE OR DELETE ON auditoria
        FOR EACH ROW EXECUTE FUNCTION auditoria_solo_insercion();
        """
    )

    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS auditoria_solo_insercion ON auditoria")
    op.execute("DROP FUNCTION IF EXISTS auditoria_solo_insercion()")
    for tabla in reversed(TABLAS):
        op.drop_table(tabla)

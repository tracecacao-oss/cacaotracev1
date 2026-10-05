"""Parte 3: ficha completa del productor, documentos de sustento, parcelas y superposiciones.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05

Regla: toda tabla nueva lleva ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY y ninguna política.
"""
from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = ("documentos", "parcelas", "superposiciones")


def _fechas() -> list[sa.Column]:
    return [
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    # Ficha completa del productor. direccion_postal queda nula solo para altas de la Parte 2.
    op.add_column("productores", sa.Column("ruc", sa.String(length=11), nullable=True))
    op.add_column("productores", sa.Column("direccion_postal", sa.Text(), nullable=True))
    op.add_column("productores", sa.Column("correo_contacto", sa.Text(), nullable=True))
    op.add_column(
        "productores", sa.Column("ppa_registrado", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.add_column("productores", sa.Column("ppa_codigo", sa.Text(), nullable=True))
    op.add_column("productores", sa.Column("codigo_agrodigital", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_productores_ruc_11_digitos"), "productores", "ruc IS NULL OR ruc ~ '^[0-9]{11}$'"
    )
    op.create_check_constraint(
        op.f("ck_productores_ppa_codigo_solo_si_registrado"), "productores", "ppa_registrado OR ppa_codigo IS NULL"
    )

    op.create_table(
        "documentos",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("cooperativa_id", sa.UUID(), nullable=False),
        sa.Column("entidad", sa.Text(), nullable=False),
        sa.Column("entidad_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("ruta", sa.Text(), nullable=False),
        sa.Column("nombre_original", sa.Text(), nullable=False),
        sa.Column("tipo_mime", sa.Text(), nullable=False),
        sa.Column("tamano_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("subido_por", sa.UUID(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("anulado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anulado_por", sa.UUID(), nullable=True),
        sa.Column("motivo_anulacion", sa.Text(), nullable=True),
        sa.CheckConstraint("entidad IN ('productor', 'parcela')", name=op.f("ck_documentos_entidad_valida")),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_documentos_sha256_hex")),
        sa.CheckConstraint(
            "tipo IN ('dni', 'constancia_ppa', 'sustento_midagri', 'archivo_geometria')",
            name=op.f("ck_documentos_tipo_valido"),
        ),
        sa.ForeignKeyConstraint(["anulado_por"], ["perfiles.id"], name=op.f("fk_documentos_anulado_por_perfiles")),
        sa.ForeignKeyConstraint(
            ["cooperativa_id"], ["cooperativas.id"], name=op.f("fk_documentos_cooperativa_id_cooperativas")
        ),
        sa.ForeignKeyConstraint(["subido_por"], ["perfiles.id"], name=op.f("fk_documentos_subido_por_perfiles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documentos")),
    )
    op.create_index("ix_documentos_entidad", "documentos", ["entidad", "entidad_id"])
    op.create_index(
        "uq_documentos_vigente_contenido",
        "documentos",
        ["entidad", "entidad_id", "tipo", "sha256"],
        unique=True,
        postgresql_where=sa.text("anulado_en IS NULL"),
    )

    op.create_table(
        "parcelas",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("productor_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("departamento", sa.Text(), nullable=False),
        sa.Column("provincia", sa.Text(), nullable=False),
        sa.Column("distrito", sa.Text(), nullable=False),
        sa.Column("centro_poblado", sa.Text(), nullable=True),
        sa.Column("tipo_geometria", sa.Text(), nullable=False),
        # El índice espacial se crea abajo, explícito.
        sa.Column(
            "geometria",
            geoalchemy2.types.Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("area_calculada_ha", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("area_declarada_ha", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("area_cultivada_ha", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("origen_geometria", sa.Text(), nullable=False),
        sa.Column("archivo_documento_id", sa.UUID(), nullable=True),
        sa.Column("midagri_estado", sa.Text(), server_default="no_registrada", nullable=False),
        sa.Column("midagri_codigo", sa.Text(), nullable=True),
        sa.Column("estado", sa.Text(), server_default="activa", nullable=False),
        sa.Column("registrada_por", sa.UUID(), nullable=False),
        sa.Column("registrada_por_rol", sa.Text(), nullable=False),
        sa.Column("cooperativa_registro_id", sa.UUID(), nullable=False),
        *_fechas(),
        sa.CheckConstraint("codigo ~ '^PA-[0-9]{5}$'", name=op.f("ck_parcelas_codigo_formato")),
        sa.CheckConstraint("tipo_geometria IN ('poligono', 'punto')", name=op.f("ck_parcelas_tipo_geometria_valido")),
        sa.CheckConstraint(
            "(tipo_geometria = 'poligono' AND GeometryType(geometria) = 'POLYGON')"
            " OR (tipo_geometria = 'punto' AND GeometryType(geometria) = 'POINT')",
            name=op.f("ck_parcelas_geometria_segun_tipo"),
        ),
        sa.CheckConstraint(
            "tipo_geometria <> 'poligono' OR area_calculada_ha IS NOT NULL",
            name=op.f("ck_parcelas_area_calculada_si_poligono"),
        ),
        sa.CheckConstraint(
            "tipo_geometria <> 'punto' OR area_declarada_ha IS NOT NULL",
            name=op.f("ck_parcelas_area_declarada_si_punto"),
        ),
        sa.CheckConstraint(
            "area_cultivada_ha <= CASE WHEN tipo_geometria = 'poligono'"
            " THEN area_calculada_ha ELSE area_declarada_ha END",
            name=op.f("ck_parcelas_cultivada_no_supera_total"),
        ),
        sa.CheckConstraint("origen_geometria IN ('dibujada', 'archivo')", name=op.f("ck_parcelas_origen_valido")),
        sa.CheckConstraint(
            "origen_geometria <> 'archivo' OR archivo_documento_id IS NOT NULL",
            name=op.f("ck_parcelas_archivo_si_origen_archivo"),
        ),
        sa.CheckConstraint(
            "midagri_estado IN ('no_registrada', 'sin_observacion', 'en_revision', 'validado')",
            name=op.f("ck_parcelas_midagri_estado_valido"),
        ),
        sa.CheckConstraint("estado IN ('activa', 'inactiva')", name=op.f("ck_parcelas_estado_valido")),
        sa.ForeignKeyConstraint(
            ["archivo_documento_id"], ["documentos.id"], name=op.f("fk_parcelas_archivo_documento_id_documentos")
        ),
        sa.ForeignKeyConstraint(
            ["cooperativa_registro_id"],
            ["cooperativas.id"],
            name=op.f("fk_parcelas_cooperativa_registro_id_cooperativas"),
        ),
        sa.ForeignKeyConstraint(["productor_id"], ["productores.id"], name=op.f("fk_parcelas_productor_id_productores")),
        sa.ForeignKeyConstraint(["registrada_por"], ["perfiles.id"], name=op.f("fk_parcelas_registrada_por_perfiles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parcelas")),
        sa.UniqueConstraint("cooperativa_registro_id", "codigo", name="uq_parcelas_cooperativa_codigo"),
    )
    op.create_index("idx_parcelas_geometria", "parcelas", ["geometria"], postgresql_using="gist")
    op.create_index(op.f("ix_parcelas_productor_id"), "parcelas", ["productor_id"])
    op.create_index(
        "uq_parcelas_productor_nombre", "parcelas", ["productor_id", sa.literal_column("lower(nombre)")], unique=True
    )

    op.create_table(
        "superposiciones",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("parcela_a_id", sa.UUID(), nullable=False),
        sa.Column("parcela_b_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("area_ha", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("porcentaje", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("estado", sa.Text(), server_default="abierta", nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("cerrada_por", sa.UUID(), nullable=True),
        sa.Column("cerrada_en", sa.DateTime(timezone=True), nullable=True),
        *_fechas(),
        sa.CheckConstraint("parcela_a_id < parcela_b_id", name=op.f("ck_superposiciones_par_ordenado")),
        sa.CheckConstraint(
            "tipo IN ('poligono_poligono', 'punto_en_poligono')", name=op.f("ck_superposiciones_tipo_valido")
        ),
        sa.CheckConstraint(
            "estado IN ('abierta', 'resuelta', 'aceptada')", name=op.f("ck_superposiciones_estado_valido")
        ),
        sa.ForeignKeyConstraint(
            ["cerrada_por"], ["perfiles.id"], name=op.f("fk_superposiciones_cerrada_por_perfiles")
        ),
        sa.ForeignKeyConstraint(
            ["parcela_a_id"], ["parcelas.id"], name=op.f("fk_superposiciones_parcela_a_id_parcelas")
        ),
        sa.ForeignKeyConstraint(
            ["parcela_b_id"], ["parcelas.id"], name=op.f("fk_superposiciones_parcela_b_id_parcelas")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_superposiciones")),
        sa.UniqueConstraint("parcela_a_id", "parcela_b_id", name="uq_superposiciones_par"),
    )
    op.create_index("ix_superposiciones_parcela_b", "superposiciones", ["parcela_b_id"])

    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for tabla in reversed(TABLAS):
        op.drop_table(tabla)
    op.drop_constraint(op.f("ck_productores_ppa_codigo_solo_si_registrado"), "productores", type_="check")
    op.drop_constraint(op.f("ck_productores_ruc_11_digitos"), "productores", type_="check")
    for columna in ("codigo_agrodigital", "ppa_codigo", "ppa_registrado", "correo_contacto", "direccion_postal", "ruc"):
        op.drop_column("productores", columna)

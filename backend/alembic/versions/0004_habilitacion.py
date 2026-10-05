"""Parte 4: análisis de cobertura forestal, visitas de campo, expediente legal y compuerta de habilitación.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-05

Regla: toda tabla nueva lleva ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY y ninguna política.
"""
from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = ("analisis_cobertura", "visitas_campo", "exenciones_documento", "decisiones_habilitacion")

TIPOS_ANTES = "'dni', 'constancia_ppa', 'sustento_midagri', 'archivo_geometria'"
TIPOS_AHORA = (
    "'dni', 'constancia_ppa', 'sustento_midagri', 'archivo_geometria', 'titulo_sunarp', 'constancia_posesion', "
    "'cusaf', 'autorizacion_serfor', 'sunafil', 'sunat', 'zonificacion', 'foto_visita', 'respuesta_analisis'"
)


def _fechas() -> list[sa.Column]:
    return [
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    # ---------- parcelas: compuerta y último cambio de geometría ----------
    op.add_column("parcelas", sa.Column("habilitacion_estado", sa.Text(), server_default="pendiente", nullable=False))
    op.create_check_constraint(
        op.f("ck_parcelas_habilitacion_estado_valido"),
        "parcelas",
        "habilitacion_estado IN ('pendiente', 'habilitada', 'observada', 'excluida')",
    )
    op.add_column(
        "parcelas",
        sa.Column("geometria_actualizada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    # Para las parcelas existentes, el último cambio de geometría conocido es su creación.
    op.execute("UPDATE parcelas SET geometria_actualizada_en = creado_en")

    # ---------- documentos: tipos legales, fotos, respuestas y cotejo ----------
    op.add_column("documentos", sa.Column("numero", sa.Text(), nullable=True))
    op.add_column("documentos", sa.Column("entidad_emisora", sa.Text(), nullable=True))
    op.add_column("documentos", sa.Column("fecha_emision", sa.Date(), nullable=True))
    op.add_column("documentos", sa.Column("fecha_vencimiento", sa.Date(), nullable=True))
    op.add_column("documentos", sa.Column("cotejado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documentos", sa.Column("cotejado_por", sa.UUID(), nullable=True))
    op.add_column("documentos", sa.Column("cotejo_nota", sa.Text(), nullable=True))
    op.create_foreign_key(op.f("fk_documentos_cotejado_por_perfiles"), "documentos", "perfiles", ["cotejado_por"], ["id"])
    op.alter_column("documentos", "subido_por", existing_type=sa.UUID(), nullable=True)
    op.drop_constraint(op.f("ck_documentos_entidad_valida"), "documentos", type_="check")
    op.create_check_constraint(
        op.f("ck_documentos_entidad_valida"), "documentos", "entidad IN ('productor', 'parcela', 'visita', 'analisis')"
    )
    op.drop_constraint(op.f("ck_documentos_tipo_valido"), "documentos", type_="check")
    op.create_check_constraint(op.f("ck_documentos_tipo_valido"), "documentos", f"tipo IN ({TIPOS_AHORA})")
    op.create_check_constraint(
        op.f("ck_documentos_subido_por_si_no_sistema"),
        "documentos",
        "subido_por IS NOT NULL OR tipo = 'respuesta_analisis'",
    )
    op.create_check_constraint(
        op.f("ck_documentos_vencimiento_despues_de_emision"),
        "documentos",
        "fecha_vencimiento IS NULL OR fecha_emision IS NULL OR fecha_vencimiento > fecha_emision",
    )

    # ---------- analisis_cobertura ----------
    op.create_table(
        "analisis_cobertura",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("parcela_id", sa.UUID(), nullable=False),
        sa.Column("cooperativa_id", sa.UUID(), nullable=False),
        sa.Column("fuente", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), server_default="pendiente", nullable=False),
        sa.Column(
            "geometria",
            geoalchemy2.types.Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("geometria_sha256", sa.String(length=64), nullable=False),
        sa.Column("es_aproximacion", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("resultado_fuente", sa.Text(), nullable=True),
        sa.Column("indicadores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("version_fuente", sa.Text(), nullable=True),
        sa.Column("respuesta_documento_id", sa.UUID(), nullable=True),
        sa.Column("solicitado_por", sa.UUID(), nullable=True),
        sa.Column("solicitado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("intentos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_detalle", sa.Text(), nullable=True),
        sa.Column("reintentar_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        *_fechas(),
        sa.CheckConstraint("fuente IN ('whisp', 'gfw')", name=op.f("ck_analisis_cobertura_fuente_valida")),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'en_proceso', 'completado', 'error')", name=op.f("ck_analisis_cobertura_estado_valido")
        ),
        sa.CheckConstraint("geometria_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_analisis_cobertura_sha256_hex")),
        sa.ForeignKeyConstraint(
            ["cooperativa_id"], ["cooperativas.id"], name=op.f("fk_analisis_cobertura_cooperativa_id_cooperativas")
        ),
        sa.ForeignKeyConstraint(["parcela_id"], ["parcelas.id"], name=op.f("fk_analisis_cobertura_parcela_id_parcelas")),
        sa.ForeignKeyConstraint(
            ["respuesta_documento_id"],
            ["documentos.id"],
            name=op.f("fk_analisis_cobertura_respuesta_documento_id_documentos"),
        ),
        sa.ForeignKeyConstraint(
            ["solicitado_por"], ["perfiles.id"], name=op.f("fk_analisis_cobertura_solicitado_por_perfiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analisis_cobertura")),
    )
    op.create_index("ix_analisis_cobertura_cola", "analisis_cobertura", ["estado", "reintentar_en"])
    op.create_index("ix_analisis_cobertura_parcela", "analisis_cobertura", ["parcela_id", "fuente"])

    # ---------- visitas_campo ----------
    op.create_table(
        "visitas_campo",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("parcela_id", sa.UUID(), nullable=False),
        sa.Column("cooperativa_id", sa.UUID(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("realizada_por_nombre", sa.Text(), nullable=False),
        sa.Column("realizada_por_cargo", sa.Text(), nullable=False),
        sa.Column("registrada_por", sa.UUID(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("perimetro_recorrido", sa.Boolean(), nullable=False),
        sa.Column("uso_observado", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("anulada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anulada_por", sa.UUID(), nullable=True),
        sa.Column("motivo_anulacion", sa.Text(), nullable=True),
        *_fechas(),
        sa.CheckConstraint(
            "motivo IN ('analisis_requiere_revision', 'verificacion_de_coordenadas', 'otro')",
            name=op.f("ck_visitas_campo_motivo_valido"),
        ),
        sa.CheckConstraint(
            "uso_observado IN ('cacao_bajo_sombra', 'cacao_sin_sombra', 'bosque', 'otro_cultivo', 'mixto')",
            name=op.f("ck_visitas_campo_uso_observado_valido"),
        ),
        sa.CheckConstraint("char_length(descripcion) >= 30", name=op.f("ck_visitas_campo_descripcion_minima")),
        sa.ForeignKeyConstraint(["anulada_por"], ["perfiles.id"], name=op.f("fk_visitas_campo_anulada_por_perfiles")),
        sa.ForeignKeyConstraint(
            ["cooperativa_id"], ["cooperativas.id"], name=op.f("fk_visitas_campo_cooperativa_id_cooperativas")
        ),
        sa.ForeignKeyConstraint(["parcela_id"], ["parcelas.id"], name=op.f("fk_visitas_campo_parcela_id_parcelas")),
        sa.ForeignKeyConstraint(
            ["registrada_por"], ["perfiles.id"], name=op.f("fk_visitas_campo_registrada_por_perfiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitas_campo")),
    )
    op.create_index("ix_visitas_campo_parcela", "visitas_campo", ["parcela_id"])

    # ---------- exenciones_documento ----------
    op.create_table(
        "exenciones_documento",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("parcela_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("declarada_por", sa.UUID(), nullable=False),
        sa.Column("declarada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("retirada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retirada_por", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('cusaf', 'autorizacion_serfor', 'sunafil', 'sunat', 'zonificacion')",
            name=op.f("ck_exenciones_documento_tipo_valido"),
        ),
        sa.CheckConstraint("char_length(motivo) >= 30", name=op.f("ck_exenciones_documento_motivo_minimo")),
        sa.ForeignKeyConstraint(
            ["declarada_por"], ["perfiles.id"], name=op.f("fk_exenciones_documento_declarada_por_perfiles")
        ),
        sa.ForeignKeyConstraint(["parcela_id"], ["parcelas.id"], name=op.f("fk_exenciones_documento_parcela_id_parcelas")),
        sa.ForeignKeyConstraint(
            ["retirada_por"], ["perfiles.id"], name=op.f("fk_exenciones_documento_retirada_por_perfiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exenciones_documento")),
    )
    op.create_index(
        "uq_exenciones_vigente",
        "exenciones_documento",
        ["parcela_id", "tipo"],
        unique=True,
        postgresql_where=sa.text("retirada_en IS NULL"),
    )

    # ---------- decisiones_habilitacion ----------
    op.create_table(
        "decisiones_habilitacion",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("parcela_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("decidida_por", sa.UUID(), nullable=True),
        sa.Column("decidida_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("requisitos", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("geometria_sha256", sa.String(length=64), nullable=False),
        sa.Column("evidencia_visita_id", sa.UUID(), nullable=True),
        sa.Column("evidencia_analisis_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "decision IN ('habilitar', 'observar', 'excluir')", name=op.f("ck_decisiones_habilitacion_decision_valida")
        ),
        sa.CheckConstraint("geometria_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_decisiones_habilitacion_sha256_hex")),
        sa.ForeignKeyConstraint(
            ["decidida_por"], ["perfiles.id"], name=op.f("fk_decisiones_habilitacion_decidida_por_perfiles")
        ),
        sa.ForeignKeyConstraint(
            ["evidencia_analisis_id"],
            ["analisis_cobertura.id"],
            name=op.f("fk_decisiones_habilitacion_evidencia_analisis_id_analisis_cobertura"),
        ),
        sa.ForeignKeyConstraint(
            ["evidencia_visita_id"],
            ["visitas_campo.id"],
            name=op.f("fk_decisiones_habilitacion_evidencia_visita_id_visitas_campo"),
        ),
        sa.ForeignKeyConstraint(
            ["parcela_id"], ["parcelas.id"], name=op.f("fk_decisiones_habilitacion_parcela_id_parcelas")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decisiones_habilitacion")),
    )
    op.create_index("ix_decisiones_habilitacion_parcela", "decisiones_habilitacion", ["parcela_id", "decidida_en"])
    # Una decisión no se edita ni se borra, tampoco con SQL directo.
    op.execute(
        """
        CREATE FUNCTION decisiones_habilitacion_inmutables() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Las decisiones de habilitación no se editan ni se borran';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER tg_decisiones_habilitacion_inmutables BEFORE UPDATE OR DELETE ON decisiones_habilitacion "
        "FOR EACH ROW EXECUTE FUNCTION decisiones_habilitacion_inmutables()"
    )

    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tg_decisiones_habilitacion_inmutables ON decisiones_habilitacion")
    op.execute("DROP FUNCTION IF EXISTS decisiones_habilitacion_inmutables()")
    op.drop_index("ix_decisiones_habilitacion_parcela", table_name="decisiones_habilitacion")
    op.drop_table("decisiones_habilitacion")
    op.drop_index("uq_exenciones_vigente", table_name="exenciones_documento")
    op.drop_table("exenciones_documento")
    op.drop_index("ix_visitas_campo_parcela", table_name="visitas_campo")
    op.drop_table("visitas_campo")
    op.drop_index("ix_analisis_cobertura_parcela", table_name="analisis_cobertura")
    op.drop_index("ix_analisis_cobertura_cola", table_name="analisis_cobertura")
    op.drop_table("analisis_cobertura")

    op.drop_constraint(op.f("ck_documentos_vencimiento_despues_de_emision"), "documentos", type_="check")
    op.drop_constraint(op.f("ck_documentos_subido_por_si_no_sistema"), "documentos", type_="check")
    op.drop_constraint(op.f("ck_documentos_tipo_valido"), "documentos", type_="check")
    op.create_check_constraint(op.f("ck_documentos_tipo_valido"), "documentos", f"tipo IN ({TIPOS_ANTES})")
    op.drop_constraint(op.f("ck_documentos_entidad_valida"), "documentos", type_="check")
    op.create_check_constraint(op.f("ck_documentos_entidad_valida"), "documentos", "entidad IN ('productor', 'parcela')")
    op.alter_column("documentos", "subido_por", existing_type=sa.UUID(), nullable=False)
    op.drop_constraint(op.f("fk_documentos_cotejado_por_perfiles"), "documentos", type_="foreignkey")
    for columna in ("cotejo_nota", "cotejado_por", "cotejado_en", "fecha_vencimiento", "fecha_emision", "entidad_emisora", "numero"):
        op.drop_column("documentos", columna)

    op.drop_column("parcelas", "geometria_actualizada_en")
    op.drop_constraint(op.f("ck_parcelas_habilitacion_estado_valido"), "parcelas", type_="check")
    op.drop_column("parcelas", "habilitacion_estado")

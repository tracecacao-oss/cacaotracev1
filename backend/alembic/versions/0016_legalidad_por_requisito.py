"""Adenda 4: perfil legal de la parcela, incidencias, documentos nuevos y cola del cruce con capas oficiales

- Tablas nuevas `parcela_variables` y `parcela_incidencias`, con RLS y sin políticas. Un trigger impide editar
  o borrar una variable (solo se marca no vigente) y borrar o reabrir una incidencia.
- Documentos de la parcela de la sección 6. `autorizacion_serfor` pasa a llamarse `autorizacion_cambio_uso`
  sin perder archivos, también en las exenciones, que quedan como historial.
- `documentos.clase`: la clase del título no inscrito (decisión del equipo del 2026-10-09).
- `parcelas.cruce_solicitado_en` y `parcelas.cruce_estado`: la cola del cruce. Las parcelas activas quedan en
  cola para su primer cruce. La migración no inventa valores: ninguna recibe un perfil.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-09

Regla: toda tabla nueva lleva ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY y ninguna política.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = ("parcela_variables", "parcela_incidencias")
DOCUMENTOS_ANTES = (
    "dni", "constancia_ppa", "sustento_midagri", "archivo_geometria", "titulo_sunarp", "constancia_posesion",
    "cusaf", "autorizacion_serfor", "sunafil", "sunat", "zonificacion", "foto_visita", "respuesta_analisis",
    "documento_entrega", "dop_pdf", "dpp_pdf", "imagen_satelital", "imagen_externa", "rnca", "partida_sunarp",
    "ficha_ruc", "vigencia_poderes", "ruc_comercio_exterior", "registro_aduanas", "factura_comercial",
    "packing_list", "certificado_origen", "certificado_fitosanitario", "certificacion", "dex_pdf_es",
    "dex_pdf_en", "dex_geojson", "dex_anexo_ii", "dex_hallazgos", "dex_leeme", "dex_paquete",
)  # fmt: skip
DOCUMENTOS_NUEVOS = (
    "titulo_no_inscrito", "certificado_catastral", "contrato_de_uso", "declaracion_jurada_tenencia",
    "constancia_comunal", "acta_comunal", "acuerdo_conservacion", "autorizacion_cambio_uso",
    "constancia_saneamiento_31145", "licencia_agua", "ficha_tecnica_ambiental", "instrumento_ambiental",
)  # fmt: skip
DOCUMENTOS_AHORA = tuple(t for t in DOCUMENTOS_ANTES if t != "autorizacion_serfor") + DOCUMENTOS_NUEVOS
EXENCIONES_ANTES = ("cusaf", "autorizacion_serfor", "sunafil", "sunat", "zonificacion")
EXENCIONES_AHORA = ("cusaf", "autorizacion_cambio_uso", "sunafil", "sunat", "zonificacion")
VARIABLES = (
    "tenencia_tipo", "en_anp", "en_tierra_forestal", "en_tierra_comunal", "junto_a_cuerpo_de_agua",
    "en_patrimonio_cultural", "usa_riego", "anio_instalacion_cultivo", "reserva_bosque_30",
)  # fmt: skip
CLASES_TITULO = ("titulo_formalizacion", "escritura_publica", "minuta")

# Una variable no se edita ni se borra: solo pasa de vigente a no vigente cuando llega otra.
FUNCION_VARIABLES = """
CREATE FUNCTION parcela_variables_fija() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Una variable del perfil legal no se borra';
    END IF;
    IF NEW.vigente AND NOT OLD.vigente
       OR (NEW.parcela_id, NEW.variable, NEW.valor, NEW.origen, NEW.registrada_en)
          IS DISTINCT FROM (OLD.parcela_id, OLD.variable, OLD.valor, OLD.origen, OLD.registrada_en)
       OR NEW.detalle IS DISTINCT FROM OLD.detalle
       OR NEW.fuente IS DISTINCT FROM OLD.fuente
       OR NEW.registrada_por IS DISTINCT FROM OLD.registrada_por THEN
        RAISE EXCEPTION 'Una variable del perfil legal no se edita: se registra otra';
    END IF;
    RETURN NEW;
END;
$$
"""
# Una incidencia no se borra y, cerrada, no cambia.
FUNCION_INCIDENCIAS = """
CREATE FUNCTION parcela_incidencias_fija() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Una incidencia de la parcela no se borra';
    END IF;
    IF OLD.estado = 'cerrada'
       OR (NEW.parcela_id, NEW.tipo, NEW.descripcion, NEW.fuente, NEW.registrada_por, NEW.registrada_en)
          IS DISTINCT FROM (OLD.parcela_id, OLD.tipo, OLD.descripcion, OLD.fuente, OLD.registrada_por,
                            OLD.registrada_en) THEN
        RAISE EXCEPTION 'Una incidencia de la parcela solo se cierra';
    END IF;
    RETURN NEW;
END;
$$
"""


def _en(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.create_table(
        "parcela_variables",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("parcela_id", sa.UUID(), nullable=False),
        sa.Column("variable", sa.Text(), nullable=False),
        sa.Column("valor", sa.Text(), nullable=False),
        sa.Column("detalle", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("origen", sa.Text(), nullable=False),
        sa.Column("fuente", sa.Text(), nullable=True),
        sa.Column("registrada_por", sa.UUID(), nullable=True),
        sa.Column("registrada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("vigente", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(f"variable IN ({_en(VARIABLES)})", name=op.f("ck_parcela_variables_variable_valida")),
        sa.CheckConstraint("origen IN ('declarado', 'cruce')", name=op.f("ck_parcela_variables_origen_valido")),
        sa.CheckConstraint(
            "origen = 'declarado' OR fuente IS NOT NULL", name=op.f("ck_parcela_variables_cruce_con_fuente")
        ),
        sa.CheckConstraint(
            "origen = 'cruce' OR registrada_por IS NOT NULL",
            name=op.f("ck_parcela_variables_declarado_con_persona"),
        ),
        sa.ForeignKeyConstraint(
            ["parcela_id"], ["parcelas.id"], name=op.f("fk_parcela_variables_parcela_id_parcelas")
        ),
        sa.ForeignKeyConstraint(
            ["registrada_por"], ["perfiles.id"], name=op.f("fk_parcela_variables_registrada_por_perfiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parcela_variables")),
    )
    op.create_index("ix_parcela_variables_parcela", "parcela_variables", ["parcela_id", "variable"], unique=False)
    op.create_index(
        "uq_parcela_variables_vigente",
        "parcela_variables",
        ["parcela_id", "variable", "origen"],
        unique=True,
        postgresql_where=sa.text("vigente"),
    )
    op.create_table(
        "parcela_incidencias",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("parcela_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("fuente", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), server_default="abierta", nullable=False),
        sa.Column("registrada_por", sa.UUID(), nullable=False),
        sa.Column("registrada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("cierre_nota", sa.Text(), nullable=True),
        sa.Column("cerrada_por", sa.UUID(), nullable=True),
        sa.Column("cerrada_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('tenencia', 'ambiental', 'otra')", name=op.f("ck_parcela_incidencias_tipo_valido")
        ),
        sa.CheckConstraint("estado IN ('abierta', 'cerrada')", name=op.f("ck_parcela_incidencias_estado_valido")),
        sa.CheckConstraint(
            "char_length(descripcion) >= 50", name=op.f("ck_parcela_incidencias_descripcion_minima")
        ),
        sa.CheckConstraint(
            "estado = 'abierta' OR "
            "(cierre_nota IS NOT NULL AND cerrada_por IS NOT NULL AND cerrada_en IS NOT NULL)",
            name=op.f("ck_parcela_incidencias_cierre_completo"),
        ),
        sa.ForeignKeyConstraint(
            ["parcela_id"], ["parcelas.id"], name=op.f("fk_parcela_incidencias_parcela_id_parcelas")
        ),
        sa.ForeignKeyConstraint(
            ["registrada_por"], ["perfiles.id"], name=op.f("fk_parcela_incidencias_registrada_por_perfiles")
        ),
        sa.ForeignKeyConstraint(
            ["cerrada_por"], ["perfiles.id"], name=op.f("fk_parcela_incidencias_cerrada_por_perfiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parcela_incidencias")),
    )
    op.create_index(
        "ix_parcela_incidencias_parcela", "parcela_incidencias", ["parcela_id", "estado"], unique=False
    )
    op.execute(FUNCION_VARIABLES)
    op.execute(
        "CREATE TRIGGER tg_parcela_variables_fija BEFORE UPDATE OR DELETE ON parcela_variables "
        "FOR EACH ROW EXECUTE FUNCTION parcela_variables_fija()"
    )
    op.execute(FUNCION_INCIDENCIAS)
    op.execute(
        "CREATE TRIGGER tg_parcela_incidencias_fija BEFORE UPDATE OR DELETE ON parcela_incidencias "
        "FOR EACH ROW EXECUTE FUNCTION parcela_incidencias_fija()"
    )
    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")

    # Documentos: los tipos nuevos y el cambio de nombre, sin perder archivos.
    op.drop_constraint(op.f("ck_documentos_tipo_valido"), "documentos", type_="check")
    op.execute("UPDATE documentos SET tipo = 'autorizacion_cambio_uso' WHERE tipo = 'autorizacion_serfor'")
    op.create_check_constraint(op.f("ck_documentos_tipo_valido"), "documentos", f"tipo IN ({_en(DOCUMENTOS_AHORA)})")
    op.add_column("documentos", sa.Column("clase", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_documentos_clase_valida"),
        "documentos",
        f"clase IS NULL OR (tipo = 'titulo_no_inscrito' AND clase IN ({_en(CLASES_TITULO)}))",
    )
    op.drop_constraint(op.f("ck_exenciones_documento_tipo_valido"), "exenciones_documento", type_="check")
    op.execute(
        "UPDATE exenciones_documento SET tipo = 'autorizacion_cambio_uso' WHERE tipo = 'autorizacion_serfor'"
    )
    op.create_check_constraint(
        op.f("ck_exenciones_documento_tipo_valido"), "exenciones_documento", f"tipo IN ({_en(EXENCIONES_AHORA)})"
    )

    # Cola del cruce: las parcelas activas quedan en cola para su primer cruce.
    op.add_column("parcelas", sa.Column("cruce_solicitado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("parcelas", sa.Column("cruce_estado", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.execute(
        "UPDATE parcelas SET cruce_solicitado_en = now() "
        "WHERE estado = 'activa' AND habilitacion_estado <> 'excluida'"
    )


def downgrade() -> None:
    op.drop_column("parcelas", "cruce_estado")
    op.drop_column("parcelas", "cruce_solicitado_en")
    op.drop_constraint(op.f("ck_exenciones_documento_tipo_valido"), "exenciones_documento", type_="check")
    op.execute(
        "UPDATE exenciones_documento SET tipo = 'autorizacion_serfor' WHERE tipo = 'autorizacion_cambio_uso'"
    )
    op.create_check_constraint(
        op.f("ck_exenciones_documento_tipo_valido"), "exenciones_documento", f"tipo IN ({_en(EXENCIONES_ANTES)})"
    )
    op.drop_constraint(op.f("ck_documentos_clase_valida"), "documentos", type_="check")
    op.drop_column("documentos", "clase")
    op.drop_constraint(op.f("ck_documentos_tipo_valido"), "documentos", type_="check")
    op.execute("UPDATE documentos SET tipo = 'autorizacion_serfor' WHERE tipo = 'autorizacion_cambio_uso'")
    op.create_check_constraint(op.f("ck_documentos_tipo_valido"), "documentos", f"tipo IN ({_en(DOCUMENTOS_ANTES)})")
    op.execute("DROP TRIGGER IF EXISTS tg_parcela_incidencias_fija ON parcela_incidencias")
    op.execute("DROP FUNCTION IF EXISTS parcela_incidencias_fija()")
    op.execute("DROP TRIGGER IF EXISTS tg_parcela_variables_fija ON parcela_variables")
    op.execute("DROP FUNCTION IF EXISTS parcela_variables_fija()")
    op.drop_index("ix_parcela_incidencias_parcela", table_name="parcela_incidencias")
    op.drop_table("parcela_incidencias")
    op.drop_index("uq_parcela_variables_vigente", table_name="parcela_variables", postgresql_where=sa.text("vigente"))
    op.drop_index("ix_parcela_variables_parcela", table_name="parcela_variables")
    op.drop_table("parcela_variables")

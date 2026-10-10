"""Adenda 6: política de la organización, actuaciones de diligencia y declaración aduanera

- Tablas nuevas `politicas_organizacion`, `actuaciones_diligencia` y `actuacion_productores`, con RLS y sin
  políticas. Triggers: una política o una actuación no se borra ni se edita (solo se anula, una vez, con
  motivo), y lo que une una actuación con sus productores no se cambia.
- `cooperativas` suma `canal_denuncias_contacto`.
- Documentos `renta_anual`, `politica_organizacion`, `evidencia_actuacion` y `dam`, y la entidad `actuacion`.
  `ruc_comercio_exterior` y `registro_aduanas` siguen admitidos en la base: los cargados se conservan como
  documentos anteriores.
- La migración no borra archivos ni inventa valores: ninguna organización recibe una política ni una
  actuación.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-09

Regla: toda tabla nueva lleva ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY y ninguna política.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = ("politicas_organizacion", "actuaciones_diligencia", "actuacion_productores")
DOCUMENTOS_ANTES = (
    "dni", "constancia_ppa", "sustento_midagri", "archivo_geometria", "titulo_sunarp", "constancia_posesion",
    "cusaf", "sunafil", "sunat", "zonificacion", "foto_visita", "respuesta_analisis", "documento_entrega",
    "dop_pdf", "dpp_pdf", "imagen_satelital", "imagen_externa", "rnca", "partida_sunarp", "ficha_ruc",
    "vigencia_poderes", "ruc_comercio_exterior", "registro_aduanas", "factura_comercial", "packing_list",
    "certificado_origen", "certificado_fitosanitario", "certificacion", "dex_pdf_es", "dex_pdf_en",
    "dex_geojson", "dex_anexo_ii", "dex_hallazgos", "dex_leeme", "dex_paquete", "titulo_no_inscrito",
    "certificado_catastral", "contrato_de_uso", "declaracion_jurada_tenencia", "constancia_comunal",
    "acta_comunal", "acuerdo_conservacion", "autorizacion_cambio_uso", "constancia_saneamiento_31145",
    "licencia_agua", "ficha_tecnica_ambiental", "instrumento_ambiental", "hoja_declaracion_productor",
    "relacion_trabajadores", "declaracion_renta",
)  # fmt: skip
DOCUMENTOS_AHORA = DOCUMENTOS_ANTES + ("renta_anual", "politica_organizacion", "evidencia_actuacion", "dam")
ENTIDADES_ANTES = (
    "productor", "parcela", "visita", "analisis", "tanda", "dop", "imagen", "dpp", "cooperativa", "lote",
    "certificacion", "dex", "declaracion_productor",
)  # fmt: skip
ENTIDADES_AHORA = ENTIDADES_ANTES + ("actuacion",)
TEMAS_POLITICA = ("integridad", "no_fraude", "canal_denuncias", "trabajo_digno", "revision_de_documentos")
TIPOS_ACTUACION = (
    "revision_de_fuente_publica", "consulta_a_partes_interesadas", "capacitacion", "verificacion_en_campo",
    "apoyo_a_productores",
)  # fmt: skip
TEMAS_ACTUACION = (
    "integridad", "tierra_forestal", "agroquimicos_y_envases", "trabajo", "tenencia", "areas_protegidas",
    "agua", "derechos_humanos",
)  # fmt: skip

# Una política o una actuación no se borra ni se edita: solo se anula, una vez, con motivo.
FUNCION_ANULABLE = """
CREATE FUNCTION {nombre}() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION '{que} no se borra: se anula con motivo';
    END IF;
    IF OLD.anulada_en IS NOT NULL
       OR (to_jsonb(NEW) - 'anulada_en' - 'anulada_por' - 'motivo_anulacion')
          IS DISTINCT FROM (to_jsonb(OLD) - 'anulada_en' - 'anulada_por' - 'motivo_anulacion') THEN
        RAISE EXCEPTION '{que} no se edita: se anula con motivo';
    END IF;
    RETURN NEW;
END;
$$
"""
FUNCION_ACTUACION_PRODUCTORES = """
CREATE FUNCTION actuacion_productores_fija() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Los productores de una actuación no se cambian';
END;
$$
"""


def _en(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def _temas(columna: str, temas: tuple[str, ...]) -> str:
    return f"cardinality({columna}) > 0 AND {columna} <@ ARRAY[{_en(temas)}]::text[]"


ANULACION = (
    "(anulada_en IS NULL) = (anulada_por IS NULL) AND (anulada_en IS NULL) = (motivo_anulacion IS NULL)"
)


def upgrade() -> None:
    op.add_column("cooperativas", sa.Column("canal_denuncias_contacto", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_cooperativas_canal_denuncias_contacto_valido"),
        "cooperativas",
        "canal_denuncias_contacto IS NULL OR char_length(canal_denuncias_contacto) BETWEEN 3 AND 200",
    )

    op.drop_constraint(op.f("ck_documentos_tipo_valido"), "documentos", type_="check")
    op.create_check_constraint(
        op.f("ck_documentos_tipo_valido"), "documentos", f"tipo IN ({_en(DOCUMENTOS_AHORA)})"
    )
    op.drop_constraint(op.f("ck_documentos_entidad_valida"), "documentos", type_="check")
    op.create_check_constraint(
        op.f("ck_documentos_entidad_valida"), "documentos", f"entidad IN ({_en(ENTIDADES_AHORA)})"
    )

    op.create_table(
        "politicas_organizacion",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("cooperativa_id", sa.UUID(), nullable=False),
        sa.Column("documento_id", sa.UUID(), nullable=False),
        sa.Column("temas", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("adoptada_en", sa.Date(), nullable=False),
        sa.Column("organo", sa.Text(), nullable=False),
        sa.Column("version_plantilla", sa.Integer(), nullable=True),
        sa.Column("registrada_por", sa.UUID(), nullable=False),
        sa.Column(
            "registrada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("anulada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anulada_por", sa.UUID(), nullable=True),
        sa.Column("motivo_anulacion", sa.Text(), nullable=True),
        sa.CheckConstraint(
            _temas("temas", TEMAS_POLITICA), name=op.f("ck_politicas_organizacion_temas_validos")
        ),
        sa.CheckConstraint(
            "char_length(organo) BETWEEN 2 AND 200", name=op.f("ck_politicas_organizacion_organo_valido")
        ),
        sa.CheckConstraint(ANULACION, name=op.f("ck_politicas_organizacion_anulacion_completa")),
        sa.ForeignKeyConstraint(
            ["cooperativa_id"],
            ["cooperativas.id"],
            name=op.f("fk_politicas_organizacion_cooperativa_id_cooperativas"),
        ),
        sa.ForeignKeyConstraint(
            ["documento_id"],
            ["documentos.id"],
            name=op.f("fk_politicas_organizacion_documento_id_documentos"),
        ),
        sa.ForeignKeyConstraint(
            ["registrada_por"],
            ["perfiles.id"],
            name=op.f("fk_politicas_organizacion_registrada_por_perfiles"),
        ),
        sa.ForeignKeyConstraint(
            ["anulada_por"], ["perfiles.id"], name=op.f("fk_politicas_organizacion_anulada_por_perfiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_politicas_organizacion")),
    )
    op.create_index(
        "ix_politicas_organizacion_cooperativa", "politicas_organizacion", ["cooperativa_id"], unique=False
    )
    op.create_table(
        "actuaciones_diligencia",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("cooperativa_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("temas", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("contraparte", sa.Text(), nullable=True),
        sa.Column("resultado", sa.Text(), nullable=False),
        sa.Column("participantes", sa.Integer(), nullable=True),
        sa.Column("departamento", sa.Text(), nullable=True),
        sa.Column("provincia", sa.Text(), nullable=True),
        sa.Column("distrito", sa.Text(), nullable=True),
        sa.Column("registrada_por", sa.UUID(), nullable=False),
        sa.Column(
            "registrada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("anulada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anulada_por", sa.UUID(), nullable=True),
        sa.Column("motivo_anulacion", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"tipo IN ({_en(TIPOS_ACTUACION)})", name=op.f("ck_actuaciones_diligencia_tipo_valido")
        ),
        sa.CheckConstraint(
            _temas("temas", TEMAS_ACTUACION), name=op.f("ck_actuaciones_diligencia_temas_validos")
        ),
        sa.CheckConstraint(
            "char_length(descripcion) >= 50", name=op.f("ck_actuaciones_diligencia_descripcion_minima")
        ),
        sa.CheckConstraint(
            "char_length(resultado) >= 20", name=op.f("ck_actuaciones_diligencia_resultado_minimo")
        ),
        sa.CheckConstraint(
            "participantes IS NULL OR participantes > 0",
            name=op.f("ck_actuaciones_diligencia_participantes_positivos"),
        ),
        sa.CheckConstraint(ANULACION, name=op.f("ck_actuaciones_diligencia_anulacion_completa")),
        sa.ForeignKeyConstraint(
            ["cooperativa_id"],
            ["cooperativas.id"],
            name=op.f("fk_actuaciones_diligencia_cooperativa_id_cooperativas"),
        ),
        sa.ForeignKeyConstraint(
            ["registrada_por"],
            ["perfiles.id"],
            name=op.f("fk_actuaciones_diligencia_registrada_por_perfiles"),
        ),
        sa.ForeignKeyConstraint(
            ["anulada_por"], ["perfiles.id"], name=op.f("fk_actuaciones_diligencia_anulada_por_perfiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actuaciones_diligencia")),
    )
    op.create_index(
        "ix_actuaciones_diligencia_cooperativa_fecha",
        "actuaciones_diligencia",
        ["cooperativa_id", "fecha"],
        unique=False,
    )
    op.create_table(
        "actuacion_productores",
        sa.Column("actuacion_id", sa.UUID(), nullable=False),
        sa.Column("productor_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actuacion_id"],
            ["actuaciones_diligencia.id"],
            name=op.f("fk_actuacion_productores_actuacion_id_actuaciones_diligencia"),
        ),
        sa.ForeignKeyConstraint(
            ["productor_id"],
            ["productores.id"],
            name=op.f("fk_actuacion_productores_productor_id_productores"),
        ),
        sa.PrimaryKeyConstraint("actuacion_id", "productor_id", name=op.f("pk_actuacion_productores")),
    )
    op.create_index(
        "ix_actuacion_productores_productor", "actuacion_productores", ["productor_id"], unique=False
    )

    op.execute(FUNCION_ANULABLE.format(nombre="politicas_organizacion_fija", que="Una política"))
    op.execute(
        "CREATE TRIGGER tg_politicas_organizacion_fija BEFORE UPDATE OR DELETE ON politicas_organizacion "
        "FOR EACH ROW EXECUTE FUNCTION politicas_organizacion_fija()"
    )
    op.execute(FUNCION_ANULABLE.format(nombre="actuaciones_diligencia_fija", que="Una actuación"))
    op.execute(
        "CREATE TRIGGER tg_actuaciones_diligencia_fija BEFORE UPDATE OR DELETE ON actuaciones_diligencia "
        "FOR EACH ROW EXECUTE FUNCTION actuaciones_diligencia_fija()"
    )
    op.execute(FUNCION_ACTUACION_PRODUCTORES)
    op.execute(
        "CREATE TRIGGER tg_actuacion_productores_fija BEFORE UPDATE OR DELETE ON actuacion_productores "
        "FOR EACH ROW EXECUTE FUNCTION actuacion_productores_fija()"
    )
    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TRIGGER tg_actuacion_productores_fija ON actuacion_productores")
    op.execute("DROP FUNCTION actuacion_productores_fija()")
    op.execute("DROP TRIGGER tg_actuaciones_diligencia_fija ON actuaciones_diligencia")
    op.execute("DROP FUNCTION actuaciones_diligencia_fija()")
    op.execute("DROP TRIGGER tg_politicas_organizacion_fija ON politicas_organizacion")
    op.execute("DROP FUNCTION politicas_organizacion_fija()")
    op.drop_index("ix_actuacion_productores_productor", table_name="actuacion_productores")
    op.drop_table("actuacion_productores")
    op.drop_index("ix_actuaciones_diligencia_cooperativa_fecha", table_name="actuaciones_diligencia")
    op.drop_table("actuaciones_diligencia")
    op.drop_index("ix_politicas_organizacion_cooperativa", table_name="politicas_organizacion")
    op.drop_table("politicas_organizacion")
    op.execute(
        "DELETE FROM documentos WHERE entidad = 'actuacion' "
        "OR tipo IN ('renta_anual', 'politica_organizacion', 'evidencia_actuacion', 'dam')"
    )
    op.drop_constraint(op.f("ck_documentos_entidad_valida"), "documentos", type_="check")
    op.create_check_constraint(
        op.f("ck_documentos_entidad_valida"), "documentos", f"entidad IN ({_en(ENTIDADES_ANTES)})"
    )
    op.drop_constraint(op.f("ck_documentos_tipo_valido"), "documentos", type_="check")
    op.create_check_constraint(
        op.f("ck_documentos_tipo_valido"), "documentos", f"tipo IN ({_en(DOCUMENTOS_ANTES)})"
    )
    op.drop_constraint(op.f("ck_cooperativas_canal_denuncias_contacto_valido"), "cooperativas", type_="check")
    op.drop_column("cooperativas", "canal_denuncias_contacto")

"""Adenda 5: declaración anual del productor, productos declarados y valores de referencia

- Tablas nuevas `declaraciones_productor` y `declaracion_productos`, con RLS y sin políticas. Un trigger impide
  borrar una declaración o cambiar lo que respondió (solo cambian su estado, su fecha de declaración al
  cargar la hoja firmada y la nota de seguimiento), y otro impide borrar un producto o cambiar algo que no
  sea su revisión.
- Documentos `hoja_declaracion_productor`, `relacion_trabajadores` y `declaracion_renta`, de la entidad
  `declaracion_productor`.
- `configuracion_plataforma` suma `uit_soles`, `uit_anio`, `jornal_minimo_referencia` y
  `jornal_referencia_nota`. Vacíos: el sistema no asume valores.
- La migración no inventa valores: ningún productor recibe una declaración.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-09

Regla: toda tabla nueva lleva ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY y ninguna política.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = ("declaraciones_productor", "declaracion_productos")
DOCUMENTOS_ANTES = (
    "dni", "constancia_ppa", "sustento_midagri", "archivo_geometria", "titulo_sunarp", "constancia_posesion",
    "cusaf", "sunafil", "sunat", "zonificacion", "foto_visita", "respuesta_analisis", "documento_entrega",
    "dop_pdf", "dpp_pdf", "imagen_satelital", "imagen_externa", "rnca", "partida_sunarp", "ficha_ruc",
    "vigencia_poderes", "ruc_comercio_exterior", "registro_aduanas", "factura_comercial", "packing_list",
    "certificado_origen", "certificado_fitosanitario", "certificacion", "dex_pdf_es", "dex_pdf_en",
    "dex_geojson", "dex_anexo_ii", "dex_hallazgos", "dex_leeme", "dex_paquete", "titulo_no_inscrito",
    "certificado_catastral", "contrato_de_uso", "declaracion_jurada_tenencia", "constancia_comunal",
    "acta_comunal", "acuerdo_conservacion", "autorizacion_cambio_uso", "constancia_saneamiento_31145",
    "licencia_agua", "ficha_tecnica_ambiental", "instrumento_ambiental",
)  # fmt: skip
DOCUMENTOS_AHORA = DOCUMENTOS_ANTES + ("hoja_declaracion_productor", "relacion_trabajadores", "declaracion_renta")
ENTIDADES_ANTES = (
    "productor", "parcela", "visita", "analisis", "tanda", "dop", "imagen", "dpp", "cooperativa", "lote",
    "certificacion", "dex",
)  # fmt: skip
ENTIDADES_AHORA = ENTIDADES_ANTES + ("declaracion_productor",)
TIPOS_PRODUCTO = ("fertilizante", "herbicida", "insecticida", "fungicida", "otro")

# Una declaración no se borra ni se edita: solo cambian su estado, su fecha de declaración (al cargar la hoja
# firmada) y la nota de seguimiento. Una vez reemplazada, no cambia más.
FUNCION_DECLARACIONES = """
CREATE FUNCTION declaraciones_productor_fija() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Una declaración del productor no se borra';
    END IF;
    IF OLD.estado = 'reemplazada' AND NEW.estado IS DISTINCT FROM OLD.estado
       OR OLD.estado = 'vigente' AND NEW.estado = 'por_firmar'
       OR (NEW.cooperativa_id, NEW.productor_id, NEW.version_cuestionario, NEW.version_texto, NEW.origen,
           NEW.registrada_por, NEW.registrada_en)
          IS DISTINCT FROM (OLD.cooperativa_id, OLD.productor_id, OLD.version_cuestionario, OLD.version_texto,
                            OLD.origen, OLD.registrada_por, OLD.registrada_en)
       OR NEW.respuestas IS DISTINCT FROM OLD.respuestas
       OR NEW.contexto IS DISTINCT FROM OLD.contexto
       OR OLD.declarada_en IS NOT NULL AND NEW.declarada_en IS DISTINCT FROM OLD.declarada_en
       OR OLD.vigente_hasta IS NOT NULL AND NEW.vigente_hasta IS DISTINCT FROM OLD.vigente_hasta THEN
        RAISE EXCEPTION 'Una declaración del productor no se edita: se registra otra';
    END IF;
    RETURN NEW;
END;
$$
"""
# Un producto declarado no se borra; solo cambia su revisión.
FUNCION_PRODUCTOS = """
CREATE FUNCTION declaracion_productos_fija() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Un producto declarado no se borra';
    END IF;
    IF (NEW.declaracion_id, NEW.nombre, NEW.tipo) IS DISTINCT FROM (OLD.declaracion_id, OLD.nombre, OLD.tipo) THEN
        RAISE EXCEPTION 'Un producto declarado no se edita: solo cambia su revisión';
    END IF;
    RETURN NEW;
END;
$$
"""


def _en(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.create_table(
        "declaraciones_productor",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("cooperativa_id", sa.UUID(), nullable=False),
        sa.Column("productor_id", sa.UUID(), nullable=False),
        sa.Column("version_cuestionario", sa.Integer(), nullable=False),
        sa.Column("version_texto", sa.Integer(), nullable=False),
        sa.Column("respuestas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("contexto", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("origen", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("registrada_por", sa.UUID(), nullable=False),
        sa.Column("registrada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("declarada_en", sa.Date(), nullable=True),
        sa.Column("vigente_hasta", sa.Date(), nullable=True),
        sa.Column("seguimiento_nota", sa.Text(), nullable=True),
        sa.Column("seguimiento_por", sa.UUID(), nullable=True),
        sa.Column("seguimiento_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "origen IN ('productor', 'personal')", name=op.f("ck_declaraciones_productor_origen_valido")
        ),
        sa.CheckConstraint(
            "estado IN ('por_firmar', 'vigente', 'reemplazada')",
            name=op.f("ck_declaraciones_productor_estado_valido"),
        ),
        sa.CheckConstraint(
            "estado = 'reemplazada' OR (estado = 'por_firmar') = (declarada_en IS NULL)",
            name=op.f("ck_declaraciones_productor_declarada_salvo_por_firmar"),
        ),
        sa.CheckConstraint(
            "(declarada_en IS NULL) = (vigente_hasta IS NULL)",
            name=op.f("ck_declaraciones_productor_vigencia_con_declaracion"),
        ),
        sa.CheckConstraint(
            "seguimiento_nota IS NULL OR char_length(seguimiento_nota) >= 50",
            name=op.f("ck_declaraciones_productor_seguimiento_minimo"),
        ),
        sa.ForeignKeyConstraint(
            ["cooperativa_id"], ["cooperativas.id"], name=op.f("fk_declaraciones_productor_cooperativa_id_cooperativas")
        ),
        sa.ForeignKeyConstraint(
            ["productor_id"], ["productores.id"], name=op.f("fk_declaraciones_productor_productor_id_productores")
        ),
        sa.ForeignKeyConstraint(
            ["registrada_por"], ["perfiles.id"], name=op.f("fk_declaraciones_productor_registrada_por_perfiles")
        ),
        sa.ForeignKeyConstraint(
            ["seguimiento_por"], ["perfiles.id"], name=op.f("fk_declaraciones_productor_seguimiento_por_perfiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_declaraciones_productor")),
    )
    op.create_index(
        "ix_declaraciones_productor_productor",
        "declaraciones_productor",
        ["productor_id", "cooperativa_id"],
        unique=False,
    )
    op.create_index(
        "uq_declaraciones_productor_vigente",
        "declaraciones_productor",
        ["productor_id", "cooperativa_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'vigente'"),
    )
    op.create_index(
        "uq_declaraciones_productor_por_firmar",
        "declaraciones_productor",
        ["productor_id", "cooperativa_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'por_firmar'"),
    )
    op.create_table(
        "declaracion_productos",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("declaracion_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("revision", sa.Text(), server_default="sin_revisar", nullable=False),
        sa.Column("registro", sa.Text(), nullable=True),
        sa.Column("revisado_por", sa.UUID(), nullable=True),
        sa.Column("revisado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("copiada_de", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "char_length(nombre) BETWEEN 2 AND 80", name=op.f("ck_declaracion_productos_nombre_valido")
        ),
        sa.CheckConstraint(f"tipo IN ({_en(TIPOS_PRODUCTO)})", name=op.f("ck_declaracion_productos_tipo_valido")),
        sa.CheckConstraint(
            "revision IN ('sin_revisar', 'figura', 'no_figura')",
            name=op.f("ck_declaracion_productos_revision_valida"),
        ),
        sa.CheckConstraint(
            "revision = 'sin_revisar' OR (revisado_por IS NOT NULL AND revisado_en IS NOT NULL)",
            name=op.f("ck_declaracion_productos_revision_con_persona"),
        ),
        sa.ForeignKeyConstraint(
            ["declaracion_id"],
            ["declaraciones_productor.id"],
            name=op.f("fk_declaracion_productos_declaracion_id_declaraciones_productor"),
        ),
        sa.ForeignKeyConstraint(
            ["revisado_por"], ["perfiles.id"], name=op.f("fk_declaracion_productos_revisado_por_perfiles")
        ),
        sa.ForeignKeyConstraint(
            ["copiada_de"],
            ["declaracion_productos.id"],
            name=op.f("fk_declaracion_productos_copiada_de_declaracion_productos"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_declaracion_productos")),
    )
    op.create_index(
        "ix_declaracion_productos_declaracion", "declaracion_productos", ["declaracion_id"], unique=False
    )
    op.execute(FUNCION_DECLARACIONES)
    op.execute(
        "CREATE TRIGGER tg_declaraciones_productor_fija BEFORE UPDATE OR DELETE ON declaraciones_productor "
        "FOR EACH ROW EXECUTE FUNCTION declaraciones_productor_fija()"
    )
    op.execute(FUNCION_PRODUCTOS)
    op.execute(
        "CREATE TRIGGER tg_declaracion_productos_fija BEFORE UPDATE OR DELETE ON declaracion_productos "
        "FOR EACH ROW EXECUTE FUNCTION declaracion_productos_fija()"
    )
    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")

    op.drop_constraint(op.f("ck_documentos_tipo_valido"), "documentos", type_="check")
    op.create_check_constraint(op.f("ck_documentos_tipo_valido"), "documentos", f"tipo IN ({_en(DOCUMENTOS_AHORA)})")
    op.drop_constraint(op.f("ck_documentos_entidad_valida"), "documentos", type_="check")
    op.create_check_constraint(
        op.f("ck_documentos_entidad_valida"), "documentos", f"entidad IN ({_en(ENTIDADES_AHORA)})"
    )

    op.add_column("configuracion_plataforma", sa.Column("uit_soles", sa.Numeric(10, 2), nullable=True))
    op.add_column("configuracion_plataforma", sa.Column("uit_anio", sa.Integer(), nullable=True))
    op.add_column(
        "configuracion_plataforma", sa.Column("jornal_minimo_referencia", sa.Numeric(10, 2), nullable=True)
    )
    op.add_column("configuracion_plataforma", sa.Column("jornal_referencia_nota", sa.Text(), nullable=True))


def downgrade() -> None:
    for columna in ("jornal_referencia_nota", "jornal_minimo_referencia", "uit_anio", "uit_soles"):
        op.drop_column("configuracion_plataforma", columna)
    op.execute("DELETE FROM documentos WHERE entidad = 'declaracion_productor'")
    op.drop_constraint(op.f("ck_documentos_entidad_valida"), "documentos", type_="check")
    op.create_check_constraint(
        op.f("ck_documentos_entidad_valida"), "documentos", f"entidad IN ({_en(ENTIDADES_ANTES)})"
    )
    op.drop_constraint(op.f("ck_documentos_tipo_valido"), "documentos", type_="check")
    op.create_check_constraint(op.f("ck_documentos_tipo_valido"), "documentos", f"tipo IN ({_en(DOCUMENTOS_ANTES)})")
    op.execute("DROP TRIGGER tg_declaracion_productos_fija ON declaracion_productos")
    op.execute("DROP FUNCTION declaracion_productos_fija()")
    op.execute("DROP TRIGGER tg_declaraciones_productor_fija ON declaraciones_productor")
    op.execute("DROP FUNCTION declaraciones_productor_fija()")
    op.drop_index("ix_declaracion_productos_declaracion", table_name="declaracion_productos")
    op.drop_table("declaracion_productos")
    op.drop_index("uq_declaraciones_productor_por_firmar", table_name="declaraciones_productor")
    op.drop_index("uq_declaraciones_productor_vigente", table_name="declaraciones_productor")
    op.drop_index("ix_declaraciones_productor_productor", table_name="declaraciones_productor")
    op.drop_table("declaraciones_productor")

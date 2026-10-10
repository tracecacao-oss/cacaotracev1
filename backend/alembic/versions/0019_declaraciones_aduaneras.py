"""Adenda 7: la declaración aduanera del lote con sus cuatro datos

- Tabla nueva `declaraciones_aduaneras`, con RLS y sin políticas: número, fecha de numeración, peso neto,
  subpartida, el archivo de tipo `dam` y si se cargó después del DEX. Como máximo una sin anular por lote.
- Trigger: no se borra y no se edita; solo se anula, una vez, con motivo.
- El tipo de documento `dam` ya existe desde la migración 0018. La migración no cambia ningún lote ni ningún
  DEX emitido.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-10

Regla: toda tabla nueva lleva ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY y ninguna política.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ANULACION = (
    "(anulada_en IS NULL) = (anulada_por IS NULL) AND (anulada_en IS NULL) = (motivo_anulacion IS NULL)"
)
FUNCION = """
CREATE FUNCTION declaraciones_aduaneras_fija() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Una declaración aduanera no se borra: se anula con motivo';
    END IF;
    IF OLD.anulada_en IS NOT NULL
       OR (to_jsonb(NEW) - 'anulada_en' - 'anulada_por' - 'motivo_anulacion')
          IS DISTINCT FROM (to_jsonb(OLD) - 'anulada_en' - 'anulada_por' - 'motivo_anulacion') THEN
        RAISE EXCEPTION 'Una declaración aduanera no se edita: se anula con motivo y se carga otra';
    END IF;
    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    op.create_table(
        "declaraciones_aduaneras",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("lote_id", sa.UUID(), nullable=False),
        sa.Column("documento_id", sa.UUID(), nullable=False),
        sa.Column("numero", sa.Text(), nullable=False),
        sa.Column("fecha_numeracion", sa.Date(), nullable=False),
        sa.Column("peso_neto_kg", sa.Numeric(10, 2), nullable=False),
        sa.Column("subpartida", sa.Text(), nullable=False),
        sa.Column("registrada_por", sa.UUID(), nullable=False),
        sa.Column(
            "registrada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("posterior_al_dex", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("anulada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anulada_por", sa.UUID(), nullable=True),
        sa.Column("motivo_anulacion", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "char_length(numero) BETWEEN 5 AND 30", name=op.f("ck_declaraciones_aduaneras_numero_valido")
        ),
        sa.CheckConstraint("peso_neto_kg > 0", name=op.f("ck_declaraciones_aduaneras_peso_positivo")),
        sa.CheckConstraint(
            "subpartida ~ '^[0-9]{4,10}$'", name=op.f("ck_declaraciones_aduaneras_subpartida_solo_digitos")
        ),
        sa.CheckConstraint(ANULACION, name=op.f("ck_declaraciones_aduaneras_anulacion_completa")),
        sa.ForeignKeyConstraint(
            ["lote_id"], ["lotes.id"], name=op.f("fk_declaraciones_aduaneras_lote_id_lotes")
        ),
        sa.ForeignKeyConstraint(
            ["documento_id"],
            ["documentos.id"],
            name=op.f("fk_declaraciones_aduaneras_documento_id_documentos"),
        ),
        sa.ForeignKeyConstraint(
            ["registrada_por"],
            ["perfiles.id"],
            name=op.f("fk_declaraciones_aduaneras_registrada_por_perfiles"),
        ),
        sa.ForeignKeyConstraint(
            ["anulada_por"], ["perfiles.id"], name=op.f("fk_declaraciones_aduaneras_anulada_por_perfiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_declaraciones_aduaneras")),
    )
    op.create_index(
        "uq_declaraciones_aduaneras_lote_vigente",
        "declaraciones_aduaneras",
        ["lote_id"],
        unique=True,
        postgresql_where=sa.text("anulada_en IS NULL"),
    )
    op.execute(FUNCION)
    op.execute(
        "CREATE TRIGGER tg_declaraciones_aduaneras_fija BEFORE UPDATE OR DELETE ON declaraciones_aduaneras "
        "FOR EACH ROW EXECUTE FUNCTION declaraciones_aduaneras_fija()"
    )
    op.execute("ALTER TABLE declaraciones_aduaneras ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TRIGGER tg_declaraciones_aduaneras_fija ON declaraciones_aduaneras")
    op.execute("DROP FUNCTION declaraciones_aduaneras_fija()")
    op.drop_index("uq_declaraciones_aduaneras_lote_vigente", table_name="declaraciones_aduaneras")
    op.drop_table("declaraciones_aduaneras")

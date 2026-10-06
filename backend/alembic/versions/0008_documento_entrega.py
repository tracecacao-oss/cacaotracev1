"""Adenda 3 de la Parte 5: documento de entrega en lugar de guía de remisión; tipo de organización

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-06 10:00:00

No se pierde ningún dato:
- Las cuatro columnas de la guía se renombran (gre_* -> doc_entrega_*) y las tandas existentes quedan con
  doc_entrega_tipo = 'guia_remision'.
- Los archivos de las guías se conservan: solo cambia el tipo del documento ('guia_remision' ->
  'documento_entrega'); la ruta en Storage y la huella no cambian.
- Los DOP ya emitidos no se tocan: su contenido está sellado.
- Las organizaciones ya creadas quedan como 'cooperativa_agraria'; el superadmin las revisa.

No hay tablas nuevas.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0008'
down_revision: str | Sequence[str] | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPOS_ORGANIZACION = "'cooperativa_agraria', 'asociacion', 'empresa'"
# El Comprobante de Operaciones de la Ley N.° 29972 queda fuera: esa ley está derogada (adenda 3, 12).
TIPOS_DOC_ENTREGA = "'guia_remision', 'liquidacion_compra'"
TIPOS_DOC_ANTES = (
    "'dni', 'constancia_ppa', 'sustento_midagri', 'archivo_geometria', 'titulo_sunarp', 'constancia_posesion', "
    "'cusaf', 'autorizacion_serfor', 'sunafil', 'sunat', 'zonificacion', 'foto_visita', 'respuesta_analisis', "
    "'guia_remision', 'dop_pdf', 'imagen_satelital', 'imagen_externa'"
)
TIPOS_DOC_AHORA = TIPOS_DOC_ANTES.replace("'guia_remision'", "'documento_entrega'")
COLUMNAS = (
    ("gre_numero", "doc_entrega_numero"),
    ("gre_fecha_emision", "doc_entrega_fecha_emision"),
    ("gre_ruc_emisor", "doc_entrega_ruc_emisor"),
    ("gre_peso_kg", "doc_entrega_peso_kg"),
)
RESTRICCIONES = (
    ("ck_tandas_gre_ruc_11_digitos", "ck_tandas_doc_entrega_ruc_11_digitos"),
    ("ck_tandas_gre_peso_positivo", "ck_tandas_doc_entrega_peso_positivo"),
)


def upgrade() -> None:
    # Tipo de organización (3): obligatorio; las ya creadas quedan como cooperativa agraria.
    op.add_column(
        "cooperativas",
        sa.Column("tipo_organizacion", sa.Text(), server_default="cooperativa_agraria", nullable=False),
    )
    op.alter_column("cooperativas", "tipo_organizacion", server_default=None)
    op.create_check_constraint(
        op.f("ck_cooperativas_tipo_organizacion_valido"),
        "cooperativas",
        f"tipo_organizacion IN ({TIPOS_ORGANIZACION})",
    )

    # Tandas (4): se renombran las columnas de la guía y se agrega el tipo del documento.
    for antes, ahora in COLUMNAS:
        op.alter_column("tandas", antes, new_column_name=ahora)
    for antes, ahora in RESTRICCIONES:
        op.execute(f"ALTER TABLE tandas RENAME CONSTRAINT {antes} TO {ahora}")
    op.execute("ALTER INDEX ix_tandas_guia RENAME TO ix_tandas_doc_entrega")
    op.add_column("tandas", sa.Column("doc_entrega_tipo", sa.Text(), nullable=True))
    op.execute("UPDATE tandas SET doc_entrega_tipo = 'guia_remision'")
    op.create_check_constraint(
        op.f("ck_tandas_doc_entrega_tipo_valido"),
        "tandas",
        f"doc_entrega_tipo IS NULL OR doc_entrega_tipo IN ({TIPOS_DOC_ENTREGA})",
    )

    # El archivo de la guía pasa a ser el documento de entrega; el archivo en Storage no cambia.
    op.drop_constraint(op.f("ck_documentos_tipo_valido"), "documentos", type_="check")
    op.execute("UPDATE documentos SET tipo = 'documento_entrega' WHERE tipo = 'guia_remision'")
    op.create_check_constraint(op.f("ck_documentos_tipo_valido"), "documentos", f"tipo IN ({TIPOS_DOC_AHORA})")

    # Plazo para emitir la liquidación de compra después de la recepción (5, regla 2).
    op.add_column(
        "configuracion_cooperativa",
        sa.Column("dias_max_emision_doc_entrega", sa.Integer(), server_default=sa.text("7"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_configuracion_cooperativa_dias_emision_no_negativos"),
        "configuracion_cooperativa",
        "dias_max_emision_doc_entrega >= 0",
    )


def downgrade() -> None:
    """Vuelve a la guía de remisión. Una tanda con liquidación de compra conserva sus datos en las columnas
    de la guía, pero pierde el tipo: revísela antes de bajar."""
    op.drop_constraint(
        op.f("ck_configuracion_cooperativa_dias_emision_no_negativos"), "configuracion_cooperativa", type_="check"
    )
    op.drop_column("configuracion_cooperativa", "dias_max_emision_doc_entrega")

    op.drop_constraint(op.f("ck_documentos_tipo_valido"), "documentos", type_="check")
    op.execute("UPDATE documentos SET tipo = 'guia_remision' WHERE tipo = 'documento_entrega'")
    op.create_check_constraint(op.f("ck_documentos_tipo_valido"), "documentos", f"tipo IN ({TIPOS_DOC_ANTES})")

    op.drop_constraint(op.f("ck_tandas_doc_entrega_tipo_valido"), "tandas", type_="check")
    op.drop_column("tandas", "doc_entrega_tipo")
    op.execute("ALTER INDEX ix_tandas_doc_entrega RENAME TO ix_tandas_guia")
    for antes, ahora in RESTRICCIONES:
        op.execute(f"ALTER TABLE tandas RENAME CONSTRAINT {ahora} TO {antes}")
    for antes, ahora in COLUMNAS:
        op.alter_column("tandas", ahora, new_column_name=antes)

    op.drop_constraint(op.f("ck_cooperativas_tipo_organizacion_valido"), "cooperativas", type_="check")
    op.drop_column("cooperativas", "tipo_organizacion")

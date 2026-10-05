"""Adenda de la Parte 4: MapBiomas Perú como tercera fuente del análisis de cobertura forestal.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-05

No crea tablas: solo amplía la restricción de `analisis_cobertura.fuente`.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOMBRE = "ck_analisis_cobertura_fuente_valida"


def upgrade() -> None:
    op.drop_constraint(op.f(NOMBRE), "analisis_cobertura", type_="check")
    op.create_check_constraint(op.f(NOMBRE), "analisis_cobertura", "fuente IN ('whisp', 'gfw', 'mapbiomas')")


def downgrade() -> None:
    op.execute("DELETE FROM analisis_cobertura WHERE fuente = 'mapbiomas'")
    op.drop_constraint(op.f(NOMBRE), "analisis_cobertura", type_="check")
    op.create_check_constraint(op.f(NOMBRE), "analisis_cobertura", "fuente IN ('whisp', 'gfw')")

"""Plantilla de proceso: la cooperativa puede desactivar las etapas que no usa, salvo las fijas

Decisión del equipo del 2026-10-06. Las fijas son las que llena el sistema (1, 3 y 4) y las que se usan al
consolidar (13, 17, 19 y 21); la base no deja desactivarlas.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-06
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0014'
down_revision: str | Sequence[str] | None = '0013'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'plantilla_proceso',
        sa.Column('activa', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )
    op.create_check_constraint(
        op.f('ck_plantilla_proceso_etapa_fija_activa'),
        'plantilla_proceso',
        'activa OR numero NOT IN (1, 3, 4, 13, 17, 19, 21)',
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_plantilla_proceso_etapa_fija_activa'), 'plantilla_proceso', type_='check')
    op.drop_column('plantilla_proceso', 'activa')

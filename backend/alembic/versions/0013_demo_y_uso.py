"""Parte 10: el DNI es único por dni y es_demo, para que un DNI ficticio nunca choque con uno real

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-06
"""
from collections.abc import Sequence

from alembic import op

revision: str = '0013'
down_revision: str | Sequence[str] | None = '0012'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint('uq_productores_dni', 'productores', type_='unique')
    op.create_unique_constraint('uq_productores_dni_es_demo', 'productores', ['dni', 'es_demo'])


def downgrade() -> None:
    op.drop_constraint('uq_productores_dni_es_demo', 'productores', type_='unique')
    op.create_unique_constraint('uq_productores_dni', 'productores', ['dni'])

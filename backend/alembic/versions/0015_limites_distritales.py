"""Límites distritales del INEI, para llenar la ubicación de una parcela desde sus coordenadas

Decisión del equipo del 2026-10-06. Carga los 1,890 distritos de app/datos/limites_distritales_inei.json.gz
(INEI, capa Distrital 2023, simplificada; ver scripts/preparar_limites_distritales.py).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-06
"""
import gzip
import json
from collections.abc import Sequence
from pathlib import Path

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = '0015'
down_revision: str | Sequence[str] | None = '0014'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ARCHIVO = Path(__file__).resolve().parents[2] / "app" / "datos" / "limites_distritales_inei.json.gz"


def upgrade() -> None:
    op.create_table(
        'limites_distritales',
        sa.Column('ubigeo', sa.String(length=6), nullable=False),
        sa.Column(
            'geometria',
            geoalchemy2.types.Geometry(geometry_type='MULTIPOLYGON', srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('ubigeo', name=op.f('pk_limites_distritales')),
    )
    op.create_index('idx_limites_distritales_geometria', 'limites_distritales', ['geometria'], postgresql_using='gist')
    op.execute('ALTER TABLE limites_distritales ENABLE ROW LEVEL SECURITY')
    datos = json.loads(gzip.decompress(ARCHIVO.read_bytes()))
    op.get_bind().execute(
        sa.text(
            "INSERT INTO limites_distritales (ubigeo, geometria) "
            "VALUES (:ubigeo, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geometria), 4326)))"
        ),
        [{"ubigeo": u, "geometria": json.dumps(g)} for u, g in datos["distritos"].items()],
    )


def downgrade() -> None:
    op.drop_index('idx_limites_distritales_geometria', table_name='limites_distritales', postgresql_using='gist')
    op.drop_table('limites_distritales')

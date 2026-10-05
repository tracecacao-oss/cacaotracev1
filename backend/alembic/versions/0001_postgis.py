"""Migración inicial: asegura PostGIS y bloquea la API de datos de Supabase sobre public.

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Si ya existe (panel de Supabase o imagen de Docker) no hace nada. Si falta, en Supabase
    # se crea en el esquema extensions, como recomienda su documentación, y nunca en public.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') THEN
                IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'extensions') THEN
                    CREATE EXTENSION postgis WITH SCHEMA extensions;
                ELSE
                    CREATE EXTENSION postgis;
                END IF;
            END IF;
        END
        $$;
        """
    )

    # alembic_version vive en public: sin RLS, la clave publicable podría leerla.
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")

    # Si PostGIS quedó instalado en public (imagen de Docker local), spatial_ref_sys también
    # queda expuesta. Se le activa RLS cuando el usuario de la API es su dueño.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'spatial_ref_sys'
                  AND tableowner = current_user
            ) THEN
                ALTER TABLE public.spatial_ref_sys ENABLE ROW LEVEL SECURITY;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # No se elimina PostGIS: otras tablas y la plataforma de Supabase dependen de él.
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")

"""Toda tabla de public debe tener RLS activo: sin políticas, la clave publicable no lee nada."""

from sqlalchemy import text

from app.db import engine


def test_todas_las_tablas_de_public_tienen_rls(base_disponible):
    with engine.connect() as conexion:
        tablas = dict(
            conexion.execute(
                text("SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public'")
            ).all()
        )
    assert "alembic_version" in tablas, "Faltan las migraciones: corre `alembic upgrade head`"
    sin_rls = sorted(nombre for nombre, activo in tablas.items() if not activo)
    assert sin_rls == [], f"Tablas de public sin RLS: {sin_rls}"


def test_ninguna_tabla_de_public_tiene_politicas(base_disponible):
    with engine.connect() as conexion:
        politicas = conexion.execute(
            text("SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public'")
        ).all()
    assert politicas == []

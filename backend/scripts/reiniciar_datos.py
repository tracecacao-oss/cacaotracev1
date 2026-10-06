"""Deja CacaoTrace completamente vacío: borra todos los datos, los archivos del bucket y los usuarios de
Supabase Auth, y conserva solo a los superadministradores (su perfil y su contraseña).

Borra cooperativas, usuarios, productores, parcelas, análisis, imágenes, tandas, DOP, corridas, DPP,
órdenes, lotes, DEX, certificaciones, configuración y auditoría. Los correlativos vuelven a empezar en 1.
La estructura de la base queda intacta, con sus protecciones: RLS en cada tabla y los triggers que impiden
editar o borrar los registros sellados. Se vacía con TRUNCATE, que no pasa por esos triggers de fila (son
de UPDATE y DELETE), y nunca los desactiva. No siembra ningún dato.

Lo corre una persona del equipo desde backend/, con las variables reales cargadas en su terminal
(DATABASE_URL, SUPABASE_URL y SUPABASE_SECRET_KEY), nunca guardadas en un archivo:

    python scripts/reiniciar_datos.py --simular    # solo muestra lo que borraría
    python scripts/reiniciar_datos.py              # muestra, pide la palabra de confirmación y borra

Primero vacía la base, en una sola transacción; después el bucket y después Supabase Auth. Si algo falla a
mitad de camino, se puede volver a correr: la base ya vacía no cambia y se borra lo que haya quedado.
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import Connection, func, insert, select, text  # noqa: E402

from app.auth_admin import ErrorAuthAdmin, crear_auth_admin  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.models import Base, Perfil  # noqa: E402
from app.storage import ErrorStorage, crear_storage  # noqa: E402

PALABRA = "VACIAR"
LOTE_ARCHIVOS = 100
PERFILES = Perfil.__table__


def tablas() -> list:
    """Las tablas del modelo (no toca spatial_ref_sys de PostGIS ni alembic_version)."""
    return list(Base.metadata.sorted_tables)


def contar(conexion: Connection) -> dict[str, int]:
    return {t.name: conexion.scalar(select(func.count()).select_from(t)) for t in tablas()}


def superadmins(conexion: Connection) -> list[dict]:
    consulta = select(PERFILES).where(PERFILES.c.rol == "superadmin").order_by(PERFILES.c.correo)
    filas = conexion.execute(consulta)
    return [dict(f._mapping) for f in filas]


def protecciones(conexion: Connection) -> tuple[int, int]:
    """(tablas del modelo sin RLS, triggers propios en esas tablas)."""
    nombres = [t.name for t in tablas()]
    sin_rls = conexion.scalar(
        text(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(:nombres) AND NOT c.relrowsecurity"
        ),
        {"nombres": nombres},
    )
    triggers = conexion.scalar(
        text(
            "SELECT count(*) FROM pg_trigger g JOIN pg_class c ON c.oid = g.tgrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(:nombres) AND NOT g.tgisinternal"
        ),
        {"nombres": nombres},
    )
    return sin_rls, triggers


def vaciar_base(conexion: Connection, conservar: list[dict]) -> None:
    """Vacía todas las tablas en un solo TRUNCATE (reinicia sus secuencias) y vuelve a insertar los perfiles
    de superadministrador tal como estaban. Corre dentro de la transacción de quien llama."""
    conexion.execute(text("SET LOCAL lock_timeout = '30s'"))
    nombres = ", ".join(f'"{t.name}"' for t in tablas())
    conexion.execute(text(f"TRUNCATE {nombres} RESTART IDENTITY"))
    ids = {p["id"] for p in conservar}
    for perfil in conservar:
        # creado_por apuntaría a un perfil borrado si no es otro superadministrador.
        fila = perfil | {"creado_por": perfil["creado_por"] if perfil["creado_por"] in ids else None}
        conexion.execute(insert(PERFILES).values(**fila))


def _tamano(total: int) -> str:
    return f"{total / 1024 / 1024:,.1f} MB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--simular", action="store_true", help="solo muestra lo que borraría")
    args = parser.parse_args()

    settings = get_settings()
    if settings.supabase_secret_key is None:
        print("Falta SUPABASE_SECRET_KEY en el entorno.")
        return 2
    from app.db import engine  # después de leer la configuración

    storage = crear_storage(settings)
    auth = crear_auth_admin(settings)
    destino = urlsplit(settings.database_url.replace("+psycopg", ""))
    print(f"Base de datos: {destino.hostname}  ·  Supabase: {settings.supabase_url}")
    print(f"Bucket: {settings.storage_bucket}")
    print()

    with engine.connect() as conexion:
        conteos = contar(conexion)
        conservar = superadmins(conexion)
        sin_rls, triggers = protecciones(conexion)
    try:
        archivos = storage.listar()
        usuarios = auth.listar_usuarios()
    except (ErrorStorage, ErrorAuthAdmin) as exc:
        print(f"FALLA al leer Supabase: {exc}")
        return 1
    ids = {p["id"] for p in conservar}
    a_borrar_auth = [u for u in usuarios if u["id"] not in ids]
    en_auth = {u["id"] for u in usuarios}

    print("Registros que se borran:")
    for tabla, n in sorted(conteos.items()):
        if n and tabla != "perfiles":
            print(f"  {tabla:<32} {n:>8}")
    print(f"  {'perfiles (sin superadministradores)':<32} {conteos.get('perfiles', 0) - len(conservar):>8}")
    print(f"  {'TOTAL':<32} {sum(conteos.values()) - len(conservar):>8}")
    print()
    total = sum(t or 0 for _, t in archivos)
    print(f"Archivos del bucket que se borran: {len(archivos)} ({_tamano(total)})")
    print(f"Usuarios de Supabase Auth que se borran: {len(a_borrar_auth)}")
    print()
    print("Superadministradores que se conservan (perfil y contraseña):")
    if not conservar:
        print("  NINGUNO. Sin un superadministrador nadie podrá entrar a crear cooperativas.")
    for p in conservar:
        aviso = "" if p["id"] in en_auth else "   <- no tiene usuario en Supabase Auth"
        print(f"  {p['nombres']} {p['apellidos']} · {p['correo']}{aviso}")
    print()
    print(f"Protecciones antes de empezar: {triggers} triggers; tablas sin RLS: {sin_rls}.")
    print()

    if args.simular:
        print("Simulación: no se borró nada.")
        return 0
    if not conservar:
        print("No se borra nada sin un superadministrador que conservar.")
        return 1
    respuesta = input(f"Esto no se puede deshacer. Escribe {PALABRA} para borrar todo: ")
    if respuesta.strip() != PALABRA:
        print("No se borró nada.")
        return 1

    with engine.begin() as conexion:
        vaciar_base(conexion, conservar)
    print("Base de datos vacía; superadministradores conservados.")

    try:
        for i in range(0, len(archivos), LOTE_ARCHIVOS):
            storage.borrar_varios([ruta for ruta, _ in archivos[i : i + LOTE_ARCHIVOS]])
        print(f"Bucket vacío: {len(archivos)} archivos borrados.")
        for u in a_borrar_auth:
            auth.borrar_usuario(u["id"])
        print(f"Supabase Auth: {len(a_borrar_auth)} usuarios borrados.")
    except (ErrorStorage, ErrorAuthAdmin) as exc:
        print(f"FALLA a mitad de camino: {exc}. Vuelve a correr el script para terminar.")
        return 1

    with engine.connect() as conexion:
        restantes = sum(contar(conexion).values()) - len(conservar)
        sin_rls_despues, triggers_despues = protecciones(conexion)
    print()
    print(f"Registros que quedan fuera de los superadministradores: {restantes}")
    print(f"Protecciones después: {triggers_despues} triggers; tablas sin RLS: {sin_rls_despues}.")
    if restantes or triggers_despues != triggers or sin_rls_despues:
        print("REVISAR: algo no quedó como se esperaba.")
        return 1
    print("Listo. El sistema está vacío.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

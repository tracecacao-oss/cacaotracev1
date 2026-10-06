"""Descarga el bucket de documentos completo a una carpeta local: la copia de respaldo de los archivos.

Lo corre una persona del equipo cada semana y antes de cada demo, desde backend/, con las variables reales
cargadas en su terminal (DATABASE_URL, SUPABASE_URL y SUPABASE_SECRET_KEY), nunca guardadas en un archivo:

    python scripts/respaldar_storage.py --destino D:/respaldos/cacaotrace/archivos

Un archivo que ya está en la carpeta con el mismo tamaño no se vuelve a bajar: en Storage nada se edita,
cada carga es un archivo nuevo, así que la misma carpeta sirve para todas las copias. Si algo falla, se
vuelve a correr y baja solo lo que falte. La copia contiene datos personales: va fuera del repositorio
(el script se niega a escribir dentro de él), en un lugar con acceso restringido.

La base de datos se respalda aparte con pg_dump 17, la versión de Postgres del proyecto, usando la
cadena del "Session pooler" del panel de Supabase (Connect), que acepta pg_dump:

    pg_dump -Fc --schema=public --no-owner --no-privileges -f cacaotrace-AAAA-MM-DD.dump "<cadena>"

Ensayo de restauración en el Postgres local (docker compose up -d). En Supabase, PostGIS vive en el
esquema extensions, así que la base restaurada lo necesita ahí mismo. Con PGHOST=localhost y
PGUSER=postgres en la terminal:

    createdb restaurada
    psql -d restaurada -c "CREATE SCHEMA extensions"
    psql -d restaurada -c "CREATE EXTENSION postgis WITH SCHEMA extensions"
    psql -d restaurada -c "ALTER DATABASE restaurada SET search_path = public, extensions"
    pg_restore -d restaurada --clean --if-exists --no-owner --no-privileges cacaotrace-AAAA-MM-DD.dump

Después, con DATABASE_URL=postgresql://postgres:postgres@localhost:5432/restaurada,
`alembic current` muestra la última migración y la API arranca contra esa base.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.storage import ClienteStorage, ErrorStorage, crear_storage  # noqa: E402

REPOSITORIO = Path(__file__).resolve().parents[2]


def _dentro(ruta: Path, carpeta: Path) -> bool:
    try:
        ruta.relative_to(carpeta)
    except ValueError:
        return False
    return True


def respaldar(storage: ClienteStorage, destino: Path) -> tuple[int, int, int, list[str]]:
    """Baja lo que falte. Devuelve (archivos bajados, bytes bajados, archivos que ya estaban, fallidos)."""
    bajados = bytes_bajados = ya_estaban = 0
    fallidos: list[str] = []
    for ruta, tamano in storage.listar():
        local = (destino / ruta).resolve()
        if not _dentro(local, destino):
            fallidos.append(ruta)  # una ruta con ".." nunca escribe fuera de la carpeta
            continue
        if local.is_file() and (tamano is None or local.stat().st_size == tamano):
            ya_estaban += 1
            continue
        try:
            contenido = storage.descargar(ruta)
        except ErrorStorage:
            fallidos.append(ruta)
            continue
        local.parent.mkdir(parents=True, exist_ok=True)
        # Se escribe aparte y se renombra: un corte a mitad nunca deja un archivo incompleto con su nombre.
        parcial = local.with_name(local.name + ".parcial")
        parcial.write_bytes(contenido)
        os.replace(parcial, local)
        bajados += 1
        bytes_bajados += len(contenido)
    return bajados, bytes_bajados, ya_estaban, fallidos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destino", required=True, type=Path, help="carpeta local, fuera del repositorio")
    args = parser.parse_args()

    destino = args.destino.expanduser().resolve()
    if _dentro(destino, REPOSITORIO):
        print("La copia tiene datos personales y el repositorio es público: elige una carpeta fuera de él.")
        return 2
    settings = get_settings()
    storage = crear_storage(settings)
    if storage is None:
        print("Falta SUPABASE_SECRET_KEY en el entorno.")
        return 2
    destino.mkdir(parents=True, exist_ok=True)
    print(f"Supabase: {settings.supabase_url}  ·  bucket: {settings.storage_bucket}")
    print(f"Destino: {destino}")

    try:
        bajados, bytes_bajados, ya_estaban, fallidos = respaldar(storage, destino)
    except ErrorStorage as exc:
        print(f"FALLA al listar el bucket: {exc}")
        return 1
    print(f"Archivos bajados: {bajados} ({bytes_bajados / 1024 / 1024:,.1f} MB). Ya estaban: {ya_estaban}.")
    if fallidos:
        print(f"No se pudieron bajar {len(fallidos)} archivos:")
        for ruta in fallidos[:20]:
            print(f"  {ruta}")
        print("Vuelve a correr el script: baja solo lo que falte.")
        return 1
    print("Listo. La copia de los archivos está completa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

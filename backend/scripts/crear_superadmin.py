"""Crea el superadministrador de CacaoTrace, o le restablece la contraseña.

Lo corre una persona del equipo desde backend/, con las variables reales cargadas en su
terminal (DATABASE_URL, SUPABASE_URL y SUPABASE_SECRET_KEY), nunca guardadas en un archivo:

    python scripts/crear_superadmin.py --correo persona@dominio --nombres "..." --apellidos "..."
    python scripts/crear_superadmin.py --restablecer --correo persona@dominio

La contraseña temporal se muestra una sola vez; en el primer ingreso se exige cambiarla.
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.auth_admin import CorreoEnUso, ErrorAuthAdmin, crear_auth_admin  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SesionLocal  # noqa: E402
from app.models import Perfil  # noqa: E402
from app.services.auditoria import registrar_auditoria  # noqa: E402
from app.services.cuentas import generar_clave_temporal  # noqa: E402

DETALLE = {"rol": "superadmin", "origen": "script"}


def crear(correo: str, nombres: str, apellidos: str) -> int:
    auth = crear_auth_admin(get_settings())
    with SesionLocal() as sesion:
        if sesion.scalar(select(Perfil.id).where(func.lower(Perfil.correo) == correo)):
            print("Ya existe un usuario con ese correo. Usa --restablecer si olvidó su contraseña.")
            return 1
        clave = generar_clave_temporal()
        try:
            usuario_id = auth.crear_usuario(correo, clave)
        except CorreoEnUso:
            print("Ese correo ya existe en Supabase Auth, sin perfil en CacaoTrace. Revísalo en el panel.")
            return 1
        try:
            sesion.add(
                Perfil(id=usuario_id, rol="superadmin", nombres=nombres, apellidos=apellidos, correo=correo)
            )
            sesion.flush()
            registrar_auditoria(None, "usuario.crear", "usuario", usuario_id, DETALLE, sesion=sesion)
            sesion.commit()
        except Exception:
            sesion.rollback()
            auth.borrar_usuario(usuario_id)
            raise
    _mostrar(correo, clave)
    return 0


def restablecer(correo: str) -> int:
    auth = crear_auth_admin(get_settings())
    with SesionLocal() as sesion:
        perfil = sesion.scalar(
            select(Perfil).where(func.lower(Perfil.correo) == correo, Perfil.rol == "superadmin")
        )
        if perfil is None:
            print("No hay un superadministrador con ese correo.")
            return 1
        clave = generar_clave_temporal()
        auth.cambiar_clave(perfil.id, clave)
        perfil.debe_cambiar_clave = True
        registrar_auditoria(None, "usuario.restablecer_clave", "usuario", perfil.id, DETALLE, sesion=sesion)
        sesion.commit()
    _mostrar(correo, clave)
    return 0


def _mostrar(correo: str, clave: str) -> None:
    print()
    print(f"  Correo:               {correo}")
    print(f"  Contraseña temporal:  {clave}")
    print()
    print("  Cópiala ahora: no se guarda en ningún lado y no volverá a mostrarse.")
    print("  En el primer ingreso se pedirá cambiarla.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--correo", required=True)
    parser.add_argument("--nombres")
    parser.add_argument("--apellidos")
    parser.add_argument("--restablecer", action="store_true", help="nueva contraseña temporal")
    args = parser.parse_args()

    settings = get_settings()
    if settings.supabase_secret_key is None:
        print("Falta SUPABASE_SECRET_KEY en el entorno.")
        return 2
    destino = urlsplit(settings.database_url.replace("+psycopg", ""))
    print(f"Base de datos: {destino.hostname}  ·  Supabase: {settings.supabase_url}")

    correo = args.correo.strip().lower()
    try:
        if args.restablecer:
            return restablecer(correo)
        if not (args.nombres and args.apellidos):
            parser.error("--nombres y --apellidos son obligatorios al crear")
        return crear(correo, args.nombres.strip(), args.apellidos.strip())
    except ErrorAuthAdmin as exc:
        print(f"FALLA en Supabase Auth: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

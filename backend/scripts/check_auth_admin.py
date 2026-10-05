"""Diagnóstico de la API de administración de Supabase Auth con el correo técnico del productor.

Comprueba en el proyecto real que Supabase acepta <dni>@productores.cacaotrace.local: crea un
usuario de prueba ya confirmado, inicia sesión con él, lo bloquea y desbloquea, y lo borra.
No toca la base de datos de CacaoTrace.

Lo corre una persona con las variables reales cargadas en su terminal, desde backend/:

    python scripts/check_auth_admin.py

Variables: SUPABASE_URL, SUPABASE_SECRET_KEY y, opcional, PRODUCTOR_EMAIL_DOMAIN.
"""

import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth_admin import ClienteAuthAdmin, ErrorAuthAdmin  # noqa: E402
from app.services.cuentas import generar_clave_temporal  # noqa: E402


def paso(texto: str) -> None:
    print(f"  · {texto}...", end=" ", flush=True)


def main() -> int:
    faltan = [v for v in ("SUPABASE_URL", "SUPABASE_SECRET_KEY") if not os.environ.get(v)]
    if faltan:
        print(f"Faltan variables de entorno: {', '.join(faltan)}")
        return 2

    dominio = os.environ.get("PRODUCTOR_EMAIL_DOMAIN", "productores.cacaotrace.local")
    # DNI ficticio de prueba: 99 seguido de 6 dígitos al azar.
    correo = f"99{secrets.randbelow(10**6):06d}@{dominio}"
    clave = generar_clave_temporal()
    auth = ClienteAuthAdmin(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    usuario_id = None

    print(f"Diagnóstico de Supabase Auth con el correo técnico {correo}")
    try:
        paso("Creando usuario confirmado")
        usuario_id = auth.crear_usuario(correo, clave)
        print("ok")

        paso("Iniciando sesión con la contraseña")
        if not auth.verificar_clave(correo, clave):
            print("FALLA: Supabase no aceptó la contraseña recién creada")
            return 1
        print("ok")

        paso("Bloqueando y desbloqueando")
        auth.bloquear(usuario_id)
        auth.desbloquear(usuario_id)
        print("ok")

        paso("Borrando usuario de prueba")
        auth.borrar_usuario(usuario_id)
        usuario_id = None
        print("ok")
    except ErrorAuthAdmin as exc:
        print(f"FALLA: {exc}")
        print(
            "Si el error es de correo inválido, Supabase rechaza el dominio: avisa al equipo antes de seguir."
        )
        return 1
    finally:
        if usuario_id is not None:
            try:
                auth.borrar_usuario(usuario_id)
            except ErrorAuthAdmin:
                print(f"  ! No se pudo borrar {correo}; bórralo a mano en Authentication > Users")

    print(f"Supabase Auth acepta el dominio {dominio} para el ingreso del productor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

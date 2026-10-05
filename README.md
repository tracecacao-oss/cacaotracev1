# CacaoTrace

Trazabilidad de cacao para cooperativas, pensada para el Reglamento (UE) 2023/1115 (EUDR).
La especificación completa está en [`docs/especificacion.md`](docs/especificacion.md).

| Pieza | Servicio | Carpeta |
| --- | --- | --- |
| Interfaz (HTML, CSS y JS sin compilación) | Cloudflare Pages | `frontend/` |
| API (Python 3.12, FastAPI) | Render | `backend/` |
| Base de datos, autenticación y archivos | Supabase (Postgres + PostGIS, Auth, Storage) | — |

El MVP anterior está en `legacy/` solo como referencia; no se despliega.

## Levantar el proyecto en local

Requisitos: Python 3.12, Docker y un usuario de prueba en el proyecto de Supabase.

```bash
# 1. Base de datos: Postgres con PostGIS
docker compose up -d

# 2. API, desde backend/
cd backend
cp .env.example .env          # completar SUPABASE_URL (y SUPABASE_SECRET_KEY si se usará Storage)
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload # http://localhost:8000, documentación en /docs

# 3. Interfaz, desde la raíz del repositorio
python -m http.server 5500 --directory frontend   # http://localhost:5500
```

En `localhost`, `frontend/config.js` apunta la API a `http://localhost:8000`. El inicio de sesión
usa el proyecto real de Supabase, así que `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` deben estar
completos en `frontend/config.js`.

## Pruebas

```bash
cd backend
ruff check .
pytest
```

Las pruebas corren contra el Postgres de Docker y nunca contra Supabase; ninguna sale a internet.
Si Docker no está arriba, las que necesitan base de datos se saltan en local. En CI son obligatorias.

## Diagnóstico de Storage

Con las variables reales cargadas en la terminal (nunca en un archivo del repositorio):

```bash
cd backend
python scripts/check_storage.py
```

Sube un archivo de prueba al bucket `documentos`, lo firma, lo descarga, compara el contenido,
comprueba que el bucket sea privado y lo borra.

## Cuentas: superadministrador y diagnóstico de Supabase Auth

Ninguna cuenta nace por registro abierto. El primer superadministrador lo crea una persona del
equipo con las variables reales (`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`) en su terminal:

```bash
cd backend
python scripts/crear_superadmin.py --correo persona@dominio --nombres "Nombre" --apellidos "Apellido"
python scripts/crear_superadmin.py --restablecer --correo persona@dominio
```

La contraseña temporal se muestra una sola vez y se cambia en el primer ingreso.

Para comprobar que Supabase acepta el correo técnico del productor (`<dni>@productores.cacaotrace.local`):

```bash
cd backend
python scripts/check_auth_admin.py
```

Crea un usuario de prueba ya confirmado, inicia sesión con él, lo bloquea, lo desbloquea y lo borra.

## Deploy

Cada merge a `main` se publica solo: Render reconstruye la API desde `render.yaml` y Cloudflare
Pages publica `frontend/`. Los secretos se cargan a mano en el panel de Render; ver la sección
"Variables de entorno y secretos" de la especificación.

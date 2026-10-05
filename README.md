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

## Mapa satelital

El mapa usa Leaflet 1.9.4 y Leaflet-Geoman 2.20.2 desde CDN, con calles de OpenStreetMap y la
capa satelital de **Esri World Imagery** (ArcGIS Location Platform, elegida por el equipo).

La capa satelital se activa al poner en `frontend/config.js` (`ESRI_API_KEY`) una clave pública de
ArcGIS Location Platform. La crea una persona del equipo:

1. Cuenta en ArcGIS Location Platform (plan gratuito: 2 millones de teselas al mes).
2. Clave de API con el permiso *Basemaps → Static basemap tiles*, restringida por referrer a
   `https://cacaotrace.pages.dev` (y al dominio propio cuando exista).
3. La clave dura como máximo un año: renovarla antes de que venza.

Condiciones de uso: mostrar la atribución de Esri (el mapa ya la muestra), no descargar teselas
para uso sin conexión, y no usar el servicio sin clave (`server.arcgisonline.com`).

## Parcelas y carga masiva

La parcela se dibuja en el mapa, se sube como archivo (GeoJSON, KML, KMZ o Shapefile comprimido en
.zip) o se escribe como lista de coordenadas en grados (también en .txt, .csv o .xlsx). Todo en
WGS 84: UTM se rechaza con un mensaje que pide grados. El padrón de productores se puede cargar
desde un Excel o CSV en Productores → Carga masiva, que revisa cada fila antes de guardar.

## Catálogo de ubicaciones

Departamento, provincia y distrito se eligen de listas encadenadas con el catálogo oficial del
INEI: `backend/app/datos/ubigeo_inei.csv` (código INEI y los tres nombres, 1891 distritos). Sale
del archivo "UBIGEO 2022_1891 distritos.xlsx" del conjunto *Ubigeos - Instituto Nacional de
Estadística e Informática* en [datosabiertos.gob.pe](https://www.datosabiertos.gob.pe). La API lo
sirve en `GET /ubigeos` y rechaza con `ubigeo_invalido` una combinación que no existe. Si el INEI
publica una versión nueva, se reemplaza el CSV con las mismas columnas y se corren las pruebas.

## Habilitación de la parcela: cobertura forestal

Cada parcela se analiza con dos fuentes, cada una con su fecha y su versión, sin combinarlas:

| Fuente | Variable en Render | Notas |
| --- | --- | --- |
| Whisp (FAO), `whisp.openforis.org` | `WHISP_API_KEY` | Riesgo para cultivos permanentes (`risk_pcrop`) e indicadores |
| GFW Data API, `data-api.globalforestwatch.org` | `GFW_API_KEY` | Alertas integradas y pérdida de cobertura desde 2021 (densidad 2000 > 30 %) |

- **La clave de GFW vence al año de creada.** La actual (alias `cacaotrace`) se creó el
  2026-10-05: **vence el 2027-10-05**. Renovarla antes y reemplazarla en Render.
- Sin una clave, esa fuente no crea análisis y la interfaz muestra "Fuente no configurada".
- El análisis corre en segundo plano dentro de la API: hasta 3 intentos por fuente, 20 consultas
  por minuto y 60 segundos de espera máxima. La respuesta completa se guarda en Storage antes de
  interpretarla; si no se puede interpretar, el análisis queda sin resultado y pide revisión en campo.
- En el mapa de la parcela se pueden encender, solo como referencia visual, Geobosques (MINAM),
  la zonificación forestal de GeoSERFOR y el mapa de bosque 2020 del JRC.

Para guardar respuestas reales de prueba en `backend/tests/datos/` con una parcela ficticia, una
persona del equipo corre `python scripts/muestras_cobertura.py` desde `backend/` y pega las claves
cuando se las pide (no se guardan en ningún archivo). También sirve descargar, desde la pestaña
Cobertura forestal de una parcela ficticia en producción, "Descargar la respuesta completa".

## Deploy

Cada merge a `main` se publica solo: Render reconstruye la API desde `render.yaml` y Cloudflare
Pages publica `frontend/`. Los secretos se cargan a mano en el panel de Render; ver la sección
"Variables de entorno y secretos" de la especificación.

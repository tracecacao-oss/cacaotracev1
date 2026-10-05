# CacaoTrace — instrucciones para Claude Code

**Especificación:** `docs/especificacion.md` es la única fuente de verdad. Lo que no está ahí no se construye sin preguntar.

**Parte en curso:** 3 — Productor y parcela. Diseño de referencia en `legacy/diseno/`: solo colores, tipografías, espaciados y estilo de componentes; manda la especificación.

## Reglas de trabajo

1. Construir parte por parte, en el orden del mapa de partes. No empezar una parte sin cumplir los criterios de aceptación de la anterior.
2. Ante un vacío o una ambigüedad, detenerse y preguntar. No inventar requisitos, datos regulatorios, integraciones ni datos de ejemplo que parezcan reales.
3. Los nombres de variables, rutas, carpetas y servicios de la especificación son literales. Cambiarlos requiere aprobación.
4. Antes de usar un servicio o una librería, revisar su documentación vigente.
5. Ningún secreto entra al repositorio (es público). Las claves viven solo en los paneles de Render, Supabase y Cloudflare.
6. Cada parte termina con pruebas en verde, un commit descriptivo y el deploy verificado en producción.
7. Toda acción con costo la ejecuta una persona del equipo, nunca Claude Code.
8. Trabajo en ramas `feat/parte-<n>-<tema>`; `main` solo recibe pull requests con CI en verde.
9. Toda tabla nueva: migración de Alembic con `ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY` y ninguna política.
10. El navegador solo habla con Supabase Auth y con la API. Todo permiso se decide en la API.

## Comandos

```bash
docker compose up -d                                   # Postgres + PostGIS local
cd backend && cp .env.example .env                     # luego completar SUPABASE_URL
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # en Linux/macOS: .venv/bin/pip
alembic upgrade head                                   # migraciones
alembic revision -m "descripcion"                      # nueva migración
uvicorn app.main:app --reload                          # API en http://localhost:8000
ruff check . && pytest                                 # lint y pruebas
python -m http.server 5500 --directory frontend        # interfaz (desde la raíz)
```

Las pruebas que necesitan Postgres se saltan en local si Docker no está arriba; en CI son obligatorias.
Las pruebas nunca llaman a Supabase: el Auth admin se simula con `AuthFalso` (tests/conftest.py) y cada prueba corre en una transacción que se revierte.

## Convenciones del código

- Permisos: `requiere_rol(...)` en el router; la cooperativa siempre de `obtener_contexto`, nunca del cuerpo, la ruta o la query.
- Servicios en `app/services/` reciben el `Contexto` como primer parámetro y auditan con `registrar_auditoria` en la misma transacción.
- Errores con `error_api(estado, codigo, mensaje)`; mensajes en español, listos para mostrar.
- Interfaz: `frontend/js/api.js` es el único que llama a `fetch`; pantallas en `frontend/js/pantallas/`; textos de usuario con `textContent`, nunca HTML.
- Geometría: validaciones solo en `backend/app/services/geometria.py`; la interfaz valida lo dibujado enviándolo a `POST /parcelas/analizar-archivo`. Mapas con `frontend/js/mapa.js` (Leaflet + Geoman con SRI; satélite Esri solo con `ESRI_API_KEY`).
- Archivos: siempre por la API a Storage (`documentos.cargar`), nunca directo desde el navegador.
- Ubicación (departamento, provincia, distrito): del catálogo oficial del INEI en `backend/app/datos/ubigeo_inei.csv`. Los servicios llaman `ubigeo.normalizar(valores, actual)` y guardan los nombres del INEI; la interfaz usa `camposUbigeo()` de `frontend/js/ubigeo.js`, que lee `GET /ubigeos`. Las Partes 5 en adelante (`lugares`) hacen lo mismo.

## Producción

| Pieza | Dónde |
| --- | --- |
| Interfaz | https://cacaotrace.pages.dev (Cloudflare Pages publica `frontend/` en cada merge a `main`) |
| API | https://cacaotrace-api.onrender.com (Render redespliega solo cuando el merge toca `backend/`) |
| Supabase | https://fbntvwuirklffsohrqoo.supabase.co (tokens ES256 por JWKS; registro público desactivado) |

La base `cacaotrace-db` de Render es del MVP anterior: no se usa y el equipo la borra.

## Estado por parte

| Parte | Estado |
| --- | --- |
| 1 Infraestructura y despliegue | Cerrada el 2026-10-04: diez criterios de aceptación verificados en producción |
| 2 Acceso y base | Cerrada el 2026-10-05: criterios 1-11 probados por el equipo en producción; 12 (CI) con este cierre |
| 3 Productor y parcela | En construcción. Decidido por el equipo el 2026-10-05: ubicación desde el catálogo oficial del INEI; "Código productor APP" = código del productor en Agro Digital (app del MIDAGRI) |

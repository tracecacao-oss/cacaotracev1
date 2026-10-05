# CacaoTrace — instrucciones para Claude Code

**Especificación:** `docs/especificacion.md` es la única fuente de verdad. Lo que no está ahí no se construye sin preguntar.

**Parte en curso:** 1 — Infraestructura y despliegue (rama `feat/parte-1-infraestructura`).

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

## Estado por parte

| Parte | Estado |
| --- | --- |
| 1 Infraestructura y despliegue | En construcción |

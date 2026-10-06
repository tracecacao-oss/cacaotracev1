# CacaoTrace — instrucciones para Claude Code

**Especificación:** `docs/especificacion.md` es la única fuente de verdad, junto con sus adendas en `docs/` (por ejemplo `docs/adenda-parte-4-fuentes.md` y `docs/adenda-2-parte-4-revision-imagenes.md`, que mandan sobre la Parte 4 donde difieran, con la adenda 2 sobre la primera; y `docs/adenda-3-parte-5-documento-entrega.md`, que manda sobre la Parte 5). Lo que no está ahí no se construye sin preguntar.

**Parte en curso:** 6 — Proceso y DPP. Al empezarla, revisar en el estado de las Partes 5 y 4 (adenda 2) lo que quedó sin probar en producción: todavía no se emitió ningún DOP real, así que el PDF (fpdf2), ahora con las imágenes de la parcela, nunca se generó en Render, y ninguna parcela de producción generó imágenes de Copernicus todavía.

**Diseño:** la interfaz debe parecerse en su mayoría a `legacy/diseno/` (decisión del 2026-10-05): sus colores, tipografías, componentes y composición (barra superior con la ruta, inspector en las fichas, tarjetas, tablas, modo oscuro). Si choca con la especificación en navegación, nombres de módulos, una tarea por pantalla o un botón principal, manda la especificación. Del diseño nunca se copian textos, datos de ejemplo ni lógica.

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
- Piezas del diseño en `frontend/js/ui.js`: `cabeceraFicha`, `seccion` y `rejilla` para fichas (la vista pasa `cabecera: null`), `avatar`, `buscador`, `toast`; íconos del diseño en `iconos.js`. Cada vista del layout lleva `titulo`, `migas` y, si aplica, `antetitulo`, `descripcion`, `accion` y `secciones`.
- Geometría: lectura y validaciones solo en `backend/app/services/geometria.py` (GeoJSON, KML, KMZ, Shapefile en .zip) y `coordenadas.py` (listas en texto, CSV o Excel; hojas con `tablas.py`); la interfaz valida lo dibujado enviándolo a `POST /parcelas/analizar-archivo`. Mapas con `frontend/js/mapa.js` (Leaflet + Geoman con SRI; satélite Esri solo con `ESRI_API_KEY`).
- Archivos: siempre por la API a Storage (`documentos.cargar`), nunca directo desde el navegador.
- Parte 4: fuentes de cobertura en `app/services/fuentes/` (protocolo `Fuente`; `registro.construir` las arma desde la configuración), cola en `analisis.procesar_siguiente` con el hilo de `app/trabajador.py`; las pruebas las simulan con `httpx.MockTransport` (`tests/habilitacion_util.py`). Fechas de Lima con `app/fechas.py`. Solo `services/habilitacion.py` cambia `habilitacion_estado`. En la interfaz, las pestañas de la parcela están en `pantallas/parcela-habilitacion.js`. Adenda: catálogos de capas y conjuntos en `app/catalogos/` (`capas_whisp.py`, `conjuntos_datos.py`, `mapbiomas_peru_c3.py`); la tabla de convergencia solo cuenta, en `services/convergencia.py`; MapBiomas lee GeoTIFF por rangos con `fuentes/cog.py` (sin GDAL), y sus pruebas usan GeoTIFF sintéticos de `tests/geotiff_util.py`.
- Parte 5: la tanda se evalúa en `services/tandas.py` (`evaluar` da requisitos, alertas y su detalle) y solo `validar` emite el DOP, en la misma transacción, con `services/dops.py`. La forma canónica y la huella salen solo de `services/sello.py`. Los PDF se arman con fpdf2 en `app/pdf/` (`base.py` para todos; el DOP en `dop.py`), con las fuentes OFL de `app/recursos/fuentes/` y el QR de segno dibujado con rectángulos. Códigos correlativos con `services/correlativos.py`. Lo público va en `routers/publico.py` con el límite por IP de `app/limite.py`. En la interfaz, campos, requisitos, alertas, huella, QR y descarga del PDF están en `frontend/js/tandas.js`; la verificación pública (`#/verificar/dop/{codigo}`) la atiende el router antes de mirar la sesión.
- Adenda 2 de la Parte 4 (`docs/adenda-2-parte-4-revision-imagenes.md`): imágenes de la parcela en `services/imagenes.py` (selección de escenas, cola en el mismo hilo, cuota y bloque del DOP) con los clientes `services/sentinel.py` (Copernicus) y `services/wayback.py` (Esri Wayback, sin clave y sin guardar sus imágenes); revisiones en `services/revisiones_imagenes.py`. Solo una parcela con la alerta `analisis_requiere_revision` genera imágenes, y solo una revisión de imágenes vigente atiende esa alerta: las visitas ya no se registran. Las pruebas simulan Copernicus y Wayback con `tests/imagenes_util.py`. En la interfaz, la pestaña Imágenes está en `pantallas/parcela-imagenes.js`.
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
| 3 Productor y parcela | Cerrada el 2026-10-05: criterios 1-13 probados por el equipo en producción; CI en verde (PRs #7, #8 y #9). Decisiones del 2026-10-05: ubicación del catálogo INEI; "Código productor APP" = código en Agro Digital; huecos, 100 ha y umbral confirmados; carga masiva de productores, KMZ, Shapefile y listas de coordenadas (sin UTM ni GPX); la interfaz toma el aspecto de `legacy/diseno` |
| 4 Habilitación de la parcela | Cerrada el 2026-10-05 por decisión del equipo (PRs #11 a #14 y la adenda de fuentes). **Probado por el equipo en producción:** análisis de Whisp, GFW y MapBiomas con fecha y versión; detalle por capa; tabla de convergencia; descarga de las respuestas completas (PA-00001 y PA-00002). **Cubierto por pruebas automáticas y revisado en local, sin prueba del equipo en producción:** capas WMS; visita con foto desde el celular; expediente; habilitar, observar y excluir; sección Habilitación; auditoría. **Sin verificar:** el criterio 7 de la adenda (`/health` durante un análisis de MapBiomas). **CI:** los PRs #12 a #14 se fusionaron sin el CI de GitHub por la caída de Actions del 2026-10-05; las 329 pruebas pasaron en local. Decisiones del 2026-10-05: 3 intentos por análisis; registros consultables, vigencias y sustento de SUNAFIL según fuentes oficiales; MapBiomas activo |
| 4 · adenda 2 Revisión de imágenes | Cerrada el 2026-10-05 por decisión del equipo (PR #21). La comprobación de viabilidad pasó (Copernicus la corrió el equipo; Wayback, sin clave). **Cubierto por pruebas automáticas (sección 13) y revisado en local, sin prueba del equipo en producción:** los 8 criterios de la sección 14. Decisiones del 2026-10-05: las visitas dejan de existir (sin pestaña ni endpoints; las registradas cuentan para la procedencia); "Buscar más imágenes" con hasta 3 escenas más cerca del corte; cuota de 30 000 PU; la revisión no vence con un análisis nuevo. Corrige que el DOP copiaba la primera decisión de habilitar |
| 5 Recepción de la tanda y DOP | Cerrada el 2026-10-05 por decisión del equipo (PRs #16 a #19). **Probado por el equipo en producción:** criterios 1 a 3 (código de la cooperativa, tope y cancha de acopio; tanda desde el celular con la foto de la guía; parcela no habilitada apagada con su motivo). **Cubierto por pruebas automáticas y revisado en local, sin prueba del equipo en producción:** criterios 4 a 10 (validar y emitir el DOP y su PDF; QR y verificación pública; alerta de volumen con nota; observar, corregir y validar; Mis entregas; anulación del DOP; auditoría). Ningún DOP se emitió todavía en producción: el primero comprueba que fpdf2 y las fuentes funcionan en Render. **CI:** en verde en los cuatro PRs; 374 pruebas. Decisiones del 2026-10-05: serie y número de la guía según SUNAT y sin registro público consultable (queda documentada); Cobertura forestal resumida ("Qué revisar", detalle plegado); alertas DIST y bosque al 31/12/2020 piden revisión solo si 3 o más mapas ven bosque (adenda, 7.2 reglas 1 y 3) |

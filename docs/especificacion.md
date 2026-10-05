# CacaoTrace — Especificación de construcción

Oct 4, 2026 · @Cacao Trace

## Cómo usar este documento

Este documento es la única fuente de verdad para construir CacaoTrace. Lo que no está escrito aquí no se construye sin preguntar antes al equipo.

El lector principal es Claude Code, trabajando dentro del repositorio. El equipo lo lee para revisar y aprobar cada parte.

### Reglas de trabajo para Claude Code

1. Construir parte por parte, en el orden del mapa de partes. No empezar una parte sin cumplir los criterios de aceptación de la anterior.
2. Ante un vacío o una ambigüedad, detenerse y preguntar. No inventar requisitos, datos regulatorios, integraciones ni datos de ejemplo que parezcan reales.
3. Los nombres de variables, rutas, carpetas y servicios de este documento son literales. Cambiarlos requiere aprobación.
4. Antes de usar un servicio o una librería, revisar su documentación vigente. Los límites y precios citados aquí son de octubre de 2026 y pueden cambiar.
5. Ningún secreto entra al repositorio. Las claves viven solo en los paneles de Render, Supabase y Cloudflare.
6. Cada parte termina con pruebas automatizadas en verde, un commit descriptivo y el deploy verificado en producción.
7. Toda acción con costo (cambiar de plan, comprar dominio) la ejecuta una persona del equipo, nunca Claude Code.

### Glosario mínimo

| Término | Significado | Nivel |
| --- | --- | --- |
| DOP | Documento de Origen del Producto | Parcela y productor |
| DPP | Documento de Procesamiento del Producto | Lote |
| DEX | Documento de Exportación | Embarque |
| DDS | Declaración de Diligencia Debida. La presenta el importador de la UE en TRACES-NT; CacaoTrace no la firma ni la envía | Fuera de alcance |
| EUDR | Reglamento (UE) 2023/1115 sobre productos libres de deforestación | Marco legal |

## Mapa de partes

La especificación tiene 10 partes que siguen el diagrama operativo de CacaoTrace: del productor al DOP, del DOP al lote procesado (DPP) y del lote al DEX. Cada parte incluye sus pantallas, sus endpoints y sus criterios de aceptación.

| N.º | Parte | Etapa del flujo | Qué cubre | Estado |
| --- | --- | --- | --- | --- |
| 1 | Infraestructura y despliegue | Base | Servicios, repositorio, variables, deploy, límites del plan gratis | Redactada |
| 2 | Acceso y base | Base | Login, cooperativas, usuarios, cinco roles, acceso del productor con DNI y estructura de la interfaz con barra lateral | Redactada |
| 3 | Productor y parcela | 1 | Ficha del productor, documentos de sustento, parcelas por dibujo o archivo, validación geométrica y superposiciones | Redactada |
| 4 | Habilitación de la parcela | 1 | Análisis de cobertura forestal por API, visita de campo, expediente legal con vencimientos y compuerta de habilitación | Redactada |
| 5 | Recepción de la tanda y DOP | 2 | Pesaje en cancha, cosecha, guía de remisión, compuerta de la tanda, emisión del DOP con huella, PDF y verificación pública | Redactada |
| 6 | Proceso y DPP | 2 | Corrida de proceso de 23 etapas, plantilla, consolidación, banda de rendimiento, tanda final al stock y emisión del DPP | Redactada |
| 7 | Orden de compra y genealogía | 3 | Importadores, órdenes, lote con selección FIFO sugerida, saldos, genealogía por parcela, indicadores y rastreo en los dos sentidos | Redactada |
| 8 | Cooperativa y recomprobación | 3 | Expediente legal de la cooperativa, documentos de embarque, recomprobación del lote con la fecha del día y panel de pendientes | Redactada |
| 9 | Informe de hallazgos y DEX | 3 | Catálogo de hallazgos por criterio del artículo 10, mensaje final, DEX sellado en español e inglés, GeoJSON y datos del Anexo II | Redactada |
| 10 | Datos de demostración y pruebas finales | Todas | Cooperativa Prueba, siembra y prueba de extremo a extremo, requisitos del piloto, calendario al 30 de octubre, guion de demo y verificación final | Redactada |

## Parte 1 — Infraestructura y despliegue

CacaoTrace corre sobre cuatro servicios en plan gratuito, con costo fijo de US$0 al mes. Cloudflare Pages sirve la interfaz, Render ejecuta la API, Supabase guarda datos, usuarios y archivos, y GitHub dispara los deploys.

### Objetivo de esta parte

Dejar desplegado un esqueleto funcional de punta a punta: una página pública que inicia sesión, llama a la API, y la API lee la base de datos. Esta parte no incluye ninguna función de negocio.

### Arquitectura

&#91;embedded content: arquitectura · 6 componentes, 4 servicios\]

El navegador carga la interfaz desde Cloudflare, inicia sesión en Supabase Auth y envía todo dato a la API. Solo la API toca Postgres y Storage.

| Componente | Servicio | Responsabilidad | Lo que no hace |
| --- | --- | --- | --- |
| Interfaz web | Cloudflare Pages | Sirve HTML, CSS y JS estáticos | No guarda datos ni secretos |
| API | Render, web service | Toda la lógica de negocio, validaciones, llamadas a fuentes externas y generación de PDF | No guarda archivos en su disco, que es efímero |
| Base de datos | Supabase Postgres con PostGIS | Datos relacionales y geometrías de parcelas | No es accesible desde el navegador |
| Autenticación | Supabase Auth | Inicio de sesión y emisión del token JWT | No decide permisos de negocio; eso lo hace la API |
| Archivos | Supabase Storage | Documentos escaneados y PDFs generados, en un bucket privado | No expone archivos públicos |
| Código y CI | GitHub | Repositorio, pruebas automáticas y disparo de deploys | No despliega ramas distintas de `main` |

### Flujo de una petición

1. El usuario abre la interfaz, servida por Cloudflare Pages.
2. La interfaz inicia sesión contra Supabase Auth y recibe un token JWT.
3. La interfaz llama a la API en Render con el encabezado `Authorization: Bearer <token>`.
4. La API verifica el token, aplica los permisos y lee o escribe en Postgres.
5. Para archivos, la API sube a Supabase Storage y entrega URLs firmadas de corta duración.

### Regla central de seguridad

El navegador solo habla con dos destinos: Supabase Auth, para iniciar sesión, y la API. Nunca consulta la base de datos ni Storage de forma directa. Todo permiso se decide en la API.

## Servicios, planes y URLs

Todos los servicios se crean en plan gratuito. Los límites son los vigentes a octubre de 2026; Claude Code debe confirmarlos en la página oficial de cada servicio antes de depender de ellos.

### Servicios

| Servicio | Plan | Nombre del recurso | Región | Límite que importa |
| --- | --- | --- | --- | --- |
| Cloudflare Pages | Free | Proyecto `cacaotrace` | Global | 500 builds al mes |
| Render | Free, web service | `cacaotrace-api` | Virginia (US East) | Se suspende tras 15 min sin tráfico; 750 horas de instancia al mes; disco efímero |
| Supabase | Free | Proyecto `cacaotrace` | East US (North Virginia) | 500 MB de base de datos; 1 GB de archivos; pausa tras 7 días sin actividad |
| GitHub | Free | `tracecacao-oss/cacaotracev1` | No aplica | Repositorio público: cualquier secreto subido queda expuesto |

Render y Supabase deben quedar en la misma región, o en la más cercana disponible, para que cada consulta a la base no cruce el continente. Si los nombres de región cambiaron, se elige la pareja más cercana entre sí.

La base de datos gratuita de Render no se usa: expira 30 días después de creada. SQLite tampoco: el disco del plan gratuito de Render se borra en cada redeploy o reinicio.

### URLs

| Etapa | Interfaz | API |
| --- | --- | --- |
| Inicial, sin dominio | `https://cacaotrace.pages.dev` | `https://cacaotrace-api.onrender.com` |
| Con dominio propio | `https://<dominio>` | `https://api.<dominio>` |

El subdominio exacto lo asigna cada servicio y puede variar si el nombre está tomado. El valor real se registra en las variables de entorno y en `frontend/config.js`.

Cuando exista dominio propio, el DNS se administra en Cloudflare. La interfaz se asocia como dominio personalizado del proyecto Pages. La API se asocia como dominio personalizado en Render, con un registro CNAME `api` que apunta al host `onrender.com` del servicio. Al agregar el dominio se actualizan `CORS_ORIGINS` y `frontend/config.js`.

### Costos

| Concepto | Costo | Cuándo |
| --- | --- | --- |
| Los cuatro servicios en plan gratuito | US$0 al mes | Desde el inicio |
| Dominio .com en Cloudflare Registrar | Cerca de US$10.44 al año | Opcional, antes de la final |
| Render Starter, API sin suspensión | US$7 al mes | Opcional, solo el mes de la final |

Fuentes de límites y precios: [Render, Deploy for Free](https://render.com/docs/free); [límites del plan gratuito de Supabase](https://www.itpathsolutions.com/supabase-free-tier-limits); [límites del plan gratuito de Cloudflare](https://eastondev.com/blog/en/posts/dev/20260526-cloudflare-free-limits/); [precio de .com en Cloudflare Registrar](https://devtoolpicks.com/blog/namecheap-vs-porkbun-vs-cloudflare-registrar-vs-godaddy-indie-hackers-2026). Solo la primera es página oficial; las demás son resúmenes de terceros.

## Stack técnico y estructura del repositorio

El backend es Python con FastAPI y la interfaz es HTML, CSS y JavaScript sin framework ni paso de compilación. Todo vive en un solo repositorio.

### Backend

| Pieza | Elección | Uso |
| --- | --- | --- |
| Lenguaje | Python 3.12 | Base del backend |
| Framework | FastAPI con Uvicorn | API HTTP |
| Acceso a datos | SQLAlchemy 2, modo síncrono, con psycopg 3 | Consultas y transacciones |
| Geometrías | GeoAlchemy2 y Shapely | Polígonos y puntos de parcelas, SRID 4326 |
| Migraciones | Alembic | Único mecanismo para cambiar el esquema |
| Validación y configuración | Pydantic 2 y pydantic-settings | Esquemas de entrada y salida, variables de entorno |
| Tokens | PyJWT con soporte criptográfico | Verificación del JWT de Supabase |
| HTTP saliente | httpx | Llamadas a fuentes externas y a Storage |
| Pruebas y estilo | pytest y ruff | Pruebas automáticas y lint |

Las versiones exactas se fijan en `backend/requirements.txt` con la última versión estable al momento de construir.

### Interfaz

| Pieza | Elección | Uso |
| --- | --- | --- |
| Lenguaje | HTML, CSS y JavaScript con módulos ES nativos | Sin compilación; lo que está en `frontend/` es lo que se publica |
| Sesión | Librería `supabase-js`, cargada desde CDN | Solo inicio y cierre de sesión y renovación del token |
| Datos | `fetch` contra la API | Toda lectura y escritura de datos |

El sistema de diseño, la barra lateral y las pantallas se especifican en la Parte 2.

### Estructura del repositorio

```text
cacaotracev1/
├── CLAUDE.md                  instrucciones permanentes para Claude Code
├── README.md                  cómo levantar el proyecto en local
├── render.yaml                definición del servicio de API en Render
├── docker-compose.yml         Postgres con PostGIS para desarrollo local
├── docs/
│   └── especificacion.md      este documento, exportado a Markdown
├── backend/
│   ├── app/
│   │   ├── main.py            crea la app, CORS y registra routers
│   │   ├── config.py          lectura de variables de entorno
│   │   ├── db.py              engine y sesión de SQLAlchemy
│   │   ├── auth.py            verificación del JWT y usuario actual
│   │   ├── storage.py         cliente de Supabase Storage
│   │   ├── routers/           un archivo por módulo de la API
│   │   ├── models/            modelos SQLAlchemy
│   │   ├── schemas/           esquemas Pydantic
│   │   └── services/          lógica de negocio
│   ├── alembic/               migraciones
│   ├── alembic.ini
│   ├── scripts/               utilidades de diagnóstico
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example           nombres de variables, sin valores
├── frontend/
│   ├── index.html
│   ├── config.js              URLs públicas y clave publicable
│   ├── css/
│   ├── js/
│   └── _headers               cabeceras de seguridad de Cloudflare Pages
├── legacy/                    MVP anterior, solo referencia, no se despliega
└── .github/workflows/ci.yml   pruebas en cada push y pull request
```

### Archivo CLAUDE.md

`CLAUDE.md` contiene, en menos de una página: la ruta de la especificación, las reglas de trabajo de este documento, los comandos para correr el backend, las pruebas y las migraciones, y la parte en la que se está trabajando. Claude Code lo actualiza al cerrar cada parte.

### Código anterior

El repositorio ya contiene un MVP previo. En el primer commit se mueve completo a `legacy/`. Sirve como referencia de reglas de negocio y de diseño visual, pero no se reutiliza sin revisarlo contra esta especificación.

## Supabase: base de datos, autenticación y archivos

Supabase aporta tres servicios y la API es la única que accede a los datos y a los archivos. El navegador usa Supabase solo para iniciar sesión.

### Base de datos

1. Motor: Postgres administrado por Supabase, con la extensión `postgis` habilitada.
2. Conexión desde Render: se usa la cadena del pooler en modo sesión, tomada del panel Connect de Supabase. La conexión directa usa IPv6 y puede fallar desde Render.
3. Pool de SQLAlchemy: `pool_size=5`, `max_overflow=0`, `pool_pre_ping=True`. El plan gratuito admite pocas conexiones simultáneas.
4. Esquema: todas las tablas en `public`, con nombres en `snake_case`. Las geometrías usan SRID 4326.
5. Migraciones: solo con Alembic. Nadie crea ni altera tablas a mano desde el panel de Supabase.
6. Las migraciones se aplican al arrancar el servicio, con `alembic upgrade head` antes de iniciar Uvicorn.

### Bloqueo del acceso directo

Supabase expone una API de datos automática que cualquiera puede llamar con la clave publicable. Para que no entregue nada:

1. Toda migración que crea una tabla incluye `ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY`.
2. No se crea ninguna política de RLS. Sin políticas, la clave publicable no lee ni escribe ninguna fila.
3. La API se conecta con el usuario de base de datos de la cadena de conexión, que no está sujeto a RLS.
4. Una prueba automática recorre las tablas de `public` y falla si alguna tiene RLS desactivado.

### Autenticación

1. Proveedor: Supabase Auth con correo y contraseña. No hay otros proveedores. El productor entra con su DNI mediante un correo técnico, descrito en la Parte 2.
2. La interfaz usa `supabase-js` solo para iniciar sesión, cerrar sesión, leer la sesión y renovar el token.
3. La API exige el encabezado `Authorization: Bearer <token>` en todo endpoint, salvo `/health` y `/health/db`.
4. La API verifica en cada petición la firma, la expiración y la audiencia `authenticated` del token.
5. La firma se verifica con las claves públicas del proyecto, publicadas en su endpoint JWKS, con caché de 10 minutos. Si el proyecto firma con secreto compartido HS256, se usa `SUPABASE_JWT_SECRET`. Claude Code confirma en el panel cuál aplica.
6. El identificador de usuario es el campo `sub` del token. Roles y pertenencia a una cooperativa se definen en la Parte 2 y viven en tablas propias, no en el token.
7. El correo integrado de Supabase admite muy pocos envíos por hora. La demo no debe depender de correos de confirmación: los usuarios se crean ya confirmados.

### Archivos

1. Un único bucket privado llamado `documentos`.
2. Ruta de cada archivo: `{cooperativa_id}/{entidad}/{entidad_id}/{uuid}.{ext}`.
3. Subida: el navegador envía el archivo a la API y la API lo sube a Storage con la clave secreta.
4. Descarga: la API verifica el permiso y devuelve una URL firmada que vence a los 5 minutos.
5. Límites que aplica la API: 10 MB por archivo y solo PDF, JPG y PNG, validando el tipo real del contenido. Las excepciones son los archivos de geometría de la Parte 3 (GeoJSON, KML, KMZ, Shapefile en .zip y listas de coordenadas en .txt, .csv o .xlsx) y la hoja de la carga masiva de productores (.csv o .xlsx), todos de hasta 2 MB.
6. Ningún archivo se guarda en la base de datos ni en el disco de Render. La base guarda la ruta, el nombre original, el tamaño y el hash SHA-256.

### Claves de Supabase

| Clave | Dónde vive | Para qué |
| --- | --- | --- |
| Publicable, antes `anon` | `frontend/config.js`, a la vista | Iniciar sesión desde el navegador |
| Secreta, antes `service_role` | Solo en Render | Subir, firmar y borrar archivos desde la API |
| Contraseña de la base | Solo en Render, dentro de `DATABASE_URL` | Conexión de la API a Postgres |

La clave publicable es segura a la vista solo mientras RLS esté activo en todas las tablas y el bucket sea privado.

## Variables de entorno y secretos

El backend lee toda su configuración de variables de entorno y la interfaz de un único archivo con valores públicos. Ningún valor secreto aparece en el repositorio, que es público.

### Backend, definidas en Render

| Variable | Formato o ejemplo | Secreta | Descripción |
| --- | --- | --- | --- |
| `ENVIRONMENT` | `production` o `development` | No | Activa o desactiva la documentación interactiva y el detalle de errores |
| `PYTHON_VERSION` | Última 3.12 disponible en Render | No | Versión de Python que usa Render |
| `DATABASE_URL` | `postgresql+psycopg://<usuario>:<clave>@<host-pooler>:5432/postgres` | Sí | Cadena del pooler en modo sesión |
| `SUPABASE_URL` | `https://<ref>.supabase.co` | No | URL del proyecto |
| `SUPABASE_SECRET_KEY` | Valor del panel de Supabase | Sí | Acceso de la API a Storage y a la administración de usuarios |
| `SUPABASE_JWT_SECRET` | Valor del panel de Supabase | Sí | Solo si el proyecto firma tokens con HS256 |
| `STORAGE_BUCKET` | `documentos` | No | Bucket privado de archivos |
| `CORS_ORIGINS` | `https://cacaotrace.pages.dev` | No | Orígenes permitidos, separados por coma |
| `PRODUCTOR_EMAIL_DOMAIN` | `productores.cacaotrace.local` | No | Dominio del correo técnico del productor, Parte 2 |
| `GIT_SHA` | Lo provee Render como `RENDER_GIT_COMMIT` | No | Versión desplegada que reporta `/health` |

### Interfaz, en `frontend/config.js`

| Constante | Ejemplo | Descripción |
| --- | --- | --- |
| `API_URL` | `https://cacaotrace-api.onrender.com` | Base de todas las llamadas a la API |
| `SUPABASE_URL` | `https://<ref>.supabase.co` | Proyecto para iniciar sesión |
| `SUPABASE_PUBLISHABLE_KEY` | Valor del panel de Supabase | Clave publicable |
| `PRODUCTOR_EMAIL_DOMAIN` | `productores.cacaotrace.local` | Dominio del correo técnico del productor, Parte 2 |

Si la página corre en `localhost`, `config.js` apunta `API_URL` a `http://localhost:8000`.

### Reglas de secretos

1. `backend/.env` está en `.gitignore` desde el primer commit. `backend/.env.example` lista los nombres sin valores.
2. En `render.yaml` los secretos se declaran con `sync: false`; una persona del equipo pega el valor en el panel de Render.
3. Los secretos nunca se imprimen en logs, mensajes de error ni respuestas de la API.
4. Claude Code nunca escribe un valor secreto en un archivo, un commit ni un mensaje. Si necesita uno, pide a una persona que lo cargue en el panel.
5. Si un secreto llega al repositorio, se rota de inmediato en Supabase; borrar el commit no basta.
6. `CORS_ORIGINS` nunca usa `*`. En producción la documentación interactiva de FastAPI queda desactivada.

## Deploy, health checks y límites

Cada cambio que llega a `main` se publica solo: Render reconstruye la API y Cloudflare Pages publica la interfaz. Nadie despliega a mano.

### Ramas y CI

1. `main` es producción. Solo recibe cambios por pull request con las pruebas en verde.
2. El trabajo se hace en ramas `feat/parte-<n>-<tema>`.
3. `.github/workflows/ci.yml` corre en cada push y pull request: levanta Postgres con PostGIS, instala dependencias, corre `ruff`, aplica las migraciones y corre `pytest`.

### API en Render

El servicio se define en `render.yaml`. Claude Code valida los nombres de campos contra la referencia vigente de Blueprints de Render antes de usarlo.

```yaml
services:
  - type: web
    name: cacaotrace-api
    runtime: python
    plan: free
    region: virginia
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    autoDeploy: true
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: STORAGE_BUCKET
        value: documentos
      - key: DATABASE_URL
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SECRET_KEY
        sync: false
      - key: CORS_ORIGINS
        sync: false
```

### Interfaz en Cloudflare Pages

1. Proyecto Pages conectado al repositorio de GitHub, rama de producción `main`.
2. Sin comando de build. Directorio de salida: `frontend`.
3. `frontend/_headers` define `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` y `Referrer-Policy: strict-origin-when-cross-origin`.

### Health checks

| Endpoint | Qué hace | Respuesta |
| --- | --- | --- |
| `GET /health` | No toca la base. Lo usa Render para saber si el servicio vive | 200 con `{"status": "ok", "version": "<git sha>"}` |
| `GET /health/db` | Ejecuta `SELECT 1` y `SELECT PostGIS_Version()` | 200 con la versión de PostGIS, o 503 si la base no responde |

### Mantener todo despierto

Un monitor externo gratuito, como UptimeRobot, llama a `GET /health/db` cada 5 minutos. Así Render no se suspende y Supabase registra actividad. Es una práctica tolerada, no una garantía de Render. Para el día de la final se pasa la API al plan Starter.

La interfaz asume que la API puede estar dormida. Si una llamada tarda más de 3 segundos, muestra el aviso "Conectando con el servidor" y reintenta hasta 90 segundos antes de mostrar un error.

### Límites del plan gratuito y mitigación

| Límite | Efecto | Mitigación |
| --- | --- | --- |
| Render suspende la API tras 15 min sin tráfico | La primera petición tarda cerca de 1 minuto | Monitor externo, aviso de espera en la interfaz, plan Starter el mes de la final |
| Render da 750 horas de instancia al mes | Un servicio encendido todo el mes usa hasta 744 | Un solo servicio gratuito en la cuenta |
| El disco de Render es efímero | Todo archivo local se pierde en cada redeploy | Archivos solo en Supabase Storage |
| Supabase pausa el proyecto tras 7 días sin actividad | La base queda fuera de línea hasta restaurarla a mano | El monitor consulta `/health/db` |
| Supabase: 500 MB de base de datos | Las escrituras fallan al llenarse | No guardar archivos ni rásteres en la base |
| Supabase: 1 GB de archivos | Las subidas fallan al llenarse | Tope de 10 MB por archivo |
| Supabase gratuito no hace copias automáticas | Un error borra datos sin vuelta atrás | Una persona corre `pg_dump` antes de cada demo y guarda la copia fuera del repositorio |

## Desarrollo local y pruebas

El proyecto se levanta en una laptop con tres comandos y las pruebas no dependen de internet ni de las cuentas reales.

### Entorno local

1. Base de datos: `docker compose up -d` levanta Postgres con PostGIS, en la misma versión mayor que el proyecto de Supabase.
2. Backend: desde `backend/`, se copia `.env.example` a `.env`, se corre `alembic upgrade head` y luego `uvicorn app.main:app --reload`.
3. Interfaz: `python -m http.server 5500 --directory frontend`.
4. El inicio de sesión en local usa el proyecto real de Supabase, con un usuario de prueba.

### Pruebas automáticas

1. Corren con `pytest` contra el Postgres de Docker, nunca contra Supabase.
2. La autenticación se prueba de dos formas. Los endpoints usan un usuario simulado por sobreescritura de dependencias. El verificador de tokens se prueba con un par de claves generado en la propia prueba.
3. Las llamadas a Storage y a servicios externos se simulan; ninguna prueba sale a internet.
4. Cada parte de la especificación agrega sus pruebas, y todas las anteriores deben seguir en verde.

### Pruebas mínimas de la Parte 1

| Prueba | Resultado esperado |
| --- | --- |
| `GET /health` | 200 con `status` y `version` |
| `GET /health/db` con base disponible | 200 con versión de PostGIS |
| `GET /health/db` con base caída | 503 |
| `GET /me` sin token | 401 |
| `GET /me` con token válido | 200 con `id` y `email` del usuario |
| `GET /me` con token vencido o firma alterada | 401 |
| Petición desde un origen no permitido | Sin cabeceras CORS de permiso |
| Recorrido de tablas de `public` | Todas con RLS activo |

### Diagnóstico de Storage

`backend/scripts/check_storage.py` sube un archivo de prueba al bucket, genera una URL firmada, lo descarga, compara el contenido y lo borra. Lo corre una persona con las variables reales cargadas en su terminal.

## Checklist de puesta en marcha

La Parte 1 se ejecuta en tres bloques, en este orden. Lo que crea cuentas, maneja secretos o cuesta dinero lo hace una persona; el código lo escribe Claude Code.

### A. Equipo, antes de empezar

- [ ] Definir qué persona y qué correo son dueños de las cuentas de Supabase, Render, Cloudflare y GitHub.
- [ ] Crear el proyecto `cacaotrace` en Supabase, región East US, y guardar la contraseña de la base en un gestor de contraseñas.
- [ ] Habilitar la extensión `postgis` en el proyecto de Supabase.
- [ ] Crear el bucket privado `documentos` en Supabase Storage.
- [ ] Crear en Supabase Auth un usuario de prueba, ya confirmado.
- [ ] Conectar los conectores de Supabase y Cloudflare en Claude. Render ya está conectado.
- [ ] Instalar Claude Code de escritorio, iniciar sesión y clonar `tracecacao-oss/cacaotracev1`.
- [ ] Exportar este documento a Markdown y guardarlo en `docs/especificacion.md`.

### B. Claude Code

- [ ] Mover el MVP anterior a `legacy/` y crear la estructura de carpetas de esta especificación.
- [ ] Crear `CLAUDE.md`, `README.md`, `.gitignore`, `backend/.env.example` y `docker-compose.yml`.
- [ ] Construir el esqueleto del backend: `config.py`, `db.py`, `auth.py`, `storage.py`, `main.py` con CORS.
- [ ] Implementar `GET /health`, `GET /health/db` y `GET /me`.
- [ ] Crear la migración inicial de Alembic, que asegura la extensión `postgis`.
- [ ] Escribir las pruebas mínimas de la Parte 1 y `scripts/check_storage.py`.
- [ ] Construir el esqueleto de la interfaz: pantalla de inicio de sesión y pantalla de estado, que muestra API, base de datos y correo del usuario.
- [ ] Crear `render.yaml`, `frontend/_headers` y `.github/workflows/ci.yml`.
- [ ] Abrir el pull request a `main` con las pruebas en verde.

### C. Equipo, después del primer merge a `main`

- [ ] En Render, crear el servicio desde `render.yaml` y pegar los valores de `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY` y `CORS_ORIGINS`.
- [ ] En Cloudflare, crear el proyecto Pages conectado al repositorio, con directorio de salida `frontend`.
- [ ] Registrar las URLs reales en `frontend/config.js` y en `CORS_ORIGINS`.
- [ ] Correr `scripts/check_storage.py` con las variables reales.
- [ ] Crear el monitor externo que llama a `GET /health/db` cada 5 minutos.
- [ ] Revisar uno por uno los criterios de aceptación.

## Criterios de aceptación de la Parte 1

La Parte 1 está terminada cuando los diez puntos se cumplen en producción, no solo en local.

1. `GET <API_URL>/health` responde 200 e informa el commit desplegado.
2. `GET <API_URL>/health/db` responde 200 con la versión de PostGIS.
3. La URL de la interfaz muestra la pantalla de inicio de sesión.
4. Con credenciales válidas, la pantalla de estado muestra API y base de datos en verde y el correo del usuario.
5. Con credenciales inválidas, la interfaz muestra un mensaje de error claro y no entra.
6. `GET /me` responde 401 sin token, con token vencido y con token alterado.
7. Una consulta a la API de datos de Supabase con la clave publicable no devuelve ninguna fila de ninguna tabla.
8. `scripts/check_storage.py` sube, firma, descarga y borra un archivo sin errores.
9. Un merge a `main` actualiza la API y la interfaz sin pasos manuales, y `/health` muestra el nuevo commit.
10. El CI está en verde y una búsqueda en el repositorio no encuentra claves, contraseñas ni archivos `.env`.

### Decisiones pendientes del equipo

Ninguna bloquea el inicio de la construcción, salvo la primera.

- [ ] Qué persona y qué correo son dueños de las cuentas.
- [ ] Nombre y extensión del dominio propio, y cuándo comprarlo.
- [ ] Si el repositorio sigue público o pasa a privado.
- [ ] Si la API pasa a Render Starter el mes de la final.
- [ ] Si el MVP anterior se conserva en `legacy/` o se elimina al cerrar la Parte 2.

## Parte 2 — Acceso y base

CacaoTrace atiende a varias cooperativas aisladas entre sí, con cinco roles y dos formas de entrar: el personal con correo y contraseña, el productor con DNI y contraseña.

### Objetivo de esta parte

Dejar funcionando el ingreso, los roles, el aislamiento entre cooperativas y la estructura de la interfaz con barra lateral. Al terminar, cada tipo de usuario entra y ve solo lo que le corresponde, aunque los módulos de negocio aún estén vacíos.

### Decisiones tomadas por el equipo

| Tema | Decisión |
| --- | --- |
| Quién inicia sesión | Personal de la cooperativa, productores y equipo CacaoTrace. El importador no tiene cuenta |
| Cooperativas | Varias en la misma plataforma; cada una ve solo sus datos |
| Alta de cooperativas | El equipo CacaoTrace crea la cooperativa y a su primer administrador |
| Alta de personal | El administrador de la cooperativa crea las cuentas de su equipo |
| Ingreso del productor | DNI de 8 dígitos y contraseña |
| Quién llena el DOP | El productor o el personal de la cooperativa; la cooperativa siempre valida |
| Productor y cooperativas | Un productor pertenece a una sola cooperativa por ahora; el modelo queda listo para varias |

### Fuera de alcance en esta parte

- Los datos completos del productor y las parcelas, que son la Parte 3.
- Correos automáticos de invitación o de recuperación de contraseña.
- Documentos de identidad distintos del DNI, como carné de extranjería.

## Roles y permisos

Hay cinco roles fijos. Cada usuario tiene exactamente un rol y, salvo el superadministrador, pertenece a exactamente una cooperativa.

### Roles

| Identificador | Quién es | Alcance | Ingreso |
| --- | --- | --- | --- |
| `superadmin` | Equipo CacaoTrace | Toda la plataforma: gestiona cooperativas y ve sus datos en solo lectura | Correo y contraseña |
| `admin_cooperativa` | Responsable de la cooperativa | Su cooperativa: todo, incluida la gestión de usuarios | Correo y contraseña |
| `operador` | Técnico de campo, acopio o planta | Su cooperativa: registra y edita datos; no gestiona personal | Correo y contraseña |
| `lector` | Gerencia, auditor o certificadora | Su cooperativa: solo lectura | Correo y contraseña |
| `productor` | Productor socio | Solo su propio perfil, sus parcelas y sus DOP | DNI y contraseña |

### Matriz de permisos

| Acción | superadmin | admin\_cooperativa | operador | lector | productor |
| --- | --- | --- | --- | --- | --- |
| Crear, editar y suspender cooperativas | Sí | No | No | No | No |
| Ver datos de cualquier cooperativa, solo lectura | Sí | No | No | No | No |
| Crear, editar y desactivar personal de su cooperativa | No | Sí | No | No | No |
| Crear y restablecer el acceso de un productor | No | Sí | Sí | No | No |
| Ver los datos de su cooperativa | No | Sí | Sí | Sí | No |
| Registrar y editar productores, DOP y lotes | No | Sí | Sí | No | No |
| Llenar y editar su propio DOP mientras no esté validado | No | No | No | No | Sí |
| Ver solo sus propios datos | No | No | No | No | Sí |
| Validar DOP, Parte 5 | No | Sí | Sí | No | No |
| Emitir el DEX, Parte 9 | No | Sí | No | No | No |

### Reglas

1. El rol vive en la tabla `perfiles`, no en el token. Cambiar un rol surte efecto en la siguiente petición.
2. Los permisos se verifican en la API con dependencias reutilizables, por ejemplo `requiere_rol("admin_cooperativa", "operador")`. La interfaz oculta lo que el rol no puede usar, pero la API es la que decide.
3. Un rol sin permiso recibe 403. Un recurso de otra cooperativa recibe 404, como si no existiera.
4. El superadministrador no crea ni edita datos de negocio de una cooperativa. Solo los consulta para dar soporte.
5. Cada parte posterior agrega sus filas a esta matriz; ninguna crea roles nuevos.

## Modelo de datos de la Parte 2

Cinco tablas sostienen el acceso: `cooperativas`, `perfiles`, `productores`, `afiliaciones` y `auditoria`. El productor es único en toda la plataforma y se vincula a una cooperativa mediante una afiliación. Las tablas de cooperativas y de productores llevan además la columna es\_demo, descrita en la Parte 10; se crea desde esta parte.

### Convenciones para todas las tablas

1. Clave primaria `id` de tipo `uuid`, generada con `gen_random_uuid()`, salvo `auditoria`.
2. Columnas `creado_en` y `actualizado_en` de tipo `timestamptz`, en UTC. La interfaz muestra las fechas en hora de Lima.
3. Los valores cerrados se guardan como `text` con restricción `CHECK`, no como tipos `ENUM` de Postgres.
4. Toda tabla tiene RLS activado y ninguna política, según la Parte 1.

### `cooperativas`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `razon_social` | text | Obligatoria |
| `nombre_comercial` | text | Opcional |
| `ruc` | char(11) | Obligatorio, único, 11 dígitos |
| `departamento`, `provincia`, `distrito` | text | Obligatorios |
| `estado` | text | `activa` o `suspendida`; por defecto `activa` |

### `perfiles`

Una fila por cada usuario que puede iniciar sesión.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `id` | uuid | Igual al identificador del usuario en Supabase Auth. Sin clave foránea, porque el esquema `auth` no existe en local |
| `rol` | text | Uno de los cinco roles |
| `cooperativa_id` | uuid | Referencia a `cooperativas`. Nulo solo si el rol es `superadmin` |
| `productor_id` | uuid | Referencia a `productores`. Obligatorio y único si el rol es `productor`; nulo en los demás |
| `nombres`, `apellidos` | text | Obligatorios |
| `correo` | text | Correo real del personal. Nulo para el productor |
| `activo` | boolean | Por defecto `true` |
| `debe_cambiar_clave` | boolean | Por defecto `true` |
| `ultimo_acceso_en` | timestamptz | Se actualiza al consultar `GET /me` |
| `creado_por` | uuid | Perfil que creó la cuenta |

### `productores`

Versión mínima. La Parte 3 agrega el resto de columnas.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `dni` | char(8) | Obligatorio, único en toda la plataforma, 8 dígitos |
| `nombres`, `apellidos` | text | Obligatorios |
| `telefono` | text | Opcional |
| `consentimiento_datos_en` | timestamptz | Momento en que se registró el consentimiento |
| `consentimiento_origen` | text | `productor` o `cooperativa` |

### `afiliaciones`

Vincula a un productor con una cooperativa.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `productor_id` | uuid | Referencia a `productores`, obligatoria |
| `cooperativa_id` | uuid | Referencia a `cooperativas`, obligatoria |
| `codigo_socio` | text | Código interno que usa la cooperativa, opcional |
| `estado` | text | `activa` o `inactiva` |
| `desde` | date | Obligatoria |
| `hasta` | date | Se llena al cerrar la afiliación |

Un índice único parcial sobre `productor_id` con la condición `estado = 'activa'` garantiza una sola cooperativa por productor. Para permitir varias en el futuro basta reemplazarlo por un índice único sobre `productor_id` y `cooperativa_id`. Ninguna otra tabla debe asumir que la afiliación es única.

Si una cooperativa intenta registrar un DNI con afiliación activa en otra, la API responde 409 con el mensaje "Este DNI ya está afiliado a otra cooperativa", sin revelar cuál.

### `auditoria`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `id` | bigint | Identidad autogenerada |
| `ocurrido_en` | timestamptz | Por defecto `now()` |
| `usuario_id` | uuid | Perfil que ejecutó la acción |
| `rol` | text | Rol en el momento de la acción |
| `cooperativa_id` | uuid | Cooperativa afectada; nulo en acciones de plataforma |
| `accion` | text | Formato `entidad.verbo`, por ejemplo `usuario.crear` |
| `entidad`, `entidad_id` | text | Qué registro se tocó |
| `detalle` | jsonb | Valores relevantes, sin contraseñas ni tokens |
| `ip` | text | Dirección de origen de la petición |

## Aislamiento entre cooperativas

La cooperativa de un usuario sale siempre de su perfil en la base de datos, nunca de un dato enviado por el navegador. Esta es la regla que impide que una cooperativa vea a otra.

### Contexto de cada petición

Una dependencia de FastAPI llamada `obtener_contexto` arma el contexto antes de ejecutar cualquier endpoint protegido. Devuelve `usuario_id`, `rol`, `cooperativa_id` y `productor_id`.

1. Verifica el token según la Parte 1.
2. Busca la fila de `perfiles` cuyo `id` es el campo `sub` del token. Si no existe, responde 403.
3. Si `activo` es `false`, responde 403 con el código `cuenta_desactivada`.
4. Si la cooperativa del perfil está `suspendida`, responde 403 con el código `cooperativa_suspendida`.
5. Si `debe_cambiar_clave` es `true`, solo permite `GET /me` y `POST /me/clave`. Todo lo demás responde 403 con el código `cambio_clave_requerido`.

### Reglas de consulta

1. Toda tabla de negocio lleva la columna `cooperativa_id`. La excepción es `productores`, que se alcanza a través de `afiliaciones`.
2. Las funciones de la capa `services` reciben el contexto como primer parámetro y filtran por su `cooperativa_id`. Ninguna acepta un `cooperativa_id` venido del cuerpo, la ruta o la query de la petición.
3. Al crear un registro, `cooperativa_id` se toma del contexto.
4. Para el rol `productor` se filtra además por el `productor_id` del contexto.
5. Un recurso de otra cooperativa responde 404, igual que uno inexistente.
6. El superadministrador elige qué cooperativa consultar con el encabezado `X-Cooperativa-Id`. Solo se acepta en peticiones `GET`, y la API lo ignora para cualquier otro rol.
7. Antes de firmar la URL de un archivo, la API comprueba que su registro pertenece a la cooperativa del contexto.

### Prueba obligatoria en todo endpoint

Cada endpoint que lee o modifica datos de una cooperativa tiene una prueba con dos cooperativas, A y B. Un usuario de A que pide un recurso de B recibe 404, y sus listados solo traen datos de A. Este patrón se repite en todas las partes siguientes.

## Cuentas y contraseñas

Ninguna cuenta nace por registro abierto ni depende de un correo. Quien crea la cuenta recibe en pantalla una contraseña temporal, una sola vez, y el usuario la cambia en su primer ingreso.

### Quién crea cada cuenta

| Cuenta | La crea | Desde |
| --- | --- | --- |
| Superadministrador | Una persona del equipo | Script `backend/scripts/crear_superadmin.py` |
| Cooperativa y su primer administrador | `superadmin` | Pantalla Cooperativas |
| Personal de la cooperativa | `admin_cooperativa` | Pantalla Usuarios |
| Acceso de un productor | `admin_cooperativa` u `operador` | Ficha del productor |

### Mecánica común

1. La API crea el usuario en Supabase Auth con la API de administración y la clave secreta, con el correo marcado como confirmado.
2. En la misma operación crea la fila de `perfiles` con `debe_cambiar_clave = true`. Si uno de los dos pasos falla, deshace el otro; no quedan cuentas huérfanas.
3. La contraseña temporal tiene 10 caracteres, letras y dígitos, sin caracteres ambiguos como `0`, `O`, `1`, `l` e `I`. Se genera con el módulo `secrets`.
4. La respuesta incluye la contraseña temporal una sola vez. No se guarda ni se escribe en logs ni en auditoría.
5. La interfaz la muestra con un botón de copiar y el aviso de que no volverá a verse.
6. El registro público de usuarios queda desactivado en la configuración de Supabase Auth.

### Ingreso del productor con DNI

1. Supabase Auth identifica a cada usuario por un correo. Para el productor, la API usa un correo técnico: `<dni>@<PRODUCTOR_EMAIL_DOMAIN>`.
2. Ese correo nunca recibe mensajes ni se muestra al usuario.
3. En la pantalla de ingreso el productor escribe su DNI y su contraseña. La interfaz arma el correo técnico e inicia sesión con él.
4. `PRODUCTOR_EMAIL_DOMAIN` es una variable nueva del backend y una constante nueva de `frontend/config.js`. Valor inicial: `productores.cacaotrace.local`.
5. Claude Code comprueba que la API de administración de Supabase acepta ese dominio. Si lo rechaza, se detiene y lo informa al equipo.
6. Solo un productor con afiliación activa puede tener acceso. Si se corrige su DNI, se actualiza también el correo técnico.

### Primer ingreso y cambio de contraseña

1. Tras iniciar sesión, la interfaz llama a `GET /me`. Si `debe_cambiar_clave` es `true`, muestra solo la pantalla de cambio de contraseña.
2. `POST /me/clave` recibe la contraseña actual y la nueva. La API comprueba la actual contra Supabase Auth, fija la nueva y pone `debe_cambiar_clave` en `false`.
3. Reglas: mínimo 8 caracteres con al menos una letra y un dígito para el personal; mínimo 6 caracteres para el productor. La nueva debe ser distinta de la temporal.
4. El mínimo configurado en el proyecto de Supabase es 6.

### Olvido de contraseña

No hay recuperación por correo. La pantalla de ingreso indica: "¿Olvidaste tu contraseña? Pide a tu cooperativa que la restablezca".

| Quien la olvidó | Quién la restablece |
| --- | --- |
| Productor | `admin_cooperativa` u `operador` de su cooperativa |
| Operador o lector | `admin_cooperativa` de su cooperativa |
| Administrador de cooperativa | Otro administrador de la misma cooperativa, o un `superadmin` |
| Superadministrador | Una persona del equipo, con el script |

Restablecer genera una nueva contraseña temporal, pone `debe_cambiar_clave` en `true` y cierra las sesiones abiertas de ese usuario.

### Desactivar cuentas

1. Las cuentas no se borran, porque la auditoría las referencia. Se desactivan con `activo = false` y se bloquean en Supabase Auth para que el token no se renueve.
2. Un administrador no puede desactivarse a sí mismo ni cambiar su propio rol.
3. Una cooperativa conserva siempre al menos un administrador activo.
4. Suspender una cooperativa bloquea a todos sus usuarios sin modificar cada cuenta.

## Endpoints de la Parte 2

La Parte 2 agrega 20 endpoints en cinco grupos. Todos exigen token y pasan por `obtener_contexto`.

### Convenciones de la API

1. Entrada y salida en JSON, con nombres de campos en español y `snake_case`.
2. Errores con la forma `{"error": {"codigo": "...", "mensaje": "..."}}`. El mensaje está en español y se puede mostrar al usuario.
3. Códigos: 400 regla de negocio incumplida, 401 token ausente o inválido, 403 sin permiso, 404 no existe o es de otra cooperativa, 409 duplicado, 422 datos mal formados.
4. Listados paginados con `?pagina=1&por_pagina=25`, máximo 100. Responden `{"items": [], "total": 0, "pagina": 1, "por_pagina": 25}`.
5. Toda acción que crea o modifica deja una fila en `auditoria`.

### Sesión

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /me` | Todos | Devuelve perfil, rol, cooperativa, `productor_id` y `debe_cambiar_clave`; actualiza `ultimo_acceso_en` |
| `POST /me/clave` | Todos | Cambia la contraseña |
| `POST /me/consentimiento` | `productor` | Registra el consentimiento de datos del propio productor |

### Plataforma

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /admin/cooperativas` | `superadmin` | Lista cooperativas con su estado y número de usuarios |
| `POST /admin/cooperativas` | `superadmin` | Crea la cooperativa y su primer administrador; devuelve la contraseña temporal |
| `GET /admin/cooperativas/{id}` | `superadmin` | Detalle de una cooperativa |
| `PATCH /admin/cooperativas/{id}` | `superadmin` | Edita datos o cambia el estado |
| `POST /admin/cooperativas/{id}/administradores` | `superadmin` | Crea otro administrador para esa cooperativa |
| `POST /admin/usuarios/{id}/restablecer-clave` | `superadmin` | Restablece la contraseña de un administrador de cooperativa |

### Personal de la cooperativa

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /usuarios` | `admin_cooperativa` | Lista el personal de su cooperativa |
| `POST /usuarios` | `admin_cooperativa` | Crea una cuenta con nombres, apellidos, correo y rol; devuelve la contraseña temporal |
| `PATCH /usuarios/{id}` | `admin_cooperativa` | Cambia nombres, rol o estado activo |
| `POST /usuarios/{id}/restablecer-clave` | `admin_cooperativa` | Genera una nueva contraseña temporal |

`POST /usuarios` solo acepta los roles `admin_cooperativa`, `operador` y `lector`. Un correo ya usado responde 409 con el código `correo_en_uso`.

### Productores, versión mínima

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /productores` | `admin_cooperativa`, `operador`, `lector` | Lista los productores con afiliación activa; busca por DNI o nombre |
| `POST /productores` | `admin_cooperativa`, `operador` | Crea el productor con DNI, nombres, apellidos, teléfono y código de socio, y su afiliación activa |
| `GET /productores/{id}` | `admin_cooperativa`, `operador`, `lector` | Detalle del productor |
| `POST /productores/{id}/acceso` | `admin_cooperativa`, `operador` | Crea la cuenta del productor; devuelve la contraseña temporal |
| `POST /productores/{id}/acceso/restablecer-clave` | `admin_cooperativa`, `operador` | Genera una nueva contraseña temporal |
| `DELETE /productores/{id}/acceso` | `admin_cooperativa`, `operador` | Desactiva la cuenta del productor |

La Parte 3 amplía estos endpoints con los datos completos del productor y sus parcelas.

### Auditoría

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /auditoria` | `admin_cooperativa`, `superadmin` | Lista paginada, con filtros por fecha, usuario y acción |

## Interfaz: estructura y pantallas

La interfaz tiene barra lateral izquierda, una sola tarea por pantalla y cada módulo dividido en secciones. La versión anterior, con todo en una pantalla, se descartó por saturada.

### Base visual

1. Sistema de diseño "Slate & Emerald": neutros pizarra y acento esmeralda.
2. Tipografías: Plus Jakarta Sans para texto y JetBrains Mono para DNI, códigos, identificadores y cifras. Se cargan desde Google Fonts.
3. La fuente de colores, espaciados y radios es el HTML del último rediseño del equipo, que debe estar en `legacy/diseno/`. Claude Code los extrae a `frontend/css/tokens.css` como variables CSS.
4. Si ese archivo no está en el repositorio, Claude Code se detiene y lo pide. No inventa una paleta.
5. El personal trabaja en laptop y el productor en celular. Las pantallas del productor deben funcionar a 360 px de ancho. Bajo 900 px la barra lateral se pliega en un botón de menú.
6. Decisión del equipo del 2026-10-05: la interfaz debe parecerse en su mayoría a ese HTML, no solo en colores sino en sus componentes y su composición: barra superior con la ruta de navegación, encabezado con antetítulo y descripción, secciones como control segmentado, fichas con la cabecera del inspector (avatar o código, insignias y una cifra destacada) y rejilla de datos, tarjetas de indicadores, tablas, avisos y tema claro u oscuro. Si choca con esta especificación en navegación, nombres de módulos, una tarea por pantalla o un botón principal, manda la especificación. Del HTML no se copian textos, datos de ejemplo ni lógica.

### Estructura de toda pantalla

1. Barra lateral: marca, nombre de la cooperativa, módulos y, al pie, nombre del usuario, rol, "Cerrar sesión" y "Contraer menú", que la deja solo con íconos.
2. Encabezado: título, ruta de navegación y como máximo un botón principal. La ruta va en una barra superior fija, junto al botón de tema claro u oscuro. Las fichas (productor, parcela, cooperativa, mi perfil) muestran el título dentro de la cabecera de su panel.
3. Secciones: pestañas secundarias bajo el título; solo una sección visible a la vez.
4. Los formularios largos se parten en pasos. Los listados van paginados y con buscador.
5. Una lista vacía explica qué va ahí y ofrece la acción para crear el primer registro.

### Módulos de la barra lateral

| Módulo | Ruta | Quién lo ve | Se construye en |
| --- | --- | --- | --- |
| Inicio | `#/inicio` | Personal | Parte 2, versión básica |
| Productores | `#/productores` | Personal | Partes 2 a 4 |
| Lotes y proceso | `#/lotes` | Personal | Partes 5 y 6 |
| Trazabilidad | `#/trazabilidad` | Personal | Parte 7 |
| Exportación | `#/exportacion` | Personal | Partes 8 y 9 |
| Cooperativa | `#/cooperativa` | Personal; Usuarios, Auditoría y Configuración solo `admin_cooperativa` | Partes 2, 5 y 8 |
| Plataforma | `#/plataforma` | `superadmin` | Parte 2 |
| Mi perfil, Mis parcelas, Mis entregas | `#/mi-perfil`, `#/mis-parcelas`, `#/mis-entregas` | `productor` | Partes 2 a 5 |

Los cuatro módulos principales son Productores, Lotes y proceso, Trazabilidad y Exportación. El cuarto se llama Exportación y no "Declaración EUDR" ni "TRACES NT": la DDS la presenta el importador, y la interfaz no debe sugerir que CacaoTrace la presenta.

Un módulo aún no construido muestra una pantalla vacía con su nombre.

### Pantallas que construye esta parte

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Ingreso | `#/ingreso` | Selector "Cooperativa" o "Productor"; correo o DNI; contraseña; texto de olvido de contraseña; aviso "Conectando con el servidor" |
| Cambio de contraseña | `#/cambiar-clave` | Contraseña actual, nueva y confirmación; única pantalla accesible mientras sea obligatorio |
| Consentimiento | `#/consentimiento` | Texto de consentimiento y botón de aceptar; solo productor, primer ingreso |
| Inicio | `#/inicio` | Saludo, nombre de la cooperativa y número de productores afiliados |
| Padrón de productores | `#/productores` | Lista con buscador, alta mínima y ficha con el botón "Crear acceso" |
| Usuarios | `#/cooperativa/usuarios` | Lista del personal, alta, cambio de rol, desactivación y restablecimiento de contraseña |
| Auditoría | `#/cooperativa/auditoria` | Tabla de acciones con filtros por fecha, usuario y acción |
| Cooperativas | `#/plataforma/cooperativas` | Lista, alta, suspensión y selector de cooperativa a consultar |
| Mi perfil | `#/mi-perfil` | Datos propios y cambio de contraseña |

Cuando el superadministrador consulta una cooperativa, una franja fija indica "Modo consulta" y el nombre de la cooperativa, y no se muestran botones de edición.

### Reglas técnicas de la interfaz

1. Navegación por hash, en `frontend/js/router.js`. Cada pantalla es un módulo en `frontend/js/pantallas/`.
2. `frontend/js/api.js` es el único archivo que llama a `fetch`. Agrega el token, maneja el aviso de espera, cierra sesión ante un 401 y redirige ante `cambio_clave_requerido`.
3. La sesión la administra `supabase-js`. El código propio no guarda tokens.
4. Ningún dato escrito por un usuario se inserta como HTML. Se usa `textContent` o una función de escape.
5. Todo texto visible está en español. Los campos tienen etiqueta, el foco es visible y el contraste es legible.

## Auditoría y consentimiento de datos

Toda acción que crea o cambia un dato queda registrada con autor, momento y detalle. En las partes siguientes ese registro demuestra quién declaró y quién validó cada DOP, y respalda el DEX.

### Auditoría

1. La función `registrar_auditoria(contexto, accion, entidad, entidad_id, detalle)` se llama dentro de la misma transacción que el cambio. Si el cambio se revierte, la fila de auditoría también.
2. La tabla solo admite inserciones. Un trigger de base de datos rechaza `UPDATE` y `DELETE` sobre `auditoria`, y no existe endpoint que la modifique.
3. `detalle` guarda los campos cambiados con su valor anterior y nuevo. Nunca contraseñas, tokens ni contenido de archivos.
4. Los inicios de sesión no se auditan aquí; los registra Supabase Auth.

### Acciones que audita esta parte

| Entidad | Acciones |
| --- | --- |
| Cooperativa | `cooperativa.crear`, `cooperativa.editar`, `cooperativa.suspender`, `cooperativa.reactivar` |
| Usuario | `usuario.crear`, `usuario.editar`, `usuario.desactivar`, `usuario.reactivar`, `usuario.restablecer_clave`, `usuario.cambiar_clave` |
| Productor | `productor.crear`, `productor.acceso_crear`, `productor.acceso_desactivar`, `productor.consentimiento` |
| Soporte | `superadmin.consultar_cooperativa`, cada vez que un superadministrador entra a ver una cooperativa |

### Consentimiento de datos personales

CacaoTrace guarda DNI, nombres, teléfono y ubicación de parcelas, que son datos personales del productor. El sistema registra su consentimiento antes de usarlos.

1. Vía productor: en su primer ingreso ve el texto de consentimiento y lo acepta. Se guarda `consentimiento_origen = productor`.
2. Vía cooperativa: al registrar a un productor, el personal marca la casilla "La cooperativa cuenta con el consentimiento firmado del productor". Se guarda `consentimiento_origen = cooperativa`.
3. En ambos casos se guarda `consentimiento_datos_en` y una fila de auditoría con la versión del texto aceptado.
4. El texto vive en un solo archivo, `frontend/textos/consentimiento.md`, con número de versión en la primera línea.
5. Claude Code no redacta el texto legal. Hasta que el equipo lo entregue, el archivo contiene la frase "TEXTO PENDIENTE DE REVISIÓN LEGAL" y la interfaz la muestra tal cual.
6. Un DOP no puede validarse si su productor no tiene consentimiento registrado. Esta regla se aplica en la Parte 5.

## Pruebas y aceptación de la Parte 2

La Parte 2 está terminada cuando los cinco roles entran en producción y cada uno ve solo lo suyo. Las pruebas automáticas simulan la API de administración de Supabase Auth.

### Pruebas automáticas mínimas

| Caso | Resultado esperado |
| --- | --- |
| Usuario de la cooperativa A pide un productor de B | 404 |
| Listado de productores de A | Solo trae productores de A |
| `operador` llama a `POST /usuarios` | 403 |
| `lector` llama a `POST /productores` | 403 |
| `productor` llama a `GET /productores` | 403 |
| Perfil con `debe_cambiar_clave` llama a un endpoint distinto de `/me` | 403 con `cambio_clave_requerido` |
| Usuario con `activo = false` | 403 con `cuenta_desactivada` |
| Usuario de una cooperativa suspendida | 403 con `cooperativa_suspendida` |
| `POST /usuarios` con correo ya usado | 409 con `correo_en_uso` |
| `POST /productores` con DNI de 7 dígitos o con letras | 422 |
| `POST /productores` con DNI afiliado a otra cooperativa | 409, sin nombrar la otra cooperativa |
| Segunda afiliación activa del mismo productor | Rechazada por el índice único |
| Desactivar al último administrador activo | 400 |
| Administrador intenta desactivarse o cambiar su propio rol | 400 |
| `superadmin` envía `POST /productores` con `X-Cooperativa-Id` | 403 |
| `operador` envía `X-Cooperativa-Id` de otra cooperativa | Se ignora; recibe datos de la suya |
| `UPDATE` o `DELETE` directo sobre `auditoria` | Rechazado por el trigger |
| Cada acción auditable | Crea su fila, sin contraseñas en `detalle` |
| Falla la creación del perfil tras crear el usuario en Auth | El usuario de Auth se elimina |

### Criterios de aceptación en producción

1. Con el script se crea el primer superadministrador, que inicia sesión.
2. El superadministrador crea dos cooperativas de prueba, cada una con su administrador.
3. Cada administrador entra, es obligado a cambiar su contraseña y crea un operador y un lector.
4. Un operador registra un productor y le crea su acceso.
5. El productor entra desde un celular con DNI y contraseña temporal, cambia la contraseña y acepta el consentimiento.
6. Desde la cooperativa A no se ve ningún dato de B, ni en pantallas ni cambiando identificadores en la URL.
7. El lector no ve botones de edición, y una llamada directa a la API responde 403.
8. Al suspender una cooperativa, ninguno de sus usuarios puede operar; al reactivarla, todos vuelven a entrar.
9. El restablecimiento de contraseña funciona en los cuatro casos de la tabla de olvido.
10. La auditoría muestra todas las acciones anteriores con autor y hora.
11. La barra lateral muestra los módulos correctos para cada uno de los cinco roles.
12. El CI está en verde, incluidas las pruebas de la Parte 1.

### Decisiones pendientes del equipo

- [ ] Entregar el texto legal del consentimiento y definir quién lo revisa.
- [ ] Subir el HTML del último rediseño a `legacy/diseno/`.
- [ ] Confirmar que el superadministrador puede ver los datos de las cooperativas en solo lectura.
- [ ] Confirmar que el operador puede crear accesos de productor y validar DOP.
- [ ] Confirmar los nombres de los módulos de la barra lateral.
- [ ] Confirmar el mínimo de 6 caracteres para la contraseña del productor.

## Parte 3 — Productor y parcela

El productor y sus parcelas se registran a mano, con documentos de sustento, y la parcela se captura dibujándola en el mapa o subiendo un archivo. No hay consulta automática a MIDAGRI.

### Objetivo de esta parte

Dejar completo el padrón: la ficha de cada productor y sus parcelas, con geometría validada y alertas de superposición. Estos registros se crean una vez y se reutilizan en cada DOP.

### Decisiones tomadas por el equipo

| Tema | Decisión |
| --- | --- |
| Datos de MIDAGRI | Se cargan manualmente o como documentos. CacaoTrace no consulta a MIDAGRI por DNI |
| Captura de la parcela | Dibujo sobre el mapa, carga de archivo (GeoJSON, KML, KMZ o Shapefile en .zip) o lista de coordenadas escrita o en hoja de cálculo |
| Carga masiva | El padrón de productores se puede cargar desde un Excel o un CSV |
| Unidad del DOP | Un DOP por parcela y por cada cosecha entregada. Se emite en la Parte 5 |
| Quién registra | El productor o el personal de la cooperativa |

### Consecuencia para el diseño

Como un DOP nace con cada cosecha, lo que no cambia entre cosechas vive en registros permanentes: el productor y la parcela. La parcela se habilita una sola vez, en la Parte 4, con su análisis de cobertura forestal y su expediente legal. El DOP de la Parte 5 solo referencia al productor y a la parcela, y agrega la tanda entregada.

Si en el futuro MIDAGRI ofrece una consulta automática, deberá llenar estos mismos campos. Por eso cada dato guarda su origen y su nivel de verificación.

### Fuera de alcance en esta parte

- Análisis de cobertura forestal y expediente legal de la parcela, que son la Parte 4, y recepción de la tanda, que es la Parte 5.
- Captura de la parcela caminando con GPS (archivos GPX).
- Coordenadas en UTM u otra proyección: se piden en grados de latitud y longitud (WGS 84).

## Ficha del productor

La ficha amplía la tabla `productores` de la Parte 2 con el registro en MIDAGRI, y cada dato muestra qué tan respaldado está.

### Niveles de verificación

Todo dato que termina en un DOP lleva uno de tres niveles. El importador que recibe el DEX debe saber en qué se apoya cada afirmación.

| Nivel | Significado | Cómo se alcanza en esta parte |
| --- | --- | --- |
| `declarado` | Alguien lo escribió; no hay respaldo | Dato ingresado sin documento |
| `documentado` | Hay un documento cargado que lo respalda | Documento vigente del tipo correspondiente |
| `verificado_en_fuente` | Se comprobó contra la fuente oficial | No se alcanza en esta parte |

El nivel no se guarda en una columna. La API lo calcula al responder, según existan documentos vigentes, para que nunca quede desactualizado.

### Campos de la ficha

| Dato | Columna | Obligatorio | Documento que lo eleva a `documentado` |
| --- | --- | --- | --- |
| DNI | `dni` | Sí | Copia del DNI, tipo `dni` |
| Nombres y apellidos, como figuran en el DNI | `nombres`, `apellidos` | Sí | Copia del DNI, tipo `dni` |
| RUC | `ruc` | No; 11 dígitos si se llena | No aplica |
| Dirección postal | `direccion_postal` | Sí | No aplica |
| Correo de contacto | `correo_contacto` | No | No aplica |
| Teléfono | `telefono` | No | No aplica |
| Está registrado en el PPA de MIDAGRI | `ppa_registrado` | Sí, por defecto `false` | Constancia o captura del PPA, tipo `constancia_ppa` |
| Número de registro en el PPA | `ppa_codigo` | Solo si `ppa_registrado` es `true` | Constancia o captura del PPA, tipo `constancia_ppa` |
| Código del productor en Agro Digital | `codigo_agrodigital` | No | No aplica |
| Código de socio en la cooperativa | `afiliaciones.codigo_socio` | No | No aplica |

Las columnas nuevas de `productores` son `ruc` (char(11)), `direccion_postal` (text), `correo_contacto` (text), `ppa_registrado` (boolean), `ppa_codigo` (text) y `codigo_agrodigital` (text). La dirección postal y el correo son los datos de contacto del proveedor que el artículo 9 del Reglamento pide reunir; el correo queda opcional porque muchos productores no lo tienen.

### Qué devuelve la API sobre un productor

Además de sus columnas, `GET /productores/{id}` devuelve tres campos calculados:

1. `nivel_identidad`: `declarado` o `documentado`.
2. `nivel_ppa`: `declarado`, `documentado` o `no_registrado`.
3. `pendientes`: lista de lo que falta para que el productor pueda respaldar un DOP. En esta parte los valores posibles son `sin_documento_dni`, `sin_consentimiento` y `sin_parcelas`.

### Reglas de edición

1. El personal con rol `admin_cooperativa` u `operador` edita todos los campos.
2. Corregir el DNI exige escribir un motivo, queda en auditoría con el valor anterior y actualiza el correo técnico de acceso.
3. El productor solo edita su teléfono y carga sus propios documentos. No cambia su DNI, sus nombres ni sus apellidos.
4. Un productor no se elimina. Se cierra su afiliación con fecha `hasta` y estado `inactiva`.

### Carga masiva de productores

1. El personal con rol `admin_cooperativa` u `operador` sube un Excel (.xlsx) o un CSV de hasta 2 MB y 1,000 filas, con una fila por productor.
2. Columnas obligatorias: DNI, nombres, apellidos y dirección postal. Opcionales: teléfono, correo, RUC, PPA (sí o no), código del PPA, código en Agro Digital y código de socio. Los encabezados se reconocen sin importar mayúsculas, tildes ni espacios, con nombres comunes como "Documento", "Domicilio" o "Celular"; las columnas desconocidas se ignoran y se informan. Puede haber filas de título antes de los encabezados.
3. Un DNI de 6 o 7 cifras se completa con ceros a la izquierda, porque Excel los borra. Si trae código del PPA y la columna PPA está vacía, se toma como registrado.
4. Primero se revisa: `POST /productores/carga-masiva/analizar` devuelve cada fila con su estado (`lista`, `error`, `repetida`, `ya_registrado` u `otra_cooperativa`) y sus mensajes, y no guarda nada. Un DNI de otra cooperativa se informa sin decir cuál.
5. Al confirmar, `POST /productores/carga-masiva` revisa el archivo de nuevo y registra solo las filas `lista`, en una sola transacción, con las mismas reglas y la misma auditoría (`productor.crear`) que el alta de uno en uno, más una fila `productor.carga_masiva` con el nombre del archivo y los totales. Las demás filas no se guardan.
6. La carga masiva no registra el consentimiento: cada productor queda con el pendiente `sin_consentimiento`.

## Documentos de sustento

Todos los archivos cargados, de esta parte y de las siguientes, se registran en una sola tabla `documentos`. El archivo vive en Supabase Storage; la tabla guarda dónde está y a qué respalda.

### Tabla `documentos`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa desde la que se cargó |
| `entidad` | text | A qué tipo de registro respalda. En esta parte: `productor` o `parcela` |
| `entidad_id` | uuid | Identificador de ese registro |
| `tipo` | text | Uno de los tipos del catálogo |
| `ruta` | text | Ruta en Storage, con el formato de la Parte 1 |
| `nombre_original` | text | Nombre del archivo al cargarlo |
| `tipo_mime` | text | Tipo detectado por contenido, no por extensión |
| `tamano_bytes` | integer | Tamaño del archivo |
| `sha256` | char(64) | Huella del contenido |
| `subido_por` | uuid | Perfil que lo cargó |
| `anulado_en`, `anulado_por`, `motivo_anulacion` | timestamptz, uuid, text | Se llenan al anular |

### Tipos de documento de esta parte

| Tipo | Respalda a | Formatos | Tope |
| --- | --- | --- | --- |
| `dni` | Productor | PDF, JPG, PNG | 10 MB |
| `constancia_ppa` | Productor | PDF, JPG, PNG | 10 MB |
| `sustento_midagri` | Parcela | PDF, JPG, PNG | 10 MB |
| `archivo_geometria` | Parcela | GeoJSON, KML, KMZ, Shapefile en .zip; .txt, .csv o .xlsx con coordenadas | 2 MB |

`sustento_midagri` es la constancia, el reporte o la captura que muestra la parcela registrada en MIDAGRI y su estado de validación.

### Reglas

1. Un documento no se borra. Se anula con un motivo, y un documento anulado deja de contar para el nivel de verificación.
2. Un documento es vigente mientras no esté anulado. Las fechas de vencimiento llegan en la Parte 4.
3. Cargar dos veces el mismo contenido para el mismo registro y tipo responde 409.
4. El productor ve y carga los documentos de su propia ficha y de sus parcelas. El personal ve los de los productores afiliados a su cooperativa.
5. La descarga es siempre por `GET /documentos/{id}/url`, que devuelve una URL firmada de 5 minutos.
6. El sistema no lee el contenido del documento. `documentado` significa que hay un archivo adjunto, no que alguien comprobó lo que dice. Esa revisión la hace una persona en la validación de la Parte 5.

## Parcelas

Una parcela es una porción continua de tierra de un productor, con una geometría en WGS 84. Un productor puede tener varias, y cada una se registra por separado. Cada parcela lleva un código corto en la columna codigo, con el formato PA- seguido de 5 dígitos, correlativo por cooperativa; es el nombre con que aparece en listados, documentos e informes.

### Tabla `parcelas`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `productor_id` | uuid | Referencia a `productores`, obligatoria |
| `nombre` | text | Nombre con que el productor conoce la parcela. Obligatorio y único por productor |
| `departamento`, `provincia`, `distrito` | text | Obligatorios |
| `centro_poblado` | text | Caserío o centro poblado, opcional |
| `tipo_geometria` | text | `poligono` o `punto` |
| `geometria` | geometry(Geometry, 4326) | Obligatoria. Solo `POLYGON` o `POINT`. Con índice GiST |
| `area_calculada_ha` | numeric(10,4) | Calculada por PostGIS para polígonos; nula para puntos |
| `area_declarada_ha` | numeric(10,4) | Obligatoria para puntos; opcional para polígonos |
| `area_cultivada_ha` | numeric(10,4) | Área con cacao. Obligatoria; no puede superar el área total |
| `origen_geometria` | text | `dibujada` o `archivo` |
| `archivo_documento_id` | uuid | Documento `archivo_geometria` de origen; obligatorio si el origen es `archivo` |
| `midagri_estado` | text | `no_registrada`, `sin_observacion`, `en_revision` o `validado`. Por defecto `no_registrada` |
| `midagri_codigo` | text | Código de la parcela en MIDAGRI, opcional |
| `estado` | text | `activa` o `inactiva` |
| `registrada_por`, `registrada_por_rol` | uuid, text | Quién la registró y con qué rol |
| `cooperativa_registro_id` | uuid | Cooperativa desde la que se registró |

El área total de una parcela es `area_calculada_ha` si es polígono y `area_declarada_ha` si es punto. El área se calcula con `ST_Area(geometria::geography) / 10000`.

### Aislamiento

La parcela pertenece al productor, no a la cooperativa. Igual que `productores`, se alcanza solo a través de una afiliación activa: el personal ve las parcelas de los productores afiliados a su cooperativa y el productor ve las suyas.

### Polígono o punto

El artículo 2(28) del Reglamento (UE) 2023/1115 exige polígono para parcelas de más de 4 ha. CacaoTrace aplica el corte del flujo operativo del equipo, que es algo más estricto: polígono desde 4 ha.

| Área total de la parcela | Geometría aceptada |
| --- | --- |
| Menos de 4 ha | Punto o polígono. La interfaz recomienda polígono |
| 4 ha o más | Solo polígono |

1. Un punto con `area_declarada_ha` de 4 o más se rechaza con el código `poligono_requerido`.
2. Las coordenadas se guardan sin redondear y se entregan con al menos 6 decimales.

### Estado en MIDAGRI

`midagri_estado` lo declara quien registra la parcela, con los mismos nombres que usa el tablero de MIDAGRI. La API devuelve además `nivel_midagri`: `no_registrada`, `declarado`, o `documentado` si existe un documento `sustento_midagri` vigente.

### Alertas de la parcela

La API devuelve en cada parcela una lista `alertas`. Ninguna impide guardar; todas se revisan al habilitar la parcela en la Parte 4.

| Alerta | Condición |
| --- | --- |
| `area_discrepante` | Polígono cuya área declarada difiere más de 20 % de la calculada |
| `diez_hectareas_o_mas` | Área total de 10 ha o más. El documento orientador de MIDAGRI recomienda acciones adicionales desde ese tamaño |
| `superposicion` | Existe al menos una superposición abierta con otra parcela |
| `sin_sustento_midagri` | `midagri_estado` distinto de `no_registrada` y sin documento que lo respalde |

### Cambios posteriores

1. Una parcela no se elimina; pasa a `inactiva`.
2. Cambiar la geometría de una parcela exige un motivo. La auditoría guarda la geometría anterior en formato WKT.
3. Cada DOP guarda su propia copia de la geometría al emitirse. Cambiar la parcela no altera los DOP ya emitidos; la Parte 5 define cuándo deben revalidarse.

## Geometría de la parcela

La geometría entra por dos caminos, dibujo o archivo, y ambos pasan por las mismas validaciones en el backend. Una geometría que falla una validación se rechaza; el sistema nunca la corrige por su cuenta.

### Dibujar en el mapa

1. El mapa usa Leaflet con el complemento Leaflet-Geoman en su versión gratuita, cargados desde CDN con versión fija.
2. Se puede dibujar un polígono o marcar un punto, y editar los vértices antes de guardar. Una parcela tiene una sola geometría.
3. El mapa ofrece una capa satelital, necesaria para reconocer el terreno, y una capa de calles.
4. Claude Code propone el proveedor de la capa satelital, confirma que sus términos permiten este uso, muestra su atribución y lo informa al equipo antes de integrarlo.
5. Un cuadro "Ir a coordenadas" centra el mapa en una latitud y longitud escritas por el usuario.
6. Mientras se dibuja, la interfaz muestra el área aproximada. El área definitiva es la que devuelve la API.

### Subir un archivo

1. Formatos aceptados: GeoJSON (`.geojson` o `.json`), KML (`.kml`), KMZ (`.kmz`, el KML comprimido de Google Earth), Shapefile comprimido en `.zip` con sus archivos `.shp`, `.shx`, `.dbf` y `.prj`, y listas de coordenadas (`.txt`, `.csv` o `.xlsx`). Como no se sabe en qué formato entrega MIDAGRI la parcela al productor, el sistema acepta todos estos.
2. Un `.shp` suelto o un `.dbf` se rechaza y el mensaje pide el `.zip` completo. Un Excel antiguo (`.xls`) se rechaza y el mensaje pide guardarlo como `.xlsx` o `.csv`. GPX y otros formatos se rechazan con `formato_no_admitido`.
3. `POST /parcelas/analizar-archivo` recibe el archivo y devuelve las geometrías que contiene, cada una con su tipo, su área, su nombre si lo trae y el resultado de las validaciones. No guarda nada.
4. La interfaz las dibuja en el mapa. Si el archivo trae varias, el usuario elige una.
5. Al guardar, la interfaz envía de nuevo el archivo junto con el índice elegido y los datos de la parcela. La API vuelve a analizarlo, y crea el documento `archivo_geometria` y la parcela en una sola transacción.
6. El KML se lee en el backend con un analizador XML seguro, como `defusedxml`. Solo se toman elementos `Polygon` y `Point`, y se ignora la altitud.
7. Los archivos comprimidos (KMZ, `.zip` y `.xlsx`) se rechazan sin abrirse si descomprimidos pasan de 50 MB o de 500 archivos.
8. Shapefile: si el `.prj` indica una proyección (por ejemplo UTM) o un datum distinto de WGS 84, se rechaza con `coordenadas_invalidas`. Sin `.prj`, valen las validaciones de coordenadas. El nombre de cada parcela se toma de la columna `nombre`, `name` o `parcela` del `.dbf`.

### Lista de coordenadas

La tercera forma de capturar la parcela es escribir o pegar sus coordenadas, por ejemplo copiadas de una constancia, de un reporte o de la app del productor. La interfaz las envía a la API como un archivo `coordenadas.txt`, que queda guardado como `archivo_geometria`. Las mismas reglas valen para un `.txt`, `.csv` o `.xlsx` subido.

1. Cada línea o fila es un vértice: latitud y longitud en grados, con punto o coma decimal, o en grados, minutos y segundos (`6°57'12"S 76°33'00"W`). Un solo vértice es un punto; tres o más, un polígono; dos se rechazan.
2. Si las columnas dicen "latitud" y "longitud" se usan; si no, cada valor se reconoce por su tamaño, porque en el Perú la latitud va de 0 a 18.5 y la longitud de 68.5 a 81.5, en valor absoluto. Si ambas vienen sin signo y sin hemisferio, se toman como sur y oeste.
3. Varias parcelas se separan con una línea en blanco, con una línea que solo trae el nombre o con una columna de nombre.
4. Los números enteros cortos al inicio de la línea se toman como numeración de vértices y se ignoran.
5. Valores en metros (UTM) se rechazan con `coordenadas_invalidas` y el mensaje pide grados. Una línea que no se entiende se rechaza indicando su número.

### Tipos de geometría

| Geometría recibida | Qué hace la API |
| --- | --- |
| `Polygon` sin huecos | La acepta |
| `Point` | Lo acepta |
| `MultiPolygon` con una sola parte | Lo convierte a `Polygon` |
| `MultiPolygon` con varias partes | Lo rechaza con el código varias\_partes y pide registrar cada parte como una parcela |
| `Polygon` con huecos | Lo rechaza con el código `poligono_con_huecos` |
| `LineString` u otro tipo | Lo rechaza con el código `tipo_no_admitido` |

### Validaciones automáticas

Viven en `backend/app/services/geometria.py` y se ejecutan en este orden.

| N.º | Regla | Código si falla |
| --- | --- | --- |
| 1 | Las coordenadas son números con latitud entre -90 y 90 y longitud entre -180 y 180 | `coordenadas_invalidas` |
| 2 | Si la geometría cae fuera del Perú pero cae dentro al intercambiar latitud y longitud, se informa que están invertidas | `coordenadas_invertidas` |
| 3 | Toda la geometría está dentro del rectángulo que contiene al Perú: latitud de -18.5 a 0.1, longitud de -81.5 a -68.5 | `fuera_de_peru` |
| 4 | El polígono tiene como máximo 2,000 vértices | `demasiados_vertices` |
| 5 | El polígono es válido según `ST_IsValid`, sin cruces entre sus lados | `geometria_invalida` |
| 6 | El área del polígono es de al menos 0.01 ha | `area_demasiado_pequena` |
| 7 | El área del polígono no supera 100 ha | `area_excesiva` |
| 8 | Un punto solo se acepta con área declarada menor que 4 ha | `poligono_requerido` |

Un valor fuera de rango en la regla 1 suele indicar coordenadas proyectadas, como UTM. El mensaje pide exportar el archivo en WGS 84.

Si el anillo de un polígono no repite el primer vértice al final, la API lo cierra. Es la única modificación que hace.

### Exportar

`GET /parcelas/{id}/geojson` devuelve un `Feature` de GeoJSON con la geometría y las propiedades `parcela_id`, `nombre`, `tipo_geometria` y `area_ha`. No incluye datos personales del productor. Las coordenadas salen con 8 decimales y el anillo en sentido antihorario.

## Superposición entre parcelas

Cada vez que se guarda una geometría, la API la compara con todas las parcelas activas de la plataforma. Una misma tierra no debe respaldar el cacao de dos productores. La única excepción son las parcelas de una cooperativa de demostración, que solo se comparan entre sí, según la Parte 10.

### Cuándo hay superposición

1. Entre dos polígonos: cuando el área común es de al menos 0.05 ha o de al menos 5 % de la parcela más pequeña. Por debajo de eso se considera imprecisión de linderos y se ignora.
2. Entre un punto y un polígono: cuando el punto cae dentro del polígono de otra parcela.
3. La búsqueda usa el índice GiST y `ST_Intersects`, y abarca todas las cooperativas.

### Tabla `superposiciones`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `parcela_a_id`, `parcela_b_id` | uuid | El par de parcelas. Único; `a` es siempre el identificador menor |
| `tipo` | text | `poligono_poligono` o `punto_en_poligono` |
| `area_ha` | numeric(10,4) | Área común; nula si el tipo es `punto_en_poligono` |
| `porcentaje` | numeric(5,2) | Área común sobre la parcela más pequeña |
| `estado` | text | `abierta`, `resuelta` o `aceptada` |
| `nota`, `cerrada_por`, `cerrada_en` | text, uuid, timestamptz | Se llenan al aceptar o resolver |

### Qué pasa en cada caso

| La otra parcela es | Al guardar | Quién ve qué |
| --- | --- | --- |
| Del mismo productor | Se rechaza con el código `superposicion_propia` | El usuario ve cuál de sus parcelas se superpone |
| De otro productor de la misma cooperativa | Se guarda y se abre una superposición | El personal ve ambas parcelas en el mapa |
| De un productor de otra cooperativa | Se guarda y se abre una superposición | Cada cooperativa ve solo su parcela, el área común y el aviso "superposición con una parcela de otra cooperativa" |

El productor ve en su parcela la alerta de superposición, sin datos de la otra parcela.

### Cómo se cierra

1. `resuelta`: se corrige una de las geometrías y la superposición desaparece. La API lo detecta sola al recalcular.
2. `aceptada` dentro de una cooperativa: un `admin_cooperativa` la acepta con una nota obligatoria que explica el caso.
3. `aceptada` entre cooperativas: solo un `superadmin` puede aceptarla, con nota, después de revisar ambos lados.
4. Al cambiar o desactivar cualquiera de las dos parcelas, la API recalcula sus superposiciones.
5. Una parcela con una superposición `abierta` no puede habilitarse. La regla se aplica en la Parte 4.

## Endpoints de la Parte 3

Los endpoints del personal trabajan sobre los productores afiliados a su cooperativa. Los del productor empiezan con `/mi` y solo tocan sus propios registros. Todos siguen las convenciones de la Parte 2.

### Productores

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /productores/{id}` | `admin_cooperativa`, `operador`, `lector` | Amplía la respuesta de la Parte 2 con `nivel_identidad`, `nivel_ppa`, `pendientes` y el resumen de parcelas |
| `PATCH /productores/{id}` | `admin_cooperativa`, `operador` | Edita la ficha. Cambiar el DNI exige el campo `motivo` |
| `POST /productores/{id}/afiliacion/cerrar` | `admin_cooperativa` | Cierra la afiliación y desactiva el acceso del productor |
| `POST /productores/carga-masiva/analizar` | `admin_cooperativa`, `operador` | Revisa una hoja de productores y devuelve el estado de cada fila. No guarda nada |
| `POST /productores/carga-masiva` | `admin_cooperativa`, `operador` | Registra las filas listas de la hoja |

### Documentos

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `POST /productores/{id}/documentos` | `admin_cooperativa`, `operador` | Carga un documento de tipo `dni` o `constancia_ppa` |
| `POST /parcelas/{id}/documentos` | `admin_cooperativa`, `operador` | Carga un documento de tipo `sustento_midagri` |
| `GET /documentos/{id}/url` | Personal de la cooperativa; productor dueño | Devuelve la URL firmada de descarga |
| `POST /documentos/{id}/anular` | `admin_cooperativa`, `operador` | Anula el documento con un motivo |

### Parcelas

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /parcelas` | `admin_cooperativa`, `operador`, `lector` | Lista las parcelas de la cooperativa, con filtros por productor, estado y alertas. Con `?formato=geojson` devuelve un `FeatureCollection` para el mapa |
| `GET /productores/{id}/parcelas` | `admin_cooperativa`, `operador`, `lector` | Parcelas de un productor |
| `POST /parcelas/analizar-archivo` | `admin_cooperativa`, `operador`, `productor` | Analiza un archivo de geometría o una lista de coordenadas y devuelve sus geometrías con validaciones. No guarda nada |
| `POST /productores/{id}/parcelas` | `admin_cooperativa`, `operador` | Crea una parcela, con geometría dibujada o con archivo e índice elegido |
| `GET /parcelas/{id}` | `admin_cooperativa`, `operador`, `lector` | Detalle con `nivel_midagri`, `alertas` y documentos |
| `PATCH /parcelas/{id}` | `admin_cooperativa`, `operador` | Edita datos. Cambiar la geometría exige `motivo` y repite validaciones y búsqueda de superposiciones |
| `POST /parcelas/{id}/desactivar` | `admin_cooperativa`, `operador` | Pasa la parcela a `inactiva` |
| `GET /parcelas/{id}/geojson` | `admin_cooperativa`, `operador`, `lector` | Exporta la geometría |

### Superposiciones

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /superposiciones` | `admin_cooperativa`, `operador`, `lector` | Lista las superposiciones que tocan parcelas de la cooperativa, con filtro por estado |
| `POST /superposiciones/{id}/aceptar` | `admin_cooperativa` | Acepta, con nota, una superposición entre parcelas de su misma cooperativa |
| `GET /admin/superposiciones` | `superadmin` | Lista las superposiciones abiertas entre cooperativas distintas |
| `POST /admin/superposiciones/{id}/aceptar` | `superadmin` | Acepta, con nota, una superposición entre cooperativas |

### Productor, sobre sus propios registros

| Método y ruta | Qué hace |
| --- | --- |
| `GET /mi/productor` | Su ficha, con `pendientes` |
| `PATCH /mi/productor` | Edita solo su teléfono |
| `POST /mi/documentos` | Carga su `dni` o su `constancia_ppa` |
| `GET /mi/parcelas` | Lista sus parcelas con alertas |
| `POST /mi/parcelas` | Crea una parcela propia |
| `GET /mi/parcelas/{id}` | Detalle de una parcela propia |
| `PATCH /mi/parcelas/{id}` | Edita una parcela propia, con las mismas reglas que el personal |
| `POST /mi/parcelas/{id}/documentos` | Carga un `sustento_midagri` |

Toda acción de esta parte que crea o modifica se audita con acciones como `productor.editar`, `documento.cargar`, `documento.anular`, `parcela.crear`, `parcela.editar_geometria`, `parcela.desactivar` y `superposicion.aceptar`.

## Pantallas de la Parte 3

El módulo Productores queda con tres secciones para el personal: Padrón, Mapa de parcelas y Superposiciones. El productor usa Mi perfil y Mis parcelas desde el celular.

### Personal de la cooperativa

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Padrón | `#/productores` | Lista con DNI, nombre, número de parcelas e indicador de pendientes; buscador; botón "Nuevo productor" y botón "Carga masiva", con plantilla CSV, revisión de cada fila y confirmación |
| Ficha del productor | `#/productores/{id}` | Encabezado con nombre, DNI y pendientes. Pestañas: Datos, Parcelas, Documentos, Acceso |
| Nueva parcela | `#/productores/{id}/parcelas/nueva` | Asistente de 3 pasos |
| Detalle de parcela | `#/parcelas/{id}` | Mapa, datos, alertas, documentos, botón de exportar GeoJSON e historial de cambios |
| Mapa de parcelas | `#/productores/mapa` | Todas las parcelas de la cooperativa sobre el mapa; al tocar una se abre su detalle |
| Superposiciones | `#/productores/superposiciones` | Lista de superposiciones abiertas; cada una muestra las parcelas en el mapa y permite aceptarla con nota |

### Pestañas de la ficha del productor

1. Datos: los campos de la ficha, cada uno con la etiqueta de su nivel de verificación.
2. Parcelas: lista con nombre, área, tipo de geometría, estado en MIDAGRI y alertas; botón "Nueva parcela".
3. Documentos: lista con tipo, fecha y quién lo cargó; acciones de ver, anular y cargar.
4. Acceso: estado de la cuenta del productor y las acciones de la Parte 2.

### Asistente de nueva parcela

1. Geometría: el usuario elige "Dibujar", "Subir archivo" o "Coordenadas". Los errores de validación aparecen aquí, junto al mapa, y no dejan avanzar.
2. Datos: nombre, ubicación, área declarada, área cultivada, estado en MIDAGRI, código y documento de sustento.
3. Revisión: área calculada, alertas y superposiciones detectadas. El botón "Guardar parcela" está solo en este paso.

### Productor

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Mi perfil | `#/mi-perfil` | Su ficha, sus pendientes en lenguaje simple y la carga de su DNI |
| Mis parcelas | `#/mis-parcelas` | Lista de sus parcelas con alertas y el mismo asistente de 3 pasos |

1. Los pendientes se muestran como frases, por ejemplo "Falta subir la foto de tu DNI".
2. La carga de documentos permite tomar la foto con la cámara del celular.
3. En el celular el mapa ocupa todo el ancho y el polígono se dibuja tocando cada vértice.

### Reglas visuales

1. Cada nivel de verificación tiene una etiqueta propia y constante en toda la aplicación: `declarado` en gris y `documentado` en esmeralda.
2. En el mapa, una parcela sin alertas, una con alertas y una con superposición abierta se distinguen por color y por una leyenda visible.
3. Los códigos de error de la API se traducen a mensajes en español que dicen qué hacer, no solo qué falló.

## Pruebas y aceptación de la Parte 3

La Parte 3 está terminada cuando una cooperativa puede dejar a un productor con su ficha documentada y sus parcelas en el mapa, por dibujo y por archivo, y las superposiciones se detectan solas.

### Datos de prueba

Los archivos de prueba viven en `backend/tests/datos/`. Claude Code los crea con coordenadas ficticias ubicadas en San Martín y nombres claramente inventados. No se usan datos de productores reales en pruebas ni en demostraciones.

### Pruebas automáticas mínimas

| Caso | Resultado esperado |
| --- | --- |
| Polígono válido de área conocida | Se crea; el área calculada difiere menos de 1 % de la esperada |
| Punto con área declarada de 3 ha | Se crea |
| Punto con área declarada de 5 ha | 400 con `poligono_requerido` |
| Polígono con lados cruzados | 400 con `geometria_invalida` |
| Coordenadas en UTM | 400 con `coordenadas_invalidas` |
| Latitud y longitud intercambiadas | 400 con `coordenadas_invertidas` |
| Polígono ubicado en otro país | 400 con `fuera_de_peru` |
| `MultiPolygon` de dos partes | 400 con `varias_partes` |
| Polígono con un hueco | 400 con `poligono_con_huecos` |
| KML y GeoJSON de la misma parcela | Producen la misma geometría |
| KML con una entidad XML externa | Se rechaza sin procesarla |
| Archivo con 3 geometrías, índice 1 | Analizar devuelve 3; crear guarda la segunda |
| Área declarada 2 ha, calculada 1.2 ha | Alerta `area_discrepante` |
| Polígono de 12 ha | Alerta `diez_hectareas_o_mas` |
| Dos parcelas del mismo productor superpuestas | 400 con `superposicion_propia` |
| Solape de 1 % y menos de 0.05 ha | No se registra superposición |
| Dos productores de la misma cooperativa, solape de 30 % | Ambas se guardan; superposición `abierta`; alerta en ambas |
| Solape entre cooperativas distintas | Cada una recibe solo su parcela y el área común |
| Se corrige la geometría y el solape desaparece | La superposición pasa a `resuelta` |
| `operador` intenta aceptar una superposición | 403 |
| `admin_cooperativa` acepta sin nota | 422 |
| Productor pide una parcela ajena en `/mi/parcelas/{id}` | 404 |
| Productor envía `nombres` en `PATCH /mi/productor` | 422 |
| KMZ, Shapefile en .zip, lista en .txt, .csv y .xlsx de la misma parcela | Producen la misma geometría que el GeoJSON |
| Shapefile con `.prj` en UTM | 400 con `coordenadas_invalidas` |
| `.shp` suelto, `.xls` o `.gpx` | 422 con `formato_no_admitido` |
| Zip que descomprimido pasa de 50 MB | Se rechaza sin abrirlo |
| Coordenadas en grados, minutos y segundos, sin signo o con la longitud primero | La misma geometría |
| Coordenadas en UTM en una lista | 400 con `coordenadas_invalidas` |
| Lista con dos vértices | Se rechaza |
| Hoja de carga masiva con filas válidas, repetidas, ya registradas, de otra cooperativa y con errores | Se registran solo las válidas; cada otra fila dice por qué |
| Hoja de carga masiva sin la columna de DNI | 422 con `columnas_faltantes` |
| Archivo ejecutable con extensión `.pdf` | 422 con `formato_no_admitido` |
| Mismo documento cargado dos veces | 409 |
| Se anula el único documento `dni` | `nivel_identidad` vuelve a `declarado` |
| Cambio de geometría sin `motivo` | 422 |
| Cambio de geometría con `motivo` | La auditoría guarda la geometría anterior en WKT |

Cada endpoint nuevo tiene además la prueba de las dos cooperativas definida en la Parte 2.

### Criterios de aceptación en producción

1. Un operador completa la ficha de un productor y carga su DNI; el nivel de identidad pasa a `documentado`.
2. El operador dibuja un polígono sobre la capa satelital y la parcela se guarda con su área calculada.
3. El operador crea una parcela desde un KML y otra desde un GeoJSON.
4. Un archivo inválido muestra un mensaje claro en español junto al mapa.
5. El productor, desde un celular, registra una parcela propia y carga la foto de su DNI con la cámara.
6. Una superposición entre dos productores aparece en la sección Superposiciones y en el mapa, y el administrador la acepta con nota.
7. En una superposición entre cooperativas, cada una ve solo su parcela.
8. El mapa de parcelas muestra todas las parcelas de la cooperativa con su leyenda.
9. El GeoJSON exportado se abre en una herramienta externa y cae en el lugar correcto.
10. Todos los cambios anteriores aparecen en la auditoría.
11. El CI está en verde, incluidas las pruebas de las Partes 1 y 2.
12. El operador registra varios productores desde un Excel y ve, antes de confirmar, qué filas tienen problemas.
13. El operador crea una parcela pegando sus coordenadas y otra desde un KMZ o un Shapefile.

### Decisiones pendientes del equipo

- [x] Confirmar qué es el "Código productor APP" del diagrama. Confirmado el 2026-10-05: es el código que el productor tiene en su app Agro Digital del MIDAGRI (`codigo_agrodigital`).
- [x] Confirmar en qué formato entrega MIDAGRI o Agro Digital la parcela al productor: archivo, constancia o captura. Respuesta del 2026-10-05: no se sabe con certeza, probablemente coordenadas; por eso se aceptan GeoJSON, KML, KMZ, Shapefile y listas de coordenadas.
- [x] Confirmar si se rechazan los polígonos con huecos. Confirmado el 2026-10-05: se rechazan.
- [x] Confirmar el tope de 100 ha por parcela. Confirmado el 2026-10-05.
- [x] Confirmar el umbral de superposición: 5 % o 0.05 ha. Confirmado el 2026-10-05.
- [x] Decidir si departamento, provincia y distrito se eligen de un catálogo oficial o se escriben. Decidido el 2026-10-05: se eligen del catálogo oficial del INEI (UBIGEO 2022, 1891 distritos, de datosabiertos.gob.pe) y se guardan con los nombres del INEI.
- [x] Decidir si se agrega la carga masiva de productores desde una hoja de cálculo. Decidido el 2026-10-05: sí, desde Excel o CSV.

## Parte 4 — Habilitación de la parcela

Una parcela puede respaldar cacao solo después de habilitarse, una vez, con tres piezas: geometría válida, análisis de cobertura forestal y expediente legal. Habilitarla o excluirla lo decide una persona de la cooperativa, no el sistema.

Esta parte corresponde a la etapa 1 del flujo operativo del equipo, "Habilitación de la parcela".

> **Estado:** cerrada el 2026-10-05 por decisión del equipo. El detalle de lo probado en producción y lo pendiente está en `CLAUDE.md`, sección "Estado por parte".
>
> **Adenda del 2026-10-05:** `docs/adenda-parte-4-fuentes.md` amplía esta parte. Agrega el detalle por capa de Whisp, dos consultas más a GFW, MapBiomas Perú como tercera fuente y la tabla de convergencia. Donde difiera de esta especificación, manda la adenda.

### Principio: exponer, no concluir

1. CacaoTrace no emite constancias, certificados ni veredictos de riesgo. Registra lo que dice cada fuente, con su nombre, su versión y su fecha.
2. La pieza se llama "análisis de cobertura forestal". El término "constancia de no deforestación" no aparece en ninguna pantalla, documento, campo ni mensaje.
3. El sistema no combina fuentes en un puntaje ni en un semáforo propio. Si dos fuentes dicen cosas distintas, muestra las dos.
4. Lo que no pudo comprobarse se registra como no comprobado y llega al informe de hallazgos de la Parte 9.
5. La fecha de corte del Reglamento es el 31 de diciembre de 2020.

La razón es de responsabilidad: quien emite una constancia o declara un riesgo responde por ella. La evaluación de riesgo le corresponde al operador que presenta la DDS; CacaoTrace le entrega los hechos ordenados.

### Qué cubre esta parte

| Pieza | Para qué sirve |
| --- | --- |
| Análisis de cobertura forestal por API | Reunir lo que dicen Whisp y GFW sobre la parcela, con fuente, versión y fecha |
| Visita de campo y procedencia de coordenadas | Registrar lo que un técnico vio en la parcela y si recorrió su lindero |
| Expediente legal de la parcela | Reunir los 7 documentos, con vencimientos, exenciones y cotejo |
| Compuerta de habilitación | Dejar constancia de quién decidió habilitar o excluir, y con qué evidencia a la vista |

## Análisis de cobertura forestal: fuentes

La primera versión consulta dos fuentes por API, Whisp y GFW, y muestra tres capas oficiales en el mapa para la revisión humana. Los datos de acceso vienen del archivo de APIs que el equipo verificó el 25 de septiembre de 2026.

### Fuentes consultadas por API

| Fuente | Papel | Acceso | Límite gratuito |
| --- | --- | --- | --- |
| Whisp, de FAO | Fuente principal. Entrega el riesgo EUDR de la parcela a partir de bosque al 2020, cultivos y cambios posteriores a 2020. Acepta puntos y polígonos | `POST https://whisp.openforis.org/api/submit/geojson`, encabezado `X-API-KEY` | 30 peticiones por minuto, 2 trabajos simultáneos, 5,000 geometrías por petición |
| GFW Data API | Segunda fuente. Alertas de deforestación y pérdida anual de cobertura dentro del polígono | `https://data-api.globalforestwatch.org`, encabezado `x-api-key` | La clave vence al año |

### Capas visuales en el mapa

| Capa | Qué muestra | Acceso |
| --- | --- | --- |
| Geobosques, MINAM | Bosque, no bosque y pérdida oficial del Perú | WMS sin autenticación |
| GeoSERFOR | Zonificación y ordenamiento forestal | WMS sin autenticación |
| JRC Global Forest Cover 2020 | Bosque al 2020 según el mapa de la Unión Europea | WMS |

Las capas son ayuda visual para quien revisa. El sistema no calcula nada con ellas.

### Fuera de la primera versión

Copernicus Sentinel Hub y el procesamiento de los rásteres de Hansen y MapBiomas quedan fuera. Procesar rásteres excede la memoria del plan gratuito de Render.

### Qué se consulta

1. Whisp: se envía un `FeatureCollection` con la parcela. De la respuesta se toma el riesgo para cultivos permanentes, que incluye cacao, y los indicadores que lo sustentan.
2. GFW, consulta de alertas: número de alertas integradas de deforestación dentro del polígono desde el 1 de enero de 2021, con el conjunto `gfw_integrated_alerts`.
3. GFW, consulta de pérdida: hectáreas de pérdida de cobertura arbórea por año desde 2021, con el conjunto `umd_tree_cover_loss`.
4. Parcela de tipo punto: Whisp recibe el punto. GFW consulta por polígono, así que recibe un círculo centrado en el punto con el área declarada, y el análisis queda marcado como aproximación.

### Reglas de integración

1. Antes de integrar, Claude Code confirma en la documentación oficial de cada fuente el endpoint, los parámetros y los nombres de los campos de respuesta. No asume ningún formato.
2. A las fuentes externas solo se envía la geometría y un identificador opaco. Nunca DNI, nombres ni datos de la cooperativa.
3. Cada fuente vive en su propio módulo, `backend/app/services/fuentes/whisp.py` y `backend/app/services/fuentes/gfw.py`, con la misma interfaz. Agregar una fuente no toca el resto del sistema.

## Modelo de datos del análisis

Cada consulta a una fuente es una fila de `analisis_cobertura`, atada a la geometría exacta que se analizó. La respuesta completa de la fuente se guarda como evidencia.

### Tabla `analisis_cobertura`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `parcela_id` | uuid | Referencia a `parcelas`, obligatoria |
| `cooperativa_id` | uuid | Cooperativa que solicitó el análisis |
| `fuente` | text | `whisp` o `gfw` |
| `estado` | text | `pendiente`, `en_proceso`, `completado` o `error` |
| `geometria` | geometry(Geometry, 4326) | Copia exacta de la geometría enviada |
| `geometria_sha256` | char(64) | Huella de la geometría de la parcela en ese momento |
| `es_aproximacion` | boolean | `true` si se analizó un círculo en lugar del punto |
| `resultado_fuente` | text | Valor que entrega la fuente, sin traducir ni reinterpretar. Nulo si la fuente no entrega uno |
| `indicadores` | jsonb | Cifras clave extraídas de la respuesta |
| `version_fuente` | text | Versión de la API o de las capas, tal como la informa la fuente |
| `respuesta_documento_id` | uuid | Documento `respuesta_analisis` con la respuesta completa |
| `solicitado_por`, `solicitado_en` | uuid, timestamptz | Quién lo pidió y cuándo. Nulo en `solicitado_por` si lo lanzó el sistema |
| `completado_en` | timestamptz | Momento en que la fuente respondió |
| `intentos` | integer | Número de intentos realizados |
| `error_detalle` | text | Causa del último fallo |

### Indicadores mínimos

| Fuente | Contenido de `indicadores` |
| --- | --- |
| `whisp` | Riesgo para cultivos permanentes; cobertura arbórea al 2020; perturbación antes y después de 2020; presencia de cultivos. Con los nombres de campo que entrega Whisp |
| `gfw` | `alertas_desde_2021`, `perdida_ha_por_anio` y el rango de fechas consultado |

### Evidencia

1. La respuesta completa de la fuente se guarda en Storage antes de interpretarla, como documento de tipo `respuesta_analisis`, en JSON, con su huella SHA-256.
2. Ese documento lo genera el sistema. Nadie puede cargarlo ni anularlo a mano.

### Campos calculados

La API agrega dos campos a cada análisis al responder.

| Campo | Valor |
| --- | --- |
| `obsoleto` | `true` si `geometria_sha256` ya no coincide con la geometría actual de la parcela |
| `vigente` | `true` si está `completado`, no es obsoleto y `completado_en` tiene menos de `ANALISIS_VIGENCIA_DIAS` días |

Un análisis nunca se borra ni se sobrescribe. Repetirlo crea una fila nueva; el historial queda.

## Ejecución del análisis

El análisis corre en segundo plano dentro de la misma API, una consulta externa a la vez, y la interfaz consulta su estado hasta que termina. El plan gratuito de Render no ofrece un proceso trabajador aparte.

### Cuándo se lanza

1. Automáticamente, al crear una parcela y cada vez que cambia su geometría.
2. A pedido, con el botón "Repetir análisis" de la parcela.
3. En ambos casos se crea una fila `pendiente` por cada fuente configurada y la API responde 202 de inmediato.

### Cómo se procesa

1. Un único bucle en segundo plano toma las filas `pendiente` en orden de llegada. Así nunca se superan los 2 trabajos simultáneos de Whisp.
2. Entre peticiones a una misma fuente se respeta un tope de 20 por minuto.
3. Cada petición tiene un tiempo máximo de 60 segundos. Si la fuente entrega el resultado de forma diferida, se sigue el mecanismo que indique su documentación.
4. Un fallo se reintenta hasta 3 veces, con esperas de 10 segundos, 1 minuto y 5 minutos. Después la fila queda en `error` con su `error_detalle`.
5. Al arrancar la API, toda fila `pendiente` o `en_proceso` con más de 10 minutos vuelve a la cola. Render reinicia el servicio con frecuencia.

### Lo que nunca se hace

1. No se generan resultados simulados fuera de las pruebas automáticas. Si una fuente falla, el análisis queda en `error`.
2. "Sin resultado" es un estado válido. Se muestra así y llega así al informe de hallazgos.
3. Un análisis en `error` no se convierte en `completado` a mano.

### Variables de entorno nuevas

Se suman a la tabla de la Parte 1 y se cargan en Render.

| Variable | Secreta | Descripción |
| --- | --- | --- |
| `WHISP_API_KEY` | Sí | Clave de Whisp. Se obtiene creando una cuenta en whisp.openforis.org |
| `GFW_API_KEY` | Sí | Clave de GFW Data API. Vence al año; su fecha de vencimiento se anota en el `README.md` |
| `ANALISIS_VIGENCIA_DIAS` | No | Días durante los que un análisis se considera vigente. Valor inicial: 180 |
| `AVISO_VENCIMIENTO_DIAS` | No | Días de anticipación con que un documento pasa a `por_vencer`. Valor inicial: 30 |

Si falta la clave de una fuente, esa fuente queda como "no configurada": no se crean análisis para ella y la interfaz lo indica. Las claves las crea y las carga una persona del equipo.

## Qué se muestra del análisis

El detalle de la parcela gana la sección "Cobertura forestal", con una tarjeta por fuente. Cada tarjeta dice quién afirma qué y cuándo; ninguna habla en nombre de CacaoTrace.

### Contenido de cada tarjeta

1. Nombre de la fuente, fecha del análisis y versión informada por la fuente.
2. Estado: en proceso, completado, error o fuente no configurada.
3. Si la geometría analizada es la actual, o si el análisis quedó obsoleto.
4. El resultado, siempre precedido por el nombre de la fuente.
5. Los indicadores que lo sustentan, con sus unidades.
6. Un enlace para descargar la respuesta completa.
7. La marca "Aproximación" cuando se analizó un círculo en lugar del punto.

### Texto del resultado

| Fuente | Valor recibido | Texto que se muestra |
| --- | --- | --- |
| Whisp | Riesgo bajo | "Whisp: riesgo bajo" |
| Whisp | Requiere más información | "Whisp: requiere más información" |
| Whisp | Riesgo alto | "Whisp: riesgo alto" |
| GFW | Cero alertas y cero pérdida | "GFW: sin alertas ni pérdida registrada desde 2021" |
| GFW | Alertas o pérdida mayores que cero | "GFW: N alertas y X ha de pérdida desde 2021" |

Los valores exactos que entrega Whisp se confirman en su documentación al integrar.

### Palabras que no se usan

Ninguna pantalla, mensaje ni documento generado contiene "constancia de no deforestación", "libre de deforestación", "certificado", "aprobado" ni "conforme" para referirse al análisis. Una prueba automática busca esas frases en el código y falla si las encuentra.

### Capas en el mapa

En el mapa de la parcela se pueden encender las capas de Geobosques, GeoSERFOR y JRC 2020, cada una con su atribución y su leyenda. Lo que el revisor observe ahí lo registra en una visita de campo o en la nota de habilitación.

### Alertas nuevas de la parcela

Se agregan a la lista `alertas` de la Parte 3.

| Alerta | Condición |
| --- | --- |
| `sin_analisis_vigente` | Alguna fuente configurada no tiene un análisis vigente |
| `analisis_requiere_revision` | Whisp entrega un valor distinto de riesgo bajo, o GFW informa alertas o pérdida desde 2021 |
| `analisis_con_error` | El último análisis de alguna fuente terminó en `error` |

`analisis_requiere_revision` no dice que haya deforestación. Dice que una persona debe mirar la parcela. El caso típico es el cacao bajo sombra, que desde el satélite se parece a un bosque.

### Vista del productor

El productor ve en su parcela las mismas tarjetas, sin el enlace a la respuesta completa.

## Visita de campo y procedencia

La visita de campo es el registro de lo que un técnico vio en la parcela. Es la respuesta del flujo a un análisis que "requiere más información", y la única forma de pasar una coordenada de "declarada" a "recorrida".

### Tabla `visitas_campo`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `parcela_id` | uuid | Referencia a `parcelas`, obligatoria |
| `cooperativa_id` | uuid | Cooperativa que hizo la visita |
| `fecha` | date | Día de la visita; no puede ser futura |
| `realizada_por_nombre`, `realizada_por_cargo` | text | Persona que estuvo en campo. Obligatorios |
| `registrada_por` | uuid | Perfil que la ingresó al sistema |
| `motivo` | text | `analisis_requiere_revision`, `verificacion_de_coordenadas` u `otro` |
| `perimetro_recorrido` | boolean | Si el técnico caminó el lindero de la parcela |
| `uso_observado` | text | `cacao_bajo_sombra`, `cacao_sin_sombra`, `bosque`, `otro_cultivo` o `mixto` |
| `descripcion` | text | Qué se observó. Obligatoria, mínimo 30 caracteres |
| `anulada_en`, `anulada_por`, `motivo_anulacion` | timestamptz, uuid, text | Se llenan al anular |

### Reglas

1. Toda visita lleva al menos una foto, cargada como documento de tipo `foto_visita`, en JPG o PNG.
2. Una visita no se edita. Si está mal, se anula con motivo y se registra otra.
3. La visita describe lo observado. No declara que la parcela cumple ni que no cumple.
4. Las visitas las registra el personal con rol `admin_cooperativa` u `operador`. El productor las ve, pero no las crea.

### Procedencia de la geometría

La API devuelve en cada parcela un objeto `procedencia`, calculado, que resume de dónde salen sus coordenadas. Alimenta los hallazgos de la Parte 9.

| Campo | Origen |
| --- | --- |
| `origen_geometria` | `dibujada` o `archivo`, de la Parte 3 |
| `registrada_por_rol` | Rol de quien la registró; `productor` significa coordenada declarada por el propio productor |
| `recorrida_en_campo` | `true` si existe una visita vigente con `perimetro_recorrido` posterior al último cambio de geometría |
| `fecha_recorrido` | Fecha de esa visita |

### Pantalla

El detalle de la parcela gana la pestaña "Visitas", con la lista de visitas, sus fotos y el botón "Registrar visita". El formulario cabe en un celular, porque suele llenarse en campo.

## Endpoints y pruebas del análisis y las visitas

Son ocho endpoints. Las pruebas simulan las llamadas HTTP a Whisp y GFW; ninguna prueba llama a las fuentes reales.

### Endpoints

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /analisis/fuentes` | Personal | Indica qué fuentes están configuradas |
| `POST /parcelas/{id}/analisis` | `admin_cooperativa`, `operador` | Solicita un análisis en cada fuente configurada. Responde 202 |
| `GET /parcelas/{id}/analisis` | Personal | Lista los análisis de la parcela, con `vigente` y `obsoleto` |
| `GET /analisis/{id}` | Personal | Detalle, con la URL firmada de la respuesta completa |
| `GET /mi/parcelas/{id}/analisis` | `productor` | Análisis de una parcela propia, sin la respuesta completa |
| `POST /parcelas/{id}/visitas` | `admin_cooperativa`, `operador` | Registra una visita con sus fotos |
| `GET /parcelas/{id}/visitas` | Personal; productor dueño por `/mi/parcelas/{id}/visitas` | Lista las visitas |
| `POST /visitas/{id}/anular` | `admin_cooperativa` | Anula una visita con motivo |

Se auditan `analisis.solicitar`, `visita.registrar` y `visita.anular`. Los análisis lanzados por el sistema quedan en auditoría con usuario nulo.

### Ejemplos de respuesta para las pruebas

Claude Code no inventa el formato de respuesta de Whisp ni de GFW. Una persona del equipo hace una llamada real con una parcela ficticia y guarda las respuestas en `backend/tests/datos/`. Las pruebas se escriben contra esos archivos.

### Notas de implementación (2026-10-05)

Tomadas de la documentación oficial de cada servicio, consultada el 2026-10-05.

1. Reintentos: hay 3 intentos en total por fila, con esperas de 10 segundos y 1 minuto entre ellos, para que "Whisp responde 500 tres veces" termine en `error` como pide la prueba. El equipo dejó la decisión a Claude Code el 2026-10-05. Una fila en `error` se vuelve a pedir con "Repetir análisis".
2. Whisp: `POST /api/submit/geojson` con el encabezado `x-api-key` y `analysisOptions` `{"externalIdColumn": "id", "unitType": "ha"}`. El identificador enviado es el del análisis, nunca datos de la parcela ni del productor. `resultado_fuente` es `risk_pcrop` (`low`, `more_info_needed` o `high`), el riesgo para cultivos permanentes, que incluye cacao. Todo valor distinto de `low`, o la falta de valor, pide revisión en campo. Un 429 trae la espera en el mensaje, no en un encabezado.
3. GFW: dos consultas por análisis, a `gfw_integrated_alerts` (alertas desde el 2021-01-01) y a `umd_tree_cover_loss` (pérdida desde 2021 con densidad de copa al 2000 mayor a 30 %, el valor por defecto de la plataforma de GFW). La versión del conjunto sale de la redirección de `latest`. GFW no entrega un veredicto, así que `resultado_fuente` queda vacío; alertas o pérdida mayores a cero piden revisión.
4. La respuesta completa se guarda en Storage antes de interpretarla. Si no tiene la forma esperada, el análisis queda `completado` sin resultado, con el motivo en `error_detalle`, y pide revisión en campo: una columna que falta nunca se lee como cero.
5. Capas WMS: Geobosques `gis.bosques.gob.pe/server/services/Interoperabilidad/bosque_humedo_2025/MapServer/WMSServer` (capas 0, 2, 3 y 5), GeoSERFOR `geo.serfor.gob.pe/geoservicios/services/Servicios_OGC/Zonificacion_Forestal/MapServer/WMSServer` (capa 0) y JRC `ies-ows.jrc.ec.europa.eu/iforce/gfc2020/wms.py` (capa `gfc2020_v4`, cita Bourgoin et al. 2026, doi:10.2905/JRC.3KATEH8).
6. La clave de GFW (alias `cacaotrace`) se creó el 2026-10-05 y vence el 2027-10-05, porque GFW la da por un año. La fecha está anotada en el `README.md`.
7. Decisión del equipo del 2026-10-05: la sección Cobertura forestal se lee de un vistazo. Arriba, "Qué revisar en esta parcela" dice en palabras, conjunto por conjunto, qué vio, cuánto y cuándo (bosque el 31/12/2020 o cambios desde el 1 de enero de 2021), explica que el 31/12/2020 es la fecha de corte y no una pérdida, y dice qué hacer (una visita de campo); si nada pide revisión, lo dice en una línea. Cada tarjeta muestra fuente, fecha, versión, resultado y si pide revisión; si la pide, se ven solo las cifras que la piden. Los indicadores, el detalle por capa, el historial de MapBiomas y la descarga de la respuesta completa quedan plegados en "Ver indicadores y detalle". De la tabla de convergencia se ven la frase de conteo y las filas que registran bosque en 2020 o cambios; la tabla completa queda plegada. La API dice en cada análisis si pide revisión (`requiere_revision`), con la regla de su fuente.
8. Decisiones del equipo del 2026-10-05 (adenda, 7.2 reglas 1 y 3): hubo bosque en la parcela el 31/12/2020 si al menos 3 conjuntos lo registran; solo entonces pide revisión, y solo entonces piden revisión las alertas DIST de GFW. Con 1 o 2 mapas, la pantalla lo muestra como dato. La API dice `hubo_bosque_2020` y `mapas_minimos_bosque_2020` en la tabla de convergencia. Sin bosque ese día, la tarjeta y el resumen las muestran como dato y explican que marcan cualquier cambio de la vegetación.

### Pruebas automáticas mínimas

| Caso | Resultado esperado |
| --- | --- |
| Se crea una parcela con las dos fuentes configuradas | Dos filas `pendiente`, una por fuente |
| Whisp responde con el ejemplo guardado | Fila `completado`; `resultado_fuente` igual al valor de la respuesta; respuesta guardada como documento con su SHA-256 |
| Whisp responde 500 tres veces | Fila en `error` con `error_detalle`; ningún resultado |
| Whisp responde 429 | Se reintenta respetando la espera |
| Falta `WHISP_API_KEY` | No se crean filas de `whisp`; `GET /analisis/fuentes` lo informa |
| Cambia la geometría de la parcela | Los análisis previos quedan `obsoleto` y se solicita uno nuevo |
| Análisis con más días que `ANALISIS_VIGENCIA_DIAS` | `vigente` es `false` |
| Parcela de tipo punto | GFW recibe un círculo con el área declarada; `es_aproximacion` es `true` |
| Contenido enviado a las fuentes | No incluye DNI, nombres ni nombre de la cooperativa |
| La API arranca con una fila `en_proceso` de hace 20 minutos | La fila vuelve a la cola |
| Búsqueda de frases prohibidas en el código | No aparece ninguna |
| Visita sin descripción o sin foto | 422 |
| Visita con `perimetro_recorrido` posterior al último cambio de geometría | `procedencia.recorrida_en_campo` es `true` |
| Cambia la geometría después de la visita | `procedencia.recorrida_en_campo` vuelve a `false` |
| Productor intenta registrar una visita | 403 |

Cada endpoint tiene además la prueba de las dos cooperativas definida en la Parte 2.

## Expediente legal de la parcela

Cada parcela tiene un expediente de 7 casillas, una por tipo de documento. La tenencia exige al menos un documento; las otras cinco casillas se cubren con un documento o con una exención motivada.

### Los 7 documentos

| Código | Documento | Grupo | Cómo se cubre la casilla | Registro público consultable |
| --- | --- | --- | --- | --- |
| `titulo_sunarp` | Título de propiedad inscrito en SUNARP | Tenencia | Al menos uno de los dos de tenencia | Sí |
| `constancia_posesion` | Constancia de posesión | Tenencia | Al menos uno de los dos de tenencia | No |
| `cusaf` | Contrato de cesión en uso para sistemas agroforestales | Uso forestal | Documento o exención | Sí |
| `autorizacion_serfor` | Autorización forestal de SERFOR o de la autoridad regional | Uso forestal | Documento o exención | No |
| `sunafil` | Sustento laboral ante SUNAFIL | Laboral | Documento o exención | Sí |
| `sunat` | Ficha RUC u otro sustento de SUNAT | Tributario | Documento o exención | Sí |
| `zonificacion` | Sustento de la zonificación forestal de la parcela | Zonificación | Documento o exención | Sí |

El catálogo vive en `backend/app/catalogos/documentos_legales.py`, de modo que cambiar un valor no exige una migración.

#### Registros, vigencias y sustento de SUNAFIL (confirmados el 2026-10-05)

Se revisaron fuentes oficiales: gob.pe, SUNARP, SUNAT, SUNAFIL, SERFOR y GeoSERFOR, MIDAGRI y El Peruano.

| Código | Dónde se coteja | Vigencia legal |
| --- | --- | --- |
| `titulo_sunarp` | "Conoce Aquí" de SUNARP (conoce-aqui.sunarp.gob.pe), con el número de partida y la oficina registral. Es gratis | No vence: el asiento surte efecto mientras no se rectifique o anule (art. 2013 del Código Civil) |
| `constancia_posesion` | No tiene registro en línea. La agencia agraria o la municipalidad que la emite lleva un registro administrativo (RM 0029-2020-MINAGRI, art. 8) | La norma no le fija plazo. Solo prueba posesión y no reconoce un derecho real (art. 3) |
| `cusaf` | GeoSERFOR, capa "Cesiones en uso": número, inicio, término y situación del contrato | 40 años, renovables por otros 40 (D.S. 020-2015-MINAGRI, arts. 58 y 61) |
| `autorizacion_serfor` | No tiene registro en línea completo: GeoSERFOR casi no publica las autorizaciones regionales | Ninguna norma nacional le fija plazo: lo pone cada resolución |
| `sunafil` | Buscador de resoluciones del sistema inspectivo de SUNAFIL, por RUC o razón social. Es gratis | No vence: la consulta vale a su fecha |
| `sunat` | Consulta RUC de SUNAT (estado y condición). La Ficha RUC electrónica trae un QR para validarla | No vence: cuenta el estado (activo) y la condición (habido) a la fecha |
| `zonificacion` | GeoSERFOR, capa Zonificación Forestal, con la resolución que la aprueba. Al 2026-10-05 solo la tienen Amazonas, Huánuco, Junín, Loreto, Madre de Dios, San Martín y Ucayali | No vence: la aprueba una resolución ministerial (Ley 29763, art. 33, modificado por la Ley 31973) |

1. **Vencimiento:** ningún tipo exige `fecha_vencimiento`. Se llena cuando el documento trae un término, como el CUSAF o una autorización con plazo.
2. **Sustento de SUNAFIL:** SUNAFIL no emite constancias para el empleador. El sustento es la búsqueda, por el RUC del productor, en el buscador de resoluciones del sistema inspectivo, guardada como PDF o captura donde se vean la fecha y el resultado. Al productor sin RUC o sin trabajadores no le corresponde ese documento: se declara una exención con ese motivo.
3. **Autorización forestal:** según la Ley 31973 (Única Disposición Complementaria Final), a un predio privado le corresponde la exención con ese motivo si cumple estas condiciones:
   - Tiene título o constancia de posesión anteriores a esa ley.
   - No tiene masa boscosa y sí tiene actividad agropecuaria.
   - Conserva el 30 % de reserva de bosque.

   Esa disposición seguiría vigente tras la sentencia del Tribunal Constitucional en el Exp. 00002-2024-AI, que no se leyó completa. La exención la decide la cooperativa caso por caso.

### Datos de cada documento legal

Los documentos legales usan la tabla `documentos` de la Parte 3, con `entidad = parcela`. La tabla gana estas columnas, todas opcionales para los demás tipos.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `numero` | text | Número de partida, de constancia o de contrato. Obligatorio en documentos legales |
| `entidad_emisora` | text | Quién lo emitió. Obligatoria en documentos legales |
| `fecha_emision` | date | Obligatoria en documentos legales; no puede ser futura |
| `fecha_vencimiento` | date | Opcional. Si se llena, debe ser posterior a la emisión |
| `cotejado_en`, `cotejado_por`, `cotejo_nota` | timestamptz, uuid, text | Se llenan al registrar un cotejo en fuente |

### Reglas de carga

1. Formatos y tope: PDF, JPG o PNG, hasta 10 MB, como los demás documentos.
2. Los carga el personal con rol `admin_cooperativa` u `operador`, o el productor sobre sus propias parcelas.
3. Una casilla puede tener varios documentos. Cuenta el vigente con vencimiento más lejano.
4. Anular un documento sigue las reglas de la Parte 3 y puede dejar la casilla sin cubrir.

## Estado del expediente, exenciones y cotejo

El estado de cada casilla y del expediente completo se calcula al consultar, con la fecha del día. Nada de esto se guarda en columnas que puedan quedar desactualizadas.

### Estado de cada casilla

| Estado | Condición |
| --- | --- |
| `vigente` | Hay un documento no anulado, sin vencimiento o con vencimiento a más de 30 días |
| `por_vencer` | El documento que cubre la casilla vence en 30 días o menos |
| `vencido` | Solo hay documentos con vencimiento pasado |
| `no_aplica` | Hay una exención vigente y ningún documento |
| `faltante` | No hay documento ni exención |

Los 30 días salen de la variable `AVISO_VENCIMIENTO_DIAS`.

### Estado del expediente

El expediente está `completo` cuando se cumplen las dos condiciones:

1. Tenencia: al menos una de las casillas `titulo_sunarp` o `constancia_posesion` está `vigente` o `por_vencer`.
2. Las otras cinco casillas están `vigente`, `por_vencer` o `no_aplica`.

En cualquier otro caso está `incompleto`, y la API devuelve qué casillas faltan.

### Exenciones

Una exención declara que un documento no aplica a esa parcela. Por ejemplo, el CUSAF no aplica a una parcela en tierra privada titulada.

| Columna de `exenciones_documento` | Tipo | Regla |
| --- | --- | --- |
| `parcela_id` | uuid | Referencia a `parcelas` |
| `tipo` | text | Uno de los cinco tipos que admiten exención |
| `motivo` | text | Por qué no aplica. Obligatorio, mínimo 30 caracteres |
| `declarada_por`, `declarada_en` | uuid, timestamptz | Quién y cuándo |
| `retirada_en`, `retirada_por` | timestamptz, uuid | Se llenan al retirarla |

1. Solo un `admin_cooperativa` declara o retira una exención.
2. Los dos documentos de tenencia no admiten exención.
3. Toda exención vigente aparece, con su motivo, en el informe de hallazgos de la Parte 9.

### Cotejo en fuente

Cotejar es comprobar el documento contra el registro público de quien lo emitió, y dejar constancia de quién lo hizo y cuándo.

1. Solo se puede cotejar un documento cuyo tipo tiene registro público consultable.
2. El cotejo lo hace una persona y lo registra con una nota que dice qué consultó y qué encontró.
3. Un documento cotejado sube a `verificado_en_fuente`. Uno sin cotejar queda en `documentado`.
4. Un documento cuyo tipo no tiene registro consultable nunca pasa de `documentado`, y así se informa en los hallazgos.

### Alertas nuevas de la parcela

| Alerta | Condición |
| --- | --- |
| `expediente_incompleto` | El expediente no está `completo` |
| `documento_por_vencer` | Alguna casilla está `por_vencer` |
| `documento_vencido` | Alguna casilla está `vencido` |
| `tenencia_solo_posesion` | La tenencia se apoya solo en una constancia de posesión, que no tiene registro público contra el cual cotejarse |

## Compuerta de habilitación

La parcela pasa por cuatro estados de habilitación. Solo un administrador de la cooperativa la habilita o la excluye, y la exclusión no tiene vuelta atrás.

### Estados

&#91;embedded content: estados de habilitación · 4 estados, 6 transiciones\]

Desde cualquier estado se puede excluir; de la exclusión no sale ninguna flecha.

| Estado | Significado | Quién lo fija |
| --- | --- | --- |
| `pendiente` | Nunca se ha habilitado | Valor inicial |
| `habilitada` | Puede respaldar tandas y DOP | `admin_cooperativa` |
| `observada` | Estuvo habilitada y dejó de cumplir un requisito. Se puede recuperar | El sistema |
| `excluida` | Se confirmó deforestación posterior al 31 de diciembre de 2020. Definitivo | `admin_cooperativa` |

El estado se guarda en la columna nueva `habilitacion_estado` de `parcelas`. Solo una parcela `habilitada` puede recibir tandas en la Parte 5.

### Requisitos para habilitar

La API calcula la lista `requisitos` de cada parcela. Cada requisito dice si se cumple y, si no, por qué.

| Requisito | Se cumple cuando |
| --- | --- |
| `parcela_activa` | La parcela está `activa` |
| `sin_superposiciones_abiertas` | No tiene superposiciones en estado `abierta` |
| `analisis_vigente` | Hay al menos una fuente configurada y cada fuente configurada tiene un análisis vigente |
| `revision_atendida` | No hay alerta `analisis_requiere_revision`, o existe una visita de campo vigente por ese motivo, posterior al último cambio de geometría y con menos de 365 días |
| `expediente_completo` | El expediente legal está `completo` |
| `productor_listo` | El productor tiene su DNI en nivel `documentado` y su consentimiento registrado |

### Decisión de habilitar

1. La toma solo un `admin_cooperativa`. El operador prepara la parcela, pero no decide.
2. Si falta algún requisito, la API responde 400 con el código `requisitos_incompletos` y la lista. No existe forma de saltarse un requisito.
3. Si la parcela tiene alguna alerta al momento de decidir, la nota es obligatoria, con un mínimo de 50 caracteres, y explica por qué se habilita a pesar de ella.
4. Habilitar no es declarar que la parcela cumple el Reglamento. Es la decisión de la cooperativa de aceptar cacao de esa parcela, con las evidencias a la vista.

### Tabla `decisiones_habilitacion`

Cada decisión es una fila que no se edita ni se borra; un trigger rechaza `UPDATE` y `DELETE`.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `parcela_id` | uuid | Referencia a `parcelas` |
| `decision` | text | `habilitar`, `observar` o `excluir` |
| `decidida_por` | uuid | Perfil que decidió. Nulo cuando decide el sistema |
| `decidida_en` | timestamptz | Momento de la decisión |
| `nota` | text | Explicación de la decisión |
| `requisitos` | jsonb | Copia de los requisitos y las alertas tal como estaban al decidir |
| `geometria_sha256` | char(64) | Huella de la geometría al decidir |
| `evidencia_visita_id`, `evidencia_analisis_id` | uuid | Evidencia citada en una exclusión |

### Paso automático a observada

1. Una parcela `habilitada` pasa a `observada` cuando deja de cumplir cualquier requisito: vence un documento, se anula un documento o una visita, cambia la geometría, aparece una superposición o el análisis pierde vigencia.
2. La condición se evalúa en cada lectura o escritura de la parcela y en una tarea diaria del bucle en segundo plano.
3. El sistema registra una decisión `observar` que nombra el requisito incumplido. No es un juicio de riesgo; es el control de que los requisitos siguen en pie.
4. Para volver a `habilitada`, un administrador decide de nuevo.
5. La tarea diaria solicita un análisis nuevo 15 días antes de que el vigente caduque, para que una parcela no quede observada solo por antigüedad.

### Exclusión

1. El único motivo admitido es la deforestación confirmada después del 31 de diciembre de 2020. Una parcela a la que le falta un documento no se excluye; queda `pendiente` u `observada`.
2. La exclusión exige una descripción de al menos 50 caracteres, la referencia a una visita de campo o a un análisis de esa parcela, y escribir la palabra `EXCLUIR` para confirmar.
3. Una parcela `excluida` no se edita, no se habilita, no recibe documentos ni respalda tandas nuevas.
4. Ningún endpoint revierte una exclusión, tampoco para el `superadmin`.
5. La parcela y su historial siguen visibles. Su geometría sigue en la búsqueda de superposiciones: una parcela nueva que se superponga con una excluida recibe la alerta `superposicion_con_excluida`.
6. La interfaz muestra un diálogo que explica que la acción es definitiva antes de pedir la confirmación.

## Endpoints y pantallas del expediente y la compuerta

El operador y el productor arman el expediente; el administrador decide. La interfaz muestra en todo momento qué falta para habilitar.

### Endpoints

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `POST /parcelas/{id}/documentos` | `admin_cooperativa`, `operador` | Se amplía: acepta los 7 tipos legales con número, entidad emisora, fecha de emisión y vencimiento |
| `POST /mi/parcelas/{id}/documentos` | `productor` | Se amplía igual, sobre parcelas propias |
| `GET /parcelas/{id}/expediente` | Personal; productor dueño por `/mi/parcelas/{id}/expediente` | Las 7 casillas con su estado, sus documentos y sus exenciones |
| `POST /documentos/{id}/cotejo` | `admin_cooperativa`, `operador` | Registra el cotejo en fuente con su nota |
| `POST /parcelas/{id}/exenciones` | `admin_cooperativa` | Declara que un tipo de documento no aplica, con motivo |
| `POST /exenciones/{id}/retirar` | `admin_cooperativa` | Retira una exención |
| `GET /parcelas/{id}/habilitacion` | Personal; productor dueño por `/mi/parcelas/{id}/habilitacion` | Estado, lista de `requisitos` e historial de decisiones |
| `POST /parcelas/{id}/habilitar` | `admin_cooperativa` | Habilita la parcela. Recibe `nota` |
| `POST /parcelas/{id}/excluir` | `admin_cooperativa` | Excluye la parcela. Recibe `descripcion`, la evidencia y `confirmacion` |
| `GET /habilitacion/resumen` | Personal | Número de parcelas por estado y lista de documentos por vencer |

Se auditan `documento.cotejar`, `exencion.declarar`, `exencion.retirar`, `parcela.habilitar`, `parcela.observar` y `parcela.excluir`.

### Pantallas

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Habilitación | `#/productores/habilitacion` | Cuarta sección del módulo Productores. Parcelas agrupadas por estado, con lo que le falta a cada una, y la lista de documentos por vencer |
| Detalle de parcela, pestaña Expediente | `#/parcelas/{id}` | Las 7 casillas como lista, cada una con su estado, su nivel de verificación y las acciones de cargar, cotejar y declarar exención |
| Detalle de parcela, pestaña Habilitación | `#/parcelas/{id}` | Lista de requisitos con una marca por cada uno, historial de decisiones y, para el administrador, los botones "Habilitar" y "Excluir" |
| Mis parcelas, productor | `#/mis-parcelas` | Estado de habilitación de cada parcela y lo que le falta, en lenguaje simple |

### Reglas de la interfaz

1. El botón "Habilitar" está apagado mientras falte un requisito, y al pasar sobre él se listan los que faltan.
2. El operador ve los requisitos, pero no los botones de decisión.
3. "Excluir" abre un diálogo que explica que la acción es definitiva, pide la descripción y la evidencia, y exige escribir `EXCLUIR`.
4. Una parcela `excluida` se muestra con una franja fija que lo indica y sin ninguna acción de edición.
5. Los estados se nombran siempre igual: Pendiente, Habilitada, Observada y Excluida. No se usan "aprobada" ni "conforme".

## Pruebas y aceptación de la Parte 4

La Parte 4 está terminada cuando una parcela real de prueba recorre el camino completo: análisis de las dos fuentes, expediente, decisión del administrador y paso automático a observada al vencer un documento.

### Pruebas automáticas del expediente y la compuerta

Se suman a las pruebas del análisis y de las visitas listadas más arriba.

| Caso | Resultado esperado |
| --- | --- |
| Título vigente y las otras cinco casillas con documento | Expediente `completo` |
| Solo constancia de posesión como tenencia | Tenencia cumplida; alerta `tenencia_solo_posesion` |
| Sin título ni constancia | Expediente `incompleto` |
| Exención sobre un documento de tenencia | 422 |
| Exención sin motivo, o declarada por un `operador` | 422 y 403 |
| Documento con vencimiento ayer | Casilla `vencido` |
| Documento que vence en 10 días | Casilla `por_vencer`; alerta `documento_por_vencer` |
| Cotejo sobre una constancia de posesión | 400 con `sin_registro_consultable` |
| Cotejo sobre un título de SUNARP | Nivel `verificado_en_fuente` |
| `operador` llama a `POST /parcelas/{id}/habilitar` | 403 |
| Habilitar con un requisito sin cumplir | 400 con `requisitos_incompletos` y la lista |
| Habilitar sin ninguna fuente de análisis configurada | 400; `analisis_vigente` no se cumple |
| Alerta `analisis_requiere_revision` sin visita de campo | `revision_atendida` no se cumple |
| Misma alerta, con visita y sin nota | 422 |
| Misma alerta, con visita y nota | La parcela pasa a `habilitada` |
| Toda decisión | Guarda la copia de requisitos y alertas del momento |
| Parcela habilitada cuyo documento vence | Pasa a `observada`; queda una decisión `observar` con usuario nulo |
| Parcela habilitada cuya geometría cambia | Pasa a `observada` |
| Parcela observada, se corrige el requisito y el administrador habilita | Vuelve a `habilitada` |
| Excluir sin evidencia, o sin la palabra de confirmación | 422 |
| Excluir con evidencia y confirmación | La parcela pasa a `excluida` |
| Editar, habilitar o cargar documentos en una parcela excluida | 400 con `parcela_excluida`, también para `superadmin` |
| Parcela nueva superpuesta con una excluida | Alerta `superposicion_con_excluida` |
| `UPDATE` o `DELETE` sobre `decisiones_habilitacion` | Rechazado por el trigger |
| Faltan 15 días para que el análisis pierda vigencia | La tarea diaria solicita un análisis nuevo |

### Criterios de aceptación en producción

1. Con las claves reales cargadas, una parcela de prueba obtiene un análisis completado de Whisp y otro de GFW, y cada tarjeta muestra fuente, fecha y versión.
2. Las capas de Geobosques, GeoSERFOR y JRC se encienden en el mapa de la parcela con su atribución.
3. Un operador registra una visita de campo con foto desde un celular.
4. El expediente llega a `completo` con documentos y exenciones.
5. El operador no ve los botones de decisión; el administrador habilita la parcela.
6. Al adelantar el vencimiento de un documento, la parcela pasa sola a `observada`, y vuelve a `habilitada` tras corregirlo y decidir de nuevo.
7. El administrador excluye una parcela de prueba, y ninguna pantalla ni llamada directa logra revertirlo.
8. La sección Habilitación muestra las parcelas por estado y los documentos por vencer.
9. Ninguna pantalla contiene las frases prohibidas.
10. Todas las decisiones aparecen en la auditoría y el CI está en verde, incluidas las Partes 1 a 3.

### Decisiones pendientes del equipo

- [x] Crear las claves de Whisp y GFW. Creadas y cargadas en Render el 2026-10-05.
- [x] Guardar una respuesta real de cada fuente para las pruebas. Guardadas el 2026-10-05 en `backend/tests/datos/whisp_respuesta_real.json` y `gfw_respuesta_real.json`, de una parcela ficticia en producción.
- [ ] Confirmar el recorte de fuentes: Geobosques, GeoSERFOR y JRC como capas visuales; Sentinel, Hansen y MapBiomas fuera de la primera versión.
- [x] Definir qué documento concreto se pide como sustento de SUNAFIL para un productor. Definido el 2026-10-05; ver "Los 7 documentos".
- [x] Confirmar qué tipos de documento tienen registro público consultable. Confirmado el 2026-10-05 con fuentes oficiales.
- [x] Definir qué tipos de documento exigen fecha de vencimiento. Ninguno la exige; ver "Los 7 documentos".
- [ ] Confirmar los plazos: 180 días de vigencia del análisis, 30 días de aviso de vencimiento y 365 días de vigencia de la visita de campo.
- [ ] Retirar del proyecto el diseño anterior de evaluación de riesgos, que calcula una conclusión y contradice el principio de esta parte.

## Parte 5 — Recepción de la tanda y DOP

Una tanda es el cacao de una sola parcela que un productor entrega y la cooperativa pesa en cancha. Al validarla, el sistema emite su DOP: productor, parcela y tanda sellados en un documento que ya no cambia.

Esta parte abre la etapa 2 del flujo operativo, "Acopio y procesamiento".

### Decisiones tomadas por el equipo

| Tema | Decisión |
| --- | --- |
| Unidad del DOP | Un DOP por parcela y por cada cosecha entregada |
| Guía de remisión | Obligatoria siempre. Sin guía no se valida la tanda |
| Quién valida | El mismo operador que recibe la tanda, o un administrador |
| Cómo se registra la producción | En baba o en grano seco, según cómo entregue el productor |
| Tope de kilos por hectárea | Lo configura cada cooperativa |

### Reglas de fondo

1. Una tanda viene de una sola parcela. Si un productor entrega cacao de dos parcelas, se registran dos tandas, cada una con su peso.
2. Solo una parcela `habilitada` puede recibir una tanda.
3. La recepción la registra el personal de la cooperativa, porque ocurre en su balanza. El productor ya aportó lo suyo en las Partes 3 y 4, y aquí consulta sus entregas y sus DOP.
4. El artículo 9 del Reglamento pide la fecha o el intervalo de producción. Por eso la tanda guarda el intervalo de cosecha, que hoy no se registra en ninguna parte.
5. Las señales de implausibilidad, como kilos por hectárea fuera de lo creíble, no bloquean. Se muestran, exigen una nota de quien valida y llegan al informe de hallazgos.

### Fuera de alcance en esta parte

- El control de calidad, la fermentación, el secado y el resto del proceso, que son la Parte 6.
- El pago al productor y cualquier dato de precios.
- La consulta automática de la guía de remisión en SUNAT.

## Configuración de la cooperativa y lugares

Antes de recibir su primera tanda, cada cooperativa fija sus propios parámetros y registra sus lugares de acopio. Sin tope de kilos por hectárea configurado no se puede registrar una tanda.

### Tabla `configuracion_cooperativa`

Una fila por cooperativa.

| Columna | Tipo | Valor inicial | Para qué sirve |
| --- | --- | --- | --- |
| `tope_kg_seco_ha_anio` | numeric(10,2) | Ninguno; lo fija el administrador | Kilos de grano seco por hectárea al año que la cooperativa considera creíbles |
| `factor_baba_a_seco` | numeric(4,3) | 0.390 | Convierte kilos en baba a su equivalente en seco para comparar contra el tope. Es el punto medio de la banda del flujo |
| `rendimiento_min`, `rendimiento_max` | numeric(4,3) | 0.330 y 0.450 | Banda de rendimiento de baba a seco. Se usa en la Parte 6 |
| `dias_max_cosecha_entrega_baba` | integer | 7 | Días creíbles entre el fin de la cosecha y la entrega en baba |
| `dias_max_cosecha_entrega_seco` | integer | 90 | Días creíbles entre el fin de la cosecha y la entrega en seco |
| `tolerancia_peso_guia_pct` | numeric(4,1) | 5.0 | Diferencia admitida entre el peso de la guía y el peso en balanza |

1. Solo un `admin_cooperativa` cambia la configuración. Cada cambio se audita con el valor anterior y el nuevo.
2. Un cambio no altera las tandas ya validadas. Cada decisión guarda los valores con que se evaluó.
3. Los valores iniciales, salvo la banda de rendimiento, son propuestas que el equipo debe confirmar.

### Tabla `lugares`

Los sitios físicos de la cooperativa. La tanda se recibe en uno, y la Parte 6 los usa en cada etapa del proceso.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa dueña |
| `nombre` | text | Obligatorio, único por cooperativa |
| `tipo` | text | `cancha_acopio`, `planta`, `almacen` u `otro` |
| `departamento`, `provincia`, `distrito` | text | Obligatorios |
| `latitud`, `longitud` | numeric(9,6) | Opcionales |
| `activo` | boolean | Por defecto `true` |

### Código de la cooperativa

La tabla `cooperativas` gana la columna `codigo`: de 3 a 6 letras mayúsculas, única y obligatoria. La fija el `superadmin` al crear la cooperativa y no cambia después, porque forma parte del código de cada DOP.

### Correlativos

Los códigos de tandas y de DOP usan la tabla `correlativos`, con las columnas `cooperativa_id`, `tipo`, `anio` y `ultimo`. El siguiente número se toma con bloqueo de fila, para que dos operadores simultáneos nunca reciban el mismo.

## La tanda

La tanda guarda cuatro grupos de datos: quién entrega y de qué parcela, el pesaje, la cosecha y la guía de remisión.

### Tabla `tandas`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa que recibe |
| `codigo` | text | `TD-{año}-{número de 6 dígitos}`, correlativo por cooperativa y año |
| `productor_id` | uuid | Productor con afiliación activa en la cooperativa |
| `parcela_id` | uuid | Parcela de ese productor |
| `lugar_id` | uuid | Lugar de tipo `cancha_acopio` donde se pesó |
| `recibida_en` | timestamptz | Fecha y hora del pesaje. No puede ser futura |
| `estado_producto` | text | `baba` o `seco` |
| `peso_kg` | numeric(10,2) | Peso neto en balanza. Mayor que cero |
| `numero_sacos` | integer | Opcional |
| `humedad_pct` | numeric(4,1) | Opcional; solo si el producto es `seco` |
| `variedad` | text | Un valor del catálogo de variedades |
| `tipo_semilla` | text | Opcional |
| `cosecha_desde`, `cosecha_hasta` | date | Intervalo de cosecha. `desde` no supera a `hasta`, y `hasta` no supera la fecha de recepción |
| `gre_numero` | text | Serie y número de la guía de remisión |
| `gre_fecha_emision` | date | No posterior a la fecha de recepción |
| `gre_ruc_emisor` | char(11) | RUC de quien emitió la guía |
| `gre_peso_kg` | numeric(10,2) | Peso que declara la guía. Opcional |
| `estado` | text | `registrada`, `observada`, `validada` o `anulada` |
| `registrada_por` | uuid | Perfil que la registró |

### Peso equivalente en seco

La API calcula `peso_seco_equivalente_kg` para comparar tandas entre sí. Si el producto es `seco`, es el mismo peso. Si es `baba`, es el peso por `factor_baba_a_seco`. Es una estimación para detectar volúmenes implausibles; el peso seco real se mide en la Parte 6.

### Variedades

El catálogo vive en `backend/app/catalogos/variedades.py`. Lista inicial, por confirmar con el equipo: CCN-51, ICS-95, IMC-67, TSH-565, Trinitario, Chuncho, sin variedad específica y otra. Con "otra", el usuario escribe el nombre.

### Guía de remisión

1. La guía puede emitirla el productor o la cooperativa. El sistema registra quién la emitió por su RUC.
2. Son obligatorios el número, la fecha de emisión, el RUC del emisor y el archivo de la guía.
3. El archivo se carga como documento de tipo `guia_remision`, con `entidad = tanda`, en PDF, JPG o PNG.
4. Claude Code confirma el formato de serie y número contra la documentación de SUNAT antes de validarlo.
5. Una misma guía puede cubrir varias tandas del mismo productor, por ejemplo una entrega de dos parcelas.
6. La guía admite cotejo en fuente, con las reglas de la Parte 4. Sin cotejo queda en `documentado`.

### Edición

Los datos de una tanda se editan solo mientras está `registrada` u `observada`. Cada cambio se audita con el valor anterior. Una tanda `validada` no cambia nunca.

## Compuerta de la tanda

Una tanda genera su DOP solo al validarse. Si algo no cuadra, se observa con un motivo, se corrige y se valida de nuevo; el flujo llama a esto revalidación.

### Estados

&#91;embedded content: estados de la tanda · 4 estados, 5 transiciones\]

Validada y anulada son estados finales: de ninguno sale una flecha.

| Estado | Significado |
| --- | --- |
| `registrada` | Pesada e ingresada; todavía sin validar |
| `observada` | Alguien encontró un problema y dejó un motivo. Se corrige y se vuelve a validar |
| `validada` | Cumplió los requisitos y tiene DOP. No cambia más |
| `anulada` | Se registró por error. No genera DOP ni cuenta en ningún cálculo |

### Requisitos para validar

La API calcula la lista `requisitos` de la tanda. Todos deben cumplirse, y ninguno se puede saltar.

| Requisito | Se cumple cuando |
| --- | --- |
| `parcela_habilitada` | La parcela está `habilitada` en el momento de validar |
| `productor_afiliado` | El productor tiene afiliación activa y consentimiento registrado |
| `datos_completos` | Peso, estado del producto, variedad, lugar e intervalo de cosecha son válidos |
| `guia_completa` | La guía tiene número, fecha, RUC del emisor y un documento vigente |
| `configuracion_lista` | La cooperativa tiene configurado su tope de kilos por hectárea |

### Alertas de la tanda

No impiden validar. Obligan a escribir una nota y llegan al informe de hallazgos.

| Alerta | Condición |
| --- | --- |
| `volumen_acumulado_excede_tope` | El peso seco equivalente de las tandas no anuladas de la parcela en los 365 días previos, incluida esta, dividido entre su área cultivada, supera `tope_kg_seco_ha_anio` |
| `dias_cosecha_entrega_altos` | Los días entre `cosecha_hasta` y la recepción superan el máximo configurado para baba o para seco |
| `peso_difiere_de_guia` | El peso de la guía difiere del peso en balanza más que la tolerancia |
| `guia_usada_por_otro_productor` | El mismo número de guía y RUC aparece en una tanda de otro productor |
| `parcela_con_alertas` | La parcela está habilitada pero tiene alertas vigentes, como un documento por vencer |

### Decisión

1. Valida un `operador` o un `admin_cooperativa`. Puede ser la misma persona que registró la tanda.
2. Con un requisito sin cumplir, la API responde 400 con `requisitos_incompletos` y la lista.
3. Si hay alertas, la nota es obligatoria, con un mínimo de 50 caracteres.
4. Validar y emitir el DOP ocurren en una sola transacción. Si la emisión falla, la tanda no queda validada.
5. Observar exige un motivo. La tanda vuelve a ser editable y puede validarse después.
6. Anular exige un motivo y solo es posible antes de validar.

### Tabla `decisiones_tanda`

Cada decisión es una fila que no se edita ni se borra, con la misma protección que `decisiones_habilitacion`.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `tanda_id` | uuid | Referencia a `tandas` |
| `decision` | text | `validar`, `observar` o `anular` |
| `decidida_por`, `decidida_en` | uuid, timestamptz | Quién y cuándo |
| `nota` | text | Nota de validación o motivo |
| `requisitos` | jsonb | Copia de requisitos, alertas y valores de configuración usados |

Que la misma persona registre y valide no se impide, pero queda a la vista: el DOP muestra ambos nombres y el informe de hallazgos lo cuenta.

## El DOP

El DOP es una copia sellada de todo lo que respalda una tanda en el momento de validarla. Lo que cambie después en el productor, la parcela o el expediente no lo altera.

### Tabla `dops`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa emisora |
| `codigo` | text | `DOP-{código de cooperativa}-{año}-{número de 6 dígitos}`. Único en toda la plataforma |
| `tanda_id` | uuid | Único: una tanda tiene un solo DOP |
| `productor_id`, `parcela_id` | uuid | Para búsquedas; el detalle está en `contenido` |
| `emitido_en`, `emitido_por` | timestamptz, uuid | Momento y perfil de la validación |
| `contenido` | jsonb | La copia sellada |
| `contenido_sha256` | char(64) | Huella del contenido |
| `pdf_documento_id` | uuid | Documento de tipo `dop_pdf` |
| `estado` | text | `vigente` o `anulado` |
| `anulado_en`, `anulado_por`, `motivo_anulacion` | timestamptz, uuid, text | Se llenan al anular |

### Contenido sellado

Por la adenda de la Parte 4, el contenido sellado copia también la tabla de convergencia de la parcela, con su frase de conteo, tal como estaba al validar la tanda.

| Bloque | Qué copia |
| --- | --- |
| Identificación | Código, razón social y RUC de la cooperativa, fecha de emisión, quién registró y quién validó |
| Productor | DNI, nombres, dirección postal, correo, RUC y registro en el PPA, cada dato con su nivel de verificación |
| Parcela | Nombre, ubicación, tipo de geometría, geometría en GeoJSON, áreas, estado en MIDAGRI y procedencia |
| Habilitación | La decisión vigente: quién, cuándo, nota y requisitos |
| Cobertura forestal | Por cada fuente: el resultado tal como lo entregó, indicadores, fecha, versión y huella de la respuesta |
| Expediente legal | Las 7 casillas: estado, número, emisor, fechas, nivel de verificación y exenciones con su motivo |
| Tanda | Código, lugar, fecha de recepción, estado del producto, peso, variedad, intervalo de cosecha y guía de remisión |
| Alertas y nota | Alertas de la tanda y de la parcela al emitir, y la nota de validación |
| No verificado | Lo que el sistema no comprobó: coordenadas no recorridas, documentos sin cotejar o sin registro consultable, análisis hechos por aproximación |

### Sello

1. La huella es el SHA-256 del contenido en forma canónica: claves ordenadas, UTF-8 y sin espacios sobrantes. Una sola función produce esa forma.
2. Un trigger rechaza todo `UPDATE` sobre `contenido`, `contenido_sha256`, `codigo` y `tanda_id`.
3. Cualquiera que tenga el contenido puede recalcular la huella y compararla con la publicada.

### PDF

1. Se genera una sola vez, al emitir, a partir de `contenido`, y se guarda en Storage como documento `dop_pdf`.
2. Se usa una librería de PDF escrita solo en Python, sin dependencias del sistema, para que funcione en Render. La misma librería servirá para el DPP y el DEX.
3. El encabezado lleva el código, la fecha, la huella y un código QR. Cada página lleva al pie el código y el número de página.
4. Hay una sección por cada bloque del contenido, en el mismo orden. La parcela incluye un croquis dibujado desde su geometría, sin mapa de fondo.
5. La primera página lleva esta leyenda: "Este documento reúne la información de origen de una tanda de cacao tal como estaba registrada al emitirse. No es una constancia ni un certificado, y no declara el cumplimiento del Reglamento (UE) 2023/1115".
6. El PDF respeta la lista de palabras que no se usan, de la Parte 4.

### Verificación pública

1. El código QR lleva a la página `#/verificar/dop/{codigo}`, que no pide inicio de sesión.
2. `GET /publico/dops/{codigo}` responde sin token y solo con cinco datos: código, estado, fecha de emisión, huella y razón social de la cooperativa.
3. No entrega datos personales, geometría ni pesos. Un código inexistente responde 404.
4. Los endpoints públicos tienen un límite de 30 peticiones por minuto por dirección IP.

### Anulación

1. Solo un `admin_cooperativa` anula un DOP, con motivo.
2. Solo se puede anular mientras su tanda no haya entrado a una corrida de proceso de la Parte 6.
3. Un DOP anulado conserva su contenido y su PDF, y la verificación pública lo muestra como anulado.
4. Su tanda sigue `validada` como registro histórico, pero se trata como anulada en todos los cálculos y no entra a proceso. La entrega corregida se registra como una tanda nueva.

## Endpoints de la Parte 5

Son 22 endpoints en cinco grupos. Solo uno, el de verificación pública, responde sin token.

### Configuración y lugares

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /configuracion` | Personal | Devuelve la configuración de la cooperativa |
| `PUT /configuracion` | `admin_cooperativa` | Cambia la configuración |
| `GET /lugares` | Personal | Lista los lugares |
| `POST /lugares` | `admin_cooperativa` | Crea un lugar |
| `PATCH /lugares/{id}` | `admin_cooperativa` | Edita o desactiva un lugar |

### Tandas

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /tandas` | Personal | Lista con filtros por estado, productor, parcela y fechas |
| `POST /tandas` | `admin_cooperativa`, `operador` | Registra una tanda |
| `GET /tandas/{id}` | Personal | Detalle con `requisitos`, `alertas` y decisiones |
| `PATCH /tandas/{id}` | `admin_cooperativa`, `operador` | Edita una tanda `registrada` u `observada` |
| `POST /tandas/{id}/documentos` | `admin_cooperativa`, `operador` | Carga la guía de remisión |
| `POST /tandas/{id}/validar` | `admin_cooperativa`, `operador` | Valida la tanda y emite su DOP. Recibe `nota` |
| `POST /tandas/{id}/observar` | `admin_cooperativa`, `operador` | Observa la tanda con un motivo |
| `POST /tandas/{id}/anular` | `admin_cooperativa`, `operador` | Anula una tanda no validada, con motivo |

### DOP

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /dops` | Personal | Lista con filtros por estado, productor, parcela y fechas |
| `GET /dops/{id}` | Personal | Detalle con el contenido sellado y la huella |
| `GET /dops/{id}/pdf` | Personal | URL firmada del PDF |
| `POST /dops/{id}/anular` | `admin_cooperativa` | Anula el DOP, con motivo |

### Productor

| Método y ruta | Qué hace |
| --- | --- |
| `GET /mi/tandas` | Sus entregas, con estado |
| `GET /mi/dops` | Sus DOP |
| `GET /mi/dops/{id}` | Detalle de un DOP propio |
| `GET /mi/dops/{id}/pdf` | URL firmada del PDF de un DOP propio |

### Público

| Método y ruta | Qué hace |
| --- | --- |
| `GET /publico/dops/{codigo}` | Verificación sin token: código, estado, fecha, huella y cooperativa |

Se auditan `configuracion.cambiar`, `lugar.crear`, `lugar.editar`, `tanda.registrar`, `tanda.editar`, `tanda.validar`, `tanda.observar`, `tanda.anular`, `dop.emitir` y `dop.anular`.

`POST /admin/cooperativas` de la Parte 2 recibe ahora también el campo `codigo`.

## Pantallas de la Parte 5

El módulo "Lotes y proceso" estrena sus dos primeras secciones, Recepción y DOP. La recepción se llena en cancha, de pie y con prisa: el asistente debe funcionar en un celular y pedir lo mínimo en cada paso.

### Personal de la cooperativa

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Recepción | `#/lotes/recepcion` | Tandas agrupadas por estado, con buscador, y el botón "Nueva tanda" |
| Nueva tanda | `#/lotes/recepcion/nueva` | Asistente de 4 pasos |
| Detalle de tanda | `#/tandas/{id}` | Datos, guía, requisitos, alertas, historial de decisiones y enlace a su DOP |
| DOP | `#/lotes/dop` | Lista de DOP con código, productor, parcela, peso, fecha y estado |
| Detalle de DOP | `#/dops/{id}` | Contenido sellado por bloques, huella, código QR y botón de descargar el PDF |
| Configuración | `#/cooperativa/configuracion` | Los parámetros de la cooperativa, con una explicación breve de cada uno |
| Lugares | `#/cooperativa/lugares` | Lista y alta de lugares |

### Asistente de nueva tanda

1. Productor y parcela: se busca al productor por DNI o nombre y se elige una de sus parcelas. Las no habilitadas aparecen apagadas, con el motivo.
2. Pesaje y cosecha: lugar, fecha y hora, estado del producto, peso, sacos, variedad e intervalo de cosecha.
3. Guía de remisión: número, fecha, RUC del emisor, peso declarado y la foto o el PDF de la guía.
4. Revisión: requisitos, alertas y los botones "Validar y emitir DOP", "Guardar sin validar" y "Observar".

Si hay alertas, el paso 4 muestra el campo de nota antes de permitir validar. Al validar, la pantalla muestra el código del DOP y el botón para descargar su PDF.

### Productor

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Mis entregas | `#/mis-entregas` | Sus tandas con fecha, parcela, peso y estado, y el PDF del DOP de cada una |

### Pública

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Verificar DOP | `#/verificar/dop/{codigo}` | Código, cooperativa, fecha de emisión, estado y huella, sin barra lateral ni inicio de sesión |

### Reglas de la interfaz

1. Mientras la cooperativa no tenga su tope configurado, Recepción muestra un aviso con enlace a Configuración y no deja crear tandas.
2. El botón de validar dice lo que hace: "Validar y emitir DOP". Tras emitir, ya no existe ningún botón de edición.
3. Los pesos se muestran con dos decimales y su unidad. Los códigos de tanda y de DOP van en tipografía monoespaciada.
4. La página pública no enlaza al resto de la aplicación ni revela si existen otros códigos.

### Notas de implementación (2026-10-05)

Tomadas de la documentación oficial de cada servicio o librería, consultada el 2026-10-05.

1. Guía de remisión, formato (punto 4 de la guía): la serie es `T` o `V` más 3 caracteres alfanuméricos (guía electrónica del remitente o del transportista), `EG01` a `EG04` o `EG07` (emitida desde SUNAT), `G` más 3 dígitos, o 3 o 4 dígitos (guía impresa); el número tiene de 1 a 8 dígitos y no es cero. Fuentes: RS 000123-2022/SUNAT y sus anexos 12, 13 y 28; Reglas de validación de SUNAT del 26.08.2026; Reglamento de Comprobantes de Pago, art. 9.4. Se guarda como `SERIE-NÚMERO` (serie numérica con 4 dígitos, número sin ceros a la izquierda) y un formato distinto responde 422 `guia_numero_invalido`. Está en `backend/app/catalogos/guia_remision.py`.
2. Guía de remisión, cotejo (punto 6 y decisión pendiente): la guía general no tiene un registro público consultable; SUNAT solo la muestra, con Clave SOL, al remitente, al transportista o al destinatario. Por eso queda en `documentado` y el bloque "No verificado" del DOP lo dice. Investigado por Claude Code; el equipo lo confirma.
3. Código de la cooperativa: es obligatorio al crear una cooperativa, pero la columna admite vacío para las creadas antes de esta parte. El `superadmin` lo fija una sola vez en "Editar datos" (`PATCH /admin/cooperativas/{id}` con `codigo`); si ya tiene, responde 400 `codigo_inmutable`, y si otra lo usa, 409 `codigo_en_uso`. Sin código, `POST /tandas` responde 400 `configuracion_incompleta`, igual que sin tope.
4. Variedad "otra": su nombre va en la columna `variedad_otra`, obligatoria solo con esa variedad.
5. Estados: se observa solo una tanda `registrada` y se anula una `registrada` u `observada`, las cinco transiciones del diagrama.
6. Volumen acumulado: cuentan las tandas de la parcela recibidas en los 365 días previos a la recepción de la tanda evaluada, incluida ella; no cuentan las anuladas ni las validadas con su DOP anulado. La alerta `guia_usada_por_otro_productor` busca en toda la plataforma y no dice en qué cooperativa. `parcela_con_alertas` guarda en su detalle cuáles son.
7. Sello: la forma canónica es `json.dumps(contenido, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` en UTF-8, con decimales y fechas como texto; la huella es su SHA-256. Solo `backend/app/services/sello.py` la produce. El trigger `dops_sellados` rechaza además el `DELETE`, y `decisiones_tanda_inmutables` protege las decisiones.
8. PDF: fpdf2 2.8.9, escrito solo en Python (depende de Pillow, fontTools y defusedxml, que también lo son o traen ruedas para Linux). El código QR lo calcula segno 1.6.6 y se dibuja con rectángulos. Las tipografías son las del diseño, Plus Jakarta Sans y JetBrains Mono, con licencia OFL, en `backend/app/recursos/fuentes/`. La leyenda contiene "certificado" para negarlo: la prueba de frases prohibidas exceptúa solo esa leyenda, con su texto exacto.
9. Variable nueva `URL_INTERFAZ` (por defecto `https://cacaotrace.pages.dev`): la dirección a la que lleva el código QR, `{URL_INTERFAZ}/#/verificar/dop/{codigo}`.
10. Límite público: vive en la memoria del proceso, porque Render corre una sola instancia, y se reinicia con cada deploy. La IP sale de `CF-Connecting-IP`, que escribe Cloudflare; el primer valor de `X-Forwarded-For` lo puede inventar quien llama.
11. CORS: la API admite ahora `PUT`, que usa `PUT /configuracion`.
12. Configuración y Lugares los ve todo el personal y el `superadmin` en modo consulta; solo el `admin_cooperativa` los cambia.

## Pruebas y aceptación de la Parte 5

La Parte 5 está terminada cuando un operador recibe una tanda en cancha desde un celular, la valida y obtiene un DOP con PDF, huella y código QR verificable sin iniciar sesión.

### Pruebas automáticas mínimas

| Caso | Resultado esperado |
| --- | --- |
| Tanda sobre una parcela `pendiente`, `observada` o `excluida` | No se puede validar; `parcela_habilitada` no se cumple |
| Tanda de un productor sin afiliación activa en la cooperativa | 404 |
| Parcela que no pertenece al productor indicado | 422 |
| Cooperativa sin tope configurado | `POST /tandas` responde 400 con `configuracion_incompleta` |
| `cosecha_hasta` posterior a la recepción, o `desde` posterior a `hasta` | 422 |
| Guía con fecha posterior a la recepción | 422 |
| Validar sin archivo de guía | 400 con `requisitos_incompletos` |
| Tanda en baba de 1,000 kg con factor 0.390 | `peso_seco_equivalente_kg` es 390.00 |
| Volumen acumulado de la parcela por encima del tope | Alerta `volumen_acumulado_excede_tope` |
| Mismo caso, con una tanda previa anulada | La anulada no cuenta |
| Días entre cosecha y entrega por encima del máximo | Alerta `dias_cosecha_entrega_altos` |
| Peso de la guía 10 % distinto del peso en balanza | Alerta `peso_difiere_de_guia` |
| Misma guía en la tanda de otro productor | Alerta `guia_usada_por_otro_productor` |
| Validar con alertas y sin nota | 422 |
| Validar con todo en orden | Tanda `validada`; DOP `vigente`; PDF guardado |
| Falla la generación del PDF durante la validación | La tanda no queda validada y no existe DOP |
| Dos validaciones simultáneas en la misma cooperativa | Códigos de DOP distintos y consecutivos |
| Mismo contenido, canonizado dos veces | Misma huella |
| `UPDATE` sobre `contenido` de un DOP | Rechazado por el trigger |
| Se edita la ficha del productor después de emitir | El contenido del DOP no cambia |
| `PATCH` sobre una tanda `validada` | 400 |
| Observar, corregir y validar | Quedan dos decisiones en `decisiones_tanda`, en orden |
| `operador` anula un DOP | 403 |
| `GET /publico/dops/{codigo}` sin token | 200 con solo los cinco datos permitidos |
| Mismo endpoint, 31 veces en un minuto | La última responde 429 |
| Productor pide el DOP de otro productor | 404 |
| PDF del DOP | No contiene ninguna de las frases prohibidas |

Cada endpoint con token tiene además la prueba de las dos cooperativas definida en la Parte 2.

### Criterios de aceptación en producción

1. El administrador configura el tope y crea una cancha de acopio.
2. Un operador registra una tanda desde un celular, con la foto de la guía tomada con la cámara.
3. Una parcela no habilitada aparece apagada en el asistente, con su motivo.
4. Al validar, se emite el DOP y su PDF se descarga con todos los bloques, el croquis de la parcela, la huella y el código QR.
5. Al escanear el código QR, la página pública muestra el DOP como vigente, sin datos personales.
6. Una tanda con volumen por encima del tope muestra la alerta y exige nota para validarse.
7. Una tanda observada se corrige y se valida, y su historial muestra los dos pasos.
8. El productor ve su entrega y descarga su DOP desde "Mis entregas".
9. Tras anular un DOP, la página pública lo muestra como anulado.
10. Todas las acciones aparecen en la auditoría y el CI está en verde, incluidas las Partes 1 a 4.

### Decisiones pendientes del equipo

- [ ] Confirmar los valores iniciales de configuración: factor 0.390, 7 días para baba, 90 días para seco y 5 % de tolerancia.
- [ ] Confirmar la lista inicial de variedades.
- [ ] Aclarar qué es la "fecha de cultivo" del diagrama. Se registró el intervalo de cosecha, que es lo que pide el artículo 9.
- [ ] Aclarar qué es el "tipo de semilla" y qué valores admite. Quedó como texto libre opcional.
- [ ] Confirmar si la guía de remisión tiene un registro público consultable para el cotejo.
- [ ] Revisar el texto de la leyenda de la primera página del DOP.
- [ ] Confirmar que una tanda viene siempre de una sola parcela.

## Parte 6 — Proceso y DPP

Una corrida de proceso toma una o varias tandas validadas, las lleva por las 23 etapas del diagrama de proceso y termina en una tanda final que entra al stock. Al consolidarla se emite el DPP, sellado igual que el DOP.

Esta parte cierra la etapa 2 del flujo operativo.

### Decisiones tomadas por el equipo

| Tema | Decisión |
| --- | --- |
| Etapas del proceso | El equipo pidió una propuesta. Se toman las 22 del primer diagrama y se agrega un traslado que faltaba, para llegar a las 23 del flujo |
| Mezcla de tandas | Las dos formas: una corrida puede ser segregada o mezclada |
| Grano entregado seco | Entra directo a selección y almacén; no pasa por fermentación ni secado |

### Reglas de fondo

1. Solo entra a una corrida una tanda `validada`, con DOP `vigente` y que no esté en otra corrida. Entra completa; no se parte.
2. Una corrida no mezcla baba con seco. Las tandas en baba van a una corrida de ruta `completa`; las tandas en seco, a una de ruta `seco`.
3. Una corrida `segregada` lleva tandas de un solo productor. Una `mezclada` lleva tandas de varios.
4. El sistema guarda cuánto pesa cada tanda dentro de la corrida. Esa proporción sobre la masa de entrada es la base de la genealogía de la Parte 7.
5. La genealogía no forma parte del DPP. El DPP termina cuando la tanda final entra al stock.
6. El rendimiento fuera de banda no bloquea. Exige una explicación y llega al informe de hallazgos.

### Fuera de alcance en esta parte

- Órdenes de compra, selección de stock y genealogía, que son la Parte 7.
- Costos, mermas valorizadas y cualquier dato contable.
- Control de inventario de sacos, insumos o envases.

## Las 23 etapas del proceso

El catálogo tiene 23 etapas en cinco fases. La etapa 11, "Traslado a zona de secado", es la única que no está en el primer diagrama del equipo: se propone porque entre la prueba de corte y el secado solar falta el traslado.

### Catálogo

| N.º | Etapa | Tipo | Fase | Aplica en ruta `seco` | Dato propio de la etapa |
| --- | --- | --- | --- | --- | --- |
| 1 | Recepción y pesaje en cancha de acopio | Operación | Ingreso | Sí | Se llena solo, desde las tandas |
| 2 | Control de calidad del cacao recibido | Inspección | Ingreso | Sí | Observación de calidad |
| 3 | Registro y codificación del lote | Operación | Ingreso | Sí | Se llena solo: código de corrida y DOP de respaldo |
| 4 | Control de trazabilidad y legalidad de origen | Inspección | Ingreso | Sí | Se llena solo: compuerta de cada tanda |
| 5 | Segregación o rechazo | Operación | Ingreso | Sí | Tipo de manejo de la corrida |
| 6 | Traslado a cajones de fermentación | Transporte | Fermentación | No | Distancia |
| 7 | Espera de cajón de fermentación disponible | Espera | Fermentación | No | Ninguno. Etapa opcional |
| 8 | Descarga y llenado del cajón | Operación | Fermentación | No | Ninguno |
| 9 | Fermentación con volteos | Operación | Fermentación | No | Fechas de volteo |
| 10 | Prueba de corte | Inspección | Fermentación | No | Porcentaje de granos bien fermentados |
| 11 | Traslado a zona de secado | Transporte | Secado | No | Distancia |
| 12 | Secado solar con volteos periódicos | Operación | Secado | No | Ninguno |
| 13 | Control de humedad | Inspección | Secado | No | Humedad en porcentaje |
| 14 | Espera bajo cobertizo por lluvia | Espera | Secado | No | Ninguno. Etapa opcional |
| 15 | Traslado a zona de zarandeo | Transporte | Selección | Sí | Distancia |
| 16 | Zarandeo y limpieza de impurezas | Operación | Selección | Sí | Ninguno |
| 17 | Clasificación por calibre y calidad | Operación | Selección | Sí | Calidad asignada |
| 18 | Selección manual de granos defectuosos | Operación | Selección | Sí | Kilos descartados |
| 19 | Pesado del cacao clasificado | Operación | Selección | Sí | Peso final en kilos |
| 20 | Traslado a zona de envasado | Transporte | Envasado y almacén | Sí | Distancia |
| 21 | Envasado en sacos de yute | Operación | Envasado y almacén | Sí | Número de sacos |
| 22 | Traslado a almacén | Transporte | Envasado y almacén | Sí | Distancia |
| 23 | Almacenamiento hasta consolidar el lote de exportación | Almacenamiento | Envasado y almacén | Sí | Ninguno |

### Datos comunes de toda etapa

Además de su dato propio, cada etapa registra lo que pide el flujo: lugar, tiempo y método.

| Dato | Regla |
| --- | --- |
| Lugar | Un registro de `lugares`. Obligatorio |
| Inicio y fin | Fecha y hora. El fin no puede ser anterior al inicio. La duración se calcula |
| Método | Texto breve: cómo se hizo |
| Responsable | Nombre de quien la ejecutó |
| Distancia | En metros. Obligatoria solo en las etapas de transporte |
| Observación | Opcional |

### Reglas del catálogo

1. El catálogo es fijo y vive en `backend/app/catalogos/etapas_proceso.py`. Una cooperativa no agrega ni quita etapas.
2. Las etapas 7 y 14 pueden marcarse como "no ocurrió". Las demás son obligatorias en su ruta.
3. En la ruta `seco`, las etapas 6 a 14 quedan como "no aplica" de forma automática.
4. Las etapas 1, 3 y 4 no se digitan. El sistema las llena con los datos de las tandas y de sus DOP.

## La corrida de proceso

La corrida se guarda en tres tablas: la corrida, las tandas que entraron y sus 23 etapas. Una plantilla por cooperativa llena los valores habituales, para que el operador solo corrija lo que cambió.

### Tabla `corridas`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa dueña |
| `codigo` | text | `CP-{año}-{número de 6 dígitos}`, correlativo por cooperativa y año |
| `ruta` | text | `completa` o `seco` |
| `tipo_manejo` | text | `segregado` o `mezclado` |
| `estado` | text | `abierta`, `en_proceso`, `consolidada` o `anulada` |
| `abierta_por`, `abierta_en` | uuid, timestamptz | Quién la creó y cuándo |
| `iniciada_en`, `consolidada_en` | timestamptz | Momentos de cambio de estado |

### Tabla `corrida_tandas`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `corrida_id` | uuid | Referencia a `corridas` |
| `tanda_id` | uuid | Única entre corridas no anuladas: una tanda entra a una sola corrida |
| `peso_kg` | numeric(10,2) | Copia del peso de la tanda al entrar |
| `observacion_calidad` | text | Opcional. Alimenta la etapa 2 |
| `proporcion` | numeric(9,6) | Peso de la tanda entre el peso total de entrada. Se fija al consolidar; la suma de la corrida es 1 |

### Tabla `corrida_etapas`

Al crear la corrida se generan sus 23 filas, ya llenas con la plantilla.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `corrida_id` | uuid | Referencia a `corridas` |
| `numero` | integer | De 1 a 23. Único por corrida |
| `situacion` | text | `pendiente`, `registrada`, `no_aplica` o `no_ocurrio` |
| `lugar_id` | uuid | Referencia a `lugares` |
| `inicio`, `fin` | timestamptz | Tiempo de la etapa |
| `metodo`, `responsable`, `observacion` | text | Datos comunes |
| `distancia_m` | numeric(8,1) | Solo en etapas de transporte |
| `datos` | jsonb | Dato propio de la etapa, con las claves que define el catálogo |
| `registrada_por`, `registrada_en` | uuid, timestamptz | Quién confirmó la etapa |

### Plantilla de proceso

La tabla `plantilla_proceso` guarda, por cooperativa y por número de etapa, los valores habituales: `lugar_id`, `metodo`, `distancia_m` y `duracion_horas`.

1. La edita un `admin_cooperativa`.
2. Al crear una corrida, cada etapa toma su lugar, método y distancia de la plantilla.
3. Los valores de la plantilla son solo un punto de partida. Una etapa cuenta como `registrada` cuando una persona la confirma con su inicio y su fin reales.
4. Sin plantilla, las etapas nacen vacías y la corrida funciona igual.

## Reglas de la corrida

Una corrida pasa de abierta a en proceso y de ahí a consolidada. Operan la corrida el `operador` y el `admin_cooperativa`; solo el administrador anula un DPP.

### Estados y acciones

| Desde | Acción | Hacia | Condición |
| --- | --- | --- | --- |
| Ninguno | Crear, eligiendo ruta y tipo de manejo | `abierta` | La cooperativa tiene al menos un lugar activo |
| `abierta` | Agregar o quitar tandas | `abierta` | Cada tanda cumple las reglas de ingreso |
| `abierta` | Iniciar | `en_proceso` | Tiene al menos una tanda. Desde aquí la lista de tandas no cambia |
| `en_proceso` | Registrar o corregir etapas | `en_proceso` | Cada corrección se audita |
| `en_proceso` | Consolidar | `consolidada` | Todas las etapas de su ruta están registradas. Se emite el DPP |
| `abierta` o `en_proceso` | Anular, con motivo | `anulada` | Sus tandas quedan libres para otra corrida |
| `consolidada` | Anular el DPP, con motivo | `en_proceso` | Solo `admin_cooperativa`, y solo si la tanda final no se ha usado |

### Ingreso de tandas

1. La tanda está `validada`, su DOP está `vigente` y no pertenece a otra corrida no anulada.
2. El estado del producto coincide con la ruta: `baba` en ruta `completa`, `seco` en ruta `seco`.
3. En una corrida `segregada`, todas las tandas son del mismo productor. Agregar una de otro productor responde 400 con `corrida_segregada`.
4. Una tanda cuya parcela está `excluida` no entra a ninguna corrida. Responde 400 con `parcela_excluida`.
5. Una tanda cuya parcela pasó a `observada` después de emitirse el DOP sí puede entrar, pero la corrida recibe la alerta `tanda_de_parcela_observada`.
6. Al iniciar la corrida, la API vuelve a comprobar las reglas 1 y 4 para cada tanda.

### Registro de etapas

1. Una etapa se registra con su lugar, inicio, fin, método y responsable, más su dato propio si lo tiene.
2. El fin de una etapa no puede ser anterior a su inicio, y ninguna fecha puede ser futura.
3. Las etapas pueden registrarse en cualquier momento mientras la corrida esté `en_proceso`. El orden cronológico se comprueba al consolidar.
4. La etapa 1 toma como inicio y fin la primera y la última recepción de sus tandas.
5. La etapa 5 se llena con el tipo de manejo elegido al crear la corrida.
6. La fase visible de una corrida es la fase de su primera etapa todavía `pendiente`.

### Comprobación al consolidar

1. Toda etapa de la ruta está `registrada`, o `no_ocurrio` en el caso de las etapas 7 y 14.
2. Los inicios de las etapas registradas no retroceden en el tiempo de una etapa a la siguiente.
3. La etapa 19 tiene peso final, la 13 tiene humedad en la ruta `completa`, y la 21 tiene número de sacos.
4. Si algo falta, la API responde 400 con `etapas_incompletas` y la lista.

## Consolidación y tanda final

Consolidar cierra la corrida: compara el grano seco que salió contra lo que entró, fija la proporción de cada tanda y crea la tanda final que entra al stock.

### Rendimiento de la ruta completa

El rendimiento es el peso final de la etapa 19 dividido entre la suma de los pesos en baba de las tandas. Se compara con la banda de la configuración, de 0.33 a 0.45 por defecto. Con 1,000 kg de baba, la banda va de 330 a 450 kg de grano seco.

| Resultado | Alerta | Qué sugiere |
| --- | --- | --- |
| Dentro de la banda | Ninguna | El peso seco es coherente con la baba registrada |
| Por encima de `rendimiento_max` | `rendimiento_sobre_banda` | Salió más grano del que explica la baba registrada. Pudo entrar cacao sin registro |
| Por debajo de `rendimiento_min` | `rendimiento_bajo_banda` | Merma inusual, o salió grano que no se registró |

### Relación de peso en la ruta seco

En la ruta `seco` se compara el peso final contra la suma de los pesos secos de entrada. Si el peso final supera la entrada en más de 1 %, la corrida recibe la alerta `peso_final_supera_entrada`. No hay límite inferior, porque la selección descarta grano.

### Reglas de la consolidación

1. Con cualquier alerta de rendimiento, la explicación es obligatoria, con un mínimo de 50 caracteres. Sin ella la API responde 422.
2. Ninguna alerta impide consolidar. La explicación, la alerta y las cifras llegan al informe de hallazgos.
3. La consolidación recibe el peso final, la humedad final, la calidad, el número de sacos y el almacén. En la ruta `completa`, la humedad propuesta es la de la etapa 13.
4. Consolidar, fijar proporciones, crear la tanda final y emitir el DPP ocurren en una sola transacción.

### Proporciones

1. La proporción de cada tanda es su peso de entrada entre el peso total de entrada de la corrida.
2. Se guarda con 6 decimales. La última se ajusta para que la suma sea exactamente 1.
3. Los kilos de la tanda final atribuibles a un DOP son su proporción por el peso seco de la tanda final.

### Tabla `tandas_finales`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa dueña |
| `codigo` | text | `TF-{año}-{número de 6 dígitos}` |
| `corrida_id` | uuid | Corrida de origen. Única entre tandas finales no anuladas |
| `peso_seco_kg` | numeric(10,2) | Peso con que entra al stock |
| `saldo_kg` | numeric(10,2) | Kilos disponibles. Empieza igual al peso; lo descuenta la Parte 7 |
| `humedad_pct` | numeric(4,1) | Humedad final |
| `calidad` | text | Calidad asignada en la etapa 17 |
| `numero_sacos` | integer | Sacos envasados |
| `lugar_id` | uuid | Almacén donde queda |
| `ingreso_stock_en` | timestamptz | Momento de ingreso. Es la fecha que usa la selección FIFO de la Parte 7 |
| `estado` | text | `en_stock`, `agotada` o `anulada` |

### Catálogo de calidades

La calidad no es texto libre. Cada cooperativa mantiene su catálogo en la tabla `calidades`, con las columnas `cooperativa_id`, `nombre` y `activo`. La etapa 17 y la tanda final usan un valor de ese catálogo, y la Parte 7 lo usa para emparejar stock con órdenes de compra. Lo edita un `admin_cooperativa`, y una corrida no puede consolidarse si la cooperativa no tiene al menos una calidad activa.

## El DPP

El DPP es la copia sellada de una corrida consolidada: qué DOP entraron, qué pasó en cada etapa y qué salió. Se sella, se convierte en PDF y se verifica igual que el DOP de la Parte 5.

### Tabla `dpps`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa emisora |
| `codigo` | text | `DPP-{código de cooperativa}-{año}-{número de 6 dígitos}`. Único en toda la plataforma |
| `corrida_id` | uuid | Corrida que documenta |
| `tanda_final_id` | uuid | Tanda final que generó |
| `emitido_en`, `emitido_por` | timestamptz, uuid | Momento y perfil de la consolidación |
| `contenido` | jsonb | La copia sellada |
| `contenido_sha256` | char(64) | Huella del contenido |
| `pdf_documento_id` | uuid | Documento de tipo `dpp_pdf` |
| `estado` | text | `vigente` o `anulado` |
| `anulado_en`, `anulado_por`, `motivo_anulacion` | timestamptz, uuid, text | Se llenan al anular |

### Contenido sellado

| Bloque | Qué copia |
| --- | --- |
| Identificación | Código, cooperativa, fecha de emisión, ruta, tipo de manejo y quién consolidó |
| Entrada | Por cada tanda: código, código y huella de su DOP, productor, parcela, peso de entrada y proporción |
| Etapas | Las 23 etapas con su situación, lugar, inicio, fin, duración, método, responsable, distancia y dato propio |
| Salida | Peso final, humedad, calidad, número de sacos, almacén y código de la tanda final |
| Rendimiento | Peso de entrada, peso final, rendimiento calculado y banda usada |
| Alertas y explicación | Alertas de la corrida y la explicación de quien consolidó |
| No verificado | Etapas llenadas con valores de plantilla sin corrección, y pesos sin documento que los respalde |

### Sello, PDF y verificación

1. Se aplican las mismas reglas de sello y de PDF que al DOP, con la misma función de forma canónica y la misma librería.
2. El PDF presenta las 23 etapas como un diagrama de análisis de proceso: una fila por etapa, con el símbolo de su tipo, su lugar, su tiempo y su distancia.
3. La leyenda de la primera página dice: "Este documento reúne el registro del procesamiento de un lote de cacao tal como estaba al consolidarse. No es una constancia ni un certificado".
4. El código QR lleva a `#/verificar/dpp/{codigo}`. `GET /publico/dpps/{codigo}` responde sin token, con código, estado, fecha, huella y cooperativa.

### Anulación

1. Solo un `admin_cooperativa` anula un DPP, con motivo.
2. Solo es posible si el saldo de su tanda final sigue igual a su peso, es decir, si ninguna orden de compra la ha usado.
3. Al anular, la tanda final pasa a `anulada` y la corrida vuelve a `en_proceso` para corregirse.
4. Consolidar de nuevo emite un DPP nuevo, con otro código, y crea otra tanda final. El DPP anulado queda en el historial.

### Qué ve el productor

"Mis entregas" muestra, para cada tanda, en qué fase está su corrida o si ya entró al stock. El productor no ve el DPP ni datos de otros productores.

## Endpoints y pantallas de la Parte 6

Son 23 endpoints. El módulo "Lotes y proceso" queda con cuatro secciones: Recepción, DOP, Corridas y Stock.

### Proceso

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /proceso/etapas` | Personal | Catálogo de las 23 etapas |
| `GET /proceso/plantilla` | Personal | Plantilla de la cooperativa |
| `PUT /proceso/plantilla` | `admin_cooperativa` | Cambia la plantilla |
| `GET /calidades` | Personal | Catálogo de calidades de la cooperativa |
| `POST /calidades` | `admin_cooperativa` | Crea una calidad |
| `PATCH /calidades/{id}` | `admin_cooperativa` | Renombra o desactiva una calidad |

### Corridas

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /corridas` | Personal | Lista con filtros por estado y fase |
| `POST /corridas` | `admin_cooperativa`, `operador` | Crea una corrida con su ruta y su tipo de manejo |
| `GET /corridas/{id}` | Personal | Detalle con tandas, etapas, alertas y rendimiento provisional |
| `GET /corridas/tandas-disponibles` | Personal | Tandas que pueden entrar a una corrida, filtradas por ruta |
| `POST /corridas/{id}/tandas` | `admin_cooperativa`, `operador` | Agrega una tanda |
| `DELETE /corridas/{id}/tandas/{tanda_id}` | `admin_cooperativa`, `operador` | Quita una tanda de una corrida `abierta` |
| `POST /corridas/{id}/iniciar` | `admin_cooperativa`, `operador` | Pasa la corrida a `en_proceso` |
| `PATCH /corridas/{id}/etapas/{numero}` | `admin_cooperativa`, `operador` | Registra o corrige una etapa |
| `POST /corridas/{id}/consolidar` | `admin_cooperativa`, `operador` | Consolida, crea la tanda final y emite el DPP |
| `POST /corridas/{id}/anular` | `admin_cooperativa`, `operador` | Anula una corrida no consolidada, con motivo |

Al registrar una etapa, la API guarda en la columna `desde_plantilla` de `corrida_etapas` si el lugar, el método y la distancia quedaron iguales a los de la plantilla. El DPP lista esas etapas en su bloque "No verificado".

### DPP y stock

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /dpps` | Personal | Lista de DPP |
| `GET /dpps/{id}` | Personal | Detalle con contenido sellado y huella |
| `GET /dpps/{id}/pdf` | Personal | URL firmada del PDF |
| `POST /dpps/{id}/anular` | `admin_cooperativa` | Anula el DPP y reabre la corrida |
| `GET /tandas-finales` | Personal | Stock, con filtros por estado y calidad |
| `GET /tandas-finales/{id}` | Personal | Detalle con su composición por DOP y los kilos atribuibles a cada uno |

### Público

| Método y ruta | Qué hace |
| --- | --- |
| `GET /publico/dpps/{codigo}` | Verificación sin token: código, estado, fecha, huella y cooperativa |

Se auditan `plantilla.cambiar`, `corrida.crear`, `corrida.agregar_tanda`, `corrida.quitar_tanda`, `corrida.iniciar`, `corrida.registrar_etapa`, `corrida.consolidar`, `corrida.anular`, `dpp.emitir` y `dpp.anular`.

### Pantallas

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Corridas | `#/lotes/corridas` | Tablero de cinco columnas, una por fase. Cada corrida es una tarjeta con código, ruta, tipo de manejo, kilos de entrada, número de tandas y etapa actual |
| Nueva corrida | `#/lotes/corridas/nueva` | Elección de ruta y tipo de manejo, lista de tandas disponibles para marcar y botón "Iniciar" |
| Detalle de corrida | `#/corridas/{id}` | Pestañas Etapas, Tandas, Consolidación y DPP |
| Stock | `#/lotes/stock` | Tandas finales con código, calidad, peso, saldo, fecha de ingreso y almacén |
| Detalle de DPP | `#/dpps/{id}` | Contenido por bloques, huella, código QR y descarga del PDF |
| Plantilla de proceso | `#/cooperativa/plantilla-proceso` | Valores habituales de cada etapa |
| Verificar DPP | `#/verificar/dpp/{codigo}` | Página pública, igual a la del DOP |

### Reglas de la interfaz

1. En el tablero las tarjetas no se arrastran. Una corrida cambia de columna sola, cuando se registran sus etapas.
2. La pestaña Etapas muestra las 23 como lista vertical agrupada por fase. Cada etapa abre un formulario corto, ya lleno con la plantilla, que el operador confirma o corrige.
3. Las etapas que el sistema llena solas y las que no aplican a la ruta se muestran, pero no se editan.
4. La pestaña Consolidación calcula el rendimiento mientras se escribe el peso final y lo muestra junto a la banda. Si queda fuera, aparece el campo de explicación.
5. Una corrida `segregada` y una `mezclada` se distinguen por una etiqueta visible en la tarjeta y en el detalle.

## Pruebas y aceptación de la Parte 6

La Parte 6 está terminada cuando una corrida mezclada y una corrida de grano seco llegan al stock, cada una con su DPP, y el sistema señala un rendimiento fuera de banda sin bloquearlo.

### Pruebas automáticas mínimas

| Caso | Resultado esperado |
| --- | --- |
| Se crea una corrida | Nacen sus 23 etapas, llenas con la plantilla |
| Corrida de ruta `seco` | Las etapas 6 a 14 quedan `no_aplica` |
| Tanda en `seco` a una corrida de ruta `completa` | 400 con `ruta_no_coincide` |
| Tanda con DOP anulado, o que ya está en otra corrida | 400 |
| Tanda de otro productor en una corrida `segregada` | 400 con `corrida_segregada` |
| Tanda de una parcela `excluida` | 400 con `parcela_excluida` |
| Tanda de una parcela `observada` | Entra; la corrida recibe `tanda_de_parcela_observada` |
| Iniciar una corrida sin tandas | 400 |
| Agregar una tanda a una corrida `en_proceso` | 400 |
| Etapa con fin anterior al inicio, o con fecha futura | 422 |
| Etapa de transporte sin distancia | 422 |
| Marcar la etapa 9 como `no_ocurrio` | 422; solo las etapas 7 y 14 lo admiten |
| Consolidar con una etapa `pendiente` | 400 con `etapas_incompletas` y la lista |
| Consolidar con inicios que retroceden en el tiempo | 400 |
| 1,000 kg de baba y 400 kg de peso final | Rendimiento 0.400; sin alerta |
| 1,000 kg de baba y 500 kg de peso final, sin explicación | 422 |
| Mismo caso, con explicación | Consolida con `rendimiento_sobre_banda` |
| 1,000 kg de baba y 300 kg de peso final, con explicación | Consolida con `rendimiento_bajo_banda` |
| Ruta `seco`: 500 kg de entrada y 520 kg de peso final | Alerta `peso_final_supera_entrada`; exige explicación |
| Tres tandas de 500, 300 y 200 kg | Proporciones 0.500000, 0.300000 y 0.200000; suman 1 |
| Tres tandas de pesos que no dividen exacto | La suma de proporciones es exactamente 1 |
| Consolidación correcta | Corrida `consolidada`; tanda final `en_stock` con saldo igual al peso; DPP `vigente` con PDF |
| Falla la generación del PDF al consolidar | Nada cambia: ni corrida, ni tanda final, ni DPP |
| Etapa confirmada sin cambiar la plantilla | `desde_plantilla` es `true` y el DPP la lista en "No verificado" |
| `UPDATE` sobre el contenido de un DPP | Rechazado por el trigger |
| `operador` anula un DPP | 403 |
| Anular un DPP cuya tanda final ya tiene saldo descontado | 400 |
| Anular un DPP intacto y consolidar de nuevo | Nuevo código de DPP y nueva tanda final; el anterior queda `anulado` |
| Anular una corrida `en_proceso` | Sus tandas vuelven a estar disponibles |
| `GET /publico/dpps/{codigo}` sin token | 200 con solo los cinco datos permitidos |

Cada endpoint con token tiene además la prueba de las dos cooperativas definida en la Parte 2.

### Criterios de aceptación en producción

1. El administrador llena la plantilla de proceso de su cooperativa.
2. Un operador crea una corrida mezclada con tandas de dos productores y la inicia.
3. El operador registra las etapas desde un celular, confirmando o corrigiendo los valores de la plantilla.
4. La corrida avanza sola por las cinco columnas del tablero.
5. Al consolidar dentro de la banda se emite el DPP, y la tanda final aparece en Stock con su saldo completo.
6. Una segunda corrida con rendimiento fuera de banda exige explicación y se consolida con su alerta.
7. Una corrida de ruta `seco` salta las etapas de fermentación y secado y llega al stock.
8. El PDF del DPP muestra las 23 etapas como diagrama de análisis de proceso, con la huella y el código QR.
9. El detalle de una tanda final muestra qué DOP la componen y cuántos kilos corresponden a cada uno.
10. El productor ve en "Mis entregas" en qué fase está su cacao.
11. Todas las acciones aparecen en la auditoría y el CI está en verde, incluidas las Partes 1 a 5.

### Decisiones pendientes del equipo

- [ ] Confirmar la etapa 11, "Traslado a zona de secado", como la etapa que completa las 23.
- [ ] Confirmar el tipo asignado a cada etapa: operación, inspección, transporte, espera o almacenamiento.
- [ ] Confirmar que cada cooperativa define su propio catálogo de calidades.
- [ ] Confirmar que una tanda entra completa a una sola corrida y no se reparte entre dos cajones.
- [ ] Confirmar que "segregada" significa un solo productor, y no una sola parcela.
- [ ] Confirmar la tolerancia de 1 % para la ruta seco.

## Parte 7 — Orden de compra y genealogía

Una orden de compra pide una cantidad y una calidad. El sistema propone qué stock usar, del más antiguo al más nuevo, arma el lote de exportación y calcula cuántos kilos de ese lote vienen de cada parcela.

Esta parte abre la etapa 3 del flujo operativo, "Exportación".

### Decisiones tomadas por el equipo

| Tema | Decisión |
| --- | --- |
| Selección del stock | FIFO sugerido. Se puede cambiar, pero con un motivo escrito |
| Uso parcial | Una tanda final puede repartirse entre varias órdenes; lo que no se usa queda como saldo |
| Quién opera | `admin_cooperativa` u `operador` crean órdenes y arman lotes |

### Reglas de fondo

1. Una orden de compra tiene un solo lote de exportación. Los embarques parciales de una misma orden quedan fuera de esta versión.
2. El lote solo toma stock de la misma calidad que pide la orden.
3. La genealogía se calcula con las proporciones sobre la masa de entrada que fijó cada corrida en la Parte 6. No se estima ni se edita a mano.
4. La masa del lote y la suma de los kilos atribuidos a las parcelas coinciden siempre de forma exacta. Si no coinciden, el lote no se confirma.
5. La genealogía pertenece al lote y al DEX, no al DPP.
6. Apartarse del orden FIFO no se impide. Se registra el motivo y llega al informe de hallazgos.

### Fuera de alcance en esta parte

- La recomprobación de vigencias al cerrar el lote, que es la Parte 8.
- El informe de hallazgos y el DEX, que son la Parte 9.
- Precios, contratos, facturación y documentos de embarque.

## Importadores y órdenes de compra

El importador es un registro de la cooperativa, no un usuario: no inicia sesión. La orden de compra guarda lo que pidió y a dónde va.

### Tabla `importadores`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa dueña del registro |
| `razon_social` | text | Nombre del importador. Obligatorio |
| `direccion` | text | Dirección postal. Obligatoria |
| `pais` | text | País del importador. Obligatorio |
| `correo` | text | Correo de contacto. Obligatorio |
| `eori` | text | Número EORI. Opcional |
| `activo` | boolean | Por defecto `true` |

Nombre, dirección y correo son los datos del operador que el DEX entrega con los nombres de campo del Anexo II del Reglamento.

### Tabla `ordenes_compra`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa vendedora |
| `codigo` | text | `OC-{año}-{número de 6 dígitos}`, correlativo por cooperativa y año |
| `importador_id` | uuid | Referencia a `importadores` |
| `referencia_importador` | text | Número de orden que usa el importador. Opcional |
| `cantidad_kg` | numeric(10,2) | Masa neta pedida. Mayor que cero |
| `tolerancia_pct` | numeric(4,1) | Variación admitida sobre la cantidad. Por defecto 0 |
| `calidad_id` | uuid | Calidad pedida, del catálogo `calidades` |
| `partida_sa` | text | Partida del Sistema Armonizado. Valor fijo `1801`, cacao en grano |
| `pais_destino`, `lugar_destino` | text | País y puerto o ciudad de destino. Obligatorios |
| `fecha_entrega` | date | Fecha de entrega acordada |
| `estado` | text | `abierta`, `con_lote`, `cerrada` o `anulada` |
| `creada_por` | uuid | Perfil que la registró |

### Estados de la orden

| Estado | Significado |
| --- | --- |
| `abierta` | Registrada, sin lote confirmado. Se puede editar |
| `con_lote` | Tiene un lote confirmado. Ya no se edita |
| `cerrada` | Su lote tiene DEX emitido. Lo fija la Parte 9 |
| `anulada` | Se canceló, con motivo. Solo es posible si no tiene un lote confirmado |

## El lote de exportación

El lote reúne el stock que cumple una orden. Nace con una sugerencia FIFO, el usuario la acepta o la cambia, y al confirmarlo se descuentan los saldos y se calcula la genealogía.

### Tabla `lotes`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa dueña |
| `codigo` | text | `LE-{año}-{número de 6 dígitos}`, correlativo por cooperativa y año |
| `orden_compra_id` | uuid | Orden que atiende. Única entre lotes no anulados |
| `estado` | text | `en_armado`, `armado` o `anulado` en esta parte. Las Partes 8 y 9 agregan los siguientes |
| `masa_neta_kg` | numeric(10,2) | Suma de las asignaciones. Se fija al confirmar |
| `desviacion_fifo` | boolean | `true` si la selección confirmada difiere de la sugerencia |
| `motivo_desviacion` | text | Obligatorio si hay desviación. Mínimo 30 caracteres |
| `armado_por`, `armado_en` | uuid, timestamptz | Quién confirmó y cuándo |

### Tabla `lote_asignaciones`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `lote_id` | uuid | Referencia a `lotes` |
| `tanda_final_id` | uuid | Única por lote |
| `kg_asignados` | numeric(10,2) | Mayor que cero y no mayor que el saldo de la tanda final |

### Sugerencia FIFO

1. Se toman las tandas finales de la cooperativa en estado `en_stock`, con saldo mayor que cero y con la calidad de la orden.
2. Se ordenan por `ingreso_stock_en`, de la más antigua a la más nueva.
3. Se asigna el saldo de cada una, en ese orden, hasta completar `cantidad_kg`. La última puede quedar asignada en parte.
4. Si el stock no alcanza, la sugerencia indica cuántos kilos faltan y el lote no puede confirmarse.
5. La sugerencia se recalcula cada vez que se consulta. No reserva nada.

### Cambio de la selección

1. El usuario puede quitar una tanda final, agregar otra de la misma calidad o cambiar los kilos de cada una.
2. Al confirmar, la API compara la selección con la sugerencia FIFO de ese momento. Si difieren en alguna tanda final o en algún peso, hay desviación.
3. Con desviación, `motivo_desviacion` es obligatorio. Sin él la API responde 422.
4. Una tanda final de otra calidad no se acepta, tampoco con motivo. Responde 400 con `calidad_no_coincide`.

### Confirmación

1. La suma de las asignaciones debe quedar dentro de `cantidad_kg` más o menos `tolerancia_pct`. Si no, responde 400 con `masa_fuera_de_tolerancia`.
2. En una sola transacción, y con bloqueo de fila sobre cada tanda final, la API descuenta los saldos, fija `masa_neta_kg`, calcula la genealogía y pasa el lote a `armado`.
3. Si el saldo de alguna tanda final ya no alcanza, porque otro lote se confirmó antes, nada se guarda y la API responde 409 con `saldo_insuficiente`.
4. Una tanda final cuyo saldo llega a cero pasa a `agotada`.
5. La orden pasa a `con_lote`.

### Anulación del lote

1. Un lote `en_armado` o `armado` se anula con motivo. Lo hace un `admin_cooperativa` o un `operador`.
2. Al anular un lote `armado` se devuelven los saldos, las tandas finales `agotada` vuelven a `en_stock` y la orden vuelve a `abierta`.
3. La genealogía de un lote anulado se conserva como historial, marcada como anulada.
4. Un lote con DEX emitido ya no se anula por esta vía. Lo define la Parte 9.

## Genealogía del lote

La genealogía responde una pregunta: de los kilos de este lote, cuántos vienen de cada parcela. Se calcula al confirmar el lote, multiplicando los kilos tomados de cada tanda final por la proporción de cada tanda en su corrida.

### Cálculo

1. Por cada asignación del lote se toma su tanda final y la corrida que la originó.
2. Por cada tanda de esa corrida, los kilos atribuidos son `kg_asignados` por su `proporcion`.
3. Cada tanda lleva a su DOP, y el DOP a su parcela y a su productor.
4. Los kilos se guardan con 4 decimales. La fila más grande del lote absorbe la diferencia de redondeo, para que la suma sea exactamente `masa_neta_kg`.
5. La proporción de cada fila en el lote es sus kilos atribuidos entre `masa_neta_kg`.

### Tabla `lote_genealogia`

Una fila por cada combinación de asignación y tanda.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `lote_id` | uuid | Referencia a `lotes` |
| `tanda_final_id`, `dpp_id` | uuid | Stock de donde salió y su DPP |
| `tanda_id`, `dop_id` | uuid | Tanda de origen y su DOP |
| `parcela_id`, `productor_id` | uuid | Parcela y productor de esa tanda |
| `kg_atribuidos` | numeric(12,4) | Kilos del lote que vienen de esa tanda |
| `proporcion_lote` | numeric(9,6) | `kg_atribuidos` entre la masa del lote |

Las filas no se editan ni se borran. Si el lote se anula, quedan marcadas como anuladas.

### Ejemplo

Dos corridas mezcladas dejaron dos tandas finales de la misma calidad.

| Tanda final | Peso seco | Ingreso al stock | Tandas de origen y proporción |
| --- | --- | --- | --- |
| TF-A | 400 kg | 1 de octubre | Parcela P1: 0.5; parcela P2: 0.3; parcela P3: 0.2 |
| TF-B | 400 kg | 5 de octubre | Parcela P1: 0.6; parcela P4: 0.4 |

Llega una orden por 500 kg. La sugerencia FIFO toma los 400 kg de TF-A y 100 kg de TF-B, que queda con 300 kg de saldo.

| Parcela | Desde TF-A | Desde TF-B | Kilos en el lote | Proporción del lote |
| --- | --- | --- | --- | --- |
| P1 | 200 | 60 | 260 | 52 % |
| P2 | 120 | 0 | 120 | 24 % |
| P3 | 80 | 0 | 80 | 16 % |
| P4 | 0 | 40 | 40 | 8 % |
| Total | 400 | 100 | 500 | 100 % |

Este ejemplo es una de las pruebas automáticas obligatorias.

### Indicadores del lote

La API los calcula y los muestra tal cual. Ninguno aprueba ni desaprueba el lote; todos pasan al informe de hallazgos de la Parte 9.

| Indicador | Qué mide |
| --- | --- |
| `balance_masa` | Masa del lote, suma de kilos atribuidos y su diferencia, que debe ser cero |
| `numero_parcelas`, `numero_productores`, `numero_dops` | Cuántos orígenes distintos tiene el lote |
| `corridas_mezcladas` | Cuántas de las corridas de origen fueron `mezclada` |
| `cobertura_genealogia_pct` | Porcentaje de la masa del lote que llega hasta un DOP vigente |
| `concentracion_mayor_parcela_pct` | Parte del lote que viene de la parcela que más aporta |
| `concentracion_tres_parcelas_pct` | Parte del lote que viene de las tres parcelas que más aportan |
| `desviacion_fifo` | Si la selección se apartó del orden FIFO, con su motivo |

En el ejemplo, la mayor parcela concentra 52 % y las tres mayores, 92 %.

## Endpoints de la Parte 7

Son 19 endpoints en cuatro grupos. Crean y modifican el `admin_cooperativa` y el `operador`; el `lector` solo consulta.

### Importadores

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /importadores` | Personal | Lista los importadores |
| `POST /importadores` | `admin_cooperativa`, `operador` | Crea un importador |
| `PATCH /importadores/{id}` | `admin_cooperativa`, `operador` | Edita o desactiva un importador |

### Órdenes de compra

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /ordenes` | Personal | Lista con filtros por estado, importador y fechas |
| `POST /ordenes` | `admin_cooperativa`, `operador` | Crea una orden |
| `GET /ordenes/{id}` | Personal | Detalle, con su lote si existe |
| `PATCH /ordenes/{id}` | `admin_cooperativa`, `operador` | Edita una orden `abierta` |
| `POST /ordenes/{id}/anular` | `admin_cooperativa`, `operador` | Anula una orden sin lote confirmado, con motivo |

### Lotes

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `POST /ordenes/{id}/lote` | `admin_cooperativa`, `operador` | Crea el lote `en_armado` de la orden, con la sugerencia FIFO como selección inicial |
| `GET /lotes` | Personal | Lista con filtros por estado |
| `GET /lotes/{id}` | Personal | Detalle con asignaciones e indicadores |
| `GET /lotes/{id}/sugerencia-fifo` | Personal | Sugerencia FIFO calculada en ese momento, con los kilos faltantes si el stock no alcanza |
| `PUT /lotes/{id}/asignaciones` | `admin_cooperativa`, `operador` | Reemplaza la selección de un lote `en_armado` |
| `POST /lotes/{id}/confirmar` | `admin_cooperativa`, `operador` | Confirma el lote. Recibe `motivo_desviacion` si hay desviación |
| `POST /lotes/{id}/anular` | `admin_cooperativa`, `operador` | Anula el lote, con motivo |
| `GET /lotes/{id}/genealogia` | Personal | Filas de genealogía, totales por parcela y por productor, e indicadores |

### Trazabilidad

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /trazabilidad/parcelas/{id}` | Personal | Recorrido hacia adelante: tandas, DOP, corridas, tandas finales y lotes donde terminó el cacao de la parcela, con kilos |
| `GET /trazabilidad/productores/{id}` | Personal | El mismo recorrido, sumando todas las parcelas del productor |
| `GET /trazabilidad/dops/{id}` | Personal | Recorrido de un DOP: su corrida, su tanda final y los lotes que lo contienen |

Se auditan `importador.crear`, `importador.editar`, `orden.crear`, `orden.editar`, `orden.anular`, `lote.crear`, `lote.cambiar_seleccion`, `lote.confirmar` y `lote.anular`.

### Qué ve el productor

`GET /mi/tandas` agrega a cada tanda el estado `en_lote_de_exportacion` cuando parte de su cacao entró a un lote confirmado. No muestra importador, orden ni kilos del lote.

## Pantallas de la Parte 7

Esta parte estrena dos módulos de la barra lateral. Exportación recibe las órdenes y arma los lotes; Trazabilidad permite recorrer la cadena en los dos sentidos.

### Módulo Exportación

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Órdenes | `#/exportacion/ordenes` | Lista de órdenes con código, importador, cantidad, calidad, entrega y estado; botón "Nueva orden" |
| Nueva orden | `#/exportacion/ordenes/nueva` | Formulario en dos pasos: importador, y luego cantidad, calidad, destino y entrega |
| Detalle de orden | `#/ordenes/{id}` | Datos de la orden y el botón "Armar lote" |
| Armar lote | `#/lotes-exportacion/{id}/armar` | Selección de stock, descrita abajo |
| Lotes | `#/exportacion/lotes` | Lista de lotes con código, orden, masa, número de parcelas y estado |
| Detalle de lote | `#/lotes-exportacion/{id}` | Pestañas Selección, Genealogía e Indicadores |
| Importadores | `#/exportacion/importadores` | Lista y alta de importadores |

### Pantalla de armado del lote

1. Arriba, la cantidad pedida, la tolerancia y la suma seleccionada, que se actualiza en vivo.
2. Al centro, las tandas finales de la calidad pedida, de la más antigua a la más nueva, con la sugerencia FIFO ya marcada.
3. Cada fila muestra código, fecha de ingreso, saldo y un campo con los kilos a tomar.
4. Si el usuario cambia algo, aparece el aviso "La selección se aparta del orden FIFO" y el campo de motivo.
5. Si el stock no alcanza, se muestra cuántos kilos faltan y el botón "Confirmar lote" queda apagado.

### Módulo Trazabilidad

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Genealogía por lote | `#/trazabilidad/lotes` | Se elige un lote y se ve de qué parcelas viene |
| Rastreo por origen | `#/trazabilidad/origen` | Se busca un productor, una parcela o un DOP y se ve a qué lotes llegó su cacao |

### Vista de genealogía de un lote

1. Un diagrama de cinco columnas: parcelas, tandas, corridas, tandas finales y lote. Los enlaces entre columnas tienen un grosor proporcional a los kilos.
2. Una tabla por parcela con productor, kilos en el lote y proporción, ordenada de mayor a menor.
3. Un mapa con todas las parcelas del lote.
4. Al tocar una parcela en cualquiera de las tres vistas, se resalta en las otras dos.
5. El diagrama puede dibujarse con una librería cargada por CDN con versión fija, o en SVG propio.

### Reglas de la interfaz

1. Los indicadores se muestran como cifras con su nombre y una frase que explica qué miden. No llevan colores de aprobado o desaprobado.
2. Un lote con desviación FIFO muestra una etiqueta visible y su motivo.
3. Los kilos se muestran con dos decimales y las proporciones como porcentaje con un decimal.

## Pruebas y aceptación de la Parte 7

La Parte 7 está terminada cuando una orden se convierte en un lote confirmado cuya genealogía suma exactamente su masa, y se puede rastrear una parcela hasta el lote y el lote hasta sus parcelas.

### Pruebas automáticas mínimas

| Caso | Resultado esperado |
| --- | --- |
| El ejemplo de la sección de genealogía | P1 260 kg, P2 120 kg, P3 80 kg, P4 40 kg; TF-B queda con 300 kg de saldo |
| Sugerencia FIFO con tres tandas finales | Las toma por fecha de ingreso, y la última en parte |
| Sugerencia con stock de otra calidad disponible | No lo incluye |
| Stock insuficiente | La sugerencia informa los kilos faltantes; confirmar responde 400 |
| Confirmar la sugerencia sin cambios | `desviacion_fifo` es `false`; no pide motivo |
| Se elige una tanda final más nueva dejando saldo en una más antigua | Hay desviación; sin motivo responde 422 |
| Misma selección, con motivo | Confirma con `desviacion_fifo` en `true` |
| Tanda final de otra calidad en la selección | 400 con `calidad_no_coincide` |
| Asignar más kilos que el saldo | 422 |
| Suma fuera de la tolerancia de la orden | 400 con `masa_fuera_de_tolerancia` |
| Dos lotes confirman a la vez sobre la misma tanda final sin saldo para ambos | Uno confirma; el otro recibe 409 con `saldo_insuficiente` y no guarda nada |
| Confirmación correcta | Saldos descontados; lote `armado`; orden `con_lote`; genealogía creada |
| Tanda final cuyo saldo llega a cero | Pasa a `agotada` |
| Pesos que no dividen exacto | La suma de `kg_atribuidos` es exactamente `masa_neta_kg` |
| Suma de `proporcion_lote` | Exactamente 1 |
| Se anula un lote `armado` | Saldos devueltos; tandas finales de vuelta a `en_stock`; orden `abierta` |
| Segundo lote para una orden que ya tiene uno no anulado | 409 |
| `PATCH` sobre una orden `con_lote` | 400 |
| Anular un DPP cuya tanda final está en un lote confirmado | 400, según la Parte 6 |
| Rastreo hacia adelante de una parcela | Devuelve sus lotes con los kilos correctos |
| `lector` intenta crear una orden | 403 |
| Productor consulta `/mi/tandas` | Ve el estado `en_lote_de_exportacion`, sin importador ni kilos |

Cada endpoint tiene además la prueba de las dos cooperativas definida en la Parte 2.

### Criterios de aceptación en producción

1. Un operador registra un importador y una orden de compra.
2. Al armar el lote, la sugerencia FIFO aparece ya marcada, de la tanda final más antigua a la más nueva.
3. El operador confirma la sugerencia y los saldos del stock bajan en la sección Stock.
4. En una segunda orden, el operador cambia la selección, el sistema exige el motivo y el lote queda marcado con desviación.
5. Una orden que pide más de lo que hay muestra los kilos faltantes y no deja confirmar.
6. La genealogía del lote muestra el diagrama, la tabla y el mapa, y la suma de kilos por parcela coincide con la masa del lote.
7. Desde Trazabilidad se busca una parcela y se ve en qué lotes terminó su cacao.
8. Los indicadores del lote se muestran como cifras, sin colores de aprobación.
9. Todas las acciones aparecen en la auditoría y el CI está en verde, incluidas las Partes 1 a 6.

### Decisiones pendientes del equipo

- [ ] Confirmar que una orden tiene un solo lote y que los embarques parciales quedan fuera.
- [ ] Confirmar que el lote solo admite stock de la calidad pedida, sin excepciones.
- [ ] Confirmar que la tolerancia de cantidad se define en cada orden y que su valor por defecto es 0.
- [ ] Confirmar si el productor debe ver que su cacao entró a un lote de exportación.

## Parte 8 — Cooperativa y recomprobación

Antes de embarcar, el sistema vuelve a mirar todo lo que respalda el lote con la fecha del día: cada parcela, cada documento sellado, el expediente legal de la cooperativa y los documentos del embarque. Si algo venció desde el acopio, el lote queda bloqueado.

Según el flujo del equipo, este es el control que más falta en la práctica: entre el acopio y el embarque pasan semanas, y lo que estaba vigente al recibir el cacao puede no estarlo al despacharlo.

### Decisiones tomadas por el equipo

| Tema | Decisión |
| --- | --- |
| Desbloqueo por parcela observada | Se espera a que la parcela se habilite de nuevo. El stock no se reemplaza dentro del lote |
| Documentos legales de la cooperativa | Todos deben estar vigentes para que el lote quede listo |
| Documentos del embarque | Factura, packing list, certificado de origen y fitosanitario se cargan antes de emitir el DEX |

### Reglas de fondo

1. La recomprobación mira el estado de hoy, no el que quedó sellado en el DOP. El DOP dice cómo estaba la parcela al recibir la tanda; la recomprobación dice cómo está al embarcar.
2. Ninguna persona marca un lote como listo. El estado `listo` lo fija el sistema cuando todas las comprobaciones pasan.
3. La recomprobación no es una evaluación de riesgo. Solo confirma que cada requisito que ya se cumplió sigue en pie.
4. Un lote bloqueado no puede recibir DEX. Emitir el DEX, en la Parte 9, repite la recomprobación en ese mismo instante.
5. Una parcela `excluida` bloquea para siempre todo stock que contenga su cacao.

### Fuera de alcance en esta parte

- El informe de hallazgos y el DEX, que son la Parte 9.
- Avisos por correo o mensajes. Los pendientes se ven en la pantalla de inicio.
- Trámites ante SENASA, SUNAT o Aduanas. El sistema solo guarda los documentos que resultan de ellos.

## Expediente legal de la cooperativa

La cooperativa tiene un expediente de 6 casillas, tomadas del diagrama operativo del equipo. A diferencia del expediente de la parcela, aquí no hay exenciones: las seis deben estar vigentes.

### Los 6 documentos

| Código | Documento | Grupo | Registro público consultable |
| --- | --- | --- | --- |
| `rnca` | Registro Nacional de Cooperativas Agrarias, de MIDAGRI | Registro agrario | No |
| `partida_sunarp` | Partida registral de la cooperativa en SUNARP | Identificación legal | Sí |
| `ficha_ruc` | Ficha RUC de SUNAT | Identificación legal | Sí |
| `vigencia_poderes` | Vigencia de poderes del representante legal, de SUNARP | Representación legal | Sí |
| `ruc_comercio_exterior` | Sustento del RUC habilitado para comercio exterior | Capacidad exportadora | Sí |
| `registro_aduanas` | Registro como exportador ante SUNAT Aduanas | Capacidad exportadora | No |

La columna "Registro público consultable" trae valores iniciales que el equipo debe confirmar. Los tipos se agregan al catálogo `documentos_legales.py` de la Parte 4.

### Cómo se guardan

1. Usan la tabla `documentos`, con `entidad = cooperativa` y `entidad_id` igual al identificador de la cooperativa.
2. Llevan los mismos datos que los documentos legales de la parcela: número, entidad emisora, fecha de emisión, fecha de vencimiento y cotejo.
3. Los carga y los anula solo un `admin_cooperativa`. El `operador` y el `lector` los ven.
4. El cotejo en fuente sigue las reglas de la Parte 4.

### Estado del expediente

1. Cada casilla tiene uno de cuatro estados: `vigente`, `por_vencer`, `vencido` o `faltante`, con las mismas condiciones de la Parte 4.
2. El expediente está `completo` cuando las seis casillas están `vigente` o `por_vencer`.
3. El estado se calcula al consultar, con la fecha del día.

### Datos de la cooperativa

La tabla `cooperativas` gana cuatro columnas, que el DEX necesita para identificar al exportador.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `direccion_postal` | text | Dirección de la cooperativa |
| `correo` | text | Correo de contacto |
| `representante_nombre` | text | Nombre del representante legal |
| `representante_dni` | char(8) | DNI del representante legal |

Las edita un `admin_cooperativa`. Las cuatro son obligatorias para que un lote quede `listo`.

## Documentos de embarque del lote

Cada lote lleva cuatro documentos propios del embarque. Los cuatro deben estar cargados antes de emitir el DEX.

### Los 4 documentos

| Código | Documento | Emisor habitual |
| --- | --- | --- |
| `factura_comercial` | Factura comercial | La cooperativa |
| `packing_list` | Lista de empaque | La cooperativa |
| `certificado_origen` | Certificado de origen | La entidad que lo emite para el destino |
| `certificado_fitosanitario` | Certificado fitosanitario | SENASA |

### Reglas

1. Usan la tabla `documentos`, con `entidad = lote`. Llevan número, entidad emisora y fecha de emisión.
2. Los cargan un `admin_cooperativa` o un `operador`, en un lote `armado`, `bloqueado` o `listo`.
3. Un documento de embarque se anula con motivo, como cualquier otro. Si falta alguno, el lote deja de estar `listo`.
4. El sistema no lee su contenido ni compara sus cifras con las del lote. Que la masa de la factura coincida con la del lote lo revisa una persona.
5. Tras emitir el DEX, los documentos de embarque del lote ya no se anulan ni se reemplazan.

## Recomprobación del lote

Recomprobar es ejecutar nueve comprobaciones sobre un lote confirmado. Si todas pasan, el lote queda `listo`; si alguna falla, queda `bloqueado` y la pantalla dice exactamente qué falló y dónde.

### Las 9 comprobaciones

| Comprobación | Sobre qué | Pasa cuando |
| --- | --- | --- |
| `parcelas_habilitadas` | Cada parcela de la genealogía | Su estado de habilitación hoy es `habilitada` |
| `sin_parcelas_excluidas` | Cada parcela de la genealogía | Ninguna está `excluida` |
| `dops_vigentes` | Cada DOP de la genealogía | Todos están `vigente` |
| `dpps_vigentes` | Cada DPP de las tandas finales del lote | Todos están `vigente` |
| `genealogia_cuadra` | El lote | La diferencia del balance de masa es cero |
| `expediente_cooperativa_completo` | La cooperativa | Sus seis casillas están `vigente` o `por_vencer` |
| `datos_cooperativa_completos` | La cooperativa | Tiene dirección postal, correo y representante legal |
| `importador_completo` | El importador de la orden | Tiene nombre, dirección y correo |
| `documentos_embarque_completos` | El lote | Tiene los cuatro documentos de embarque vigentes |

Cada comprobación que falla lista sus casos, por ejemplo: la parcela, su estado y el requisito de habilitación que dejó de cumplir.

### Tabla `recomprobaciones`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `lote_id` | uuid | Referencia a `lotes` |
| `ejecutada_por` | uuid | Perfil que la pidió. Nulo si la ejecutó el sistema |
| `ejecutada_en` | timestamptz | Momento de la ejecución |
| `resultado` | text | `sin_observaciones` o `con_observaciones` |
| `detalle` | jsonb | Las nueve comprobaciones, cada una con su resultado y sus casos |

Las filas no se editan ni se borran.

### Estados del lote

| Desde | Acción | Hacia | Condición |
| --- | --- | --- | --- |
| `armado` | Recomprobar | `listo` | Las nueve comprobaciones pasan |
| `armado` | Recomprobar | `bloqueado` | Alguna falla |
| `bloqueado` | Recomprobar | `listo` | Las nueve pasan |
| `listo` | Recomprobar | `bloqueado` | Alguna falla |
| `listo` | Emitir el DEX, en la Parte 9 | `cerrado` | La recomprobación se repite al emitir y pasa |
| `armado`, `bloqueado` o `listo` | Anular, con motivo | `anulado` | Un lote `bloqueado` o `listo` solo lo anula un `admin_cooperativa` |

### Cómo se desbloquea

1. Si una parcela está `observada`, se corrige en la parcela lo que falta, un administrador la habilita de nuevo y se recomprueba el lote.
2. No se puede cambiar el stock de un lote `armado`, `bloqueado` o `listo`. La selección solo se edita mientras el lote está `en_armado`.
3. Si falla el expediente de la cooperativa o falta un documento de embarque, se carga el documento y se recomprueba.
4. Si una parcela está `excluida`, el lote no tiene salida. Solo puede anularse.

### Stock retenido

1. Una tanda final está retenida cuando alguna de las tandas de su corrida viene de una parcela `excluida`. El cacao ya se mezcló y no se puede separar.
2. La API calcula el campo `retenida` al consultar; no es un estado guardado.
3. Una tanda final retenida no aparece en la sugerencia FIFO ni se acepta en una selección. Responde 400 con `stock_retenido`.

### Tarea diaria

El bucle en segundo plano recomprueba una vez al día los lotes `listo` y `bloqueado`. Guarda una fila nueva solo cuando el resultado o sus casos cambian. Así un lote se desbloquea solo cuando sus parcelas vuelven a estar habilitadas.

### Exclusión posterior al cierre

Si una parcela se excluye cuando su cacao ya está en un lote `cerrado`, el DEX no se altera, porque está sellado. El lote recibe la alerta `exclusion_posterior_al_cierre`, que se audita y aparece en la pantalla de inicio. Informar al importador es responsabilidad de la cooperativa y ocurre fuera del sistema.

## Endpoints y pantallas de la Parte 8

Son 9 endpoints. La pantalla de inicio deja de ser un saludo y pasa a mostrar lo que hay que atender.

### Cooperativa

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /cooperativa` | Personal | Datos de la cooperativa |
| `PATCH /cooperativa` | `admin_cooperativa` | Edita dirección postal, correo y representante legal |
| `GET /cooperativa/expediente` | Personal | Las seis casillas con su estado y sus documentos |
| `POST /cooperativa/documentos` | `admin_cooperativa` | Carga un documento legal de la cooperativa |

El cotejo y la anulación usan los endpoints de documentos de las Partes 3 y 4.

### Lote

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `POST /lotes/{id}/documentos` | `admin_cooperativa`, `operador` | Carga un documento de embarque |
| `GET /lotes/{id}/documentos` | Personal | Lista los documentos de embarque |
| `POST /lotes/{id}/recomprobar` | `admin_cooperativa`, `operador` | Ejecuta la recomprobación y devuelve su resultado |
| `GET /lotes/{id}/recomprobaciones` | Personal | Historial de recomprobaciones |

### Pendientes

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /pendientes` | Personal | Resumen de lo que requiere atención en la cooperativa |

`GET /pendientes` devuelve, con cantidad y lista: documentos de parcelas por vencer y vencidos, documentos de la cooperativa por vencer y vencidos, parcelas observadas, tandas sin validar, lotes bloqueados con su motivo, y lotes que no están `listo` a 15 días o menos de su fecha de entrega.

Se auditan `cooperativa.editar`, `lote.recomprobar` y el cambio de estado del lote que resulte.

### Pantallas

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Inicio | `#/inicio` | Panel de pendientes, agrupados por tipo, cada uno con enlace al registro que hay que atender |
| Datos y expediente legal | `#/cooperativa/legal` | Datos de la cooperativa y sus seis casillas, con estado, nivel de verificación y acciones |
| Detalle de lote, pestaña Embarque | `#/lotes-exportacion/{id}` | Los cuatro documentos de embarque, con carga y anulación |
| Detalle de lote, pestaña Recomprobación | `#/lotes-exportacion/{id}` | Las nueve comprobaciones con su resultado, los casos que fallan y el botón "Recomprobar" |

### Reglas de la interfaz

1. Un lote `bloqueado` muestra una franja fija con el número de comprobaciones que fallan y un enlace a la pestaña Recomprobación.
2. Cada caso que falla enlaza al registro donde se corrige: la parcela, el expediente de la cooperativa o el documento que falta.
3. La pantalla nombra los resultados como "sin observaciones" y "con observaciones". No usa "aprobado" ni "conforme".
4. El panel de inicio muestra primero lo vencido, luego lo que está por vencer y al final lo demás.
5. El productor no ve el panel de pendientes de la cooperativa. Su inicio muestra solo sus propios pendientes y el estado de sus parcelas.

## Pruebas y aceptación de la Parte 8

La Parte 8 está terminada cuando un lote se bloquea solo porque a una de sus parcelas se le venció un documento después del acopio, y se desbloquea solo cuando la parcela vuelve a estar habilitada.

### Pruebas automáticas mínimas

| Caso | Resultado esperado |
| --- | --- |
| Lote con todo en orden | Recomprobación `sin_observaciones`; lote `listo` |
| Una parcela del lote pasa a `observada` | `parcelas_habilitadas` falla y nombra la parcela y el requisito; lote `bloqueado` |
| Esa parcela se habilita de nuevo y se recomprueba | Lote `listo` |
| Una parcela del lote pasa a `excluida` | `sin_parcelas_excluidas` falla; el lote no vuelve a `listo` con ninguna acción |
| Tanda final con cacao de una parcela excluida | `retenida` es `true`; no aparece en la sugerencia FIFO |
| Esa tanda final en una selección | 400 con `stock_retenido` |
| Falta un documento legal de la cooperativa | `expediente_cooperativa_completo` falla |
| Documento de la cooperativa con vencimiento ayer | La casilla queda `vencido` y el lote `bloqueado` |
| Cooperativa sin representante legal registrado | `datos_cooperativa_completos` falla |
| Faltan documentos de embarque | `documentos_embarque_completos` falla y lista los que faltan |
| Se anula un documento de embarque de un lote `listo` | La siguiente recomprobación deja el lote `bloqueado` |
| `PUT /lotes/{id}/asignaciones` sobre un lote `bloqueado` | 400 |
| `operador` anula un lote `bloqueado` | 403 |
| `operador` carga un documento legal de la cooperativa | 403 |
| Tarea diaria sobre un lote `bloqueado` cuya parcela ya está habilitada | El lote pasa a `listo`; queda una recomprobación con usuario nulo |
| Tarea diaria sin cambios | No se crea una fila nueva |
| Parcela excluida después de cerrar el lote | El lote recibe `exclusion_posterior_al_cierre`; el DEX no cambia |
| `UPDATE` o `DELETE` sobre `recomprobaciones` | Rechazado por el trigger |
| `GET /pendientes` con un documento vencido y un lote bloqueado | Ambos aparecen, con enlace a su registro |

Cada endpoint tiene además la prueba de las dos cooperativas definida en la Parte 2.

### Criterios de aceptación en producción

1. El administrador completa los datos de la cooperativa y carga sus seis documentos legales.
2. Un operador carga los cuatro documentos de embarque de un lote.
3. Al recomprobar un lote con todo en orden, queda `listo` y las nueve comprobaciones se muestran sin observaciones.
4. Se adelanta el vencimiento de un documento de una parcela del lote: la parcela pasa a observada y el lote a bloqueado, con el caso exacto a la vista.
5. Tras renovar el documento y habilitar la parcela, el lote vuelve a `listo`.
6. Mientras el lote está bloqueado, nadie puede cambiar su selección de stock.
7. La pantalla de inicio muestra los documentos por vencer, las parcelas observadas y los lotes bloqueados, con enlaces que llevan al registro correcto.
8. Una tanda final con cacao de una parcela excluida aparece como retenida en Stock y no se puede asignar.
9. Todas las acciones aparecen en la auditoría y el CI está en verde, incluidas las Partes 1 a 7.

### Decisiones pendientes del equipo

- [ ] Definir qué documento concreto sustenta el "RUC comercio exterior" y cuál el "Registro SUNAT Aduanas".
- [ ] Confirmar qué documentos de la cooperativa tienen registro público consultable.
- [ ] Definir qué documentos de la cooperativa exigen fecha de vencimiento.
- [ ] Confirmar que un lote bloqueado solo puede anularlo un administrador.
- [ ] Confirmar el aviso de 15 días antes de la fecha de entrega.

## Parte 9 — Informe de hallazgos y DEX

El DEX es el expediente que la cooperativa entrega al importador: todo lo que respalda un lote, más un informe que dice dónde están los riesgos y a qué se deben. No concluye ni se firma. El importador lo lee, evalúa, decide y presenta la DDS en TRACES.

Esta parte cierra la etapa 3 del flujo operativo.

> **Adenda de la Parte 4:** se suman al catálogo los hallazgos de su sección 8:
> - `conjuntos_registran_bosque_2020`, `conjuntos_registran_cambio_posterior`, `conjuntos_discrepan`, `mapbiomas_pocos_pixeles` y `mapbiomas_sin_cobertura_reciente`.
> - En "Datos del lote", cuántos conjuntos de datos se consultaron por parcela, con el mínimo y el máximo del lote.
>
> El contenido sellado del DEX copia la tabla de convergencia de cada parcela.

### Decisiones tomadas por el equipo

| Tema | Decisión |
| --- | --- |
| Criterios propios de cada importador | Fuera de la primera versión |
| Entrega al importador | La cooperativa descarga el expediente y lo envía por su cuenta. El importador no tiene cuenta ni enlace |
| Idioma | Español e inglés |
| Quién emite | Solo un `admin_cooperativa`, según la matriz de la Parte 2 |

### Principio: exponer, no concluir

1. Declarar "riesgo despreciable" hace responsable a quien lo declara si la debida diligencia no se sostiene. El sistema no lo declara.
2. El informe cuenta hechos, los ata a su origen y dice lo que no se pudo comprobar, incluido lo que juega en contra de la cooperativa.
3. El informe no puntúa el lote. No hay puntaje, semáforo, porcentaje de cumplimiento ni calificación.
4. Cada hallazgo se redacta sin adjetivos y sin ponderación: qué se observó, en qué parcela o tanda, con qué dato.
5. El DEX no lleva firma. Lo que se firma es la DDS, y la firma el importador.
6. Los textos del informe salen de plantillas fijas. No se generan con un modelo de lenguaje: los mismos datos producen siempre el mismo texto.

### Qué sale del sistema

| Archivo | Para qué le sirve al importador |
| --- | --- |
| DEX en PDF, en español y en inglés | Leer el expediente completo y conservarlo |
| GeoJSON de las parcelas del lote | Cargar la geolocalización al presentar la DDS |
| Datos del Anexo II, en JSON | Tener a mano los campos de la DDS que salen de este flujo |
| Informe de hallazgos, en JSON | Procesar los hallazgos en sus propias herramientas |

### Fuera de alcance en esta parte

- La presentación de la DDS y cualquier conexión con TRACES.
- La afirmación de riesgo y la firma, que son del operador.
- Los criterios configurables por importador.
- El historial de deforestación de la región, que el flujo nombra como contexto. El informe lo declara como no cubierto.

## Informe de hallazgos

El informe recorre las tres etapas hacia atrás desde el lote y reúne todo lo que pesa sobre el riesgo. Tiene cinco secciones, y cada hallazgo va etiquetado con el criterio del artículo 10 al que corresponde.

### Secciones del informe

| Sección | Contenido |
| --- | --- |
| Datos del lote | Orden, masa, cobertura del pedido, número de parcelas y productores, concentración, corridas mezcladas y antigüedad de los análisis de cobertura |
| Hallazgos | Lo que alguna regla del sistema señaló, en tres grupos |
| Lo que no pudimos verificar | Lo que el sistema recibió sin poder comprobarlo |
| Contexto | Clasificación de riesgo del país y certificaciones vigentes de la cooperativa |
| Mensaje final | Resumen directo de dónde están los riesgos y a qué se deben. Termina devolviendo la conclusión al operador |

### Grupos de hallazgos

| Grupo | Código | Qué reúne |
| --- | --- | --- |
| Impide el cierre del lote | `impide_cierre` | Comprobaciones de la Parte 8 que fallan. En un DEX emitido este grupo está vacío, porque un lote bloqueado no recibe DEX |
| Requiere atención | `requiere_atencion` | Alertas y decisiones tomadas con nota: algo se salió de lo habitual y alguien lo explicó |
| No verificado | `no_verificado` | Datos declarados, documentos sin cotejo o sin registro consultable, y análisis hechos por aproximación |

### Datos de cada hallazgo

| Campo | Contenido |
| --- | --- |
| `codigo` | Tipo de hallazgo, del catálogo |
| `grupo` | Uno de los tres grupos |
| `etapa` | Etapa del flujo donde se originó: 1, 2 o 3 |
| `criterio` | Número del criterio del artículo 10, de 1 a 10 |
| `sujeto` | A qué se refiere: parcela, tanda, corrida, lote o cooperativa, con su código |
| `hecho` | Una frase generada por plantilla, en español y en inglés |
| `datos` | Las cifras y fechas que sustentan el hecho |
| `peso_en_lote_pct` | Qué parte de la masa del lote aporta el sujeto, cuando aplica |
| `explicacion` | La nota o el motivo que escribió la persona que decidió, cuando existe |

### Los diez criterios del artículo 10

Siete criterios se alimentan desde el flujo. Los otros tres se nombran igual, para que el operador sepa qué le queda por cubrir.

| N.º | Criterio | De dónde sale en CacaoTrace |
| --- | --- | --- |
| 1 | Presencia de bosque y prevalencia de deforestación | Análisis de cobertura forestal por parcela |
| 2 | Complejidad de la cadena | Número de parcelas y productores, concentración y corridas mezcladas |
| 3 | Riesgo de mezcla o elusión | Rendimiento, kilos por hectárea, superposiciones y desviación FIFO |
| 4 | Tenencia y derechos de terceros | Estado del título o de la posesión, exenciones y vencimientos |
| 5 | Corrupción y fraude | Documentos sin registro consultable o sin cotejar |
| 6 | Clasificación de riesgo del país | Contexto registrado por el superadministrador |
| 7 | Certificación de terceros | Certificaciones vigentes de la cooperativa |
| 8 | Derechos humanos y conflicto armado | No cubierto por el sistema. Se declara |
| 9 | Reclamaciones previas | No cubierto. Corresponde al historial del importador |
| 10 | Conclusiones del grupo de expertos | No cubierto. Corresponde al importador |

Claude Code contrasta esta lista con el texto del artículo 10 del Reglamento (UE) 2023/1115 antes de fijar los nombres de los criterios en el informe.

### Cuándo se calcula

1. El informe se puede consultar en cualquier momento para un lote `armado`, `bloqueado` o `listo`. Esa versión es preliminar y cambia con los datos.
2. Al emitir el DEX, el informe se calcula una última vez y queda sellado dentro del expediente.

## Catálogo de hallazgos

El catálogo es cerrado: cada hallazgo nace de una regla que ya existe en las Partes 3 a 8. Nadie escribe hallazgos a mano; las notas de las personas aparecen solo como explicación de un hallazgo.

### Etapa 1, parcela

| Código | Se genera cuando | Criterio | Grupo |
| --- | --- | --- | --- |
| `analisis_requiere_revision` | Una fuente entregó un valor distinto de riesgo bajo, o GFW informó alertas o pérdida desde 2021. Incluye lo que registró la visita de campo | 1 | Requiere atención |
| `diez_hectareas_o_mas` | La parcela tiene 10 ha o más | 1 | Requiere atención |
| `area_discrepante` | El área declarada difiere más de 20 % de la calculada | 3 | Requiere atención |
| `superposicion_aceptada` | La parcela tiene una superposición aceptada con nota | 3 | Requiere atención |
| `superposicion_con_excluida` | La parcela se superpone con una parcela excluida | 3 | Requiere atención |
| `tenencia_solo_posesion` | La tenencia se apoya solo en una constancia de posesión | 4 | Requiere atención |
| `exencion_declarada` | Una casilla del expediente está cubierta por una exención | 4 | Requiere atención |
| `documento_por_vencer` | Una casilla está `por_vencer` al emitir | 4 | Requiere atención |
| `coordenada_no_recorrida` | Ningún técnico recorrió el lindero después del último cambio de geometría. Indica quién registró la geometría | 1 | No verificado |
| `analisis_por_aproximacion` | Una parcela de tipo punto se analizó como círculo | 1 | No verificado |
| `documento_sin_registro_consultable` | Un documento del expediente no tiene registro público contra el cual cotejarse | 5 | No verificado |
| `documento_sin_cotejar` | Un documento con registro público no fue cotejado | 5 | No verificado |

### Etapa 2, acopio y proceso

| Código | Se genera cuando | Criterio | Grupo |
| --- | --- | --- | --- |
| `tanda_observada` | La tanda fue observada antes de validarse. Incluye el motivo | 3 | Requiere atención |
| `volumen_acumulado_excede_tope` | El volumen acumulado de la parcela superó el tope de la cooperativa | 3 | Requiere atención |
| `dias_cosecha_entrega_altos` | Pasaron más días de lo configurado entre la cosecha y la entrega | 3 | Requiere atención |
| `peso_difiere_de_guia` | El peso de la guía difiere del peso en balanza | 3 | Requiere atención |
| `guia_usada_por_otro_productor` | La misma guía aparece en la tanda de otro productor | 3 | Requiere atención |
| `registro_y_validacion_misma_persona` | La misma persona registró y validó la tanda | 5 | Requiere atención |
| `rendimiento_sobre_banda` | El rendimiento de la corrida superó la banda. Incluye la explicación | 3 | Requiere atención |
| `rendimiento_bajo_banda` | El rendimiento quedó bajo la banda. Incluye la explicación | 3 | Requiere atención |
| `peso_final_supera_entrada` | En la ruta seco salió más peso del que entró | 3 | Requiere atención |
| `guia_sin_cotejar` | La guía de remisión no fue cotejada | 5 | No verificado |
| `etapas_desde_plantilla` | La corrida tiene etapas confirmadas con los valores de la plantilla. Indica cuántas | 3 | No verificado |

### Etapa 3, lote

| Código | Se genera cuando | Criterio | Grupo |
| --- | --- | --- | --- |
| `comprobacion_fallida` | Una comprobación de la Parte 8 falla. Uno por cada caso | Según la comprobación | Impide el cierre del lote |
| `parcela_cambio_de_estado` | La parcela pasó por `observada` entre la emisión de su DOP y el cierre | 1 o 4, según el requisito que dejó de cumplirse | Requiere atención |
| `desviacion_fifo` | La selección de stock se apartó del orden FIFO. Incluye el motivo | 3 | Requiere atención |

### Hallazgos que están siempre

| Código | Texto | Criterio |
| --- | --- | --- |
| `vinculo_fisico_no_comprobado` | El sistema no comprueba el vínculo físico entre el grano y la parcela | 3 |
| `historial_regional_no_cubierto` | El sistema no incluye el historial de deforestación de la región | 1 |
| `criterio_no_cubierto` | Uno por cada criterio 8, 9 y 10: el sistema no lo cubre y le corresponde al operador | 8, 9 y 10 |

Los tres pertenecen al grupo No verificado.

### Reglas del catálogo

1. Cada regla es una función propia en `backend/app/services/hallazgos/`, con su prueba. Agregar una regla no modifica las demás.
2. Los hallazgos se generan uno por sujeto. El mensaje final los agrupa; los datos los conservan separados.
3. Dentro de cada grupo se ordenan por `peso_en_lote_pct`, de mayor a menor.
4. Un hallazgo no desaparece porque alguien lo haya explicado. La explicación lo acompaña.

## Mensaje final del informe

El mensaje final es lo primero que lee el importador. Dice en pocas líneas dónde están los riesgos y a qué se deben, y termina devolviéndole la conclusión.

### Estructura fija

1. Encabezado: código de la orden, masa del lote, número de parcelas y de productores, y departamentos de origen.
2. "Impide el cierre del lote", con su número de hallazgos. Solo aparece en informes preliminares.
3. "Requiere atención", con su número de hallazgos.
4. "No verificado", con su número de hallazgos.
5. "Contexto": clasificación del país y certificaciones de la cooperativa.
6. Cierre fijo: "La evaluación de riesgo y su conclusión corresponden al operador".

### Reglas de redacción

1. Cada grupo abre con su nombre y su número de hallazgos. Si está vacío, dice "Ningún hallazgo en este grupo".
2. Los hallazgos del mismo código se cuentan por separado, pero se redactan juntos en una sola frase que nombra las parcelas y su peso sumado en el lote.
3. Dentro de cada grupo, las frases van de mayor a menor peso en el lote.
4. Los porcentajes llevan dos decimales y las fechas se escriben completas.
5. Lo que dice una fuente se cita entre comillas y con su nombre, por ejemplo "Whisp: requiere más información".
6. Las plantillas no contienen adjetivos de valoración. Una prueba automática busca en ellas palabras como "grave", "leve", "preocupante", "seguro" y "confiable".
7. La versión en inglés tiene la misma estructura. Su cierre es "The risk assessment and its conclusion are the operator's responsibility".

### Ejemplo ilustrativo

Los datos de este ejemplo son inventados y solo muestran la forma del texto.

> Orden OC-2026-000031 · 1,500.00 kg de cacao en grano seco · 7 parcelas de 6 productores en San Martín.
>
> Requiere atención — 3. El análisis de cobertura forestal de PA-00004, que aporta 12.40 % del lote, devolvió "Whisp: requiere más información"; la visita de campo del 14 de agosto de 2026 registró cacao bajo sombra. La tenencia de PA-00003 y PA-00008, que aportan 21.30 % del lote, se apoya solo en constancia de posesión.
>
> No verificado — 12. Cinco de las siete parcelas tienen coordenadas que ningún técnico recorrió; aportan 63.75 % del lote. Las constancias de posesión de PA-00003 y PA-00008 no tienen registro público contra el cual cotejarse. El sistema no comprueba el vínculo físico entre el grano y la parcela. El sistema no incluye el historial de deforestación de la región. Los criterios de derechos humanos y conflicto armado, reclamaciones previas y conclusiones del grupo de expertos no están cubiertos por el sistema.
>
> Contexto. Perú figura como riesgo estándar en la clasificación registrada el 3 de octubre de 2026. La cooperativa no registra certificaciones vigentes.
>
> La evaluación de riesgo y su conclusión corresponden al operador.

## El DEX

El DEX es la copia sellada del lote en el momento de emitirse: su genealogía, el respaldo de cada parcela, la recomprobación de ese instante y el informe de hallazgos. Se sella como el DOP y el DPP.

### Tabla `dex`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Cooperativa emisora |
| `codigo` | text | `DEX-{código de cooperativa}-{año}-{número de 6 dígitos}`. Único en toda la plataforma |
| `lote_id` | uuid | Lote que documenta. Único entre DEX no anulados |
| `emitido_en`, `emitido_por` | timestamptz, uuid | Momento y perfil de la emisión |
| `contenido` | jsonb | La copia sellada |
| `contenido_sha256` | char(64) | Huella del contenido |
| `archivos` | jsonb | Identificador de documento de cada archivo generado |
| `estado` | text | `vigente` o `anulado` |
| `anulado_en`, `anulado_por`, `motivo_anulacion` | timestamptz, uuid, text | Se llenan al anular |

### Contenido sellado

| Bloque | Qué copia |
| --- | --- |
| Identificación | Código, fecha de emisión y quién emitió |
| Exportador | Razón social, RUC, dirección postal, correo y representante legal de la cooperativa, y sus seis documentos legales con número, fechas y nivel de verificación |
| Importador y orden | Nombre, dirección, país, correo y EORI del importador; código, referencia, cantidad, calidad, destino y entrega de la orden |
| Producto | Partida SA 1801, descripción "cacao en grano", nombre científico Theobroma cacao L., masa neta y país de producción |
| Genealogía | Por parcela: código, productor, ubicación, área, tipo de geometría, kilos y proporción en el lote, e intervalo de cosecha de sus tandas |
| Respaldo por parcela | Códigos y huellas de sus DOP, estado de habilitación, resultado de cada fuente de análisis con fecha y versión, y estado de sus siete casillas |
| Proceso | Códigos y huellas de los DPP, y rendimiento de cada corrida |
| Embarque | Los cuatro documentos, con número, emisor, fecha y huella |
| Recomprobación | Resultado de las nueve comprobaciones al emitir |
| Informe de hallazgos | Sus cinco secciones, en español y en inglés |

### Datos personales

El DEX nombra a cada productor con sus nombres y apellidos. No incluye su DNI, su teléfono ni su dirección. El texto de consentimiento de la Parte 2 debe cubrir que el nombre del productor y la ubicación de su parcela se entregan al comprador.

### Emisión

1. Emite solo un `admin_cooperativa`, sobre un lote `listo`.
2. La API ejecuta la recomprobación en ese instante. Si algo falla, el lote pasa a `bloqueado`, responde 400 con `lote_bloqueado` y no se emite nada.
3. Antes de confirmar, la pantalla muestra el mensaje final del informe y exige marcar la casilla "Entiendo que el DEX no declara el nivel de riesgo ni reemplaza la DDS".
4. En una sola transacción se calcula el informe, se arma y se sella el contenido, se generan los archivos, el lote pasa a `cerrado` y la orden a `cerrada`. Si falla la generación de un archivo, nada cambia.
5. Tras la emisión, el lote, sus asignaciones, su genealogía y sus documentos de embarque ya no cambian.

### Leyenda

La primera página del PDF lleva este texto: "Este expediente reúne la información de origen, proceso y exportación de un lote de cacao tal como estaba registrada al emitirse. No es una Declaración de Diligencia Debida, no evalúa el nivel de riesgo y no lleva firma. La evaluación de riesgo y la presentación de la DDS corresponden al operador".

### Verificación pública

El código QR lleva a `#/verificar/dex/{codigo}`. `GET /publico/dex/{codigo}` responde sin token con los mismos cinco datos que el DOP: código, estado, fecha, huella y cooperativa.

### Anulación

1. Solo un `admin_cooperativa` anula un DEX, con motivo.
2. El lote vuelve a `armado` y la orden a `con_lote`. Para emitir de nuevo hay que recomprobar.
3. El DEX anulado conserva su contenido y sus archivos, y la verificación pública lo muestra como anulado.
4. Una nueva emisión recibe un código nuevo.

### Conservación

Ningún DEX, ni la evidencia que cita, se borra del sistema.

### Datos de contexto

| Tabla | Columnas | Quién la mantiene |
| --- | --- | --- |
| `certificaciones` | `cooperativa_id`, `nombre`, `entidad_certificadora`, `numero`, `vigente_desde`, `vigente_hasta` y un documento de tipo `certificacion` | `admin_cooperativa` |
| `configuracion_plataforma` | Una sola fila: `clasificacion_pais`, `clasificacion_fecha` y `clasificacion_referencia` | `superadmin` |

`clasificacion_pais` admite `bajo`, `estandar` o `alto`, y `clasificacion_referencia` cita la publicación de la Comisión Europea de donde sale. Si la fila está vacía, el informe dice "clasificación del país no registrada"; el sistema no asume un valor.

## Archivos que salen del sistema

Al emitir el DEX se generan seis archivos, todos a partir del mismo contenido sellado, y un paquete ZIP que los reúne. La cooperativa descarga el paquete y lo envía al importador por su cuenta.

### Contenido del paquete

| Archivo | Contenido |
| --- | --- |
| `{código}-es.pdf` | El expediente en español |
| `{código}-en.pdf` | El expediente en inglés |
| `parcelas.geojson` | La geolocalización de todas las parcelas del lote |
| `anexo_ii.json` | Los campos de la DDS que salen de este flujo |
| `hallazgos.json` | El informe de hallazgos estructurado, en los dos idiomas |
| `LEEME.txt` | Qué es cada archivo, el código y la huella del DEX, y cómo verificarlo en la página pública |

Los documentos de evidencia, como títulos, guías o certificados, no van en el paquete. El DEX los lista con su número, su fecha y su huella, y la cooperativa entrega copias si el importador las pide.

### PDF en dos idiomas

1. Los dos PDF tienen la misma estructura y salen del mismo contenido.
2. Los textos fijos, como etiquetas, leyendas y plantillas de hallazgos, viven en `backend/app/textos/es.json` y `backend/app/textos/en.json`. Una prueba comprueba que ambos tienen las mismas claves.
3. Lo que escribieron las personas, como notas, motivos y explicaciones, no se traduce. En el PDF en inglés aparece en español, bajo la etiqueta "Original text in Spanish".
4. Lo que dijo una fuente se cita tal como lo entregó.
5. Los nombres de los grupos de hallazgos en inglés son "Blocks lot closure", "Requires attention" y "Not verified".

### Orden de las secciones del PDF

1. Leyenda y mensaje final del informe.
2. Identificación, exportador, importador y orden, y producto.
3. Genealogía: tabla por parcela y un croquis con todas las parcelas del lote, sin mapa de fondo.
4. Respaldo por parcela: un bloque por cada una.
5. Proceso y embarque.
6. Recomprobación.
7. Informe de hallazgos completo.
8. Lista de documentos de evidencia, con número, fecha y huella.

### GeoJSON

1. Es un `FeatureCollection` con un `Feature` por parcela del lote, en WGS 84, con al menos 6 decimales y sin datos personales.
2. Propiedades propuestas para cada parcela: `ProductionPlace` con el código de la parcela, `ProducerCountry` con `PE` y `Area` en hectáreas.
3. Antes de fijar las propiedades, Claude Code las contrasta con la descripción oficial del archivo GeoJSON que publica la Comisión Europea para el EUDR. Si difieren, manda la descripción oficial y lo informa al equipo.
4. Antes de generar el archivo, cada geometría vuelve a pasar las validaciones de la Parte 3.

### Datos del Anexo II

`anexo_ii.json` es una ayuda para el importador. No es un envío a TRACES ni usa su interfaz.

1. Claude Code toma los nombres y el orden de los campos del texto oficial del Anexo II del Reglamento (UE) 2023/1115. No los inventa.
2. El archivo llena lo que sale de este flujo: partida, descripción y nombre científico del producto, masa neta, país de producción, referencia al GeoJSON, intervalo de cosecha del lote y datos de contacto de la cooperativa.
3. Los datos del importador se copian tal como la cooperativa los registró, con la marca "a confirmar por el operador".
4. La afirmación de riesgo y la firma quedan expresamente vacías, con la nota "corresponde al operador".

### Descarga

1. Descargan un `admin_cooperativa` o un `operador`, con URLs firmadas de 5 minutos.
2. Cada descarga se audita con quién y cuándo.
3. El sistema no envía nada al importador ni guarda si el expediente fue entregado.

## Endpoints y pantallas de la Parte 9

Son 13 endpoints. El módulo Exportación gana la sección DEX, y el detalle del lote gana las pestañas Hallazgos y DEX.

### Hallazgos y DEX

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /lotes/{id}/hallazgos` | Personal | Informe preliminar del lote, con sus cinco secciones |
| `GET /lotes/{id}/geojson` | Personal | GeoJSON preliminar de las parcelas del lote |
| `POST /lotes/{id}/dex` | `admin_cooperativa` | Recomprueba, emite el DEX y genera sus archivos |
| `GET /dex` | Personal | Lista de DEX, con filtros por estado e importador |
| `GET /dex/{id}` | Personal | Detalle con contenido sellado y huella |
| `GET /dex/{id}/descargas` | `admin_cooperativa`, `operador` | URLs firmadas del paquete y de cada archivo |
| `POST /dex/{id}/anular` | `admin_cooperativa` | Anula el DEX, con motivo |

### Contexto

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /certificaciones` | Personal | Lista las certificaciones de la cooperativa |
| `POST /certificaciones` | `admin_cooperativa` | Registra una certificación con su documento |
| `PATCH /certificaciones/{id}` | `admin_cooperativa` | Edita o anula una certificación |
| `GET /admin/configuracion` | `superadmin` | Devuelve la clasificación del país registrada |
| `PUT /admin/configuracion` | `superadmin` | Cambia la clasificación, su fecha y su referencia |

### Público

| Método y ruta | Qué hace |
| --- | --- |
| `GET /publico/dex/{codigo}` | Verificación sin token: código, estado, fecha, huella y cooperativa |

Se auditan `dex.emitir`, `dex.descargar`, `dex.anular`, `certificacion.registrar`, `certificacion.editar` y `plataforma.configurar`.

### Pantallas

| Pantalla | Ruta | Contenido |
| --- | --- | --- |
| Detalle de lote, pestaña Hallazgos | `#/lotes-exportacion/{id}` | Mensaje final arriba; debajo, los hallazgos por grupo, con filtro por etapa y por criterio |
| Detalle de lote, pestaña DEX | `#/lotes-exportacion/{id}` | Para el administrador, el botón "Emitir DEX". Tras emitir, el código, la huella, el código QR y las descargas |
| DEX | `#/exportacion/dex` | Lista de DEX con código, lote, importador, masa, fecha y estado |
| Certificaciones | `#/cooperativa/certificaciones` | Lista y alta de certificaciones |
| Configuración de plataforma | `#/plataforma/configuracion` | Clasificación del país, fecha y referencia |
| Verificar DEX | `#/verificar/dex/{codigo}` | Página pública, igual a la del DOP |

### Reglas de la interfaz

1. La pestaña Hallazgos muestra cada hallazgo como una frase con su sujeto, su criterio y su peso en el lote. No usa colores de gravedad; los tres grupos se distinguen por su título.
2. Cada hallazgo enlaza al registro de donde sale: la parcela, la tanda, la corrida o el documento.
3. El diálogo de emisión muestra el mensaje final completo y la casilla de entendimiento antes de habilitar el botón de confirmar.
4. En un lote `bloqueado`, la pestaña DEX explica que no se puede emitir y enlaza a la pestaña Recomprobación.
5. La pantalla de un DEX emitido permite ver el expediente en cualquiera de los dos idiomas.
6. Ninguna pantalla de esta parte muestra un puntaje, un semáforo ni una frase que califique al lote.

## Pruebas y aceptación de la Parte 9

La Parte 9 está terminada cuando un administrador emite el DEX de un lote listo y descarga un paquete con los dos PDF, el GeoJSON y los dos JSON, cuyo informe cuenta los hechos del lote sin calificarlo.

### Pruebas automáticas mínimas

| Caso | Resultado esperado |
| --- | --- |
| Cada regla del catálogo, con un lote armado para dispararla | Genera su hallazgo, con el grupo, la etapa y el criterio del catálogo |
| Cada regla, con un lote que no la dispara | No genera el hallazgo |
| Cualquier lote | Incluye los tres hallazgos que están siempre |
| Lote con parcelas en tenencia solo por posesión | Un hallazgo por parcela en los datos; una sola frase en el mensaje final |
| Hallazgo con nota de quien decidió | La nota aparece en `explicacion` y el hallazgo sigue presente |
| Mismos datos, informe calculado dos veces | Texto idéntico, carácter por carácter |
| Plantillas en español y en inglés | Tienen las mismas claves y ninguna contiene adjetivos de valoración |
| Suma de `peso_en_lote_pct` de todas las parcelas | 100 |
| `POST /lotes/{id}/dex` por un `operador` | 403 |
| Emitir sobre un lote `armado` o `bloqueado` | 400 |
| Emitir sobre un lote `listo` cuya parcela se observó un minuto antes | 400 con `lote_bloqueado`; el lote pasa a `bloqueado`; no existe DEX |
| Emitir sin marcar la casilla de entendimiento | 422 |
| Emisión correcta | DEX `vigente`; lote `cerrado`; orden `cerrada`; seis archivos y el paquete guardados |
| Falla la generación de un archivo | Nada cambia: ni DEX, ni lote, ni orden |
| DEX emitido | El grupo `impide_cierre` está vacío |
| `UPDATE` sobre el contenido de un DEX | Rechazado por el trigger |
| Se edita un productor o una parcela después de emitir | El contenido del DEX no cambia |
| `parcelas.geojson` | Es un `FeatureCollection` válido, con una geometría por parcela del lote y sin datos personales |
| `anexo_ii.json` | La afirmación de riesgo y la firma están vacías, con su nota |
| PDF en inglés con una nota escrita por una persona | La nota aparece en español bajo "Original text in Spanish" |
| Los dos PDF y los JSON | No contienen puntaje, semáforo ni las frases prohibidas de la Parte 4 |
| Contenido del DEX | No incluye DNI, teléfono ni dirección de ningún productor |
| Clasificación del país sin registrar | El informe dice "clasificación del país no registrada" |
| Anular un DEX | Lote `armado`; orden `con_lote`; verificación pública `anulado` |
| Segunda emisión tras anular | Código nuevo |
| `GET /publico/dex/{codigo}` sin token | 200 con solo los cinco datos permitidos |
| `lector` pide `GET /dex/{id}/descargas` | 403 |

Cada endpoint con token tiene además la prueba de las dos cooperativas definida en la Parte 2.

### Criterios de aceptación en producción

1. El superadministrador registra la clasificación del país con su fecha y su referencia.
2. Sobre un lote `armado`, la pestaña Hallazgos muestra el informe preliminar con su mensaje final.
3. Sobre un lote `bloqueado`, el informe muestra el grupo "Impide el cierre del lote" con el caso exacto.
4. El administrador emite el DEX de un lote `listo`, después de leer el mensaje final y marcar la casilla.
5. El paquete se descarga y contiene los seis archivos.
6. El PDF en español y el PDF en inglés tienen las mismas secciones y las mismas cifras.
7. El GeoJSON se abre en una herramienta externa y muestra todas las parcelas del lote en su lugar.
8. El código QR del PDF lleva a la página pública, que muestra el DEX como vigente.
9. Una persona ajena al equipo lee el mensaje final y puede decir dónde están los riesgos del lote sin abrir el resto del expediente.
10. Ninguna pantalla ni archivo califica al lote ni declara un nivel de riesgo.
11. Todas las acciones aparecen en la auditoría y el CI está en verde, incluidas las Partes 1 a 8.

### Decisiones pendientes del equipo

- [ ] Elegir el nombre del primer grupo: "Impide el cierre del lote", que describe lo que hace el sistema, o "Impide la conformidad", que usa el flujo del equipo.
- [ ] Revisar con un asesor legal las dos leyendas y la casilla de entendimiento, en español y en inglés.
- [ ] Confirmar que el DEX nombra a los productores y que el consentimiento lo cubre.
- [ ] Confirmar que los documentos de evidencia no van dentro del paquete.
- [ ] Registrar la referencia oficial de la clasificación de riesgo del Perú.
- [ ] Decidir si el historial de deforestación de la región se cubre en una versión posterior con los datos agregados de Geobosques.
- [ ] Revisar las frases de las plantillas de hallazgos antes de la demo, en los dos idiomas.

## Parte 10 — Datos de demostración y pruebas finales

La plataforma arranca en blanco. Solo contiene al superadministrador y una cooperativa de demostración llamada Prueba, con datos ficticios que recorren todo el flujo. Las cooperativas reales las crea el equipo, y sus datos entran a mano durante el piloto.

### Decisiones tomadas por el equipo

| Tema | Decisión |
| --- | --- |
| Alcance para la final del 30 de octubre | Todo, de la Parte 1 a la 9 |
| Datos iniciales | Ninguno, salvo la cooperativa Prueba |
| Datos reales | Los cargan las cooperativas del piloto, creadas por el equipo como superadministrador |
| Duración de la demo | Sin preferencia. El guion se arma por bloques que se pueden recortar |

### Consecuencia: producción es real desde el primer día

Como el mismo sistema guarda la demostración y los datos reales de las cooperativas del piloto, esta parte fija tres cosas que antes podían esperar:

1. Los datos de demostración no deben poder confundirse con los reales ni mezclarse con ellos.
2. Antes de cargar el primer productor real, el consentimiento, las copias de respaldo y el control de espacio deben estar resueltos.
3. Las pruebas finales se hacen con la cooperativa Prueba, nunca con datos de una cooperativa real.

### Qué cubre esta parte

| Pieza | Para qué sirve |
| --- | --- |
| Marca de demostración | Aislar a la cooperativa Prueba de las reales |
| Escenario de datos | Dejar el flujo completo armado, con casos listos para mostrar |
| Siembra y prueba de extremo a extremo | Crear el escenario en producción y probarlo en cada cambio de código |
| Requisitos del piloto | Lo que debe existir antes de cargar datos reales |
| Calendario y orden de recorte | Llegar al 30 de octubre con la cadena completa funcionando |
| Guion y verificación final | Qué se muestra y qué se revisa antes de la final |

## La cooperativa Prueba

Prueba es una cooperativa como cualquier otra, con una marca que la aísla: `es_demo`. Todo lo que cuelga de ella es ficticio y lo dice a la vista.

### Datos fijos

| Dato | Valor |
| --- | --- |
| Razón social | Cooperativa Prueba (demostración) |
| Código | `PRB` |
| RUC | `20000000001`, ficticio |
| Ubicación | San Martín |
| Marca | `es_demo = true` |

### La marca `es_demo`

1. Es una columna booleana nueva de `cooperativas`. La fija el `superadmin` al crear la cooperativa y no cambia después.
2. `productores` gana la misma columna. Un productor creado desde una cooperativa de demostración nace con `es_demo = true`.
3. La unicidad del DNI pasa a ser por `dni` y `es_demo`. Así un DNI ficticio nunca choca con el de un productor real.

### Efectos de la marca

| Dónde | Qué cambia |
| --- | --- |
| Interfaz | Los usuarios de la cooperativa ven una franja fija "Demostración: datos ficticios" |
| DOP, DPP y DEX | Cada página del PDF lleva la marca de agua "DEMOSTRACIÓN — DATOS FICTICIOS". El contenido sellado incluye `es_demo` |
| GeoJSON y archivos JSON | Llevan el campo `es_demo` en `true` |
| Verificación pública | La página y el endpoint indican "Documento de demostración" |
| Superposiciones | Las parcelas de demostración solo se comparan entre sí. Nunca abren una superposición con una parcela real, ni al revés |
| Documentos cargados | La siembra usa archivos PDF generados que dicen "DOCUMENTO DE DEMOSTRACIÓN — SIN VALOR" |
| Fuentes externas | Los análisis de cobertura sí se piden a Whisp y GFW. El resultado es real para ese lugar, aunque la parcela sea ficticia |

### Datos ficticios

1. Los nombres de productores empiezan con "Demo", por ejemplo "Demo Uno".
2. Los DNI de demostración van de `00000001` en adelante.
3. Las geometrías son las de `backend/tests/datos/`, ubicadas en San Martín.
4. El importador de demostración se llama "Importador Demo B.V.", con dirección y correo inventados.

## Escenario de datos de Prueba

El escenario deja la cadena completa armada y, además, un registro detenido en cada punto del flujo, listo para avanzar con uno o dos clics durante la demo.

### Base

| Elemento | Contenido |
| --- | --- |
| Usuarios | Un administrador, un operador, un lector y el acceso del productor Demo Uno |
| Lugares | Una cancha de acopio, una planta y un almacén |
| Configuración | Tope de 1,500 kg de grano seco por hectárea al año; el resto, valores iniciales |
| Calidades | "Grado 1" y "Grado 2" |
| Plantilla de proceso | Completa para las 23 etapas |
| Expediente de la cooperativa | Sus seis documentos y sus cuatro datos |
| Importador | Importador Demo B.V. |

### Parcelas

| Parcela | Productor | Geometría | Estado final | Caso que muestra |
| --- | --- | --- | --- | --- |
| PA-00001 | Demo Uno | Polígono, 2.1 ha | Habilitada | Caso sin alertas: título cotejado y perímetro recorrido |
| PA-00002 | Demo Uno | Polígono, 1.4 ha | Habilitada | Segunda parcela del mismo productor |
| PA-00003 | Demo Dos | Polígono, 0.2 ha cultivadas | Habilitada | Tenencia solo por constancia de posesión |
| PA-00004 | Demo Tres | Polígono | Habilitada | Visita de campo con fotos y perímetro recorrido |
| PA-00005 | Demo Cuatro | Punto, 1.8 ha | Habilitada | Parcela de tipo punto y análisis por aproximación |
| PA-00006 | Demo Cinco | Polígono | Habilitada | Superposición con PA-00007 aceptada con nota, y una exención |
| PA-00007 | Demo Seis | Polígono | Observada | Se le anula un documento al final de la siembra, para bloquear un lote |
| PA-00008 | Demo Siete | Polígono | Pendiente | Expediente incompleto. Aparece apagada al recibir una tanda |
| PA-00009 | Demo Siete | Polígono | Excluida | Exclusión de demostración. No tiene tandas |

Como los análisis de cobertura son reales, su resultado no se conoce de antemano. Si alguna parcela recibe la alerta `analisis_requiere_revision`, la siembra le registra una visita de campo de demostración y una nota de habilitación.

### Corridas y stock

| Corrida | Ruta y manejo | Tandas de entrada | Resultado |
| --- | --- | --- | --- |
| 1 | Completa, mezclada | PA-00001: 500 kg; PA-00003: 300 kg; PA-00004: 200 kg, en baba | Consolidada. Tanda final 1: 400 kg, Grado 1. Rendimiento 0.400 |
| 2 | Completa, mezclada | PA-00002: 400 kg; PA-00005: 300 kg; PA-00006: 200 kg, en baba | Consolidada. Tanda final 2: 450 kg, Grado 1. Rendimiento 0.500, sobre la banda, con explicación |
| 3 | Seco, segregada | PA-00007: 310 kg, en seco | Consolidada. Tanda final 3: 300 kg, Grado 1 |
| 4 | Completa, mezclada | PA-00001: 300 kg; PA-00006: 200 kg, en baba | En proceso, con todas sus etapas registradas y sin consolidar |

### Órdenes y lotes

| Orden | Cantidad | Lote | Selección | Estado final |
| --- | --- | --- | --- | --- |
| 1 | 600 kg | Lote 1 | Tanda final 1: 400 kg; tanda final 2: 200 kg. Sigue el orden FIFO | Cerrado, con DEX emitido |
| 2 | 300 kg | Lote 2 | Tanda final 3: 300 kg. Se aparta del FIFO, con motivo | Bloqueado, porque PA-00007 quedó observada |
| 3 | 150 kg | Lote 3 | Tanda final 2: 150 kg | Listo, sin DEX |
| 4 | 100 kg | Sin lote | La tanda final 2 conserva 100 kg de saldo | Orden abierta |

### Genealogía esperada del lote 1

La prueba de extremo a extremo comprueba estas cifras.

| Parcela | Desde tanda final 1 | Desde tanda final 2 | Kilos en el lote |
| --- | --- | --- | --- |
| PA-00001 | 200.0000 | 0 | 200.0000 |
| PA-00003 | 120.0000 | 0 | 120.0000 |
| PA-00004 | 80.0000 | 0 | 80.0000 |
| PA-00002 | 0 | 88.8889 | 88.8889 |
| PA-00005 | 0 | 66.6667 | 66.6667 |
| PA-00006 | 0 | 44.4444 | 44.4444 |
| Total | 400.0000 | 200.0000 | 600.0000 |

### Registros detenidos para la demo

| Qué se quiere mostrar | Registro preparado |
| --- | --- |
| Recibir y validar una tanda con alerta | Tanda de 600 kg en baba de PA-00003, registrada y sin validar. Supera el tope acumulado |
| Revalidar una tanda | Tanda de PA-00004, observada con motivo |
| Consolidar una corrida | Corrida 4 |
| Armar un lote con la sugerencia FIFO | Orden 4 |
| Ver un lote bloqueado y desbloquearlo | Lote 2 y PA-00007 |
| Emitir un DEX | Lote 3 |
| Leer un DEX completo | Lote 1 |
| Ver una parcela no habilitada y una excluida | PA-00008 y PA-00009 |

## Siembra y prueba de extremo a extremo

El escenario se escribe una sola vez, en `backend/app/demo/escenario.py`, y se usa de dos formas: como prueba automática en cada cambio de código y como siembra de la cooperativa Prueba en producción.

### Cómo está escrito el escenario

1. El escenario llama a las mismas funciones de la capa `services` que usa la API. No inserta filas directamente en la base.
2. Por eso cada paso pasa por las mismas compuertas, requisitos y auditoría que una persona usando la aplicación.
3. Cada paso actúa con el rol que le corresponde: el superadministrador crea la cooperativa, el administrador habilita, el operador recibe tandas.
4. Si un paso no puede cumplirse, el escenario se detiene con un mensaje que dice qué requisito faltó. No fuerza ningún estado.

### Uso 1: prueba de extremo a extremo

1. Vive en `backend/tests/e2e/test_flujo_completo.py` y corre en el CI con cada cambio.
2. Usa el Postgres de Docker y las respuestas de Whisp y GFW guardadas en `backend/tests/datos/`.
3. Al terminar comprueba el estado final del escenario: estados de parcelas, saldos de las tandas finales, estados de los lotes, la genealogía del lote 1 y el contenido del DEX.
4. Comprueba también que una segunda cooperativa, creada en la misma prueba, no ve nada de Prueba.

### Uso 2: siembra en producción

1. Se ejecuta con `python -m app.demo.sembrar`, desde la terminal de una persona del equipo, con las variables reales cargadas. No se ejecuta desde Claude Code.
2. Usa las fuentes reales. Tras crear las parcelas espera a que terminen sus análisis, con un máximo de 15 minutos.
3. Si falta una clave de Whisp o de GFW, o los análisis no terminan, la siembra se detiene después de crear las parcelas y lo explica. Puede retomarse con el mismo comando.
4. Al terminar imprime en la terminal, una sola vez, los correos y las contraseñas de los usuarios de demostración.
5. Si ya existe una cooperativa con el código `PRB`, la siembra retoma lo que falte o termina sin cambios. Nunca duplica datos.

### Reinicio

La cooperativa Prueba no se reinicia ni se borra, porque el sistema no borra documentos sellados ni auditoría. Si hace falta un escenario limpio, la siembra acepta `--codigo PRB2` y crea otra cooperativa de demostración junto a la primera.

## Piloto con datos reales

Antes de registrar al primer productor real deben estar resueltas cuatro cosas: el consentimiento, las copias de respaldo, el control de espacio y las cuentas con que el equipo cargará datos.

### Requisitos antes del primer dato real

| Requisito | Por qué | Quién lo resuelve |
| --- | --- | --- |
| Texto de consentimiento entregado y revisado | Sin él, la aplicación muestra "TEXTO PENDIENTE DE REVISIÓN LEGAL" | Equipo |
| Copia de respaldo en marcha | El plan gratuito de Supabase no hace copias automáticas | Equipo |
| Compresión de imágenes activa | Sin ella, el espacio de archivos se llena con pocas decenas de parcelas | Claude Code |
| Una cuenta de administrador por cooperativa para quien cargue datos | El superadministrador no puede crear datos de negocio | Equipo |

Mientras el archivo de consentimiento contenga el texto pendiente, la API rechaza la creación de productores en cooperativas reales, con el código `consentimiento_no_definido`. La cooperativa Prueba no tiene esa restricción.

### Quién carga los datos reales

1. El superadministrador crea cada cooperativa real y su primer administrador, pero no puede registrar productores, parcelas ni tandas. Esa regla de la Parte 2 se mantiene.
2. Si una persona del equipo va a cargar datos de una cooperativa, recibe una cuenta `admin_cooperativa` en esa cooperativa.
3. Cada cuenta pertenece a una sola cooperativa y usa un correo distinto. Quien cargue datos de tres cooperativas necesita tres cuentas.
4. Así la auditoría muestra quién registró cada dato y en nombre de qué cooperativa.
5. Los datos de prueba se cargan solo en la cooperativa Prueba, nunca en una real.

### Compresión de imágenes

1. Antes de subir un JPG o un PNG, la interfaz lo reduce a un máximo de 1,600 píxeles en su lado mayor y lo guarda como JPEG con calidad 0.75. Los PDF se suben sin cambios.
2. La huella SHA-256 se calcula sobre el archivo que realmente se guarda.
3. La regla se aplica a todas las cargas de documentos y fotos de las Partes 3 a 9.

Como estimación, una foto de celular sin comprimir pesa cerca de 3 MB y comprimida cerca de 0.4 MB. Con 1 GB caben unos 340 documentos sin comprimir y unos 2,500 comprimidos.

### Control de espacio

1. `GET /admin/uso`, solo para `superadmin`, devuelve el espacio usado en archivos y en base de datos, en total y por cooperativa, y el porcentaje de los límites del plan.
2. Los límites salen de dos variables nuevas: `LIMITE_STORAGE_MB`, con valor 1024, y `LIMITE_DB_MB`, con valor 500.
3. La pantalla de plataforma muestra el uso y avisa al pasar de 70 % y de 90 %.
4. Al acercarse al límite, la salida es pasar Supabase al plan de pago. Lo decide y lo ejecuta una persona del equipo.

### Copias de respaldo

1. Una persona del equipo ejecuta `pg_dump` cada semana y antes de cada demo.
2. `backend/scripts/respaldar_storage.py` descarga el bucket completo a un disco local. Se ejecuta con la misma frecuencia.
3. Las copias contienen datos personales. Se guardan fuera del repositorio, en un lugar con acceso restringido.
4. Antes de la final se hace un ensayo de restauración: la copia se restaura en el Postgres de Docker y la aplicación arranca contra ella.

### Ritmo de los análisis

La cola procesa una consulta externa a la vez. Si una cooperativa registra muchas parcelas el mismo día, sus análisis pueden tardar desde minutos hasta más de una hora. La interfaz muestra cuántos análisis hay en cola.

## Calendario hasta el 30 de octubre

Entre el lunes 5 y el jueves 29 de octubre hay 25 días para construir nueve partes, sembrar y ensayar. El calendario no tiene días de holgura: un día perdido en una parte se recupera recortando, no alargando.

### Calendario

| Parte | Fechas | Días |
| --- | --- | --- |
| 1. Infraestructura y despliegue | Lunes 5 y martes 6 | 2 |
| 2. Acceso y base | Miércoles 7 a viernes 9 | 3 |
| 3. Productor y parcela | Sábado 10 a lunes 12 | 3 |
| 4. Habilitación de la parcela | Martes 13 a jueves 15 | 3 |
| 5. Recepción de la tanda y DOP | Viernes 16 a domingo 18 | 3 |
| 6. Proceso y DPP | Lunes 19 a miércoles 21 | 3 |
| 7. Orden de compra y genealogía | Jueves 22 y viernes 23 | 2 |
| 8. Cooperativa y recomprobación | Sábado 24 | 1 |
| 9. Informe de hallazgos y DEX | Domingo 25 a martes 27 | 3 |
| 10. Siembra, verificación final y ensayos | Miércoles 28 y jueves 29 | 2 |
| Final | Viernes 30 |  |

### Reglas de avance

1. Una parte se da por terminada cuando sus criterios de aceptación pasan en producción.
2. Cada día termina con el CI en verde y lo construido desplegado.
3. Si una parte lleva un día de atraso, Claude Code lo informa ese mismo día y el equipo decide qué recortar.
4. El martes 27 se congela el código. El 28 y el 29 solo se corrigen errores, se siembra la cooperativa Prueba y se ensaya.
5. Si una entrega del equipo no llega a tiempo, Claude Code avanza con los valores iniciales de este documento y la deja anotada como pendiente. Se detiene solo en tres casos: falta el HTML del rediseño, faltan las respuestas reales de Whisp y GFW, o falta una cuenta o una clave.

### Entregas del equipo

| Entrega | La necesita | Fecha límite |
| --- | --- | --- |
| Cuentas de Supabase, Render y Cloudflare, con dueño definido | Parte 1 | Lunes 5 |
| HTML del último rediseño en `legacy/diseno/` | Parte 2 | Martes 6 |
| Texto de consentimiento | Parte 2 y piloto | Jueves 8 |
| Claves de Whisp y GFW, y una respuesta real de cada una | Parte 4 | Lunes 12 |
| Los 7 documentos de la parcela confirmados: vencimientos, registros consultables y sustento de SUNAFIL | Parte 4 | Lunes 12 |
| Parámetros de configuración y lista de variedades confirmados | Parte 5 | Jueves 15 |
| Las 23 etapas confirmadas | Parte 6 | Domingo 18 |
| Los 6 documentos de la cooperativa confirmados | Parte 8 | Viernes 23 |
| Leyendas y plantillas de hallazgos revisadas, y referencia de la clasificación del país | Parte 9 | Sábado 24 |
| Render en plan Starter y, si se decide, dominio propio conectado | Final | Lunes 26 |

### Orden de recorte

El equipo decidió construir todo. Si el calendario se atrasa, se recorta en este orden. Cada recorte deja intacta la cadena de la parcela al DEX.

1. El PDF del DEX en inglés. Queda el PDF en español; el informe en JSON conserva los dos idiomas.
2. El diagrama de cinco columnas de la genealogía. Quedan la tabla y el mapa.
3. Las capas visuales de Geobosques, GeoSERFOR y JRC en el mapa.
4. La segunda fuente de análisis, GFW. Queda Whisp.
5. Las pantallas de certificaciones y de configuración de plataforma. Sus datos se cargan con la siembra.
6. El cotejo en fuente. Todos los documentos quedan en nivel `documentado`.
7. El dibujo de parcelas desde la cuenta del productor. El productor conserva la consulta y la carga de documentos.
8. La verificación pública del DPP. Quedan las del DOP y el DEX.
9. La edición de la plantilla de proceso por pantalla. La plantilla se carga con la siembra.
10. La tarea diaria automática. Queda la recomprobación manual.

### Lo que nunca se recorta

Las compuertas, los sellos con huella, la auditoría, el aislamiento entre cooperativas, la regla de exponer sin concluir y las pruebas automáticas de cada parte.

## Guion de demo y verificación final

La demo recorre la cadena con la cooperativa Prueba en seis bloques. Cada bloque avanza un registro que la siembra dejó detenido, así que ninguno depende de escribir datos largos en vivo.

### Bloques del guion

| Bloque | Qué se muestra | Registro | Tiempo aproximado |
| --- | --- | --- | --- |
| 1. Recepción y DOP | Desde un celular, el operador valida una tanda con alerta, escribe la nota y se emite el DOP. Se escanea el código QR y se abre la verificación pública | Tanda de PA-00003 | 60 segundos |
| 2. Proceso | El tablero de corridas, la consolidación de una corrida y su DPP | Corrida 4 | 45 segundos |
| 3. Lote y genealogía | Se arma un lote con la sugerencia FIFO y se ve de qué parcelas viene, en diagrama, tabla y mapa | Orden 4 | 60 segundos |
| 4. Recomprobación | Un lote bloqueado, el caso exacto que lo bloquea y su desbloqueo al habilitar de nuevo la parcela | Lote 2 y PA-00007 | 60 segundos |
| 5. DEX | El administrador lee el mensaje final, emite el DEX y abre el PDF | Lote 3 | 60 segundos |
| 6. Cierre | El panel de pendientes, una parcela excluida y la franja de demostración | PA-00009 | 30 segundos |

La versión corta usa los bloques 1, 3 y 5, y cabe en 3 minutos. La versión completa dura unos 5 minutos.

### Respaldo de la demo

1. El jueves 29 se graba en video el guion completo sobre producción.
2. El paquete del DEX del lote 1 se descarga antes de la final y queda en el equipo que presenta.
3. Si la red falla, se muestra el video y se abre el PDF descargado.

### Verificación final

- [ ] El CI está en verde, incluida la prueba de extremo a extremo.
- [ ] La siembra de Prueba terminó en producción y cada registro detenido está en su punto.
- [ ] El guion completo se recorrió dos veces a mano, una de ellas desde un celular.
- [ ] Render está en plan Starter y el monitor externo sigue activo.
- [ ] Las claves de Whisp y de GFW están vigentes.
- [ ] Hay copia de respaldo del día y el ensayo de restauración funcionó.
- [ ] Una consulta a la API de datos de Supabase con la clave publicable no devuelve ninguna fila.
- [ ] La búsqueda de secretos en el repositorio no encuentra nada.
- [ ] Dos cooperativas reales del piloto no ven datos entre sí ni de Prueba.
- [ ] Los PDF de DOP, DPP y DEX de Prueba llevan la marca de agua de demostración.
- [ ] Ninguna pantalla ni documento contiene puntajes, semáforos ni las frases prohibidas.
- [ ] El video de respaldo y el paquete del DEX están en el equipo que presenta.

### Decisiones pendientes del equipo

- [ ] Confirmar el calendario y quién trabaja con Claude Code cada día.
- [ ] Definir los correos de las cuentas de administrador con que el equipo cargará datos de cada cooperativa real.
- [ ] Definir dónde se guardan las copias de respaldo y quién responde por ellas.
- [ ] Fijar la duración de la demo, para elegir los bloques.

## Cómo entregar este documento a Claude Code

El documento se usa en dos formatos: Markdown dentro del repositorio, para que Claude Code lo consulte en cada sesión, y PDF para el equipo.

1. Exportar este documento a Markdown y guardarlo en el repositorio como `docs/especificacion.md`.
2. Exportarlo también a PDF, para leerlo y compartirlo en el equipo.
3. Abrir Claude Code sobre el repositorio y empezar con esta instrucción: "Lee `docs/especificacion.md` completo. Luego construye solo la Parte 1, siguiendo las reglas de trabajo del inicio del documento. Antes de escribir código, dime qué entendiste de la Parte 1 y qué necesitas de mí".
4. Al cerrar cada parte, pedir la siguiente con la misma forma. No pedir dos partes a la vez.
5. Cada vez que el equipo cierre una decisión pendiente, actualizar este documento primero y volver a exportarlo. El documento manda sobre lo que se haya dicho en una conversación.

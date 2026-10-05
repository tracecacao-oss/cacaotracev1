# CacaoTrace

Trazabilidad de cacao para cooperativas, pensada para el reglamento europeo de
deforestación (EUDR). Convierte la operación de campo en evidencia, en tres documentos:

| Documento | Nivel | Qué prueba |
|---|---|---|
| **DOP**, origen del producto | Parcela | Geolocalización, tenencia y verificación satelital |
| **DPP**, procesamiento del producto | Lote | Entregas con guía de remisión, etapas y balance de masa |
| **DEX**, documento de exportación | Embarque | Genealogía de la orden y las cinco compuertas superadas |

La declaración de diligencia debida (DDS) la presenta el importador en TRACES NT.
CacaoTrace le entrega el DEX con la evidencia y el GeoJSON de las parcelas.

## Qué hace

1. **Mis productores**: productores, parcelas en mapa (polígono, o punto hasta 4 ha), documentos
   con su nivel de verificación y veredicto satelital de tres estados. El ámbar va a revisión humana.
2. **Diagrama de procesos**: lotes, entregas por parcela con su GRE, etapas y balance de masa
   de baba a grano seco. Al cerrar el lote se emite el DPP.
3. **Genealogía del lote**: órdenes de compra, asignación de lotes (manual o del más antiguo
   al más nuevo) y proporción de origen por parcela.
4. **Resumen**: cinco compuertas por orden (origen, deforestación, tenencia, custodia, embarque).
   Con todas abiertas se genera el DEX: paquete con huella SHA-256, GeoJSON, versión para
   imprimir y enlace de verificación para el importador.

Cada cooperativa tiene sus usuarios (administrador y operador) y solo ve sus datos.

## Correr en local

```bash
pip install Flask
python app.py            # http://localhost:8000
```

Sin `DATABASE_URL` usa un archivo SQLite (`cacaotrace.db`). La primera vez crea una cooperativa
de ejemplo: `demo@cacaotrace.pe` con la contraseña de `DEMO_PASSWORD` (por defecto `cacao-demo-2026`).

Pruebas: `python -m unittest tests.test_flujo -v`

## Desplegar en Render

Opción rápida: **New > Blueprint** y elegir este repositorio. `render.yaml` crea el servicio web
y la base PostgreSQL y los conecta.

Variables de entorno:

| Variable | Para qué |
|---|---|
| `DATABASE_URL` | Conexión a PostgreSQL. Sin ella se usa SQLite, que en Render se borra en cada reinicio |
| `DEMO_PASSWORD` | Contraseña de la cuenta de ejemplo |
| `DEMO_EMAIL` | Correo de la cuenta de ejemplo (por defecto `demo@cacaotrace.pe`) |
| `REGISTRO_CODIGO` | Si se define, registrar una cooperativa nueva exige este código |
| `GFW_API_KEY` | Activa la consulta real a Global Forest Watch. Sin ella, la verificación es simulada |
| `PYTHON_VERSION` | `3.12.7` |

## Estructura

```
app.py        Servidor Flask: sesiones, API y reglas de integridad
motor.py      Reglas de negocio puras: DOP, balance de masa, genealogía, compuertas, DEX
satelite.py   Verificación satelital (Global Forest Watch o simulada)
semilla.py    Datos de ejemplo (ficticios)
db.py         Capa de datos: SQLite en local, PostgreSQL en producción
static/       Interfaz (HTML, CSS y JavaScript sin dependencias de compilación)
tests/        Prueba de punta a punta
```

## Límites conocidos

- La verificación satelital es **simulada** mientras no haya `GFW_API_KEY`. El conector de
  Global Forest Watch está escrito, pero falta probarlo contra la API real.
- MIDAGRI y SUNAT no se consultan en línea: el polígono se importa como GeoJSON y las guías
  y la DAM se registran con su número y su archivo.
- El catálogo de documentos y las cinco compuertas están en `motor.py` y son fáciles de ajustar.
- El GeoJSON del DEX no se ha validado contra TRACES NT.

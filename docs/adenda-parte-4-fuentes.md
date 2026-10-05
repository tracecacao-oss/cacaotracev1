# Adenda a la Parte 4 — Refuerzo del análisis de cobertura forestal

Fecha: 5 de octubre de 2026. Decisión del equipo.

Esta adenda amplía la Parte 4 de `docs/especificacion.md`. Donde difiera de ella, manda esta adenda. Todo lo demás de la Parte 4 sigue igual, incluidas las reglas de trabajo y el principio de exponer sin concluir.

## 1. Objetivo

Que cada parcela tenga más respaldo independiente frente a las dos preguntas que hace el Reglamento, y que ese respaldo llegue ordenado al DOP y al DEX.

| Código | Pregunta |
| --- | --- |
| `estado_2020` | ¿Qué había en la parcela al 31 de diciembre de 2020? |
| `cambio_posterior` | ¿Qué cambió en la parcela después del 31 de diciembre de 2020? |

El sistema sigue sin afirmar que una parcela "no fue deforestada". Muestra qué dice cada conjunto de datos sobre cada pregunta y cuántos coinciden. No hay puntaje, semáforo ni conclusión.

## 2. Qué se agrega

| Refuerzo | Qué aporta | Costo |
| --- | --- | --- |
| A. Detalle por capa de Whisp | Qué capas internas de Whisp vieron bosque en 2020 y cuáles vieron cambios | Ninguna llamada nueva |
| B. Dos consultas más a GFW | Bosque natural al 2020 y alertas DIST desde 2021 | Misma clave |
| C. Historial de MapBiomas Perú | Uso del suelo de la parcela, año por año | Fuente nueva, sin clave |
| D. Tabla de convergencia | Todo lo anterior en una sola tabla por parcela | Solo presentación |

Orden de construcción: A, B, comprobación de viabilidad de C, C, D. Si C no pasa su comprobación, se construyen A, B y D sin C.

## 3. Refuerzo A — Detalle por capa de Whisp

1. No se hacen llamadas nuevas. El detalle se extrae de la respuesta completa que ya se guarda como `respuesta_analisis`.
2. `indicadores` gana la clave `capas`: una lista con, por cada capa, su nombre tal como lo entrega Whisp, su `pregunta`, su `conjunto_de_datos`, su valor y su unidad.
3. `pregunta` admite `estado_2020`, `cambio_posterior`, `cultivo` u `otra`.
4. La correspondencia entre capa, pregunta y conjunto de datos vive en `backend/app/catalogos/capas_whisp.py`. Se arma a partir de la respuesta real guardada en `backend/tests/datos/` y de la documentación de Whisp. No se inventan nombres de capas.
5. Una capa que no esté en el catálogo se guarda y se muestra con `pregunta = otra`. Nunca se descarta.
6. Los análisis de Whisp ya completados se reprocesan una vez desde su respuesta guardada, con `python -m app.scripts.reprocesar_whisp`. No se vuelve a consultar a Whisp.

## 4. Refuerzo B — Dos consultas más a GFW

| Conjunto | Qué se consulta | Pregunta | Clave en `indicadores` |
| --- | --- | --- | --- |
| `sbtn_natural_forests_map` | Hectáreas de la parcela clasificadas como bosque natural en 2020 | `estado_2020` | `bosque_natural_2020_ha` |
| `umd_glad_dist_alerts` | Número de alertas DIST dentro de la parcela desde el 1 de enero de 2021 | `cambio_posterior` | `alertas_dist_desde_2021` |

1. Se suman a las dos consultas existentes, dentro del mismo análisis de fuente `gfw`.
2. Antes de integrarlas, confirmar en la documentación de GFW el nombre, la versión vigente y la forma de consulta de cada conjunto. La versión usada se guarda en `version_fuente`.
3. El análisis de GFW queda `completado` solo si las cuatro consultas responden. Si una falla, queda en `error` con el detalle y se reintenta completo.
4. Para parcelas de tipo punto se mantiene el círculo con el área declarada y la marca de aproximación.

## 5. Refuerzo C — Historial de MapBiomas Perú

### 5.1 Qué se obtiene

Para cada año entre `MAPBIOMAS_ANIO_INICIAL` y `MAPBIOMAS_ANIO_FINAL`, las hectáreas de la parcela en cada clase de uso del suelo. De ahí salen cuatro hechos, que no son conclusiones:

| Clave en `indicadores` | Contenido |
| --- | --- |
| `clase_predominante_2020` | Clase con más área en la parcela en 2020 |
| `bosque_2020_ha` | Hectáreas en clases de bosque en 2020 |
| `cambio_bosque_a_no_bosque_ha` | Hectáreas que eran bosque en 2020 y no lo son en el último año disponible |
| `anios` | Por cada año, hectáreas por clase |

### 5.2 Datos

1. Un archivo GeoTIFF por año, de 30 m de resolución, en esta dirección, tomada del archivo de APIs del equipo:
   `https://storage.googleapis.com/mapbiomas-public/initiatives/peru/collection_3/LULC/peru_collection3_integration_v1-classification_{AÑO}.tif`
2. La leyenda de clases se copia de la leyenda oficial de MapBiomas Perú, Colección 3, a `backend/app/catalogos/mapbiomas_peru_c3.py`. Incluye qué clases cuentan como bosque según esa leyenda. No se inventa ni se resume.
3. Se lee solo la ventana de la parcela, con peticiones HTTP por rango. Nunca se descarga un archivo completo ni se guarda en disco.

### 5.3 Comprobación de viabilidad, antes de construir

`backend/scripts/check_mapbiomas.py` comprueba, contra las direcciones reales y con una parcela de `backend/tests/datos/`:

1. Que las direcciones respondan y acepten peticiones por rango.
2. Que los archivos estén organizados en bloques, de modo que leer una ventana no obligue a traer franjas enteras.
3. La memoria máxima y el tiempo de leer todos los años para una parcela, en un proceso limitado a 512 MB.

Si la memoria máxima supera 150 MB, o el tiempo supera 60 segundos, o la dependencia de lectura de rásteres no instala en Render, **detenerse e informar al equipo**. No se construye el refuerzo C y `MAPBIOMAS_ACTIVO` queda en `false`.

### 5.4 Reglas

1. Es una fuente nueva, `mapbiomas`, con su fila en `analisis_cobertura` y su módulo `backend/app/services/fuentes/mapbiomas.py`, con la misma interfaz que las demás.
2. `resultado_fuente` queda nulo: MapBiomas no entrega un valor de riesgo.
3. Se cuentan los píxeles cuyo centro cae dentro de la parcela. El área de cada píxel se calcula según su latitud.
4. Con 30 m de resolución, una hectárea son unos 11 píxeles. Si la parcela tiene menos de 10 píxeles, el análisis lleva la marca `pocos_pixeles`.
5. Para parcelas de tipo punto se usa el círculo con el área declarada y la marca de aproximación.
6. Como evidencia se guarda, en un documento `respuesta_analisis`, la tabla de píxeles por año y clase, las direcciones consultadas y las cabeceras de versión de cada archivo.
7. `version_fuente` dice "MapBiomas Perú, Colección 3" y el último año cubierto.
8. Corre en la misma cola de análisis, una consulta a la vez.
9. Cuando `MAPBIOMAS_ACTIVO` es `true`, MapBiomas cuenta como fuente configurada para el requisito `analisis_vigente`.
10. Lo ocurrido después del último año cubierto no lo ve esta fuente. Eso se declara; ver sección 8.

### 5.5 Variables nuevas

| Variable | Valor inicial | Descripción |
| --- | --- | --- |
| `MAPBIOMAS_ACTIVO` | `false` | Se pasa a `true` solo si la comprobación de viabilidad pasa |
| `MAPBIOMAS_ANIO_INICIAL` | `2015` | Primer año del historial |
| `MAPBIOMAS_ANIO_FINAL` | `2024` | Último año disponible en la colección |
| `UMBRAL_BOSQUE_2020_PCT` | `10` | Porcentaje del área de la parcela desde el cual se considera que un conjunto "registra bosque en 2020" |

## 6. Refuerzo D — Tabla de convergencia

Se muestra en el detalle de la parcela y se copia al contenido sellado del DOP y del DEX.

1. Una fila por **conjunto de datos**, no por API. Si el mismo conjunto llega por Whisp y por GFW, se cuenta una sola vez y la fila dice por dónde se consultó.
2. Columnas: conjunto de datos, consultado vía, fecha, "Al 31 de diciembre de 2020" y "Después de 2020". Una celda queda vacía si ese conjunto no mide esa pregunta.
3. Bajo la tabla va una frase de conteo, generada por plantilla:
   "Conjuntos de datos consultados: N. Registran bosque en 2020: A de B que lo miden. Registran cambios después de 2020: C de D que lo miden."
4. Un conjunto "registra bosque en 2020" si su medida de bosque alcanza `UMBRAL_BOSQUE_2020_PCT` del área de la parcela. "Registra cambios" si alguna de sus medidas de cambio es mayor que cero.
5. La frase solo cuenta. No lleva adjetivos, no dice que la parcela cumple y no resume en una palabra.
6. Si dos conjuntos responden distinto a la misma pregunta, la tabla muestra los dos valores tal cual.

## 7. Cambios en textos y alertas

### 7.1 Textos de las tarjetas

| Fuente | Texto |
| --- | --- |
| GFW | Al texto actual se agrega: "X ha de bosque natural en 2020; N alertas DIST desde 2021" |
| MapBiomas | "MapBiomas Perú: en 2020, clase predominante {clase}; X ha de bosque en 2020; Y ha pasaron de bosque a otra clase entre 2020 y {último año}" |

Siguen prohibidas las frases de la Parte 4. Se agrega a la lista "no deforestada" y "sin deforestación".

### 7.2 Alerta `analisis_requiere_revision`

Se activa, además de los casos ya definidos, cuando:

1. GFW informa alertas DIST desde 2021 y hubo bosque en la parcela el 31 de diciembre de 2020 (regla 3). Decisión del equipo del 2026-10-05: DIST marca cualquier cambio de la vegetación (poda, cosecha, renovación del cultivo) sin decir la causa; sin bosque en la fecha de corte, sus alertas se muestran como dato y no piden visita.
2. MapBiomas informa `cambio_bosque_a_no_bosque_ha` mayor que cero.
3. Al menos 3 conjuntos registran bosque en 2020, cada uno en al menos `UMBRAL_BOSQUE_2020_PCT` del área de la parcela. Decisión del equipo del 2026-10-05: un solo mapa puede ver árboles de sombra, frutales o cercos vivos (por ejemplo, la cobertura de árboles de Hansen); con 1 o 2 mapas, la pantalla lo muestra como dato y no pide visita. El mínimo vive en `MAPAS_MINIMOS_BOSQUE_2020` (`backend/app/services/convergencia.py`).

La regla 3 existe porque cacao entregado desde una parcela mapeada como bosque en 2020 necesita que una persona la mire. El caso típico sigue siendo el cacao bajo sombra.

## 8. Hallazgos nuevos para la Parte 9

Se suman al catálogo cuando se construya la Parte 9.

| Código | Se genera cuando | Criterio | Grupo |
| --- | --- | --- | --- |
| `conjuntos_registran_bosque_2020` | Uno o más conjuntos registran bosque en 2020. Nombra cuáles y cuánta área | 1 | Requiere atención |
| `conjuntos_registran_cambio_posterior` | Uno o más conjuntos registran cambios después de 2020. Nombra cuáles | 1 | Requiere atención |
| `conjuntos_discrepan` | Dos conjuntos responden distinto a la misma pregunta | 1 | Requiere atención |
| `mapbiomas_pocos_pixeles` | La parcela tiene menos de 10 píxeles en MapBiomas | 1 | No verificado |
| `mapbiomas_sin_cobertura_reciente` | Siempre que se use MapBiomas: no cubre lo ocurrido después de su último año | 1 | No verificado |

En "Datos del lote" se agrega cuántos conjuntos de datos se consultaron por parcela, con el mínimo y el máximo del lote.

## 9. Pruebas mínimas

| Caso | Resultado esperado |
| --- | --- |
| Respuesta real de Whisp guardada | `indicadores.capas` contiene todas sus capas, cada una con su pregunta |
| Capa de Whisp que no está en el catálogo | Se guarda con `pregunta = otra` |
| Reprocesar un análisis de Whisp ya completado | Gana `capas` sin llamar a Whisp |
| Falla una de las cuatro consultas de GFW | El análisis queda en `error` |
| GeoTIFF sintético pequeño creado en la prueba | Las hectáreas por clase coinciden con las esperadas |
| Parcela con 6 píxeles | Marca `pocos_pixeles` |
| GeoTIFF sintético con bosque en 2020 y agricultura en el último año | `cambio_bosque_a_no_bosque_ha` mayor que cero y alerta `analisis_requiere_revision` |
| El mismo conjunto llega por Whisp y por GFW | La tabla de convergencia lo cuenta una vez |
| Dos conjuntos discrepan sobre 2020 | La tabla muestra ambos valores |
| Frase de conteo | Coincide con los datos y no contiene adjetivos ni frases prohibidas |
| `MAPBIOMAS_ACTIVO` en `false` | No se crean análisis de MapBiomas y la tabla no lo lista |
| Lectura de MapBiomas en las pruebas | Ninguna prueba sale a internet |

## 10. Criterios de aceptación en producción

1. Una parcela de prueba muestra el detalle por capa de Whisp.
2. La tarjeta de GFW muestra bosque natural en 2020 y alertas DIST.
3. La comprobación de viabilidad de MapBiomas quedó documentada con sus cifras de memoria y tiempo.
4. Si pasó, la parcela muestra su historial de uso del suelo por año, con la clase predominante en 2020.
5. La tabla de convergencia aparece en el detalle de la parcela con su frase de conteo.
6. Ninguna pantalla afirma que una parcela no fue deforestada.
7. El servicio en Render sigue respondiendo `/health` durante y después de un análisis de MapBiomas.

## 11. Decisiones pendientes del equipo

- [ ] Confirmar el umbral de 10 % para "registra bosque en 2020".
- [ ] Confirmar el rango de años del historial, 2015 a 2024.
- [ ] Decidir si se suman después las imágenes de antes y después con Sentinel.

## 12. Registro de la construcción (2026-10-05)

### Comprobación de viabilidad de MapBiomas (`backend/scripts/check_mapbiomas.py`)

Corrida el 2026-10-05 contra las direcciones reales, con la parcela de `backend/tests/datos/whisp_respuesta_real.json`, en un proceso limitado a 512 MB (Job Object de Windows).

| Comprobación | Resultado |
| --- | --- |
| Peticiones por rango, 2015 a 2024 | Los 10 archivos responden 206. 2025 todavía no existe (404) |
| Organización en bloques | BigTIFF en bloques de 256 x 256, LZW con predictor horizontal, 8 bits, WGS 84 |
| Tiempo de leer los 10 años | 30,2 s (máximo 60) |
| Memoria máxima del proceso | 48,2 MB (máximo 150) |
| Dependencia de rásteres en Render | Ninguna nueva: el lector (`app/services/fuentes/cog.py`) es Python con numpy, que ya estaba |

Pasó, así que `MAPBIOMAS_ACTIVO` queda en `true` en `render.yaml`. Por parcela y año se hacen 5 peticiones: la cabecera, la georreferencia (que el archivo guarda después de la tabla de bloques), las dos entradas de la tabla de bloques y el bloque. Ese mismo día la lectura inicial de cabecera bajó de 64 KB a 16 KB y la comprobación se repitió: 27,1 s y 47,7 MB. Son unos 30 KB por año.

### Fuentes de los catálogos

- `capas_whisp.py`: tabla oficial `lookup_datasets.csv` y `layers_description.md` de Whisp (commit addae78 del 2026-09-28) y la respuesta real guardada.
- `conjuntos_datos.py`: nombres de los conjuntos de datos según Whisp, los metadatos de GFW y la leyenda de MapBiomas.
- `mapbiomas_peru_c3.py`: el PDF "Códigos de los valores del píxel… usados en la Colección 3" de peru.mapbiomas.org. El CSV de leyenda publicado junto a él es de la Colección 4 y no se usó.

### Decisiones de construcción

1. **Medidas de bosque al 2020 en Whisp.** Son las capas de los temas `treecover`, `primary`, `naturally_reg_2020` y `planted_plantation_2020`. `SBTN_natural_2020` responde a `estado_2020`, pero mide tierra natural y no solo bosque, así que no cuenta para "registra bosque".
2. **Series anuales.** En las columnas por año decide el año: 2021 en adelante es `cambio_posterior`. Whisp marca `TMF_def_2021` a `TMF_def_2025` como `disturbance_before`, pero su nombre dice el año de la deforestación. En la tabla de convergencia se muestran los agregados (`*_after_2020`); las columnas por año quedan en el detalle por capa.
3. **Mismo conjunto por dos vías.** Comparten fila UMD Global Forest Change (Whisp `GFC_*` y GFW `umd_tree_cover_loss`) y SBTN (Whisp `SBTN_natural_2020` y GFW `sbtn_natural_forests_map`).
4. **Consultas nuevas de GFW.** `sbtn_natural_forests_map` se agrupa por `sbtn_natural_forests_map__class` y se suma el área de la clase 1, "Natural Forest". `umd_glad_dist_alerts` cuenta las alertas con `umd_glad_dist_alerts__date` desde el 2021-01-01.
5. **Análisis anteriores a la adenda.** Un análisis de GFW anterior no trae DIST, y esa pregunta queda sin medir. Los de Whisp ganan `capas` al arrancar la API, sin volver a consultar a Whisp.
6. **Puntos.** Whisp analiza el punto tal cual, así que cualquier valor distinto de cero cuenta como "registra bosque", como en el propio Whisp.
7. **Hectáreas por píxel.** El área de cada píxel se calcula con la esfera de igual área del WGS 84 (radio 6 371 007 m), entre las latitudes de sus dos bordes.

### Respuestas reales guardadas

El 2026-10-05, ya en producción, el equipo bajó con "Descargar la respuesta completa" las tres respuestas de la parcela ficticia PA-00002:
- `whisp_respuesta_real_2.json`;
- `gfw_respuesta_real_adenda.json`, con las cuatro consultas: la clase de bosque natural llega como texto ("Non-Forest") y hay pérdida en 2022 con la columna `area__ha`;
- `mapbiomas_respuesta_real.json`, la evidencia de 74 píxeles en 10 años: 50 peticiones, una de ellas con la cabecera de 64 KB de entonces.

Coinciden con lo que se interpretaba; las pruebas usan esos archivos.

### Pendiente

- Las decisiones de la sección 11.

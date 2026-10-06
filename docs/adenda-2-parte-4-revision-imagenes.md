# Adenda 2 a la Parte 4 — Revisión de imágenes en lugar de visita de campo

Fecha: 5 de octubre de 2026. Decisión del equipo.

Esta adenda modifica la Parte 4 de `docs/especificacion.md` y convive con `docs/adenda-parte-4-fuentes.md`. Donde difiera de la especificación, manda esta adenda. El principio de exponer sin concluir no cambia.

## 1. Qué cambia y por qué

Hoy, cuando una fuente pide revisión, la aplicación indica que un técnico debe visitar la parcela. Eso se elimina. Una visita muestra cómo está la parcela hoy, pero la pregunta del Reglamento es cómo estaba al 31 de diciembre de 2020, y eso solo se ve en imágenes de esa época.

| Antes | Ahora |
| --- | --- |
| Una fuente pide revisión y un técnico visita la parcela | Una fuente pide revisión y el administrador revisa imágenes satelitales |
| El requisito `revision_atendida` se cumple con una visita de campo | Se cumple con una revisión de imágenes registrada |
| La visita era parte obligatoria del camino | La visita queda como registro opcional y ya no forma parte de este camino |

## 2. Flujo nuevo

1. Cuando una parcela recibe la alerta `analisis_requiere_revision`, el sistema genera su juego de imágenes satelitales. Una parcela sin esa alerta no genera imágenes.
2. La pantalla de la parcela indica: "Qué hacer: el administrador revisa las imágenes de la parcela en la pestaña Imágenes y registra lo que observa. Con esa revisión decide en Habilitación."
3. Un `admin_cooperativa` abre la pestaña Imágenes, compara la imagen anterior a la fecha de corte con las posteriores y registra su revisión.
4. Con la revisión registrada, el requisito `revision_atendida` se cumple y el administrador decide habilitar o excluir, como define la Parte 4.

### 2.1 Lo que esta adenda no toca

Esta adenda no cambia cuándo se activa la alerta `analisis_requiere_revision`. Rige la regla que el equipo ya definió y que está implementada en el código. La sección 7.2 de `docs/adenda-parte-4-fuentes.md` queda sin efecto. Aquí solo se define qué pasa después de que la alerta aparece.

## 3. Fuentes de imágenes

| Fuente | Resolución | Papel | Se guarda |
| --- | --- | --- | --- |
| Sentinel-2, por Copernicus Data Space | 10 m | Imagen fechada cercana a la fecha de corte, y posteriores. Es la evidencia que se sella | Sí, en Storage |
| Esri World Imagery Wayback | Alta, variable según el lugar | Imagen de alta resolución para mirar el detalle. Su fecha de captura puede estar lejos de la fecha de corte | Solo sus datos, salvo que los términos permitan más |

1. Los datos de acceso de Copernicus están en el archivo de APIs del equipo: Process API en `https://sh.dataspace.copernicus.eu/api/v1/process`, con autenticación OAuth2 de credenciales de cliente.
2. En Wayback, la fecha de publicación de una versión no es la fecha de captura. La fecha de captura, el proveedor y la resolución se leen de los metadatos de cada versión. Solo se muestra la fecha de captura.
3. Antes de integrar cada fuente, confirmar en su documentación oficial la forma de consulta y los términos de uso. En especial, confirmar si los términos de Esri permiten guardar o incluir en un PDF una imagen de Wayback. Mientras no esté confirmado, Wayback se muestra solo dentro de la aplicación y no se guarda ni se imprime.
4. Las imágenes de Sentinel-2 llevan la atribución que exige Copernicus.
5. Para Wayback no se crean cuentas nuevas. Se usa la cuenta de ArcGIS Location Platform que el equipo ya tiene. Claude Code confirma si el servicio exige la clave pública existente o ninguna.
6. Todo se mantiene dentro de planes gratuitos. No se integra ninguna fuente de pago.

## 4. Comprobación de viabilidad, antes de construir

`backend/scripts/check_imagenes.py` comprueba, con una parcela de `backend/tests/datos/`:

1. Que la cuenta de Copernicus entrega una imagen de Sentinel-2 de 2020 para esa parcela.
2. Cuántas unidades de procesamiento consume el juego completo de una parcela. El plan gratuito da 10,000 al mes, según el archivo de APIs del equipo.
3. Que la nubosidad se puede medir sobre la parcela, no solo sobre la escena completa.
4. Que Wayback devuelve versiones y fechas de captura para ese lugar.

Si el punto 1 o el 3 fallan, **detenerse e informar al equipo**. Si falla el 4, se construye sin Wayback.

## 5. Selección de imágenes de Sentinel-2

### 5.1 Qué imágenes se piden

| Imagen | Regla de selección |
| --- | --- |
| Anterior al corte | La escena utilizable más cercana al 31 de diciembre de 2020, sin pasarse de esa fecha. Se busca primero en 2020; si no hay, se retrocede hasta el 1 de enero de 2019 |
| Una por año | Para cada año completo desde 2021, la escena utilizable con menos nubes sobre la parcela |
| Reciente | La escena utilizable más reciente de los últimos 12 meses |

### 5.2 Qué es una escena utilizable

1. Menos de `IMAGENES_NUBES_MAX_PCT` de la parcela está cubierta por nube o sombra de nube, medido con la clasificación de escena de Sentinel-2 sobre la parcela y un margen alrededor.
2. La parcela queda completa dentro de la escena.
3. Si en un período no existe ninguna escena utilizable, esa imagen queda como "sin imagen utilizable" y así se muestra. No se rellena con una imagen nublada.

### 5.3 Cómo se genera cada imagen

1. Dos versiones de cada escena: color natural y falso color infrarrojo, que distingue mejor los tipos de vegetación.
2. El recorte cubre la parcela más un margen de `IMAGENES_MARGEN_M` metros, para ver el entorno.
3. El lindero de la parcela se dibuja sobre la imagen. Para parcelas de tipo punto se dibuja el círculo con el área declarada.
4. Tamaño mínimo de 512 píxeles por lado. La imagen se amplía si hace falta, sin inventar detalle, y la resolución real de 10 m se indica siempre.

## 6. Modelo de datos

### 6.1 Tabla `imagenes_parcela`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `parcela_id` | uuid | Referencia a `parcelas` |
| `cooperativa_id` | uuid | Cooperativa que la generó |
| `fuente` | text | `sentinel2` o `esri_wayback` |
| `papel` | text | `anterior_al_corte`, `anual`, `reciente` o `alta_resolucion` |
| `fecha_captura` | date | Fecha real de captura |
| `dias_respecto_al_corte` | integer | Negativo si es anterior al 31 de diciembre de 2020 |
| `resolucion_m` | numeric(6,2) | Resolución real de la imagen |
| `nubes_parcela_pct` | numeric(5,2) | Nubosidad sobre la parcela; nulo en Wayback |
| `identificador_fuente` | text | Identificador de la escena o de la versión de Wayback |
| `proveedor` | text | Satélite o proveedor que informa la fuente |
| `geometria_sha256` | char(64) | Huella de la geometría de la parcela al generarla |
| `documento_natural_id`, `documento_infrarrojo_id` | uuid | Documentos de tipo `imagen_satelital`; nulos si la imagen no se guarda |
| `estado` | text | `pendiente`, `generada`, `sin_imagen_utilizable` o `error` |

Las imágenes guardadas son documentos generados por el sistema, con su huella SHA-256. Nadie las carga ni las anula a mano. Una imagen queda obsoleta si cambia la geometría de la parcela. El juego nuevo se genera solo si la parcela vuelve a tener la alerta.

### 6.2 Tabla `revisiones_imagenes`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `parcela_id` | uuid | Referencia a `parcelas` |
| `cooperativa_id` | uuid | Cooperativa de quien revisa |
| `revisada_por`, `revisada_en` | uuid, timestamptz | Quién y cuándo |
| `imagenes` | jsonb | Identificadores de las imágenes que estaban a la vista al revisar |
| `observacion_2020` | text | `bosque`, `cultivo_o_uso_agricola`, `mixto` o `no_se_distingue` |
| `observacion_cambio` | text | `sin_cambio_visible`, `cambio_visible` o `no_se_distingue` |
| `descripcion` | text | Qué vio y en qué imágenes. Obligatoria, mínimo 50 caracteres |
| `geometria_sha256` | char(64) | Huella de la geometría revisada |
| `anulada_en`, `anulada_por`, `motivo_anulacion` | timestamptz, uuid, text | Se llenan al anular |

Una revisión no se edita. Si está mal, se anula con motivo y se registra otra.

## 7. La revisión

1. La registra solo un `admin_cooperativa`. El operador y el lector ven las imágenes y las revisiones, pero no las registran.
2. Para registrar una revisión debe existir la imagen anterior al corte y al menos una posterior.
3. `observacion_2020` responde: qué se ve en la parcela en la imagen anterior al corte.
4. `observacion_cambio` responde: si entre esa imagen y las posteriores se ve un cambio de cobertura dentro del lindero.
5. La revisión registra lo que una persona con nombre observó en imágenes identificadas. No es un veredicto del sistema.
6. La revisión deja de estar vigente si cambia la geometría de la parcela o si se anula.

### 7.1 Cuando no se distingue

Con 10 m de resolución, el cacao bajo sombra y el bosque pueden verse iguales. Si alguna de las dos observaciones es `no_se_distingue`:

1. El requisito `revision_atendida` no se cumple.
2. El administrador puede pedir otras fechas con "Buscar más imágenes", que amplía los períodos de búsqueda.
3. El administrador puede cargar una imagen externa como documento de tipo `imagen_externa`, indicando su fuente y su fecha de captura. Entra al juego de imágenes con el papel `externa`.
4. Si aun así no se distingue, la parcela sigue `pendiente`. No hay otra vía para cumplir el requisito.

## 8. Cambios en la compuerta de habilitación

1. `revision_atendida` se cumple cuando no hay alerta `analisis_requiere_revision`, o cuando existe una revisión de imágenes vigente, posterior al último análisis, en la que ninguna de las dos observaciones es `no_se_distingue`.
2. Se elimina de ese requisito toda referencia a la visita de campo y al plazo de 365 días.
3. La nota de habilitación sigue siendo obligatoria cuando la parcela tiene alertas.
4. Si la revisión registró `cambio_visible` y el administrador habilita igual, la nota es obligatoria y el hecho llega al informe de hallazgos.
5. Para excluir una parcela, la evidencia puede ser una revisión de imágenes o un análisis. Ya no se exige una visita.

### 8.1 Qué pasa con las visitas de campo

1. La tabla, los endpoints y la pestaña Visitas se conservan. Una visita sigue siendo la única forma de marcar una geometría como recorrida en campo.
2. El motivo `analisis_requiere_revision` se retira de las visitas nuevas. Quedan `verificacion_de_coordenadas` y `otro`.
3. Ningún texto de la aplicación propone una visita como respuesta a un análisis.

## 9. Pantallas

### 9.1 Pestaña Imágenes del detalle de parcela

1. Una tira con todas las imágenes en orden de fecha. Cada una muestra fuente, fecha de captura, días respecto al corte, resolución y nubosidad sobre la parcela.
2. Un comparador de dos imágenes lado a lado, con el lindero dibujado en ambas y con zoom sincronizado. Por defecto compara la anterior al corte con la reciente.
3. Un selector entre color natural y falso color infrarrojo.
4. La vista de alta resolución de Wayback, con su fecha de captura a la vista.
5. Los períodos sin imagen utilizable aparecen en la tira como espacios marcados, no se ocultan.
6. Para el administrador, el botón "Registrar revisión", con las dos observaciones y la descripción, y el botón "Buscar más imágenes".
7. El historial de revisiones, con quién, cuándo y qué registró.
8. En una parcela sin alerta, la pestaña muestra el texto "Esta parcela no tiene alertas de análisis; no se generaron imágenes".

### 9.2 Reglas

1. La fecha de captura va siempre junto a la imagen, en texto grande. Una imagen sin fecha visible no se muestra.
2. Junto a cada imagen de Sentinel-2 se indica "Resolución: 10 m". No se la presenta como alta resolución.
3. Siguen prohibidas las frases de la Parte 4 y de la primera adenda.
4. El productor ve las imágenes de sus parcelas y el resultado de las revisiones, sin poder registrarlas.

## 10. Endpoints

| Método y ruta | Roles | Qué hace |
| --- | --- | --- |
| `GET /parcelas/{id}/imagenes` | Personal; productor dueño por `/mi/parcelas/{id}/imagenes` | Lista el juego de imágenes con sus datos y URLs firmadas |
| `POST /parcelas/{id}/imagenes` | `admin_cooperativa`, `operador` | Regenera el juego de una parcela con alerta. Responde 202. Sin alerta responde 400 con `sin_alerta` |
| `POST /parcelas/{id}/imagenes/buscar-mas` | `admin_cooperativa` | Amplía los períodos de búsqueda |
| `POST /parcelas/{id}/imagenes/externa` | `admin_cooperativa` | Carga una imagen externa con su fuente y fecha |
| `GET /parcelas/{id}/revisiones-imagenes` | Personal; productor dueño | Historial de revisiones |
| `POST /parcelas/{id}/revisiones-imagenes` | `admin_cooperativa` | Registra una revisión |
| `POST /revisiones-imagenes/{id}/anular` | `admin_cooperativa` | Anula una revisión, con motivo |

La generación usa la misma cola en segundo plano que los análisis. Se auditan `imagenes.generar`, `imagenes.cargar_externa`, `revision_imagenes.registrar` y `revision_imagenes.anular`.

## 11. Variables y cuota

| Variable | Secreta | Valor inicial | Descripción |
| --- | --- | --- | --- |
| `COPERNICUS_CLIENT_ID` | Sí | Lo crea el equipo | Cliente OAuth de Copernicus Data Space |
| `COPERNICUS_CLIENT_SECRET` | Sí | Lo crea el equipo | Secreto de ese cliente |
| `IMAGENES_NUBES_MAX_PCT` | No | `5` | Nubosidad máxima sobre la parcela para que una escena sea utilizable |
| `IMAGENES_MARGEN_M` | No | `150` | Margen alrededor de la parcela en el recorte |
| `IMAGENES_CUOTA_MENSUAL_PU` | No | `10000` | Unidades de procesamiento del plan |

1. El sistema lleva la cuenta de las unidades usadas en el mes. Al llegar a 80 % de la cuota deja de generar imágenes nuevas y lo indica en la pantalla de plataforma.
2. Si faltan las credenciales de Copernicus, la fuente queda como "no configurada", igual que las demás.
3. Las credenciales las crea y las carga en Render una persona del equipo.

## 12. DOP, DEX e informe de hallazgos

1. Solo para las parcelas que tuvieron la alerta, el bloque "Cobertura forestal" del contenido sellado del DOP gana las imágenes de Sentinel-2 anterior al corte y reciente, con sus datos y sus huellas, y la revisión vigente.
2. Para esas parcelas, el PDF del DOP y el del DEX muestran las dos imágenes en color natural con el lindero, la fecha de captura de cada una, y quién hizo la revisión, cuándo y qué registró.
3. Una parcela sin alerta no lleva imágenes ni revisión en sus documentos.
4. Las imágenes de Wayback se listan con su fecha de captura, proveedor y resolución. Solo se incluyen como imagen si se confirmó que los términos lo permiten.

Hallazgos nuevos para la Parte 9:

| Código | Se genera cuando | Criterio | Grupo |
| --- | --- | --- | --- |
| `revision_de_imagenes_registrada` | La parcela tuvo alerta de análisis y hay una revisión vigente. Nombra a quien revisó, la fecha, las imágenes y lo que registró | 1 | Requiere atención |
| `habilitada_con_cambio_visible` | La revisión registró `cambio_visible` y la parcela fue habilitada. Incluye la nota | 1 | Requiere atención |
| `imagen_previa_lejana` | La imagen anterior al corte es de más de 180 días antes del 31 de diciembre de 2020 | 1 | No verificado |
| `sin_imagen_de_alta_resolucion_previa` | No hay imagen de alta resolución con fecha de captura anterior al corte | 1 | No verificado |

El informe lleva además este texto fijo en "Lo que no pudimos verificar": "La revisión de imágenes la hace personal de la cooperativa. Las imágenes revisadas se adjuntan para que el operador pueda repetirla."

## 13. Pruebas mínimas

| Caso | Resultado esperado |
| --- | --- |
| Parcela cuyo análisis no activa la alerta | No se genera ninguna imagen |
| Parcela que recibe la alerta | Se genera su juego de imágenes |
| `POST /parcelas/{id}/imagenes` en una parcela sin alerta | 400 con `sin_alerta` |
| La regla de activación de la alerta | Las pruebas existentes de esa regla siguen pasando sin cambios |
| Escenas simuladas de 2020 con distintas fechas y nubes | Se elige la utilizable más cercana al corte, sin pasarse |
| Todas las escenas de 2020 nubladas sobre la parcela | Se retrocede a 2019; si tampoco hay, queda `sin_imagen_utilizable` |
| Año sin escena utilizable | La tira lo muestra como espacio marcado |
| Versión de Wayback con fecha de publicación 2021 y captura 2019 | Se guarda y se muestra 2019 |
| `operador` registra una revisión | 403 |
| Revisión sin imagen anterior al corte | 400 |
| Revisión con descripción de 20 caracteres | 422 |
| Alerta de análisis y revisión con `sin_cambio_visible` | `revision_atendida` se cumple |
| Revisión con `no_se_distingue` | `revision_atendida` no se cumple |
| Alerta de análisis y solo una visita de campo, sin revisión | `revision_atendida` no se cumple |
| Cambia la geometría después de la revisión | La revisión deja de estar vigente y se genera un juego nuevo |
| Habilitar con `cambio_visible` y sin nota | 422 |
| Excluir citando una revisión de imágenes | La parcela pasa a `excluida` |
| Cuota al 80 % | No se generan imágenes nuevas y la pantalla lo indica |
| Textos de la aplicación | Ninguno propone una visita ante un análisis |
| Pruebas de imágenes | Ninguna sale a internet |

## 14. Criterios de aceptación en producción

1. Una parcela de prueba con alerta muestra su imagen de Sentinel-2 anterior al corte, una por año y la reciente, cada una con su fecha. Una parcela sin alerta no genera imágenes.
2. El comparador muestra dos imágenes lado a lado con el lindero y el cambio entre color natural e infrarrojo.
3. La vista de alta resolución muestra la fecha de captura real.
4. En una parcela con alerta, el texto "Qué hacer" habla de revisar imágenes y no menciona visitas.
5. El administrador registra una revisión y la parcela puede habilitarse; el operador no ve el botón.
6. Una revisión con `no_se_distingue` no destraba la habilitación.
7. El PDF del DOP muestra las dos imágenes con sus fechas y la revisión.
8. La pantalla de plataforma muestra las unidades de procesamiento usadas en el mes.

## 15. Lo que el equipo debe entregar

- [ ] Crear la cuenta en Copernicus Data Space y un cliente OAuth, y cargar `COPERNICUS_CLIENT_ID` y `COPERNICUS_CLIENT_SECRET` en Render.
- [ ] Correr `check_imagenes.py` con esas credenciales en la terminal.

## 16. Decisiones pendientes del equipo

- [ ] Confirmar que, si las imágenes no permiten distinguir, la parcela queda pendiente sin otra vía.
- [ ] Confirmar el tope de 5 % de nubes sobre la parcela.
- [ ] Confirmar con Esri si se puede incluir una imagen de Wayback en un PDF.

## 17. Registro de la construcción (2026-10-05)

### Decisiones del equipo

1. **Las visitas ya no atienden un análisis.** Una parcela habilitada cuya alerta se atendió con una visita pasa sola a `observada` cuando se aplica esta adenda, hasta que el administrador registre una revisión de imágenes. La pestaña Visitas se conserva solo para marcar un lindero recorrido en campo (8.1).
2. **"Buscar más imágenes"** agrega hasta 3 escenas utilizables más, las más cercanas antes del 31 de diciembre de 2020 que aún no estén en el juego (dentro de 2020 y 2019), para ver mejor si había bosque en la fecha de corte, y vuelve a buscar la escena utilizable más reciente.
3. **Cuota:** `IMAGENES_CUOTA_MENSUAL_PU` = 30000, la cuota que informó el equipo para su cuenta. La documentación pública de Copernicus indica 10,000 al mes para usuarios generales.
4. **Imagen externa:** se guarda con `fuente` = `externa` y `papel` = `externa`, valores que la tabla de la sección 6.1 no listaba.

### Comprobación de viabilidad (`backend/scripts/check_imagenes.py`)

- **Wayback (punto 4): pasa.** Para la parcela de `tests/datos/whisp_respuesta_real.json` hay 10 versiones con fecha de captura real (`SRC_DATE2`); las imágenes distintas son del 30/09/2012 y del 29/01/2023, a 0.5 m, de Maxar/Vantor (WorldView-2). La configuración, los metadatos y las teselas responden sin clave: la cuenta de ArcGIS Location Platform no hace falta para Wayback. El servicio rechaza (403) el identificador por defecto de httpx; las peticiones se identifican como CacaoTrace.
- **Copernicus (puntos 1 a 3):** pendiente de que el equipo lo corra con sus credenciales.
- **Términos de Esri:** el Master Agreement E204 (sección 3.2) no permite guardar ni almacenar sus datos fuera de sus productos, y permite representaciones estáticas en informes, con atribución. El resumen de términos pide consultar a Esri para el uso comercial de contenido de Living Atlas. Mientras el equipo no lo confirme con Esri, Wayback se muestra solo dentro de la aplicación (3.3).

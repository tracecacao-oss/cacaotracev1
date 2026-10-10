# Adenda 7 — El lote: aduanas y legalidad por requisito (Partes 8 y 9)

Fecha: 9 de octubre de 2026.

Esta adenda modifica lo que `docs/especificacion.md` dice del lote de exportación: sus documentos de embarque (Parte 8) y lo que el lote muestra en su pantalla y en el DEX (Parte 9). Donde difiera de la especificación o de las adendas anteriores, manda esta adenda.

Se construye después de las adendas 4, 5 y 6. Usa los requisitos de la parcela, del productor y de la organización que ellas definen, con sus estados.

No agrega ni quita ninguna comprobación del lote. No cambia la genealogía, la sugerencia FIFO, los cuatro documentos de embarque de hoy, la recomprobación diaria, la emisión del DEX ni su mensaje final. Tampoco el análisis de cobertura forestal ni la regla que decide cuándo salta una alerta.

La fuente es el "Documento orientador para la diligencia debida de la legalidad del café y cacao en el marco del EUDR" (MIDAGRI, MINCETUR y ADEX; European Forest Institute, 2026). En adelante, "el orientador". El propio documento dice que no es jurídicamente vinculante ni asesoría legal.

Las decisiones propias de esta adenda están en la sección 11 y esperan confirmación del equipo.

## 1. Qué cambia y por qué

El orientador pide una sola cosa al lote: la declaración aduanera (requisito 7.2). Lo demás que pide es de la parcela, del productor o de la organización, y ya está en las adendas 4, 5 y 6.

Pero el lote es el único lugar donde todo eso se junta. Hoy el DEX muestra la legalidad parcela por parcela y como lista de hallazgos. Nadie ve el lote completo frente a cada requisito.

| Antes | Ahora |
| --- | --- |
| Cuatro documentos de embarque | Los mismos cuatro, más la declaración aduanera, que no frena |
| Nada se compara con lo declarado en aduanas | El sistema compara el peso y la subpartida de la declaración aduanera con el lote |
| Con el lote cerrado no se puede cargar nada | La declaración aduanera se puede agregar después de emitir el DEX, sin cambiarlo |
| La legalidad del lote se lee parcela por parcela | Un cuadro muestra el lote completo, requisito por requisito del orientador, pesado por kilos |

### Regla de efecto

Un lote queda listo cuando pasa las nueve comprobaciones de la Parte 8. Esta adenda no agrega ninguna.

Todo lo que esta adenda agrega no bloquea. Se muestra y llega al informe de hallazgos.

El sistema sigue sin concluir. El cuadro de legalidad no tiene total, puntaje ni calificación: muestra cuentas y porcentajes de masa, y quien lo lee saca su conclusión.

## 2. Qué frena un lote y de dónde viene

Ninguna comprobación es nueva. Tres cambian por dentro con las adendas 4, 5 y 6. Esta tabla no pide construir nada: fija cómo quedan.

| Comprobación | Qué mira | Qué cambió |
| --- | --- | --- |
| `parcelas_habilitadas` | Cada parcela de la genealogía está `habilitada` hoy | Su compuerta mira ahora el perfil legal, la tenencia, los permisos obligatorios y las incidencias (adenda 4), y la declaración anual del productor (adenda 5) |
| `sin_parcelas_excluidas` | Ninguna parcela está `excluida` | Nada |
| `dops_vigentes` | Cada DOP de la genealogía está vigente | Nada |
| `dpps_vigentes` | Cada DPP de las tandas finales está vigente | Nada |
| `genealogia_cuadra` | La masa del lote es la suma de los kilos atribuidos | Nada |
| `expediente_cooperativa_completo` | Los tres documentos de identidad de la organización | Antes eran seis (adenda 6) |
| `datos_cooperativa_completos` | Dirección, correo y representante | Nada |
| `importador_completo` | Nombre, dirección y correo del importador | Nada |
| `documentos_embarque_completos` | Los documentos de embarque obligatorios | Los mismos cuatro; sección 3 |

1. Cuando una parcela no está habilitada, el caso de la comprobación ya dice qué requisito dejó de cumplir. Con las adendas 4 y 5 ese texto nombra también el requisito legal o la declaración del productor que falta. No hace falta programar nada aparte: sale del detalle de cada requisito.
2. El caso nombra además al productor de la parcela, para ir directo a corregirlo.

## 3. Documentos de embarque

El catálogo `documentos_embarque` suma un tipo y un dato por tipo: si es obligatorio.

| Código | Documento | Emisor habitual | Obligatorio |
| --- | --- | --- | --- |
| `factura_comercial` | Factura comercial | La organización | Sí |
| `packing_list` | Lista de empaque | La organización | Sí |
| `certificado_origen` | Certificado de origen | La entidad que lo emite para el destino | Sí |
| `certificado_fitosanitario` | Certificado fitosanitario | SENASA | Sí |
| `dam` | Declaración Aduanera de Mercancías | SUNAT | No |

1. `documentos_embarque_completos` mira solo los obligatorios. El lote puede quedar listo y el DEX puede emitirse sin `dam`.
2. El requisito 7.2 del orientador también habla de los permisos previos que se tramitan por la VUCE. De ellos, el sistema ya pide el certificado fitosanitario.
3. La pestaña Embarque muestra `dam` después de los cuatro obligatorios, con la etiqueta "No frena el lote".

## 4. Declaración aduanera

### 4.1 Qué se registra

Al cargar la `dam` se escriben cuatro datos, además del archivo.

| Dato | Regla |
| --- | --- |
| `numero` | Número de la declaración, como figura en ella |
| `fecha_numeracion` | Fecha de numeración. No futura |
| `peso_neto_kg` | Peso neto declarado, en kilos. Mayor que 0 |
| `subpartida` | Subpartida nacional declarada. Se guarda solo con dígitos |

Se guardan en la tabla `declaraciones_aduaneras`.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `lote_id` | uuid | Referencia a `lotes` |
| `documento_id` | uuid | El archivo, de tipo `dam` y entidad `lote` |
| `numero`, `fecha_numeracion`, `peso_neto_kg`, `subpartida` | text, date, numeric(10,2), text | Los cuatro datos |
| `registrada_por`, `registrada_en` | uuid, timestamptz | Quién la cargó y cuándo |
| `posterior_al_dex` | boolean | Verdadero si se cargó con el lote `cerrado` |
| `anulada_en`, `anulada_por`, `motivo_anulacion` | timestamptz, uuid, text | No se edita ni se borra: se anula con motivo y se carga otra |

1. Un lote tiene como máximo una declaración aduanera sin anular.
2. La cargan el `admin_cooperativa` y el `operador`, como los demás documentos de embarque. La anula el `admin_cooperativa`.

### 4.2 Comparación con el lote

El sistema compara dos cosas al cargar y cada vez que se consulta.

| Comparación | Regla | Qué muestra |
| --- | --- | --- |
| Peso | `peso_neto_kg` frente a `masa_neta_kg` del lote | La diferencia en kilos y en porcentaje. "Difiere" si pasa de `DAM_TOLERANCIA_PESO_PCT`, con valor inicial 1 |
| Subpartida | `subpartida` frente a `partida_sa` de la orden | "Difiere" si no empieza con la partida de la orden, que hoy es 1801 |

1. La comparación no bloquea. Si algo difiere, la pestaña lo dice junto a la declaración y el lote recibe el hallazgo `dam_difiere_del_lote`.
2. El sistema no lee el archivo. Compara lo que la persona escribió.

### 4.3 Cotejo en fuente

1. La `dam` admite cotejo en fuente: una persona busca el número en la consulta pública de SUNAT y registra la nota, como en la Parte 4.
2. La pantalla enlaza las dos consultas que nombra el orientador: `https://ww3.sunat.gob.pe/aduanas/informli/ildua.htm` y `http://www.aduanet.gob.pe/aduanas/informgest/ExpoDef.htm`.
3. El sistema no consulta esas páginas.

### 4.4 Después de emitir el DEX

A veces la declaración aduanera se numera después de entregar el DEX.

1. La `dam` es el único documento que se puede cargar con el lote `cerrado`. Los demás siguen como hoy.
2. El DEX emitido no cambia: su contenido y su huella son los mismos.
3. La pestaña DEX del lote muestra el bloque "Agregado después de la emisión", con los cuatro datos, la comparación, la fecha en que se cargó y si tiene cotejo.
4. La verificación pública del DEX suma ese bloque con tres datos: el número, la fecha de numeración y la fecha en que se agregó. No muestra pesos ni el archivo.
5. Si la comparación difiere en una declaración posterior al DEX, el lote guarda la alerta `dam_difiere_del_lote` en `alertas`, como hace hoy con `exclusion_posterior_al_cierre`.

## 5. Cuadro de legalidad por requisito

### 5.1 Qué es

Una tabla que toma cada requisito del orientador y cuenta, para un lote, a cuántos sujetos les aplica y en qué estado está cada uno. Lo calcula el sistema desde lo que ya está cargado. Nadie lo escribe.

### 5.2 Filas

El orden y la composición viven en `backend/app/catalogos/cuadro_legalidad.py`. Cada fila toma su estado de un requisito ya definido.

| Fila | Ref. | De quién | De dónde sale el estado |
| --- | --- | --- | --- |
| Tenencia | 1.1, 1.2 | Parcela | `tenencia`, adenda 4 |
| Acuerdo con la comunidad | 1.3, 1.4 | Parcela | `acuerdo_comunal` |
| Área protegida | 2.1, 2.13 | Parcela | `area_protegida` |
| Tierra forestal | 2.2, 2.10, 2.11 | Parcela | `tierra_forestal` |
| Agua de riego | 2.4 | Parcela | `agua_de_riego` |
| Faja marginal | 2.5 | Parcela | `faja_marginal` |
| Instrumento ambiental | 2.12, 3.3 | Parcela | `instrumento_ambiental` |
| Patrimonio cultural | 3.1 | Parcela | `patrimonio_cultural` |
| Daños ambientales | 3.4 | Parcela | Incidencias de tipo `ambiental` de la parcela |
| Agroquímicos | 2.3 | Productor | `agroquimicos`, adenda 5 |
| Envases | 2.7 | Productor | `envases` |
| Condiciones de trabajo | 4.1 a 4.5 | Productor | `condiciones_de_trabajo` |
| Igualdad y maternidad | 4.6, 4.7 | Productor | `igualdad_y_maternidad` |
| Menores de edad | 5.2 | Productor | `menores_de_edad` |
| Trabajo libre | 5.3, 5.4 | Productor | `trabajo_libre` |
| Tributos del productor | 7.1 | Productor | `tributos` del productor |
| Tributos de la organización | 7.1 | Organización | `tributos`, adenda 6 |
| Registro de cooperativas | 7.1 | Organización | `registro_cooperativas` |
| Integridad | 7.3, 5.5 | Organización | `integridad` |
| Actuaciones de diligencia | Varios | Organización | `actuaciones` |
| Aduanas | 7.2 | Lote | `dam` de este lote |

1. Son 21 filas. Entre todas nombran los 31 requisitos que el orientador considera pertinentes para el cacao.
2. Daños ambientales aplica a una parcela cuando tiene alguna incidencia de tipo `ambiental`. Con la incidencia cerrada cuenta como con sustento; abierta, como por atender.
3. Debajo del cuadro va la lista de los nueve requisitos que no se piden, con su motivo: los ocho no pertinentes y el 2.6, que es solo para café. Es la tabla 3.3 de la adenda 4.

### 5.3 Columnas

| Columna | Qué muestra |
| --- | --- |
| Requisito, referencia, nivel y diligencia | Los del orientador |
| Le aplica a | Cuántos sujetos del lote tienen el requisito en un estado distinto de `no_aplica`, y qué porcentaje de la masa del lote aportan |
| Con sustento | Los que están `sustentado`, `por_vencer` o `declarado`. Cuenta y porcentaje de masa |
| Nivel de verificación | De los que tienen sustento, cuántos están `declarado`, `documentado` y `verificado_en_fuente` |
| Por atender | Los que están `por_atender`. Cuenta y porcentaje de masa |
| Sin sustento | Los que están `sin_sustento`, `vencido` o `sin_dato`. Cuenta y porcentaje de masa |

1. Los sujetos de una fila de parcela son las parcelas de la genealogía. Los de una fila de productor, sus productores.
2. El peso de una parcela en el lote es el que ya calcula el informe de hallazgos desde la genealogía. El de un productor es la suma de los pesos de sus parcelas.
3. En las filas de la organización y del lote hay un solo sujeto. En vez de cuenta y porcentaje se muestra su estado, y lo que falta cuando falta algo.
4. Si a ningún sujeto le aplica, la fila se muestra igual, con "No aplica a este lote".
5. El cuadro no tiene fila de totales ni ningún número que resuma el lote. No usa colores para calificar un estado.
6. Los porcentajes llevan dos decimales en el contenido sellado y uno en pantalla y en el PDF.

### 5.4 Cuándo se calcula

1. Mientras el lote no está cerrado, el cuadro se calcula al consultarlo, con el estado de hoy. Se rotula "preliminar", como el informe de hallazgos.
2. Al emitir el DEX se calcula en ese instante y se sella en su contenido. Desde entonces, la pantalla muestra el sellado.
3. Está disponible desde que el lote está `armado`, que es cuando su genealogía queda fija.
4. Lo calcula `backend/app/services/cuadro_legalidad.py`, con los mismos datos que reúne el informe de hallazgos. No repite reglas: lee el estado de cada requisito de los servicios de las adendas 4, 5 y 6.

## 6. Rutas

| Ruta | Quién | Qué hace |
| --- | --- | --- |
| `GET /lotes/{lote_id}/legalidad` | Personal | El cuadro, preliminar o sellado, con la lista de requisitos que no se piden |
| `GET /lotes/{lote_id}/legalidad/{fila}` | Personal | Los sujetos de una fila, cada uno con su estado, su peso y su sustento |
| `POST /lotes/{lote_id}/documentos` | `admin_cooperativa`, `operador` | Ya existe. Acepta `dam` con sus cuatro datos, también con el lote `cerrado` |
| `GET /lotes/{lote_id}/documentos` | Personal | Ya existe. Suma la declaración aduanera con su comparación |
| `POST /lotes/{lote_id}/declaracion-aduanera/anular` | `admin_cooperativa` | La anula, con motivo |

Otra organización recibe 404 en todas las rutas de un lote que no es suyo. La verificación pública del DEX suma el bloque de la sección 4.4 a lo poco que ya muestra.

## 7. Pantallas

1. El lote suma la pestaña "Legalidad", entre Indicadores y Embarque. También se abre por `#/lotes-exportacion/{id}/legalidad`.
2. La pestaña muestra el cuadro agrupado por de quién es cada fila: parcelas, productores, organización y lote. Arriba dice si es preliminar o el sellado en el DEX.
3. Cada cuenta es un enlace. Abre la lista de parcelas o de productores que hay detrás, y cada uno lleva a su ficha.
4. En pantallas angostas cada fila se apila como una tarjeta, con sus cuatro cuentas.
5. La pestaña Embarque suma la declaración aduanera, con sus cuatro datos, la comparación y el botón de cotejo. Con el lote `cerrado` ofrece "Agregar la declaración aduanera".
6. La pestaña DEX muestra el bloque "Agregado después de la emisión" cuando lo hay.
7. La página pública de verificación del DEX muestra ese mismo bloque, con sus tres datos.

## 8. DEX e informe de hallazgos

### DEX

1. El contenido del DEX suma el bloque `legalidad_por_requisito`, con el cuadro sellado y la lista de requisitos que no se piden.
2. El PDF suma la sección "Legalidad por requisito", después de la genealogía y antes de "Respaldo por parcela". Lleva una línea que dice de dónde salen los requisitos, que el orientador no es jurídicamente vinculante y que el cuadro no califica al lote.
3. Si el lote tiene `dam` al emitir, sus cuatro datos y la comparación van con los documentos de embarque.
4. El archivo de hallazgos del paquete suma el cuadro, para quien lo lea con un programa.
5. El LEEME nombra la sección nueva.
6. Los DEX anteriores se leen como hoy.

### Hallazgos nuevos

Son de la etapa 3 y su sujeto es el lote.

| Código | Se genera cuando | Grupo | Tema |
| --- | --- | --- | --- |
| `lote_sin_dam` | El lote no tiene declaración aduanera al emitir el DEX | No verificado | 11 |
| `dam_difiere_del_lote` | El peso o la subpartida de la declaración aduanera difieren del lote. Dice cuál, con los dos valores | Requiere atención | 3 |

1. Los hallazgos de las adendas 4, 5 y 6 no cambian. El cuadro los resume; no los reemplaza.
2. Los textos van en `es.json` y `en.json`, con las mismas claves.

## 9. Datos y migración

1. Tabla nueva: `declaraciones_aduaneras`, con RLS activado y sin políticas.
2. Tipo de documento nuevo: `dam`.
3. Variable nueva del backend: `DAM_TOLERANCIA_PESO_PCT`, con valor inicial 1.
4. El esquema de la verificación pública del DEX suma el bloque de la declaración aduanera posterior.
5. La migración no cambia ningún lote ni ningún DEX emitido.
6. `CLAUDE.md` nombra esta adenda y sus convenciones.

## 10. Pruebas mínimas y aceptación

### Pruebas automáticas

| Caso | Resultado esperado |
| --- | --- |
| Lote con los cuatro documentos y sin `dam` | Puede quedar listo; al emitir, hallazgo `lote_sin_dam` |
| `dam` con peso igual a la masa del lote y subpartida que empieza con 1801 | Sin diferencias; ningún hallazgo |
| `dam` con peso 3 % mayor que el lote | "Difiere"; hallazgo `dam_difiere_del_lote` con los dos pesos; no bloquea |
| `dam` con peso 0,5 % mayor, con el valor inicial de 1 % | No difiere; la diferencia se muestra igual |
| `dam` con subpartida que empieza con 0901 | "Difiere"; hallazgo |
| `dam` sin `peso_neto_kg` | 422 |
| Segunda `dam` sin anular la primera | 400 |
| `dam` cargada con el lote `cerrado` | Se acepta con `posterior_al_dex`; el contenido y la huella del DEX no cambian |
| Factura comercial cargada con el lote `cerrado` | 400, como hoy |
| Verificación pública de un DEX con `dam` posterior | Muestra número, fecha de numeración y fecha en que se agregó; no muestra pesos |
| `dam` posterior que difiere | El lote guarda la alerta `dam_difiere_del_lote` |
| Cuadro de un lote de 3 parcelas de 2 productores | 21 filas; en cada fila de parcela, la suma de las cuentas de sus columnas es el número de parcelas a las que aplica |
| Fila Tenencia con una parcela de declaración jurada y dos con título | Con sustento: 3; nivel: 1 declarado y 2 documentado |
| Productor con dos parcelas en el lote | Su peso en una fila de productor es la suma de los pesos de las dos |
| Fila Envases cuando ningún productor usa agroquímicos | "No aplica a este lote" |
| Fila Daños ambientales con una incidencia ambiental abierta | Por atender: 1 |
| Porcentajes de una fila de parcela que aplica a todas | Suman 100 |
| Cuadro antes y después de emitir | Antes, preliminar y con el estado de hoy. Después, el sellado, aunque cambie una parcela |
| Cuadro | No trae total ni ningún campo que resuma el lote |
| Textos | Los textos nuevos no usan las palabras prohibidas de la Parte 4 ni dicen que el lote cumple o incumple |
| DEX emitido antes de la migración | Su contenido y su huella no cambian |
| Aislamiento | Otra organización recibe 404 en el cuadro y en la declaración aduanera |

### Criterios de aceptación en producción

1. Un lote armado muestra en la pestaña Legalidad sus 21 filas, sin que nadie escriba nada.
2. Al tocar una cuenta de "Sin sustento" se abre la lista de parcelas o de productores, y desde ahí se llega a la ficha para corregir.
3. Al cargar una declaración aduanera con un peso distinto, la pestaña Embarque muestra la diferencia en kilos y en porcentaje.
4. Un DEX nuevo trae la sección "Legalidad por requisito" en español y en inglés, con las mismas cifras.
5. A un lote cerrado se le agrega la declaración aduanera y la página pública de su DEX la muestra aparte.
6. Una persona ajena al equipo lee el cuadro y explica qué significa una fila sin ayuda.

## 11. Lecturas del orientador y decisiones pendientes

### Diferencias y vacíos del orientador

| Punto | Qué dice | Cómo se tomó aquí |
| --- | --- | --- |
| 7.2, documento | La declaración aduanera, o su consulta pública por número | Se carga el archivo con su número; la consulta es el cotejo |
| 7.2, VUCE | Dice que solo el exportador puede ver los permisos previos de la VUCE | No se pide nada nuevo: ya está el certificado fitosanitario |
| Vista por lote | Da los requisitos uno por uno y no dice cómo presentarlos para un embarque | El cuadro de la sección 5 |
| Requisitos de un mismo tema | Varios comparten una misma orientación, como 4.1 a 4.5 | Una fila por grupo, con todas sus referencias |

### Antes de programar

1. Claude Code busca en los instructivos de SUNAT el formato del número de la declaración aduanera. Si lo confirma, lo valida. Si no, lo deja como texto de 5 a 30 caracteres.
2. Claude Code confirma que las dos direcciones de consulta de la declaración aduanera responden.
3. Claude Code revisa si el mecanismo de cotejo de la Parte 4 sirve tal cual para `dam`, que no es un documento del expediente legal. Si no, se detiene y pregunta.
4. Claude Code revisa que las adendas 4, 5 y 6 estén construidas y que cada requisito exponga su estado, su nivel y su sustento. Si a alguno le falta, se detiene y pregunta antes de calcular el cuadro por otra vía.

> **Lectura de las fuentes y decisiones del equipo del 10 de octubre de 2026.**
> 1. **Número de la declaración aduanera.** La consulta pública de SUNAT lo pide en partes: régimen, aduana (código de tres dígitos), año y número correlativo, sin decir su largo. El instructivo DESPA-IT.00.04 da un número de orden de seis caracteres, pero es de 2010 y ya no se aplica a la exportación definitiva. No se confirmó un formato: el número queda como texto de 5 a 30 caracteres, igual que en la adenda 6.
> 2. **Las dos consultas responden** (HTTP 200). La de una declaración pide un reCAPTCHA. El sistema no las consulta.
> 3. **Cotejo de `dam`.** Ya se extendió en la adenda 6, por decisión del equipo del 9 de octubre: el catálogo de embarque dice qué documento tiene registro consultable y el cotejo lo acepta también con el lote `cerrado`.
> 4. **Adendas 4, 5 y 6.** Las tres están construidas y fusionadas (PRs #41, #42 y #45). Los requisitos de la parcela exponen su estado, su nivel y su sustento; los del productor, su estado, su nivel y sus papeles; los de la organización, su estado y lo que falta, que es lo que la sección 5.3, regla 3, pide para esas filas. Las 21 filas nombran los 31 requisitos, y los nueve que no se piden son los de la tabla 3.3 de la adenda 4.
> 5. **Lo que la adenda 6 ya construyó.** La `dam` no obligatoria, su carga con el lote `cerrado`, su cotejo, el bloque "Agregado después de la emisión" y el hallazgo `lote_sin_dam` ya existen. Esta adenda suma los cuatro datos, la comparación, la anulación propia y `dam_difiere_del_lote`.
> 6. **Anulación.** El equipo decidió que anular la declaración aduanera anula también su archivo, en la misma transacción. El archivo no se anula por su cuenta: responde 400, como la política de la organización en la adenda 6.
> 7. **Verificación pública.** Muestra solo los tres datos de la sección 4.4, regla 4: número, fecha de numeración y fecha en que se agregó. Esta adenda manda sobre la 6, que mostraba además si tenía cotejo.

### Decisiones pendientes del equipo

- [ ] Confirmar que la declaración aduanera no frena y que se puede agregar después del DEX.
- [ ] Confirmar que la página pública del DEX puede mostrar el número de la declaración aduanera.
- [ ] Confirmar el 1 % de `DAM_TOLERANCIA_PESO_PCT`.
- [ ] Confirmar que el cuadro de legalidad se construye ahora, y que va en el DEX.
- [ ] Preguntar al agente de aduanas si el certificado de origen y el certificado fitosanitario se emiten siempre para el destino de la organización. Si alguno no se emite en todos los embarques, hoy ese lote no podría quedar listo, y conviene que deje de ser obligatorio.

## 12. Construcción (10 de octubre de 2026)

Registro de Claude Code. Rama `feat/adenda-7-lote`, migración 0019.

### Confirmado antes de construir

Las cuatro comprobaciones de la sección 11 y las decisiones del equipo están en el recuadro de "Antes de programar": la anulación de la declaración aduanera arrastra su archivo y la página pública muestra tres datos.

### Decisiones de construcción por confirmar

La adenda no las dice.

1. **Datos de la declaración aduanera.**
   - El número va de 5 a 30 caracteres.
   - La subpartida se escribe como figura en la declaración. Se guarda solo con sus dígitos, de 4 a 10.
   - El peso neto lleva dos decimales.
   - La entidad emisora del archivo queda SUNAT.
2. **Comparación.**
   - La diferencia en porcentaje es (declarado − masa del lote) ÷ masa del lote × 100, con dos decimales.
   - "Difiere" cuando su valor absoluto pasa de `DAM_TOLERANCIA_PESO_PCT`. Igual a la tolerancia no difiere.
   - La subpartida difiere si no empieza con la `partida_sa` de la orden.
3. **Anulación.**
   - Se anula en los mismos estados del lote en que se carga: armado, bloqueado, listo y cerrado.
   - Un archivo `dam` cargado entre las adendas 6 y 7, sin sus cuatro datos, no cuenta como declaración. Se anula solo, y la pestaña Embarque pide cargarlo de nuevo con sus datos.
4. **Alerta después del DEX.**
   - `dam_difiere_del_lote` se guarda en el lote al cargar una declaración posterior al DEX que difiere, y se audita como `lote.alerta`.
   - Como `exclusion_posterior_al_cierre`, la alerta no se borra si después se anula la declaración.
   - Aparece en la ficha del lote y en el inicio, en el grupo "Declaraciones aduaneras que difieren de su lote".
5. **Hallazgo `dam_difiere_del_lote`.**
   - Sale también en el informe preliminar, con la declaración sin anular de hoy.
   - Dice cuál difiere, con los dos valores, y que se compara con lo que escribió la persona.
6. **Cuadro.**
   - "Le aplica a" cuenta todo estado distinto de `no_aplica`, también `sin_dato`.
   - Un productor sin declaración anual vigente queda `sin_dato` en sus siete filas.
   - Daños ambientales:
     - sin incidencias ambientales, no aplica;
     - con alguna abierta, por atender;
     - con todas cerradas, con sustento, de nivel declarado (la nota de cierre).
   - Las filas de la organización toman el estado y lo que falta de los requisitos de la adenda 6. No tienen nivel.
   - La fila Aduanas está `sustentado` con una declaración sin anular (nivel documentado, o verificado en fuente si tiene cotejo), y dice su número y si difiere. Sin declaración, está `sin_sustento` y nombra lo que falta.
   - El sellado guarda los sujetos de cada fila, con su estado, su nivel, su peso y su sustento: la lista detrás de cada cuenta de un lote cerrado sale del DEX. De los productores, nombres y apellidos, nunca el DNI.
   - Con el lote cerrado, si su DEX se emitió antes de esta adenda, la ruta responde `no_disponible`.
   - En un lote en armado o anulado no hay cuadro: responde 400.
   - El nombre y el motivo de los nueve requisitos que no se piden viven en `es.json` y `en.json`. El 1.5 se escribe "Expropiación con arreglo a la ley", para no usar una palabra prohibida de la Parte 4.
7. **DEX, versión 5.**
   - El embarque lleva la declaración sin anular con sus cuatro datos y la comparación. Un archivo `dam` sin datos no va.
   - "Agregado después de la emisión" lista las declaraciones sin anular que no quedaron selladas. De un DEX anulado, solo las que se cargaron mientras estuvo vigente.
   - La página pública muestra el nombre del documento, el número, la fecha de numeración y la fecha en que se agregó.
8. **Caso de una parcela no habilitada.**
   - Dice "La parcela PA-… (nombre), de {productor}, está …".
   - Lleva `productor_id` para el enlace "Ir al productor".
   - El hallazgo `comprobacion_fallida` lo dice en los dos idiomas.
9. **Pantalla.**
   - En la pestaña Legalidad, cada sujeto de una cuenta lleva a la ficha de la parcela o a la pestaña Declaración del productor.
   - En pantallas angostas, cada fila se apila con sus cuatro cuentas.
10. **Escenario de demostración.** Carga la declaración aduanera con la masa del lote y una subpartida ficticia de la partida 1801 (`1801000000`).

### Para el equipo

1. Al desplegar, el comando de inicio de Render aplica la migración 0019. No cambia ningún lote ni ningún DEX.
2. Un archivo de declaración aduanera cargado con la adenda 6 antes de este despliegue aparece sin sus cuatro datos: se anula y se carga de nuevo.
3. Las decisiones pendientes de la sección 11.

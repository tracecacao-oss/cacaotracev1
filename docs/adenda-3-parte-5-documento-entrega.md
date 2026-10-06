# Adenda 3 a la Parte 5 — Documento de entrega en lugar de guía de remisión

Fecha: 6 de octubre de 2026. Decisión del equipo.

Esta adenda modifica la Parte 5 de `docs/especificacion.md`. Donde difiera de la especificación, manda esta adenda. Todo lo demás de la Parte 5 sigue igual.

## 1. Qué cambia y por qué

La Parte 5 exige una guía de remisión para validar una tanda. En la práctica, un productor pequeño no tiene RUC y no emite guías. El documento que sustenta la entrega lo emite casi siempre quien recibe el cacao, y cambia según el tipo de organización.

| Antes | Ahora |
| --- | --- |
| Guía de remisión obligatoria siempre | Documento de entrega obligatorio, de uno de tres tipos |
| Requisito `guia_completa` | Requisito `documento_entrega_completo` |
| Paso 3 del asistente: "Guía de remisión" | Paso 3 del asistente: "Documento de entrega" |

## 2. Los tres tipos aceptados

| Código | Documento | Quién lo emite | Cuándo corresponde |
| --- | --- | --- | --- |
| `guia_remision` | Guía de remisión | El productor, la organización que recibe o el transportista | Cuando el traslado se hizo con guía |
| `comprobante_operaciones_29972` | Comprobante de Operaciones – Ley N.º 29972 | La cooperativa agraria que recibe | Cuando una cooperativa agraria adquiere cacao de un socio |
| `liquidacion_compra` | Liquidación de compra | La organización que recibe | Cuando compra a un productor que no da comprobante por no tener RUC |

1. Basta un documento, de cualquiera de los tres tipos.
2. El sistema registra el tipo y lo muestra tal cual en la tanda, en el DOP y en el DEX. No trata a un tipo como mejor que otro.
3. Antes de fijar formatos de serie y número, confirmar en la documentación de SUNAT el formato vigente de cada tipo.

## 3. Tipo de organización

La tabla `cooperativas` gana la columna `tipo_organizacion`.

| Valor | Significado |
| --- | --- |
| `cooperativa_agraria` | Cooperativa agraria en el sentido de la Ley N.º 29972 |
| `asociacion` | Asociación de productores |
| `empresa` | Empresa acopiadora o exportadora |

1. La fija el `superadmin` al crear la organización y puede corregirla después. Es obligatoria.
2. Las organizaciones ya creadas quedan como `cooperativa_agraria` en la migración; el `superadmin` las revisa.
3. El tipo `comprobante_operaciones_29972` solo se ofrece a organizaciones de tipo `cooperativa_agraria`. Para las demás no aparece en el selector y la API lo rechaza con `tipo_no_disponible`.

## 4. Cambios en la tabla `tandas`

Las cuatro columnas de la guía se renombran y se agrega el tipo.

| Columna anterior | Columna nueva | Regla |
| --- | --- | --- |
| No existía | `doc_entrega_tipo` | Uno de los tres códigos |
| `gre_numero` | `doc_entrega_numero` | Serie y número |
| `gre_fecha_emision` | `doc_entrega_fecha_emision` | Ver sección 5 |
| `gre_ruc_emisor` | `doc_entrega_ruc_emisor` | 11 dígitos. Ver sección 5 |
| `gre_peso_kg` | `doc_entrega_peso_kg` | Peso que declara el documento. Opcional |

1. La migración renombra las columnas sin perder datos. Las tandas existentes quedan con `doc_entrega_tipo = guia_remision`.
2. El tipo de documento de archivo `guia_remision` pasa a llamarse `documento_entrega`. Los archivos ya cargados se conservan.
3. Los DOP ya emitidos no se tocan: su contenido está sellado.

## 5. Reglas por tipo

| Regla | `guia_remision` | `comprobante_operaciones_29972` | `liquidacion_compra` |
| --- | --- | --- | --- |
| RUC del emisor | Cualquiera válido | Debe ser el RUC de la organización que recibe | Debe ser el RUC de la organización que recibe |
| Fecha de emisión | No posterior a la recepción | Entre el día de la recepción y `dias_max_emision_doc_entrega` días después | Igual que el comprobante |
| Archivo del documento | Obligatorio para validar | Obligatorio para validar | Obligatorio para validar |

1. Si el RUC del emisor no cumple la regla de su tipo, la API responde 422 con `emisor_no_corresponde`.
2. `dias_max_emision_doc_entrega` es un parámetro nuevo de `configuracion_cooperativa`, con valor inicial 7. Existe porque el comprobante y la liquidación suelen emitirse después de pesar.
3. La tanda se puede registrar sin documento el día de la recepción. No se valida, ni se emite su DOP, hasta que el documento esté completo.

## 6. Requisito y alertas

### 6.1 Requisito

`documento_entrega_completo` reemplaza a `guia_completa`. Se cumple cuando la tanda tiene tipo, número, fecha, RUC del emisor y un archivo vigente, y pasa las reglas de su tipo.

### 6.2 Alertas

| Alerta anterior | Alerta nueva | Condición |
| --- | --- | --- |
| `peso_difiere_de_guia` | `peso_difiere_del_documento` | El peso del documento difiere del peso en balanza más que la tolerancia |
| `guia_usada_por_otro_productor` | `documento_usado_por_otro_productor` | El mismo tipo, número y RUC aparece en una tanda de otro productor |
| No existía | `liquidacion_con_productor_con_ruc` | El tipo es `liquidacion_compra` y la ficha del productor tiene RUC |

La tercera existe porque la liquidación de compra corresponde cuando el productor no tiene RUC. No bloquea; exige nota y llega a los hallazgos.

## 7. Pantallas

1. El paso 3 del asistente de nueva tanda se llama "Documento de entrega".
2. Empieza con un selector de tipo. Cada opción lleva una línea de ayuda que dice quién lo emite y cuándo corresponde, con el texto de la tabla de la sección 2.
3. Al elegir `comprobante_operaciones_29972` o `liquidacion_compra`, el RUC del emisor se llena solo con el de la organización y no se edita.
4. El texto de ayuda del paso dice: "Sin documento de entrega la tanda se guarda, pero no se valida."
5. En listados, detalle de tanda y documentos, la palabra "guía" se reemplaza por "documento de entrega", salvo cuando el tipo sea una guía.
6. El formulario de cooperativas del `superadmin` gana el campo "Tipo de organización".

## 8. DOP, DEX e informe de hallazgos

1. El bloque "Tanda" del contenido sellado guarda el tipo de documento de entrega junto con su número, fecha, emisor y nivel de verificación.
2. El PDF lo muestra con su nombre completo, por ejemplo "Comprobante de Operaciones – Ley N.º 29972, E001-123".
3. En la Parte 9, el hallazgo `guia_sin_cotejar` pasa a llamarse `documento_entrega_sin_cotejar`.
4. Se agrega el hallazgo `liquidacion_con_productor_con_ruc`, criterio 5, grupo Requiere atención.
5. "Datos del lote" agrega cuántas tandas del lote se sustentan con cada tipo de documento.

## 9. Pruebas mínimas

| Caso | Resultado esperado |
| --- | --- |
| Tanda con cada uno de los tres tipos, completa | Se valida y se emite el DOP |
| Tanda sin documento de entrega | Se guarda; no se valida |
| Comprobante 29972 con RUC distinto al de la organización | 422 con `emisor_no_corresponde` |
| Comprobante 29972 en una organización de tipo `asociacion` | 400 con `tipo_no_disponible` |
| Liquidación de compra emitida 3 días después de la recepción | Se acepta |
| Liquidación de compra emitida 10 días después | 422 |
| Guía de remisión con fecha posterior a la recepción | 422 |
| Liquidación de compra con productor que tiene RUC | Alerta `liquidacion_con_productor_con_ruc`; exige nota |
| Mismo documento en tandas de dos productores | Alerta `documento_usado_por_otro_productor` |
| Migración sobre tandas existentes | Conservan sus datos y quedan como `guia_remision` |
| DOP emitido antes de la migración | Su contenido y su huella no cambian |
| Textos de la interfaz | "Guía" aparece solo cuando el tipo es una guía |

## 10. Criterios de aceptación en producción

1. El paso 3 del asistente muestra el selector con los tres tipos y su ayuda.
2. En una organización de tipo asociación no aparece el comprobante de la Ley 29972.
3. Se valida una tanda con comprobante de operaciones y otra con liquidación de compra, y cada DOP muestra el tipo correcto.
4. Las tandas registradas antes del cambio siguen visibles con sus datos.

## 11. Decisiones pendientes del equipo

- [ ] Confirmar con las organizaciones del piloto, o con su contador, qué documento emiten hoy al recibir cacao. En especial, qué documento emite una cooperativa agraria al recibir cacao de un socio (sección 12).
- [ ] Confirmar los 7 días de plazo para emitir el comprobante o la liquidación después de la recepción.
- [ ] Revisar el tipo de organización de cada cooperativa ya creada.
- [ ] Para la Parte 8: decidir qué documentos legales se piden a una asociación, ya que el registro de cooperativas agrarias no le aplica.

## 12. Registro de la construcción (2026-10-06)

**Estado:** cerrada el 2026-10-06 por decisión del equipo (PR #22). El detalle de lo probado está en `CLAUDE.md`, sección "Estado por parte".

### La Ley N.° 29972 está derogada

La Segunda Disposición Complementaria Derogatoria de la Ley N.° 31335, Ley de perfeccionamiento de la asociatividad de los productores agrarios en cooperativas agrarias (El Peruano, 10/08/2021), dice: "Derógase la Ley 29972, Ley que promueve la inclusión de los productores agrarios a través de las cooperativas, y normas complementarias". El tipo `comprobante_operaciones_29972` corresponde a esa ley.

La Ley N.° 31335 regula en su lugar el Documento Acto Cooperativo (DAC), y sus reglas no calzan con las de este tipo:

- La cooperativa atribuye con él a cada socio sus ingresos por mes, no por entrega.
- Es un documento físico que autoriza la SUNAT.
- Es opcional para los socios con ingresos de hasta 140 UIT al año (artículos 28 y 43).
- El acto cooperativo no es acto de comercio y está inafecto al IGV (artículos 4 y 31).

**Decisión del equipo:** construir sin ese tipo. Hoy hay dos tipos, `guia_remision` y `liquidacion_compra`. El tipo de las cooperativas agrarias se agrega cuando el equipo confirme con su contador qué documento emite la cooperativa al recibir cacao de un socio (decisión pendiente 1 de la sección 11). Mientras tanto no se usan:

- el error `tipo_no_disponible` (3, regla 3);
- la regla del RUC de la organización para ese tipo (5).

### Serie y número de la liquidación de compra

Antes de fijar el formato se consultó la documentación de SUNAT (2, regla 3):

- **Cuándo se emite:** Reglamento de Comprobantes de Pago, artículo 6, inciso 1.3, con el texto de la RS 244-2019/SUNAT. La emite quien adquiere productos primarios agropecuarios a personas naturales que no otorgan comprobante por carecer de RUC, hasta 75 UIT de ventas al año por vendedor. Es electrónica. En formato impreso solo se emite en contingencia o en zonas con baja o nula conexión a internet.
- **Serie electrónica:** Anexo N.° 27 de la RS 097-2012/SUNAT, con el texto de la RS 123-2022/SUNAT. La serie tiene 4 caracteres alfanuméricos y empieza con "L" (ejemplo L001). El correlativo tiene hasta 8 dígitos y empieza en 1. En el SEE-SOL la serie es E001.
- **Serie impresa:** Reglamento de Comprobantes de Pago, artículo 9.4. La serie del comprobante impreso tiene 3 dígitos y el correlativo 7. Como en la guía, también se aceptan series numéricas de 4 dígitos.

El catálogo de los tipos, con sus fuentes, está en `backend/app/catalogos/documento_entrega.py`.

### Lo construido, además de lo que dicen las secciones 3 a 8

- **Migración 0008.**
  - Agrega `cooperativas.tipo_organizacion`: obligatoria y sin valor por defecto; las organizaciones ya creadas quedan como `cooperativa_agraria`.
  - Renombra las cuatro columnas de la guía y agrega `doc_entrega_tipo`; todas las tandas existentes quedan como `guia_remision`.
  - Cambia el tipo de documento `guia_remision` a `documento_entrega`.
  - Agrega `configuracion_cooperativa.dias_max_emision_doc_entrega` = 7.
  - Ningún dato se pierde. Se comprobó en la base local de la interfaz: las 5 tandas existentes conservan sus datos, sus 4 archivos siguen ahí y las huellas de los 4 DOP siguen cuadrando.
- **Errores nuevos de la API:**
  - `documento_tipo_requerido`: hay datos del documento sin su tipo.
  - `documento_numero_invalido`: serie o número fuera del formato de su tipo.
  - `documento_fecha_invalida`: fecha fuera de la regla de su tipo.
  - `fecha_futura`: fecha de emisión posterior a hoy.
  - `emisor_no_corresponde`: la liquidación lleva un RUC que no es el de la organización.
- **RUC de la liquidación:** si falta, la API lo llena con el de la organización. La interfaz lo muestra lleno y sin poder editarse.
- **Requisito `documento_entrega_completo`:** al evaluar la tanda se vuelven a revisar las reglas de su tipo, porque el plazo de la configuración o el RUC pueden haber cambiado desde el registro.
- **Nombre de la tolerancia:** la columna `tolerancia_peso_guia_pct` conserva su nombre; la pantalla la llama tolerancia del documento de entrega.
- **DOP:** el contenido sellado pasa a la versión 3, con el bloque `documento_entrega`. Los DOP emitidos antes conservan el bloque `guia_remision`, y la pantalla y el PDF los siguen mostrando.
- **"No verificado" del DOP:** para la liquidación de compra, dice que no se cotejó con SUNAT.
- **Pendiente para la Parte 9:** los cambios de la sección 8, reglas 3 a 5 (hallazgos y "Datos del lote"), se aplican cuando se construya esa parte.


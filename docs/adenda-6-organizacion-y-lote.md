# Adenda 6 — Organización, diligencia y aduanas (Partes 8 y 9)

Fecha: 9 de octubre de 2026.

Esta adenda modifica lo que `docs/especificacion.md` pide a la organización y al lote: el expediente legal de la organización y los documentos de embarque (Parte 8), y lo que de ellos llega a los hallazgos y al DEX (Parte 9). Donde difiera de la especificación o de las adendas anteriores, manda esta adenda.

Se construye después de las adendas 4 y 5. Usa el perfil legal de la parcela, la declaración del productor, el tema 11 del artículo 10 y los estados de requisito que ellas definen.

No cambia las otras comprobaciones del lote (parcelas, DOP, DPP, genealogía, datos de la organización e importador), las certificaciones, el análisis de cobertura forestal ni la regla que decide cuándo salta una alerta. Los nombres de tablas, rutas y servicios que hoy dicen `cooperativa` no se renombran.

La fuente es el "Documento orientador para la diligencia debida de la legalidad del café y cacao en el marco del EUDR" (MIDAGRI, MINCETUR y ADEX; European Forest Institute, 2026). En adelante, "el orientador". El propio documento dice que no es jurídicamente vinculante ni asesoría legal.

Decisión del equipo del 9 de octubre de 2026: la organización sigue lo que dice el orientador, y solo frena lo básico. Las decisiones propias de esta adenda están en la sección 14 y esperan confirmación.

## 1. Qué cambia y por qué

Hoy toda organización tiene las mismas seis casillas y las seis deben estar vigentes para que un lote quede listo, sea cooperativa, asociación o empresa. Dos de esas casillas piden un registro de exportadores que no existe. Y el sistema no guarda nada de lo que el orientador más pide a la organización: sus reglas de integridad y lo que hace en su zona.

| Antes | Ahora |
| --- | --- |
| Seis casillas iguales para todas | Cada organización ve lo que le toca según su `tipo_organizacion` |
| Las seis frenan el lote | Frena la identidad: ficha RUC, partida registral y vigencia de poderes |
| `rnca` para todas | `rnca` solo para la cooperativa agraria, y no frena |
| `ruc_comercio_exterior` y `registro_aduanas` | Salen. Lo aduanero se sustenta con la declaración aduanera de cada lote |
| Nada sobre integridad | Una política que cubre cinco temas, con plantilla para firmar |
| Nada sobre lo que la organización hace | Registro de actuaciones de diligencia, con un cuadro que dice dónde hacen falta |
| Cuatro documentos de embarque | Los mismos cuatro, más la declaración aduanera, que no frena |

## 2. Qué pide el orientador a la organización y al lote

La numeración es la del Anexo 2 del orientador.

| Ref. | Requisito | Nivel y diligencia | Qué pide el orientador | Cómo se cubre aquí |
| --- | --- | --- | --- | --- |
| 7.1 | Paga los tributos de su régimen | Alto, aligerada | La declaración jurada del impuesto a la renta, revisada con la consulta del RUC | Ficha RUC comparada con la consulta de SUNAT, y declaración anual de renta |
| 7.2 | El exportador cumple las formalidades aduaneras | Alto, aligerada | La Declaración Aduanera de Mercancías, o su consulta pública por número. Los permisos previos van por la VUCE | `dam` en cada lote. De los permisos previos ya se pide el certificado fitosanitario |
| 7.3 | Sin corrupción, fraude ni conflicto de intereses | Bajo, estándar | Políticas de integridad, capacitación en ética, verificación de la autenticidad de los documentos, canal de denuncias, código de conducta y política de no fraude | Política con cinco temas y actuaciones de tipo capacitación |
| 5.5 y 4.6 | Sin acoso; igualdad | Según el requisito | Canales confidenciales de queja y campañas, de manera gradual | Tema `canal_denuncias` de la política, con su contacto |
| 2.3 y 2.7 | Agroquímicos y envases | Bajo, estándar | Entregar a los productores la lista de productos registrados, capacitarlos y verificar por muestreo | Lista que arma el sistema y actuaciones |
| 1.1 a 1.4 | Tenencia | Alto, aligerada | Consultar si hay conflictos de tierras con autoridades locales, Defensoría del Pueblo y prensa | Actuaciones |
| 2.1, 2.2 | Áreas protegidas y tierra forestal | Alto y bajo | Consultar a actores locales; apoyar a los productores a obtener su acuerdo o su CCUSAF | Actuaciones |
| 4.1 a 4.7 y 5.2 a 5.4 | Trabajo y derechos humanos | Según el requisito | Política laboral, capacitaciones documentadas, campañas y auditorías de campo por muestreo | Tema `trabajo_digno` de la política y actuaciones |

El orientador agrupa lo que recomienda en cinco familias: análisis cartográfico, recopilación y verificación de documentos, consultas con partes interesadas, implementación de procedimientos y verificación en campo. Las dos primeras ya están en las adendas 4 y 5. Las otras tres son trabajo de la organización, y el orientador pide dejarlas anotadas en un "registro de actuaciones de diligencia debida".

### Regla de efecto

Un lote no queda listo por causa de la organización solo si le falta la identidad: ficha RUC, partida registral o vigencia de poderes.

Todo lo demás de esta adenda no bloquea. Se muestra y llega al informe de hallazgos.

El sistema sigue sin concluir. Ningún texto dice que una organización "cumple": dice qué documentos tiene, qué temas cubre su política y qué actuaciones registró.

## 3. Requisitos de la organización y del lote

El catálogo vive en `backend/app/catalogos/requisitos_organizacion.py`.

| Código | Ref. | Nivel y diligencia | Aplica cuando | Sustento | Bloquea |
| --- | --- | --- | --- | --- | --- |
| `identidad` | Base | — | Siempre | `ficha_ruc`, `partida_sunarp` y `vigencia_poderes`, los tres | Sí |
| `tributos` | 7.1 | Alto, aligerada | Siempre | `ficha_ruc` y `renta_anual` | No |
| `registro_cooperativas` | 7.1 | Alto, aligerada | `tipo_organizacion = cooperativa_agraria` | `rnca` | No |
| `integridad` | 7.3, 5.5 | Bajo, estándar | Siempre | Política que cubra los cinco temas de la sección 5 | No |
| `actuaciones` | Varios | — | Siempre | Una actuación vigente por cada tema esperado, sección 6 | No |
| `aduanas` | 7.2 | Alto, aligerada | Cada lote | `dam` | No |

Estados: `no_aplica`, `sustentado`, `por_vencer`, `vencido` y `sin_sustento`, con el significado de la adenda 4. Un requisito con varios sustentos está `sustentado` solo cuando los tiene todos.

## 4. Expediente de la organización

`TIPOS_COOPERATIVA` se reemplaza por este catálogo. Cada tipo dice a qué `tipo_organizacion` aplica y si es de identidad.

| Código | Documento | Aplica a | Identidad | Registro consultable |
| --- | --- | --- | --- | --- |
| `ficha_ruc` | Ficha RUC de SUNAT | Todas | Sí | Sí |
| `partida_sunarp` | Partida registral de la organización en SUNARP | Todas | Sí | Sí |
| `vigencia_poderes` | Vigencia de poderes del representante legal (SUNARP) | Todas | Sí | Sí |
| `renta_anual` | Declaración jurada anual del impuesto a la renta, o constancia de haberla presentado | Todas | No | No |
| `rnca` | Constancia de inscripción en el Registro Nacional de Cooperativas Agrarias (MIDAGRI) | Solo `cooperativa_agraria` | No | No (sección 14) |

1. La comprobación `expediente_cooperativa_completo` pasa cuando los tres documentos de identidad están `vigente` o `por_vencer`. Su nombre en pantalla pasa a ser "Identidad de la organización".
2. `renta_anual` exige la fecha de presentación como fecha de emisión. Vence sola a los `RENTA_VIGENCIA_MESES` de esa fecha, con valor inicial 18.
3. `rnca` se mantiene, aunque el orientador no lo nombra, porque de esa inscripción dependen los beneficios de la Ley N.º 31335, que el orientador sí cita al explicar los tributos. No frena, por decisión del equipo del 9 de octubre de 2026 (sección 14), aunque la ley hace obligatoria la inscripción: su falta se muestra y llega al informe de hallazgos.
4. `ruc_comercio_exterior` y `registro_aduanas` salen del catálogo. SUNAT pide para exportar tener RUC y no tener la condición de no habido; no hay un registro aparte de exportadores. Los archivos ya cargados se conservan y se ven como "documentos anteriores". No se pueden cargar nuevos.
5. Un `rnca` cargado por una organización que no es cooperativa agraria también pasa a "documentos anteriores".
6. Los tres documentos de identidad admiten cotejo en fuente, como hoy. La pantalla enlaza la consulta del RUC que nombra el orientador: `https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp`.
7. Al cotejar la ficha RUC, la nota dice el estado y la condición que muestra SUNAT. El sistema no consulta esa página: la comparación la hace una persona.
8. Los cargan y los anulan solo un `admin_cooperativa`, como hoy.

## 5. Política de la organización

El orientador pide a la organización varios documentos de conducta. En vez de una casilla por documento, la organización carga su política y marca qué temas cubre. Puede ser un documento o varios.

| Tema | Qué debe decir | Ref. |
| --- | --- | --- |
| `integridad` | Que nadie da ni recibe pagos indebidos, y cómo se manejan los conflictos de interés | 7.3 |
| `no_fraude` | Que no se alteran pesos, calidades, orígenes ni documentos, y que no se mezcla cacao de origen desconocido | 7.3 |
| `canal_denuncias` | Cómo se presenta una queja o una denuncia, quién la recibe, que es confidencial y que no hay represalias | 7.3, 5.3 a 5.5 |
| `trabajo_digno` | Sin menores de 18 años, trabajo libre, igualdad, sin acoso, y seguridad en el trabajo | 4.1 a 4.7, 5.2 a 5.5 |
| `revision_de_documentos` | Cómo comprueba la organización que los documentos que recibe son auténticos | 7.3 |

1. Un tema está `sustentado` cuando al menos una política vigente lo cubre.
2. `canal_denuncias` necesita además el contacto del canal escrito en los datos de la organización: `canal_denuncias_contacto`, un texto de hasta 200 caracteres con un teléfono, un correo o la ubicación de un buzón.
3. El requisito `integridad` está `sustentado` cuando los cinco temas lo están.
4. Las políticas no vencen. Se muestra su fecha de adopción.
5. Quien carga la política marca los temas. El sistema no lee el archivo.

### Plantilla para firmar

1. `GET /cooperativa/politica/hoja` devuelve un PDF con el texto del Anexo A y los datos de la organización ya escritos: razón social, RUC, tipo y contacto del canal.
2. El PDF se arma con fpdf2 en `backend/app/pdf/politica_organizacion.py`. El texto vive en un archivo de textos con su número de versión, junto a los de las adendas 4 y 5. El PDF imprime la versión al pie.
3. El órgano de dirección que el PDF sugiere depende del tipo: Consejo de Administración en una cooperativa agraria, Consejo Directivo en una asociación, y Directorio o Gerencia General en una empresa.
4. La organización la firma y la carga marcando los cinco temas. La plantilla no se guarda como documento; la que cuenta es la firmada.
5. Si falta `canal_denuncias_contacto`, la pantalla lo pide antes de descargar.
6. En una organización de demostración, la hoja lleva la misma marca de agua que los demás PDF.

### Tabla `politicas_organizacion`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Organización |
| `documento_id` | uuid | El archivo, de tipo `politica_organizacion` |
| `temas` | text[] | Uno o más de los cinco temas |
| `adoptada_en` | date | Fecha en que el órgano de dirección la adoptó. No futura |
| `organo` | text | Quién la adoptó |
| `version_plantilla` | integer | Versión del Anexo A, si se usó la plantilla. Nulo si es un documento propio |
| `registrada_por`, `registrada_en` | uuid, timestamptz | Quién la cargó y cuándo |
| `anulada_en`, `anulada_por`, `motivo_anulacion` | timestamptz, uuid, text | No se borra: se anula con motivo |

### El contacto del canal llega al productor

1. "Mi perfil" del productor muestra "Quejas y denuncias" con el contacto del canal de su organización.
2. La hoja de la declaración anual del productor, de la adenda 5, imprime ese contacto antes de la firma.
3. El sistema no recibe ni guarda denuncias. Solo muestra a dónde llevarlas.

## 6. Actuaciones de diligencia

Una actuación es algo que la organización hizo para conocer o reducir un riesgo de legalidad en su zona. Cada una es una ficha corta.

### 6.1 Tipos

| Código | Qué es | Ejemplos del orientador |
| --- | --- | --- |
| `revision_de_fuente_publica` | Revisar una fuente pública | La lista de sancionados de OEFA; los reportes de conflictos de la Defensoría del Pueblo; la Base de Datos de Pueblos Indígenas |
| `consulta_a_partes_interesadas` | Preguntar a alguien de la zona | Municipalidad, agencia agraria, autoridades de una comunidad, vendedores de agroquímicos, organizaciones locales |
| `capacitacion` | Capacitación o campaña a productores o al personal | Equipo de protección y envases; derechos básicos de los trabajadores; ética y revisión de documentos |
| `verificacion_en_campo` | Visita a una muestra de productores | Qué productos usan, dónde dejan los envases, quiénes trabajan |
| `apoyo_a_productores` | Ayuda para regularizar algo | Tramitar una constancia de posesión, un CCUSAF, un acuerdo de conservación o una licencia de agua |

`verificacion_en_campo` no es la visita que la adenda 2 retiró. No atiende alertas de cobertura forestal ni cuenta para habilitar una parcela.

### 6.2 Temas y cuándo se espera una actuación

| Tema | Ref. | Diligencia | Señal que hace esperar una actuación |
| --- | --- | --- | --- |
| `integridad` | 7.3 | Estándar | Siempre |
| `tierra_forestal` | 2.2, 2.10, 2.11 | Estándar | Alguna parcela activa con `en_tierra_forestal = si` |
| `agroquimicos_y_envases` | 2.3, 2.7 | Estándar | Algún productor con `usa_agroquimicos = si` |
| `trabajo` | 4.1 a 4.7 | Estándar | Algún productor que contrata trabajadores |
| `tenencia` | 1.1 a 1.4 | Aligerada | Alguna incidencia de tenencia registrada en los últimos 12 meses |
| `areas_protegidas` | 2.1, 2.13 | Aligerada | Alguna parcela activa con `en_anp` distinto de `no` |
| `agua` | 2.4, 2.5 | Aligerada | Alguna parcela activa con `agua_de_riego` sin sustento o con `junto_a_cuerpo_de_agua = si` |
| `derechos_humanos` | 5.2 a 5.5 | Aligerada | Algún productor con `menores_de_edad` o `trabajo_libre` en `por_atender` |

1. La regla sigue al orientador. Con diligencia estándar se espera actuar siempre que la organización esté expuesta. Con diligencia aligerada, solo cuando salta un caso.
2. Las señales se cuentan sobre todos los productores y las parcelas activas de la organización, con el estado de hoy.
3. Una actuación cuenta para sus temas durante `ACTUACION_VIGENCIA_MESES` desde su fecha, con valor inicial 12.
4. El requisito `actuaciones` está `sustentado` cuando cada tema esperado tiene al menos una actuación vigente. Si no, está `sin_sustento` y dice qué temas faltan.
5. El catálogo de tipos, temas y fuentes sugeridas vive en `backend/app/catalogos/actuaciones.py`.

### 6.3 Cuadro de señales

`GET /cooperativa/diligencia` devuelve, por cada tema: la señal con su cuenta, si se espera una actuación, cuántas actuaciones vigentes hay y la fecha de la última.

La cuenta dice lo que hay detrás. Ejemplos: "32 productores declaran que queman o entierran envases", "5 parcelas en tierra forestal", "2 productores declaran menores de 18 años".

### 6.4 Fuentes sugeridas

Al registrar una `revision_de_fuente_publica`, el formulario sugiere las fuentes que nombra el orientador. Solo llevan enlace las que el orientador da con dirección.

| Fuente | Temas | Enlace |
| --- | --- | --- |
| OEFA, administrados sancionados | `agroquimicos_y_envases`, `agua` | `https://publico.oefa.gob.pe/administrados-sancionados/#/` |
| Base de Datos de Pueblos Indígenas u Originarios, Ministerio de Cultura | `tenencia` | `https://bdpi.cultura.gob.pe/buscador-de-localidades-de-pueblos-indigenas` |
| Defensoría del Pueblo, reportes de conflictos sociales | `tenencia`, `areas_protegidas` | Sin enlace |
| SUNAFIL, información pública de inspecciones y sanciones | `trabajo`, `derechos_humanos` | Sin enlace |
| Ministerio de la Mujer y Poblaciones Vulnerables, Programa Aurora | `derechos_humanos` | Sin enlace |
| Prensa y organizaciones de la sociedad civil | Todos | Sin enlace |

### 6.5 Tabla `actuaciones_diligencia`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Organización |
| `tipo` | text | Uno de los cinco tipos |
| `temas` | text[] | Uno o más de los ocho temas |
| `fecha` | date | Día en que se hizo. No futura |
| `descripcion` | text | Qué se hizo. Mínimo 50 caracteres |
| `contraparte` | text | La fuente revisada o con quién se habló. Obligatoria en los dos primeros tipos |
| `resultado` | text | Qué se encontró o qué se acordó. Mínimo 20 caracteres |
| `participantes` | integer | Cuántas personas, en una capacitación. Opcional |
| `departamento`, `provincia`, `distrito` | text | Dónde. Opcionales, del catálogo del INEI |
| `registrada_por`, `registrada_en` | uuid, timestamptz | Quién la registró y cuándo |
| `anulada_en`, `anulada_por`, `motivo_anulacion` | timestamptz, uuid, text | No se edita ni se borra: se anula con motivo |

1. La tabla `actuacion_productores` une una actuación con los productores que alcanzó. Es opcional. La pantalla permite buscarlos y marcarlos.
2. La evidencia son documentos de tipo `evidencia_actuacion`, de la entidad nueva `actuacion`: lista de asistencia, foto, captura de pantalla o informe. Se pueden agregar después.
3. El nivel de verificación de una actuación es `declarado` sin evidencia y `documentado` con ella.
4. Registran el `admin_cooperativa` y el `operador`. Anula solo el `admin_cooperativa`.
5. La evidencia no sale del sistema. El DEX dice si existe, no la incluye: una lista de asistencia tiene nombres y DNI.

### 6.6 Lista de productos buscados en SENASA

El orientador pide dar a los productores la lista de productos registrados y no registrados. La organización ya la tiene: son las revisiones que el personal hizo en las declaraciones de la adenda 5.

1. `GET /cooperativa/productos-revisados` devuelve cada producto declarado en una declaración vigente: nombre, tipo, su revisión más reciente con su fecha y su número de registro, y cuántos productores lo declaran.
2. `GET /cooperativa/productos-revisados/hoja` devuelve un PDF para repartir, con dos grupos: los que figuran y los que no figuran en el registro de SENASA. Lleva la fecha, las dos direcciones de consulta de SENASA y la leyenda "Esta lista no reemplaza la consulta del registro".
3. El texto no usa "autorizado" ni "prohibido", como en la adenda 5.

## 7. El lote: declaración aduanera

1. El catálogo de documentos de embarque suma `dam`, "Declaración Aduanera de Mercancías", con emisor habitual "SUNAT". Cada tipo del catálogo dice ahora si es obligatorio. Los cuatro de hoy lo son; `dam` no.
2. `documentos_embarque_completos` mira solo los obligatorios. El lote puede quedar listo y el DEX puede emitirse sin `dam`.
3. `dam` exige número y fecha de numeración.
4. Admite cotejo en fuente. La pantalla enlaza las dos consultas que nombra el orientador: `https://ww3.sunat.gob.pe/aduanas/informli/ildua.htm` y `http://www.aduanet.gob.pe/aduanas/informgest/ExpoDef.htm`.
5. Si al emitir el DEX el lote no tiene `dam`, recibe el hallazgo `lote_sin_dam`.
6. `dam` es el único documento que se puede cargar con el lote `cerrado`. El DEX emitido no cambia: su contenido y su huella son los mismos.
7. La verificación pública del DEX suma el bloque "Agregado después de la emisión", con el número de la declaración aduanera, su fecha de numeración, la fecha en que se cargó y si tiene cotejo. La pestaña DEX del lote muestra lo mismo.
8. El requisito 7.2 también habla de los permisos previos que se tramitan por la VUCE. De ellos, el sistema ya pide el certificado fitosanitario, que es uno de los cuatro documentos obligatorios.

## 8. Comprobaciones del lote

| Comprobación | Hoy | Con esta adenda |
| --- | --- | --- |
| `expediente_cooperativa_completo` | Las seis casillas | Los tres documentos de identidad |
| `documentos_embarque_completos` | Los cuatro documentos | Los cuatro documentos obligatorios |
| Las otras siete | — | No cambian |

Un lote que hoy está `bloqueado` solo por `rnca`, `ruc_comercio_exterior` o `registro_aduanas` deja de estarlo en la siguiente recomprobación. Ningún lote pasa a `bloqueado` por esta adenda.

## 9. Rutas

| Ruta | Quién | Qué hace |
| --- | --- | --- |
| `GET /cooperativa/expediente` | Personal | Ya existe. Devuelve los documentos que aplican, los requisitos de la sección 3 y los "documentos anteriores" |
| `POST /cooperativa/documentos` | `admin_cooperativa` | Ya existe. Acepta `renta_anual` y deja de aceptar los dos tipos que salen |
| `PATCH /cooperativa` | `admin_cooperativa` | Ya existe. Acepta `canal_denuncias_contacto` |
| `GET /cooperativa/politica/hoja` | `admin_cooperativa` | La plantilla para firmar |
| `GET /cooperativa/politicas` | Personal | Las políticas cargadas y el estado de cada tema |
| `POST /cooperativa/politicas` | `admin_cooperativa` | Carga una política con sus temas, su fecha de adopción y su órgano |
| `POST /cooperativa/politicas/{politica_id}/anular` | `admin_cooperativa` | La anula, con motivo |
| `GET /cooperativa/diligencia` | Personal | El cuadro de señales y el requisito `actuaciones` |
| `GET /actuaciones` | Personal | Lista, con filtros por tipo, tema y fechas |
| `POST /actuaciones` | `admin_cooperativa`, `operador` | Registra una actuación |
| `GET /actuaciones/{actuacion_id}` | Personal | Su ficha, sus productores y su evidencia |
| `POST /actuaciones/{actuacion_id}/evidencias` | `admin_cooperativa`, `operador` | Carga un archivo de evidencia |
| `POST /actuaciones/{actuacion_id}/anular` | `admin_cooperativa` | La anula, con motivo |
| `GET /cooperativa/productos-revisados` | Personal | La lista de la sección 6.6 |
| `GET /cooperativa/productos-revisados/hoja` | Personal | El PDF para repartir |
| `POST /lotes/{lote_id}/documentos` | Como hoy | Ya existe. Acepta `dam`, también con el lote `cerrado` |

Otra organización recibe 404 en políticas, actuaciones y evidencias que no son suyas.

## 10. Pantallas

### Organización

1. "Datos y expediente legal" se ordena en tres bloques: Identidad, Tributos y registro, y Política. Cada documento dice si frena un lote.
2. Los documentos que no aplican al tipo de organización no aparecen. Los anteriores van al final, plegados.
3. El bloque Política muestra los cinco temas con su estado, las políticas cargadas, el botón "Descargar política para firmar" y el campo del contacto del canal.
4. Al cargar una política, el formulario pide marcar los temas, la fecha de adopción y el órgano.
5. La barra lateral de la organización suma "Diligencia", en `#/cooperativa/diligencia`. Arriba va el cuadro de señales, con un botón "Registrar actuación" en cada tema. Debajo, la lista de actuaciones. A un lado, "Descargar lista de productos".
6. El formulario de una actuación pide tipo, temas, fecha, descripción, resultado y, según el tipo, la fuente o la contraparte. Lo demás es opcional. Cabe en una pantalla de celular.
7. La ficha de un productor muestra las actuaciones que lo alcanzaron.

### Lote

1. La pestaña Embarque muestra `dam` después de los cuatro obligatorios, con la etiqueta "No frena el lote".
2. Con el lote `cerrado`, la pestaña ofrece "Agregar la declaración aduanera".

### Productor

"Mi perfil" muestra el contacto del canal de quejas y denuncias de su organización.

## 11. DEX e informe de hallazgos

### DEX

1. El contenido del DEX suma el bloque `organizacion`: los documentos del expediente con su estado y su nivel, los cinco temas de la política con la fecha de adopción, si hay contacto del canal, el cuadro de señales y las actuaciones vigentes.
2. El PDF suma la sección "La organización y su diligencia", después de "Declaraciones de los productores". De cada actuación muestra fecha, tipo, temas, descripción, resultado y nivel. No muestra la evidencia ni los nombres de los productores alcanzados.
3. Si el lote tiene `dam` al emitir, su número y su fecha van con los documentos de embarque.
4. La descripción y el resultado de una actuación son palabras de la organización. El DEX las presenta así, como hoy las notas de las personas.

### Hallazgos nuevos

Son de la etapa 3. Su sujeto es la organización, salvo `lote_sin_dam`, que es del lote. Todos van a No verificado: son documentos o registros que faltan.

| Código | Se genera cuando | Tema |
| --- | --- | --- |
| `tributos_organizacion_sin_sustento` | No hay `renta_anual` vigente | 11 |
| `registro_cooperativas_sin_sustento` | Es cooperativa agraria y no hay `rnca` vigente | 11 |
| `politica_incompleta` | Algún tema de la política no está sustentado. Lista cuáles | 5 |
| `sin_actuaciones_de_diligencia` | Algún tema esperado no tiene una actuación vigente. Lista cada tema con su señal | 11 |
| `lote_sin_dam` | El lote no tiene `dam` al emitir el DEX | 11 |

1. `documento_sin_cotejar`, `documento_por_vencer` y `comprobacion_fallida` siguen como hoy para los documentos de la organización.
2. Los hallazgos del productor de la adenda 5 suman en sus datos las actuaciones vigentes que lo alcanzaron, con su fecha y su tipo. Se muestran junto a la nota de seguimiento.
3. Los textos van en `es.json` y `en.json`, con las mismas claves.

## 12. Datos y migración

1. Tablas nuevas: `politicas_organizacion`, `actuaciones_diligencia` y `actuacion_productores`. Las tres con RLS activado y sin políticas.
2. `cooperativas` suma `canal_denuncias_contacto`.
3. Tipos de documento nuevos: `renta_anual`, `politica_organizacion`, `evidencia_actuacion` y `dam`. Entidad de documento nueva: `actuacion`.
4. Variables nuevas del backend: `RENTA_VIGENCIA_MESES`, con valor inicial 18, y `ACTUACION_VIGENCIA_MESES`, con valor inicial 12.
5. Servicios nuevos: `backend/app/services/diligencia.py`, con las políticas, las actuaciones, las señales y la lista de productos. `services/cooperativa.py` conserva el expediente y aplica el catálogo nuevo.
6. Cada acción audita en la misma transacción.
7. La migración no borra archivos ni inventa valores. Ninguna organización recibe una política ni una actuación por defecto.
8. `CLAUDE.md` nombra esta adenda y sus convenciones.

## 13. Pruebas mínimas y aceptación

### Pruebas automáticas

| Caso | Resultado esperado |
| --- | --- |
| Asociación con ficha RUC, partida y poderes vigentes, sin nada más | `expediente_cooperativa_completo` pasa; el lote puede quedar listo |
| Cualquier organización sin vigencia de poderes | La comprobación falla; el lote queda `bloqueado` |
| Cooperativa agraria sin `rnca` | El lote puede quedar listo; hallazgo `registro_cooperativas_sin_sustento` |
| Asociación o empresa | `registro_cooperativas` no aplica; `rnca` no aparece |
| Cargar `ruc_comercio_exterior` | 422 |
| Organización con `ruc_comercio_exterior` cargado antes | Se ve en "documentos anteriores"; no cuenta para nada |
| Lote `bloqueado` solo por `registro_aduanas` | Pasa a `listo` en la siguiente recomprobación |
| Sin `renta_anual` | Hallazgo `tributos_organizacion_sin_sustento`; no bloquea |
| `renta_anual` presentada hace 19 meses | `vencido` |
| Política que marca tres temas | `integridad` `sin_sustento`; `politica_incompleta` lista los dos que faltan |
| Dos políticas que juntas cubren los cinco temas | `integridad` `sustentado` |
| Cinco temas cubiertos y sin contacto del canal | `canal_denuncias` sin sustento |
| Política anulada | Sus temas dejan de contar |
| Plantilla de la política | El PDF trae la razón social, el RUC, el órgano sugerido según el tipo y el contacto del canal |
| Un productor con `usa_agroquimicos = si` y ninguna actuación | `agroquimicos_y_envases` esperado; `sin_actuaciones_de_diligencia` lo lista |
| Ningún productor contrata | `trabajo` no se espera |
| Ninguna parcela en área protegida | `areas_protegidas` no se espera |
| Un productor con `menores_de_edad` `por_atender` | `derechos_humanos` esperado |
| Actuación de hace 13 meses | No cuenta |
| Actuación sin `contraparte` de tipo `consulta_a_partes_interesadas` | 422 |
| Actuación con evidencia | Nivel `documentado` |
| Actuación que alcanza a un productor | Aparece en su ficha y en los datos de sus hallazgos |
| Actuación anulada | Deja de contar; se conserva |
| Lista de productos | Trae cada producto una vez, con su revisión más reciente |
| Lote sin `dam` | Puede quedar listo; al emitir, hallazgo `lote_sin_dam` |
| `dam` cargada con el lote `cerrado` | Se acepta; el contenido y la huella del DEX no cambian; la verificación pública la muestra aparte |
| Factura comercial cargada con el lote `cerrado` | 400, como hoy |
| Textos | Los textos nuevos de pantalla, de los PDF y de los hallazgos no usan las palabras prohibidas de la Parte 4. Tampoco dicen que una organización cumple o incumple |
| DEX emitido antes de la migración | Su contenido y su huella no cambian |
| Aislamiento | Otra organización recibe 404 en políticas, actuaciones y evidencias |
| Permisos | El `operador` registra actuaciones y no carga políticas; el `lector` solo ve |

### Criterios de aceptación en producción

1. Una asociación ve tres documentos de identidad y no ve el registro de cooperativas.
2. La organización escribe el contacto de su canal, descarga la política con sus datos, la carga firmada con los cinco temas, y el productor ve el contacto en su cuenta.
3. El cuadro de señales muestra, sin que nadie lo escriba, cuántos productores usan agroquímicos y cuántos contratan trabajadores.
4. El personal registra una capacitación desde el celular, con su foto, y el tema deja de aparecer como pendiente.
5. La lista de productos se descarga con los productos que el personal ya buscó en SENASA.
6. Un DEX nuevo trae la sección "La organización y su diligencia".
7. A un lote cerrado se le agrega la declaración aduanera y la página pública de su DEX la muestra aparte.

## 14. Lecturas del orientador y decisiones pendientes

### Diferencias y vacíos del orientador

| Punto | Qué dice | Cómo se tomó aquí |
| --- | --- | --- |
| 7.1, de quién es | La tabla principal dice "El exportador"; el Anexo 2, "El productor" | Aquí, la parte del exportador. La del productor está en la adenda 5 |
| 7.1, cooperativas | El Anexo 2 describe la retención de 1,5 % que la cooperativa hace a sus socios entre 30 y 140 UIT | No se pide un documento aparte. Queda dentro de la declaración anual de renta |
| 7.3, documentos | Lista "código de conducta de la empresa proveedora" y "código de conducta del proveedor" | Un solo tema, `integridad` |
| Registro de actuaciones | Lo nombra una vez y no dice qué debe contener | Los campos de la sección 6.5 |
| Partida registral y poderes | No los nombra | Se mantienen como identidad: el DEX nombra al exportador y a su representante |
| Registro de cooperativas | No lo nombra | Se mantiene para cooperativas y no frena |
| 5.5 | Pide canales de queja "de manera gradual y proporcional al contexto" | Un tema de la política y un contacto. No frena |

### Antes de programar

1. Claude Code confirma en la orientación aduanera de SUNAT (`https://www.sunat.gob.pe/orientacionaduanera/exportacion/requisitos.html`) que para exportar se pide RUC sin la condición de no habido, y que no hay otro registro. Si encuentra otra cosa, se detiene y pregunta.
2. Claude Code lee la Ley N.º 31335 y el Decreto Supremo N.º 023-2021-MIDAGRI. Confirma qué documento recibe una cooperativa inscrita en el registro y si hay una lista pública de inscritas. Con eso fija el nombre de `rnca` y su "registro consultable".
3. Claude Code busca en los instructivos de SUNAT el formato del número de la declaración aduanera. Si lo confirma, lo valida. Si no, lo deja como texto de 5 a 30 caracteres.
4. Claude Code confirma que las dos direcciones de consulta de la declaración aduanera y la de la consulta del RUC responden.
5. Claude Code revisa si el mecanismo de cotejo de la Parte 4 sirve tal cual para `dam`, que no es un documento del expediente legal. Si no, se detiene y pregunta.

> **Lectura de las fuentes y decisiones del equipo del 9 de octubre de 2026.**
> 1. **SUNAT, requisitos del exportador.** La orientación aduanera pide "Número del Registro único de contribuyente (RUC) y no tener la condición de no habido", y el mandato al agente de aduana. No nombra otro registro de exportadores. Coincide con la sección 4, regla 4.
> 2. **Ley N.º 31335 y Decreto Supremo N.º 023-2021-MIDAGRI.**
>    - Al aprobar la inscripción, la autoridad emite una Resolución Directoral y entrega la "Constancia de Inscripción" (art. 13.4 del reglamento). Esa constancia es el único requisito previo para los beneficios de la ley (art. 13.8). El nombre de `rnca` queda como está.
>    - El reglamento dice que la información del registro "puede ser consultada por los ciudadanos" por los medios digitales que el MIDAGRI habilite (art. 5). No se encontró una consulta en línea: `rnca` queda sin registro consultable.
>    - La inscripción es obligatoria (art. 8.1). El artículo 26 de la ley dice que solo las cooperativas inscritas pueden usar la denominación de cooperativa agraria y operar al amparo de esa ley. Las inscritas actualizan su información cada año, hasta el 30 de abril (art. 17).
>    - El equipo decidió que `rnca` **no frena** el lote. Su falta es el hallazgo `registro_cooperativas_sin_sustento`. La sección 4, regla 3, se corrigió para no decir que una cooperativa sin inscripción puede operar.
> 3. **Número de la declaración aduanera.** La consulta pública de SUNAT pide el número en partes: aduana, año, régimen y número correlativo. El procedimiento vigente de exportación definitiva (DESPA-PG.02, versión 7) no fija su longitud ni sus separadores, y el instructivo general de la declaración (DESPA-IT.00.04) ya no se aplica a esa exportación. No se confirmó un formato: el número queda como texto de 5 a 30 caracteres.
> 4. **Las tres consultas responden** (HTTP 200): las dos de la declaración aduanera y la del RUC. La del RUC responde 403 a pedidos automáticos y abre desde un navegador. La de una declaración pide un reCAPTCHA. El sistema no las consulta: la comparación la hace una persona.
> 5. **Cotejo de `dam`.** El cotejo de la Parte 4 solo acepta documentos del expediente legal y respondía 400 con la `dam`. El equipo decidió **extenderlo**: el catálogo de embarque dice qué documento tiene registro consultable (solo `dam`), y el cotejo lo acepta también con el lote `cerrado`, con los mismos campos y la misma auditoría.

### Decisiones pendientes del equipo

- [ ] Confirmar que el registro de cooperativas deja de frenar.
- [ ] Confirmar que salen `ruc_comercio_exterior` y `registro_aduanas`.
- [ ] Confirmar la política con cinco temas en lugar de cinco casillas.
- [ ] Confirmar que las actuaciones se construyen ahora, y que no frenan.
- [ ] Confirmar que la declaración aduanera no frena y se puede agregar después del DEX.
- [ ] Confirmar con el contador los 18 meses de vigencia de la declaración de renta.
- [ ] Un asesor legal revisa el texto del Anexo A antes de que una organización real lo firme.
- [ ] Cada organización define quién atiende su canal de quejas y denuncias antes de publicar el contacto.

## 15. Construcción (10 de octubre de 2026)

Registro de Claude Code. Rama `feat/adenda-6-organizacion`, migración 0018.

### Confirmado antes de construir

Las cinco comprobaciones de la sección 14 y las decisiones del equipo están en el recuadro de "Antes de programar": `rnca` no frena y el cotejo se extiende a la declaración aduanera.

### Decisiones de construcción por confirmar

La adenda no las dice.

1. **Estado de los requisitos con documentos.**
   - Identidad, tributos y registro de cooperativas se calculan con las casillas de sus documentos.
   - Un requisito está `sin_sustento` si le falta algún documento, `vencido` si alguno venció, `por_vencer` si alguno vence pronto y `sustentado` si todos están vigentes.
   - El estado "completo" del expediente, sus faltantes y su insignia miran solo la identidad.
2. **Declaración de renta.**
   - Pide número de orden y entidad emisora, como los demás documentos de la organización.
   - La fecha de presentación va como fecha de emisión. El vencimiento lo pone el sistema: `RENTA_VIGENCIA_MESES` después.
3. **Registro de cooperativas.**
   - Una asociación o una empresa que intenta cargarlo recibe 422 (`tipo_no_aplica`).
   - Si una organización deja de ser cooperativa agraria, su `rnca` cargado pasa a "documentos anteriores".
4. **Política.**
   - Se anula la política, no su archivo: anular el archivo por su cuenta responde 400. Una política cuyo archivo estuviera anulado tampoco cuenta.
   - Al cargarla, una casilla dice si es la plantilla del sistema. Si se marca, guarda la versión vigente del Anexo A; se admite de la 1 a la vigente.
   - El órgano llega escrito con el que sugiere la plantilla según el tipo de organización.
   - El tema `canal_denuncias` cubierto por una política, pero sin contacto, dice "falta el contacto del canal".
5. **Contacto del canal.**
   - En "Mi perfil" del productor sale el de la organización de su cuenta.
   - En la hoja de la declaración anual va en un recuadro antes de la firma, solo si la organización lo registró, también en la copia. Su texto vive en `plantillas_legales.json` (clave `canal` de `declaracion_productor`), fuera de los bloques. No es parte de lo declarado: la versión del texto de la declaración sigue siendo 1.
6. **Actuaciones.**
   - El lugar va completo (departamento, provincia y distrito) o no va: si falta uno, 422.
   - Solo se marcan productores con afiliación activa en la organización. Otro productor responde 422.
   - Cuenta hasta el día en que se cumplen `ACTUACION_VIGENCIA_MESES` desde su fecha, ese día incluido.
   - La evidencia la cargan el administrador y el operador; la anula solo el administrador, como los documentos de la organización. Una actuación anulada no recibe evidencia: 400.
   - La contraparte admite hasta 400 caracteres; la descripción y el resultado, hasta 4 000.
   - La lista trae hasta 500, de la más reciente a la más antigua, con las anuladas marcadas. Con `productor_id`, las que alcanzaron a ese productor: así las muestra su ficha.
7. **Señales.**
   - Los productores son los de afiliación activa, con las respuestas de su declaración vigente. Las parcelas son las activas de esos productores.
   - `tierra_forestal` y `areas_protegidas` miran el valor del perfil que manda (el más exigente entre el cruce y lo declarado, adenda 4).
   - `agua` cuenta las parcelas con el requisito `agua_de_riego` sin sustento o vencido, o con `junto_a_cuerpo_de_agua = si`.
   - `tenencia` cuenta las incidencias de tenencia registradas en los últimos 12 meses, abiertas o cerradas.
   - `derechos_humanos` cuenta los productores con `menores_de_edad` o `trabajo_libre` por atender.
   - Integridad se espera siempre. Los otros siete, cuando su cuenta es mayor que cero: la regla de cada señal ya dice si basta con estar expuesto o hace falta un caso.
   - El cuadro y el DEX dicen la cuenta con un texto fijo, en español y en inglés (`organizacion.senales` de `es.json` y `en.json`).
8. **Lista de productos.**
   - Un producto es un nombre normalizado (sin tildes, mayúsculas ni espacios de más). Lleva el nombre con que se declaró primero.
   - Su revisión es la de fecha más reciente entre las declaraciones vigentes; sin ninguna, "sin buscar".
   - El PDF trae solo los que figuran y los que no figuran. Los que nadie buscó todavía no van.
9. **Declaración aduanera.**
   - Si no se escribe la entidad emisora, queda SUNAT.
   - También se anula con el lote cerrado, como se carga.
   - "Agregado después de la emisión" son las declaraciones vigentes del lote que no quedaron selladas en el embarque del DEX; se comparan por su huella. De un DEX anulado, solo las cargadas mientras estuvo vigente.
   - Si el DEX se anula, el lote vuelve a armado como siempre, y la siguiente emisión sella la declaración con los demás documentos.
   - `lote_sin_dam` aparece también en el informe preliminar: dice hoy lo que diría al emitir.
10. **DEX, versión 4.**
    - El exportador lista solo los documentos que aplican a su tipo de organización.
    - El bloque `organizacion` lleva: los documentos con su estado y su nivel; los requisitos con su estado y los códigos de lo que falta; los cinco temas de la política con su fecha de adopción; si hay contacto del canal; las señales; y las actuaciones vigentes con su nivel.
    - No lleva la evidencia ni los productores alcanzados.
    - Un DEX anterior a la adenda se sigue leyendo: su PDF no tiene la sección.
11. **Hallazgos.**
    - El sujeto de los de la organización es `organizacion`, con el código de la organización o, si no tiene, su RUC. En la pantalla, `sin_actuaciones_de_diligencia` lleva a Diligencia y los demás al expediente.
    - Los hechos dicen el estado del documento ("faltante", "vencido").
    - En los del productor, las actuaciones que lo alcanzaron van en `datos.actuaciones`, con su fecha y su tipo en los dos idiomas. El informe en pantalla y el PDF las muestran debajo de la explicación.
12. **Recomprobación.** La comprobación conserva su código `expediente_cooperativa_completo`. Se llama "Identidad de la organización" y es sobre "La organización".
13. **Pantallas.**
    - "Diligencia" va en la barra lateral después de "Datos y expediente legal".
    - Las actuaciones que alcanzaron a un productor van en la pestaña Declaración de su ficha, junto a la nota de seguimiento.
14. **Migración.** Al bajar de la 0018 se borran las filas de documentos de los tipos y la entidad nuevos; los archivos de Storage quedan.
15. **Escenario de demostración y simulación.**
    - El escenario carga los documentos que aplican a una cooperativa agraria (cinco) y la declaración aduanera con los cuatro obligatorios.
    - No carga política ni actuaciones: su DEX trae `politica_incompleta` y `sin_actuaciones_de_diligencia`.
    - En la simulación, la declaración de renta reemplaza a los dos registros de exportador. El guion no suma pasos de política ni de actuaciones.

### Para el equipo

1. Al desplegar, el comando de inicio de Render aplica la migración 0018. Ninguna organización recibe una política ni una actuación.
2. Un lote bloqueado solo por `rnca`, `ruc_comercio_exterior` o `registro_aduanas` queda listo en su siguiente recomprobación.
3. Revisar el tipo de cada organización en Plataforma: solo la cooperativa agraria ve el registro de cooperativas.
4. Los pendientes de la sección 14: el contador (18 meses de la renta), el asesor legal (Anexo A) y quién atiende el canal de cada organización antes de publicar su contacto.

## Anexo A — Política de integridad, trabajo digno y diligencia debida

Versión 1, redactada para revisión de un asesor legal. Lo que va entre llaves lo llena el sistema; las líneas, la organización.

> **POLÍTICA DE INTEGRIDAD, TRABAJO DIGNO Y DILIGENCIA DEBIDA**
>
> {razón social de la organización} · RUC N.º {ruc} · {tipo de organización}
>
> Adoptada por {órgano de dirección sugerido}: ______________________, en sesión del ____ de __________ de 20____.
>
> **1. Objeto y alcance.** Esta política fija las reglas con que la organización acopia, procesa y vende cacao. Obliga a sus directivos, a su gerencia y a todo su personal. En lo que les corresponde, la organización la da a conocer a sus socios, a los productores que le entregan cacao y a sus proveedores, y espera de ellos la misma conducta.
>
> **2. Integridad.** Nadie que actúe en nombre de la organización ofrece, da, pide ni recibe pagos, regalos o favores indebidos, sea a funcionarios públicos, a compradores, a proveedores o a quienes la auditan. Quien tenga un interés personal o familiar en una decisión lo declara por escrito y no participa en ella. Los registros contables y de acopio reflejan lo que ocurrió.
>
> **3. No fraude.** La organización no altera pesos, calidades, fechas, orígenes ni documentos. No registra el cacao de una parcela a nombre de otra. No recibe cacao de origen desconocido ni lo mezcla con cacao de origen registrado. No hace afirmaciones engañosas sobre el origen, el volumen o las cualidades de su cacao.
>
> **4. Trabajo digno.** En la organización, y en las parcelas de quienes le entregan cacao, se promueven y se exigen estas reglas: (a) ninguna persona menor de dieciocho (18) años trabaja en las labores del cultivo ni del acopio; (b) todo trabajo es libre, y nadie es retenido por deudas, documentos o pagos pendientes; (c) la jornada, el pago y el seguro de los trabajadores respetan la ley; (d) a igual trabajo corresponde igual pago, sin distinción por sexo, origen, religión u otra condición; (e) no se tolera el acoso sexual ni ninguna forma de violencia; y (f) quien trabaja recibe condiciones seguras y el equipo de protección que su labor requiera.
>
> **5. Agroquímicos y envases.** La organización entrega a sus productores la lista de los productos que buscó en el registro del SENASA, los capacita en su uso y en el manejo de los envases vacíos, y no distribuye productos que no figuren en ese registro.
>
> **6. Canal de quejas y denuncias.** Cualquier persona —trabajador, socio, productor o tercero— puede presentar una queja o una denuncia por un hecho contrario a esta política. Puede hacerlo con su nombre o de forma anónima, por este medio: {contacto del canal}. La recibe: ______________________ (nombre o cargo). La organización guarda reserva sobre la identidad de quien denuncia y sobre el contenido de la denuncia. No toma ni permite represalias contra quien denuncia de buena fe. Acusa recibo en ____ días y responde en ____ días. Lleva un registro de los casos y de lo que resolvió. Si el hecho puede ser delito, lo pone en conocimiento de la autoridad competente.
>
> **7. Revisión de documentos.** La organización comprueba los documentos que recibe de productores y proveedores antes de aceptarlos: pide el original o una copia legible; lo compara con el registro público cuando existe; y anota quién lo revisó y en qué fecha. Un documento dudoso, alterado o que no coincide con el registro público no se acepta, y el caso queda anotado.
>
> **8. Capacitación.** Al menos una vez al año la organización capacita a su personal y a sus productores sobre esta política, y deja constancia de la fecha, los temas y los asistentes.
>
> **9. Faltas.** La falta a esta política se trata según el estatuto y el reglamento interno de la organización, sin perjuicio de las responsabilidades que fije la ley.
>
> **10. Vigencia.** Esta política rige desde su adopción. Se revisa cada dos años, o antes si cambia la ley.
>
> Firma: ______________________   Nombre: ______________________   Cargo: ______________
>
> Firma: ______________________   Nombre: ______________________   Cargo: ______________
>
> Referencias: Código Penal, Decreto Legislativo N.º 635; Decreto Legislativo N.º 1385, que sanciona la corrupción en el ámbito privado; Ley N.º 31110, Ley del régimen laboral agrario; Ley N.º 27942, Ley de Prevención y Sanción del Hostigamiento Sexual; Documento orientador para la diligencia debida de la legalidad del café y cacao en el marco del EUDR, requisitos 2.3, 2.7, 4.1 a 4.7, 5.2 a 5.5 y 7.3. Versión 1.

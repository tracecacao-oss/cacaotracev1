# Adenda 5 — Declaración y documentos del productor (Partes 3, 4, 5 y 9)

Fecha: 9 de octubre de 2026.

Esta adenda modifica lo que `docs/especificacion.md` pide al productor: su ficha (Parte 3), el requisito `productor_listo` de la compuerta (Parte 4), lo que del productor se sella en el DOP (Parte 5) y lo que llega a los hallazgos y al DEX (Parte 9). Donde difiera de la especificación o de las adendas anteriores, manda esta adenda.

Se construye después de la adenda 4 (`docs/adenda-4-legalidad-por-requisito.md`): usa su tema 11 del artículo 10 y sus estados de requisito.

Cubre solo al productor. Lo que el orientador pide a la organización y al lote va en una adenda posterior. Hasta entonces no cambian el expediente de la organización ni los documentos de embarque.

No cambia el texto ni el registro del consentimiento, la copia del DNI, la constancia del PPA, la carga masiva de productores, la legalidad de la parcela de la adenda 4, el análisis de cobertura forestal ni la regla que decide cuándo salta una alerta.

La fuente es el "Documento orientador para la diligencia debida de la legalidad del café y cacao en el marco del EUDR" (MIDAGRI, MINCETUR y ADEX; European Forest Institute, 2026). En adelante, "el orientador". El propio documento dice que no es jurídicamente vinculante ni asesoría legal.

Las reglas de efecto de esta adenda siguen la decisión del equipo del 9 de octubre de 2026 para la parcela: solo frena lo básico. Las decisiones propias de esta adenda están en la sección 14 y esperan confirmación del equipo.

## 1. Qué cambia y por qué

Hoy al productor se le piden dos cosas: la copia del DNI y el consentimiento de datos. Lo laboral y lo tributario estaban en dos casillas de cada parcela, `sunafil` y `sunat`, que casi siempre se llenaban con una exención. La adenda 4 retiró esas casillas.

El orientador no pide papeles al productor pequeño. Pide una encuesta a todos los productores y, solo cuando una respuesta lo amerita, algún documento.

| Antes | Ahora |
| --- | --- |
| `productor_listo` = copia del DNI y consentimiento | `productor_listo` = copia del DNI, consentimiento y declaración anual vigente |
| Casillas `sunafil` y `sunat` por parcela | Una declaración por productor, una vez al año |
| Lo que no aplicaba se llenaba con exención | Las preguntas que no aplican no aparecen |
| Nada sobre agroquímicos ni envases | El productor declara qué usa; el personal lo busca en el registro de SENASA |
| El sistema no tenía nada que mostrar sobre trabajo en la parcela | El DEX muestra lo que cada productor declaró y lo que quedó por atender |

## 2. Qué pide el orientador al productor

Son 14 de los 40 requisitos. La numeración es la del Anexo 2 del orientador, como en la adenda 4.

| Ref. | Requisito | Nivel y diligencia | Qué pide el orientador | Cómo se cubre aquí |
| --- | --- | --- | --- | --- |
| 2.3 | Usa solo agroquímicos autorizados | Bajo, estándar | Tener la lista de plaguicidas y fertilizantes registrados por SENASA y comprobar que los productos usados figuran | Lista de productos declarada y revisión del personal en el registro de SENASA |
| 2.7 | Maneja residuos y envases según la norma | Bajo, estándar | Preguntar con un cuestionario periódico cómo se aplican los productos, cuáles son y qué se hace con los envases | Preguntas `quien_aplica` y `destino_envases` |
| 4.1 | Sus trabajadores tienen contrato según la ley | Alto, aligerada | Encuesta a todos los productores para saber si tienen trabajadores. Contratos solo si hay permanentes | Pregunta `quien_trabaja`. Con permanentes pide la relación de trabajadores |
| 4.2 | No exceden la jornada legal | Bajo, estándar | La misma encuesta recoge los horarios | Pregunta `horas_por_dia` |
| 4.3 | Salario no menor al mínimo | Bajo, estándar | La misma encuesta recoge los salarios | Pregunta `jornal_soles` |
| 4.4 | Acceso a salud y seguro de vida | Bajo, estándar | La misma encuesta recoge la afiliación a EsSalud o al SIS | Pregunta `seguro_salud` |
| 4.5 | Seguridad y salud en el trabajo | Bajo, estándar | Registro de entrega de equipo de protección | Pregunta `equipo_proteccion` |
| 4.6 | Sin discriminación | Bajo, estándar | Primero ver si son 5 ha o más. Solo entonces preguntar | Pregunta `mismo_pago`, con 5 ha o más |
| 4.7 | Descanso por maternidad y paternidad | Bajo, estándar | Con trabajadores permanentes, encuesta sobre el descanso pre y postnatal | Pregunta `descanso_maternidad_paternidad`, con 5 ha o más y permanentes |
| 5.2 | No emplea menores de 18 años | Alto, aligerada | Recoger por encuesta quiénes trabajan y sus edades; mirar si los menores van a la escuela | Pregunta `menores_trabajan` y sus dos preguntas de detalle |
| 5.3 | Los trabajadores pueden renunciar libremente | Alto, aligerada | Declaración voluntaria de los productores | Pregunta `pueden_dejar_el_trabajo` |
| 5.4 | Sin trabajo forzoso | Alto, aligerada | La misma declaración | La misma pregunta |
| 5.5 | Prohíbe el acoso sexual y protege a las víctimas | Alto, aligerada | Políticas y canales de queja | Queda para la adenda de la organización |
| 7.1 | Paga los tributos de su régimen | Alto, aligerada | Ver si vende menos de 75 UIT al año. Sobre ese monto, pedir por muestreo la declaración del impuesto a la renta y revisar el RUC | Pregunta `ventas_superan_75_uit`. Solo con `si` pide RUC y declaración de renta |

El orientador advierte, en sus notas 30 y 39, que se debate si lo laboral y los derechos humanos entran en el ámbito del Reglamento. Por eso aquí van como declaración del productor.

### Regla de efecto

Las parcelas de un productor no se habilitan solo si a él le falta la base:

1. La copia del DNI.
2. El consentimiento de datos.
3. La declaración anual vigente.

Ninguna respuesta de la declaración bloquea. Lo que quede por atender se muestra, exige nota al habilitar y llega al informe de hallazgos.

El sistema sigue sin concluir. Ningún texto dice que un productor "cumple" la ley laboral, tributaria o sanitaria: dice qué declaró, quién lo registró y qué falta.

## 3. Lo que se le pide al productor

### 3.1 Base

| Qué | Estado | Bloquea |
| --- | --- | --- |
| Copia del DNI (`dni`) | Ya existe. No cambia | Sí |
| Consentimiento de datos | Ya existe. No cambia | Sí |
| Declaración anual | Nueva. Secciones 4 y 5 | Sí |
| Constancia del PPA (`constancia_ppa`) | Ya existe. No cambia. El orientador no la pide | No |

### 3.2 Lo que el sistema calcula

Nadie escribe estos datos. Se muestran al empezar la declaración y se guardan con ella.

| Dato | De dónde sale | Para qué |
| --- | --- | --- |
| `area_total_ha` | Suma del área de las parcelas activas del productor en la organización, como ya la calcula `services/productores.py` | Decide si se muestran `mismo_pago` y `descanso_maternidad_paternidad` |
| `parcelas_activas` | El mismo cálculo | Contexto |
| `tiene_ruc` | El campo `ruc` de su ficha | Requisito `tributos` |
| `kilos_12_meses` | Suma de los kilos de sus tandas validadas en los últimos 12 meses | Se muestra junto a la pregunta de las 75 UIT, como ayuda |

1. El sistema no calcula las ventas del productor: no guarda precios.
2. Con menos de 5 ha se presume agricultura familiar, como hace el orientador. Esa presunción solo decide qué preguntas se muestran.

### 3.3 Papeles que pide una respuesta

| Respuesta | Papel | Bloquea |
| --- | --- | --- |
| `quien_trabaja = permanentes` | `relacion_trabajadores`: relación de trabajadores permanentes, con sus contratos o su planilla | No |
| `ventas_superan_75_uit = si` | `declaracion_renta`: declaración jurada anual del impuesto a la renta, o la constancia de haberla presentado. Además, el RUC en la ficha | No |

Ninguna otra respuesta pide un papel.

## 4. Declaración anual: cuestionario, versión 1

Son 18 preguntas. Cuatro se hacen a todos. Las demás aparecen solo si una respuesta o el área las abren. Un productor que trabaja con su familia y no usa agroquímicos responde cuatro.

"Contrata" significa `quien_trabaja` distinto de `solo_familia`.

| Código | Pregunta en pantalla | Valores | Se muestra | Ref. |
| --- | --- | --- | --- | --- |
| `quien_trabaja` | ¿Quién trabaja en tus parcelas? | `solo_familia`, `eventuales`, `permanentes` | Siempre | 4.1 |
| `trabajadores_numero` | ¿Cuántas personas contratas en la temporada de más trabajo? | Entero de 1 a 500 | Si contrata | 4.1 |
| `acuerdo_por_escrito` | ¿El acuerdo con ellas está por escrito? | `si`, `no` | Si contrata | 4.1 |
| `jornal_soles` | ¿Cuánto pagas por un día de trabajo? | Número mayor que 0, en soles | Si contrata | 4.3 |
| `horas_por_dia` | ¿Cuántas horas se trabaja en un día normal? | Número de 1 a 16 | Si contrata | 4.2 |
| `seguro_salud` | ¿Tienen seguro de salud, como EsSalud o el SIS? | `todos`, `algunos`, `ninguno` | Si contrata | 4.4 |
| `equipo_proteccion` | ¿Les das equipo de protección, como botas, guantes y mascarilla? | `si`, `no` | Si contrata | 4.5 |
| `pueden_dejar_el_trabajo` | ¿Cualquiera de ellos puede dejar el trabajo cuando quiera, sin deudas ni documentos retenidos? | `si`, `no` | Si contrata | 5.3, 5.4 |
| `mismo_pago` | ¿Pagas lo mismo a hombres y mujeres por el mismo trabajo? | `si`, `no` | Si contrata y `area_total_ha` es 5 o más | 4.6 |
| `descanso_maternidad_paternidad` | ¿Respetas el descanso por maternidad y por paternidad? | `si`, `no`, `no_se_presento` | Si `quien_trabaja = permanentes` y `area_total_ha` es 5 o más | 4.7 |
| `menores_trabajan` | ¿Trabaja en tus parcelas alguna persona menor de 18 años? | `no`, `si_de_la_familia`, `si_contratados` | Siempre | 5.2 |
| `menor_edad_minima` | ¿Qué edad tiene el más joven? | Entero menor que 18 | Si `menores_trabajan` no es `no` | 5.2 |
| `menores_van_a_la_escuela` | ¿Van a la escuela? | `si`, `algunos`, `no` | Si `menores_trabajan` no es `no` | 5.2 |
| `usa_agroquimicos` | ¿Usas fertilizantes, herbicidas, insecticidas o fungicidas? | `no`, `si` | Siempre | 2.3 |
| `productos` | ¿Cuáles? Escribe el nombre de cada producto | Lista de 1 a 20. Cada uno con nombre comercial y tipo: `fertilizante`, `herbicida`, `insecticida`, `fungicida` u `otro` | Si usa | 2.3 |
| `quien_aplica` | ¿Quién los aplica? | `yo_o_mi_familia`, `trabajadores`, `servicio_contratado` | Si usa | 2.7 |
| `destino_envases` | ¿Qué haces con los envases vacíos? | `devuelve_o_centro_de_acopio`, `triple_lavado_y_guarda`, `quema`, `entierra`, `bota_o_reutiliza` | Si usa | 2.7 |
| `ventas_superan_75_uit` | ¿Tus ventas de todo el año pasan de 75 UIT? | `no`, `si`, `no_sabe` | Siempre | 7.1 |

1. El catálogo vive en `backend/app/catalogos/declaracion_productor.py`, con su número de versión, la condición de cada pregunta y su ayuda de una línea.
2. La API valida que estén respondidas exactamente las preguntas que corresponden al productor. Si falta una o sobra otra, responde 422.
3. Cuando el personal registra la declaración, las preguntas se muestran en tercera persona.
4. La pregunta de las 75 UIT muestra el monto en soles cuando la plataforma tiene registrado el valor de la UIT (sección 9), y los `kilos_12_meses` como ayuda.
5. La ayuda de `menores_trabajan` dice que cuenta también a hijos y familiares que hacen labores del cultivo. No se guardan nombres ni datos de ningún menor ni de ningún trabajador.
6. La ayuda de `quien_trabaja` explica las tres opciones: solo tú y tu familia; contratas personas por días, en cosecha o poda; tienes trabajadores todo el año.
7. Un cambio de preguntas o de valores crea una versión nueva del cuestionario. Las declaraciones guardan la versión con que se respondieron.

## 5. Cómo se registra y cuándo vale

### 5.1 Dos caminos

| Camino | Pasos | Cuándo vale |
| --- | --- | --- |
| El productor, desde su cuenta | Responde las preguntas, lee el resumen y el texto del Anexo A, y toca "Declaro" | Al tocar "Declaro" |
| El personal, en su nombre | Registra las respuestas, descarga la hoja para firmar, el productor la firma y pone su huella, y el personal carga la foto o el escaneo con la fecha de firma | Al cargar la hoja firmada |

1. Registran en nombre del productor el `admin_cooperativa` y el `operador`.
2. Una declaración registrada por el personal queda `por_firmar` y no cuenta para nada hasta tener su hoja firmada.
3. La fecha de firma no puede ser futura ni anterior al día en que se registraron las respuestas.

### 5.2 Estados

| Estado | Condición |
| --- | --- |
| `por_firmar` | La registró el personal y falta la hoja firmada |
| `vigente` | El productor la declaró, o tiene hoja firmada, y no pasó su fecha `vigente_hasta` |
| `vencida` | Pasó su fecha `vigente_hasta` |
| `reemplazada` | Hay otra posterior del mismo productor |

1. Se guardan `por_firmar`, `vigente` y `reemplazada`. `vencida` se calcula al consultar, con la fecha del día, como hoy los documentos.
2. Un productor tiene como máximo una declaración `vigente` y una `por_firmar` por organización.
3. Cuando una declaración pasa a `vigente`, la `vigente` anterior y cualquier `por_firmar` más antigua quedan `reemplazada`. Mientras está `por_firmar` no reemplaza a la vigente. Registrar otra `por_firmar` reemplaza a la `por_firmar` anterior.
4. Las declaraciones no se editan ni se borran. Para corregir se registra otra.

### 5.3 Vigencia

1. `vigente_hasta` es la fecha en que se declaró más `DECLARACION_PRODUCTOR_VIGENCIA_MESES`, con valor inicial 12.
2. Está "por vencer" cuando faltan 30 días o menos.
3. Si después de declarar el `area_total_ha` del productor cruza las 5 ha, hacia arriba o hacia abajo, su ficha lo avisa y ofrece declarar de nuevo. No bloquea.

### 5.4 Hoja para firmar

1. `GET /productores/{id}/declaraciones/{declaracion_id}/hoja` devuelve un PDF con los datos del productor y de la organización, las preguntas mostradas con su respuesta y el texto del Anexo A.
2. El PDF se arma con fpdf2 en `backend/app/pdf/declaracion_productor.py`. El texto vive en un archivo de textos con su número de versión, junto al de la declaración de tenencia de la adenda 4. El PDF imprime la versión al pie.
3. La hoja firmada se carga como documento de tipo `hoja_declaracion_productor`.
4. De una declaración `vigente` la misma ruta devuelve la copia, con quién la declaró y cuándo. El productor la descarga desde su cuenta.
5. En una organización de demostración, la hoja lleva la misma marca de agua que los demás PDF.

### 5.5 Tabla `declaraciones_productor`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `cooperativa_id` | uuid | Organización ante la que se declara |
| `productor_id` | uuid | Referencia a `productores` |
| `version_cuestionario` | integer | Versión del catálogo |
| `version_texto` | integer | Versión del texto del Anexo A |
| `respuestas` | jsonb | Código y valor de cada pregunta mostrada |
| `contexto` | jsonb | Los datos de la sección 3.2 y los valores de referencia de la sección 9, como estaban al registrar |
| `origen` | text | `productor` o `personal` |
| `estado` | text | `por_firmar`, `vigente` o `reemplazada` |
| `registrada_por`, `registrada_en` | uuid, timestamptz | Quién registró las respuestas y cuándo |
| `declarada_en` | date | Día en que el productor tocó "Declaro" o firmó la hoja. Nulo mientras está `por_firmar` |
| `vigente_hasta` | date | `declarada_en` más los meses de vigencia |
| `seguimiento_nota`, `seguimiento_por`, `seguimiento_en` | text, uuid, timestamptz | Sección 5.7 |

### 5.6 Productos declarados y su revisión

Cada producto de la pregunta `productos` es una fila de la tabla `declaracion_productos`.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `declaracion_id` | uuid | Referencia a `declaraciones_productor` |
| `nombre` | text | Nombre comercial, de 2 a 80 caracteres |
| `tipo` | text | `fertilizante`, `herbicida`, `insecticida`, `fungicida` u `otro` |
| `revision` | text | `sin_revisar`, `figura` o `no_figura` |
| `registro` | text | Número de registro que muestra SENASA. Opcional |
| `revisado_por`, `revisado_en` | uuid, timestamptz | Quién lo buscó y cuándo |
| `copiada_de` | uuid | Fila de la que se copió la revisión, si se copió |

1. Revisan el `admin_cooperativa` y el `operador`. Buscan el producto en la consulta pública de SENASA y marcan si figura.
2. La pantalla enlaza las dos consultas que nombra el orientador: el registro de plaguicidas (`https://servicios.senasa.gob.pe/SIGIAWeb/sigia_consulta_producto.html`) y el de insumos (`https://servicios.senasa.gob.pe/SIGIAWeb/ip_productoprincipal.html`).
3. El sistema no consulta a SENASA. No se encontró un servicio público para hacerlo. Si Claude Code encuentra uno documentado, se detiene y pregunta antes de integrarlo.
4. Al registrar un producto, si en la misma organización hay una revisión de ese mismo nombre y tipo con menos de 12 meses, el sistema la copia y lo indica. Los nombres se comparan sin tildes, sin mayúsculas y sin espacios de más.
5. El formulario sugiere los nombres ya declarados en la organización.
6. Las palabras "autorizado" y "prohibido" no se usan. El texto es "figura en el registro de SENASA consultado el dd/mm/aaaa" o "no figura".
7. La revisión se puede cambiar. Cada cambio queda en la auditoría.

### 5.7 Nota de seguimiento

El orientador pide que, ante una señal, la organización actúe: informar al productor, capacitarlo o visitarlo. El sistema guarda lo que la organización hizo.

1. El `admin_cooperativa` puede escribir una nota de seguimiento sobre la declaración vigente, de 50 caracteres como mínimo.
2. La nota aparece como explicación de los hallazgos de ese productor en el DEX.
3. La nota se puede reemplazar. Cada cambio queda en la auditoría.

### 5.8 Rutas

| Ruta | Quién | Qué hace |
| --- | --- | --- |
| `GET /declaraciones-productor/cuestionario` | Cualquier usuario con sesión | El catálogo vigente y los valores de referencia |
| `GET /productores/{id}/declaracion` | Personal | La vigente, la `por_firmar`, el historial, los datos calculados y los requisitos |
| `POST /productores/{id}/declaraciones` | `admin_cooperativa`, `operador` | Registra las respuestas. Queda `por_firmar` |
| `GET /productores/{id}/declaraciones/{declaracion_id}/hoja` | Personal | La hoja para firmar, o la copia |
| `POST /productores/{id}/declaraciones/{declaracion_id}/hoja-firmada` | `admin_cooperativa`, `operador` | Carga la hoja firmada con su fecha. Pasa a `vigente` |
| `POST /productores/{id}/declaraciones/{declaracion_id}/documentos` | `admin_cooperativa`, `operador` | Carga `relacion_trabajadores` o `declaracion_renta` |
| `PATCH /productores/{id}/declaraciones/{declaracion_id}/productos/{producto_id}` | `admin_cooperativa`, `operador` | Revisión de un producto |
| `PUT /productores/{id}/declaraciones/{declaracion_id}/seguimiento` | `admin_cooperativa` | Nota de seguimiento |
| `GET /mi/declaracion` | Productor | Su declaración, sus requisitos y lo que falta. Sin la nota de seguimiento |
| `POST /mi/declaracion` | Productor | Responde y declara. Pasa a `vigente` |
| `GET /mi/declaracion/hoja` | Productor | La copia de su declaración vigente |
| `POST /mi/declaracion/documentos` | Productor | Carga `relacion_trabajadores` o `declaracion_renta` |

Otra organización recibe 404 en todas las rutas de un productor que no es suyo.

## 6. Requisitos del productor: catálogo y estados

El catálogo vive en `backend/app/catalogos/requisitos_productor.py`. Cada requisito lleva su código, las referencias del orientador, el nivel y la diligencia. Ninguno bloquea.

| Código | Ref. | Nivel y diligencia | Aplica cuando | Con qué se sustenta |
| --- | --- | --- | --- | --- |
| `condiciones_de_trabajo` | 4.1 a 4.5 | Bajo, estándar. El 4.1 es alto, aligerada | Contrata | Sus respuestas. Con `permanentes`, además `relacion_trabajadores` |
| `igualdad_y_maternidad` | 4.6, 4.7 | Bajo, estándar | Contrata y `area_total_ha` es 5 o más | Sus respuestas |
| `trabajo_libre` | 5.3, 5.4 | Alto, aligerada | Contrata | Su respuesta |
| `menores_de_edad` | 5.2 | Alto, aligerada | Siempre | Su respuesta |
| `agroquimicos` | 2.3 | Bajo, estándar | Siempre | Su respuesta. Si usa, la revisión de cada producto |
| `envases` | 2.7 | Bajo, estándar | `usa_agroquimicos = si` | Su respuesta |
| `tributos` | 7.1 | Alto, aligerada | `ventas_superan_75_uit` distinto de `no` | RUC en la ficha y `declaracion_renta` |

### Estados

| Estado | Condición |
| --- | --- |
| `sin_dato` | El productor no tiene declaración vigente |
| `no_aplica` | La declaración dice que no aplica |
| `declarado` | Lo cubre la respuesta del productor y no deja nada por atender |
| `por_atender` | Una respuesta declara un hecho de la tabla siguiente |
| `sin_sustento` | Pide un papel o una revisión y falta |
| `sustentado` | El papel o la revisión está |

1. `sin_dato`, `no_aplica`, `sin_sustento` y `sustentado` son los mismos estados de la adenda 4. `declarado` y `por_atender` son propios del productor.
2. El nivel de verificación de una respuesta es siempre `declarado`. El de un requisito con papel cargado es `documentado`.
3. Las palabras "cumple", "incumple", "conforme" y "aprobado" no se usan para un requisito.

### Qué deja un requisito `por_atender`

| Respuesta | Condición |
| --- | --- |
| `horas_por_dia` | Mayor que 8 |
| `jornal_soles` | Menor que el jornal de referencia, si la plataforma lo tiene registrado (sección 9) |
| `seguro_salud` | `algunos` o `ninguno` |
| `equipo_proteccion` | `no` |
| `mismo_pago` | `no` |
| `descanso_maternidad_paternidad` | `no` |
| `pueden_dejar_el_trabajo` | `no` |
| `menores_trabajan` | `si_de_la_familia` o `si_contratados` |
| `destino_envases` | `quema`, `entierra` o `bota_o_reutiliza` |
| Un producto declarado | `revision = no_figura` |

`acuerdo_por_escrito = no` se muestra y no deja nada por atender: el orientador recuerda que el contrato verbal es válido.

### Cómo se calcula cada estado

| Requisito | Regla |
| --- | --- |
| `condiciones_de_trabajo` | `no_aplica` si no contrata. `por_atender` si alguna de sus cuatro respuestas lo deja así. Si no, con `permanentes`: `sustentado` con `relacion_trabajadores` cargada y `sin_sustento` sin ella. Con `eventuales`: `declarado` |
| `igualdad_y_maternidad` | `no_aplica` si no contrata o suma menos de 5 ha. `por_atender` o `declarado` según sus respuestas |
| `trabajo_libre` | `no_aplica` si no contrata. `por_atender` o `declarado` |
| `menores_de_edad` | `por_atender` o `declarado` |
| `agroquimicos` | `declarado` si no usa. `por_atender` si un producto no figura. `sin_sustento` si queda alguno sin revisar. `sustentado` si todos figuran |
| `envases` | `no_aplica` si no usa. `por_atender` o `declarado` |
| `tributos` | `no_aplica` con `no`. `sin_sustento` con `no_sabe`, o con `si` cuando falta el RUC o la `declaracion_renta`. `sustentado` con `si`, RUC y `declaracion_renta` |

Un requisito puede dejar más de un hallazgo. Un productor con trabajadores permanentes sin seguro y sin relación cargada deja dos.

## 7. Tipos de documento

Los papeles de la declaración pertenecen a esa declaración. Por eso no llevan vencimiento propio: al renovar la declaración se piden otra vez, si la respuesta los vuelve a pedir.

| Código | Documento | De qué entidad |
| --- | --- | --- |
| `hoja_declaracion_productor` | Hoja de la declaración anual firmada por el productor | `declaracion_productor` |
| `relacion_trabajadores` | Relación de trabajadores permanentes, con sus contratos o su planilla | `declaracion_productor` |
| `declaracion_renta` | Declaración jurada anual del impuesto a la renta, o constancia de haberla presentado | `declaracion_productor` |

1. Se agrega `declaracion_productor` a las entidades de documento.
2. `dni` y `constancia_ppa` siguen siendo documentos del productor y no cambian.
3. Los documentos `sunafil` y `sunat` que quedaron en parcelas como "documentos anteriores" siguen ahí. No se mueven al productor.

## 8. Compuerta: `productor_listo`

| Hoy | Con esta adenda |
| --- | --- |
| Copia del DNI y consentimiento | Copia del DNI, consentimiento y declaración anual `vigente` |

1. El detalle del requisito dice qué falta: "copia del DNI", "consentimiento de datos", "declaración anual", "hoja firmada de la declaración" o "declaración anual vencida".
2. Cuando la declaración vence, `productor_listo` deja de cumplirse y las parcelas habilitadas de ese productor pasan a `observada`, igual que hoy cuando vence un documento. La recomprobación de un lote con esas parcelas actúa como ya lo hace con cualquier parcela `observada`.
3. Cada requisito del productor en `por_atender` o `sin_sustento` es una alerta de sus parcelas: `productor_por_atender` y `productor_sin_sustento`. Con cualquier alerta, la nota al habilitar sigue siendo obligatoria, con 50 caracteres como mínimo.
4. Los pendientes del productor suman `sin_declaracion_anual`, `declaracion_por_firmar` y `declaracion_por_vencer`.
5. Tras la migración ningún productor tiene declaración. Sus parcelas habilitadas pasan a `observada` hasta que declare. Los DOP ya emitidos no se tocan.

## 9. Valores de referencia de la plataforma

Dos valores cambian con el tiempo y el sistema no los asume. Los registra el superadministrador en la configuración de plataforma, junto a la clasificación del país.

| Campo | Qué es | Si está vacío |
| --- | --- | --- |
| `uit_soles`, `uit_anio` | Valor de la UIT y su año. En 2026 es S/ 5 500 | La pregunta dice "75 UIT" sin monto |
| `jornal_minimo_referencia`, `jornal_referencia_nota` | Pago mínimo por día de trabajo que la organización toma como referencia, y de dónde sale | `jornal_soles` no se compara con nada y nunca queda `por_atender` |

1. El jornal de referencia no viene cargado. El equipo lo registra después de confirmarlo con su contador.
2. Cada declaración guarda en `contexto` los valores con que se evaluó. Cambiar la referencia no cambia el estado de las declaraciones ya registradas.

## 10. Pantallas

### Personal

1. La ficha del productor suma la pestaña "Declaración". Arriba, el estado: sin declaración, por firmar, vigente hasta una fecha, por vencer o vencida. Debajo, tres bloques: Respuestas, Requisitos y Papeles.
2. "Registrar declaración" abre el cuestionario. Empieza mostrando lo que el sistema ya sabe, de la sección 3.2. Cada pregunta aparece cuando su condición se cumple.
3. Al guardar, la pantalla ofrece "Descargar hoja para firmar" y "Cargar hoja firmada".
4. Requisitos: una fila por requisito, con por qué aplica, el nivel y la diligencia del orientador, el estado y lo que sigue. Los que no aplican van al final, plegados.
5. Los estados se muestran como "Declarado", "Por atender", "Sustentado", "Sin sustento", "No aplica" y "Falta la declaración".
6. La lista de productos tiene, por producto, el enlace a la consulta de SENASA y los botones "Figura" y "No figura".
7. El inicio suma el grupo de pendientes "Declaraciones de productores": vencidas, por vencer, por firmar y sin declaración.
8. La lista de productores permite filtrar por esos cuatro casos.

### Productor

1. "Mi perfil" muestra en "Lo que falta" la declaración anual, con el enlace "Responder ahora".
2. `#/mi-declaracion` hace una pregunta por pantalla, en lenguaje simple y de tú. Al final muestra el resumen de sus respuestas, el texto del Anexo A y el botón "Declaro".
3. Con declaración vigente, la misma pantalla muestra sus respuestas, hasta cuándo vale y "Descargar mi declaración".
4. Si el personal ya la registró y falta la firma, la pantalla lo dice. El productor puede declararla él mismo desde su cuenta, y eso reemplaza a la `por_firmar`.
5. El productor no ve la nota de seguimiento.

### Superadministrador

La pantalla de configuración de la plataforma suma los cuatro campos de la sección 9.

## 11. DOP, DEX e informe de hallazgos

### DOP

1. El DOP sube de versión. El bloque `productor` suma `declaracion`: su fecha, su origen, hasta cuándo vale, las versiones del cuestionario y del texto, las respuestas, y los siete requisitos con su estado.
2. Los DOP anteriores se leen como hoy.

### DEX

1. El contenido del DEX suma el bloque `productores`: por cada productor del lote, lo mismo que sella el DOP, con el estado de hoy.
2. El PDF suma la sección "Declaraciones de los productores", después de "Respaldo por parcela". Empieza con un cuadro de totales: cuántos productores tiene el lote, cuántos contratan trabajadores, cuántos usan agroquímicos y cuántos tienen algo por atender. Sigue una fila por productor.
3. La sección dice que son declaraciones del productor, que la organización no las comprobó en campo salvo que la nota de seguimiento diga otra cosa, y cita el orientador como marco.

### Hallazgos nuevos

Los hallazgos del productor se calculan como los de la parcela: con el estado de hoy, no con lo sellado en el DOP. Son de la etapa 1. Su sujeto es de tipo `productor` y se nombra como en la genealogía. Su peso en el lote es la suma de los pesos de sus parcelas.

Regla de grupo para el productor: un hecho declarado que deja algo por atender va a Requiere atención. Un papel o una revisión que falta va a No verificado.

| Código | Se genera cuando | Grupo |
| --- | --- | --- |
| `condiciones_de_trabajo_por_atender` | `condiciones_de_trabajo` o `igualdad_y_maternidad` están `por_atender`. Lista cada hecho con su valor declarado | Requiere atención |
| `menores_en_la_parcela` | `menores_de_edad` está `por_atender`. Incluye si son de la familia o contratados, la edad del más joven y si van a la escuela | Requiere atención |
| `trabajo_no_libre` | `trabajo_libre` está `por_atender` | Requiere atención |
| `agroquimico_no_figura` | Un producto declarado no figura en el registro de SENASA. Lista cuáles y la fecha de consulta | Requiere atención |
| `envases_por_atender` | `envases` está `por_atender`. Incluye lo declarado | Requiere atención |
| `agroquimicos_sin_revisar` | Queda algún producto sin revisar. Lista cuáles | No verificado |
| `permanentes_sin_relacion` | Tiene trabajadores permanentes y no cargó `relacion_trabajadores` | No verificado |
| `tributos_sin_sustento` | `tributos` está `sin_sustento`. Dice qué falta, o que el productor no sabe | No verificado |

1. Todos van al tema 11, "Otra información sobre la legalidad de la producción (art. 10.2, letra m)", que agregó la adenda 4. El tema 8 sigue como no cubierto.
2. Cada hallazgo lleva en sus datos la referencia del orientador, el nivel y la diligencia.
3. La explicación de un hallazgo del productor es la nota de seguimiento, si la hay.
4. Los textos van en `es.json` y `en.json`, con las mismas claves. Dicen "el productor declara", nunca afirman el hecho por cuenta del sistema.
5. Un productor sin declaración vigente no genera estos hallazgos: sus parcelas ya están `observada` y el lote lo informa por esa vía.

## 12. Datos y migración

1. Tablas nuevas: `declaraciones_productor` y `declaracion_productos`. Las dos con RLS activado y sin políticas.
2. `configuracion_plataforma` suma `uit_soles`, `uit_anio`, `jornal_minimo_referencia` y `jornal_referencia_nota`.
3. Variable nueva del backend: `DECLARACION_PRODUCTOR_VIGENCIA_MESES`, con valor inicial 12.
4. Se agregan los tres tipos de documento y la entidad de la sección 7.
5. El servicio nuevo `backend/app/services/declaracion_productor.py` registra, declara, calcula los requisitos y arma el bloque del DOP y del DEX. `services/habilitacion.py` le pregunta si el productor tiene declaración vigente.
6. Cada acción audita en la misma transacción: registrar, declarar, cargar la hoja firmada, revisar un producto y escribir el seguimiento.
7. La migración no inventa valores: ningún productor recibe una declaración por defecto.
8. `CLAUDE.md` nombra esta adenda y sus convenciones.

## 13. Pruebas mínimas y aceptación

### Pruebas automáticas

| Caso | Resultado esperado |
| --- | --- |
| Productor sin declaración | `productor_listo` no se cumple; sus parcelas no se habilitan |
| Declaración registrada por el personal, sin hoja | Queda `por_firmar`; `productor_listo` no se cumple |
| Se carga la hoja firmada | Pasa a `vigente`; `productor_listo` se cumple |
| El productor declara desde su cuenta | `vigente` al instante, con `origen = productor` |
| Declaración de hace 13 meses | `vencida`; las parcelas habilitadas pasan a `observada` |
| Declaración nueva `vigente` | La anterior queda `reemplazada` y se conserva |
| `solo_familia`, sin menores, sin agroquímicos, ventas `no` | Se responden 4 preguntas; ningún hallazgo |
| `solo_familia` con `jornal_soles` en el envío | 422 |
| `eventuales` sin `horas_por_dia` | 422 |
| `eventuales`, `area_total_ha` de 3 | No se muestra `mismo_pago` |
| `eventuales`, `area_total_ha` de 6 | Se muestra `mismo_pago` y no `descanso_maternidad_paternidad` |
| `permanentes`, `area_total_ha` de 6 | Se muestran las dos |
| `horas_por_dia` de 10 | `condiciones_de_trabajo` `por_atender`; hallazgo con el valor declarado |
| `jornal_soles` menor que la referencia registrada | `por_atender` |
| `jornal_soles` sin referencia registrada | No queda `por_atender` |
| `permanentes` sin `relacion_trabajadores` | `sin_sustento`; hallazgo `permanentes_sin_relacion` |
| `menores_trabajan = si_de_la_familia` | Pide edad y escuela; hallazgo `menores_en_la_parcela`; las parcelas se pueden habilitar con nota |
| `pueden_dejar_el_trabajo = no` | Hallazgo `trabajo_no_libre`; no bloquea |
| `usa_agroquimicos = si` con un producto sin revisar | `agroquimicos` `sin_sustento`; hallazgo `agroquimicos_sin_revisar` |
| El personal marca un producto `no_figura` | `por_atender`; hallazgo `agroquimico_no_figura` con la fecha |
| Otro productor declara el mismo producto ya revisado | La revisión se copia, con `copiada_de` |
| `destino_envases = quema` | Hallazgo `envases_por_atender` |
| `ventas_superan_75_uit = si` sin RUC | `tributos` `sin_sustento` |
| `ventas_superan_75_uit = si` con RUC y `declaracion_renta` | `sustentado` |
| UIT no registrada | La pregunta no muestra monto |
| El área cruza 5 ha después de declarar | Aviso en la ficha; no bloquea |
| Hoja para firmar | El PDF trae los datos del productor, cada pregunta mostrada con su respuesta y el texto del Anexo A |
| Nota de seguimiento | Aparece como explicación de los hallazgos del productor |
| Peso de un hallazgo del productor | Suma de los pesos de sus parcelas en el lote |
| Textos | Los textos nuevos de pantalla, del PDF y de los hallazgos no usan las palabras prohibidas de la Parte 4. Tampoco dicen que un productor cumple o incumple, ni que un producto está autorizado o prohibido |
| DOP emitido antes de la migración | Su contenido y su huella no cambian |
| Aislamiento | Otra organización recibe 404 en la declaración, la hoja, los productos y el seguimiento |
| Permisos | El `lector` ve y no registra; el productor no ve el seguimiento; solo el `admin_cooperativa` lo escribe |

### Criterios de aceptación en producción

1. Un productor entra con su DNI desde el celular, responde cuatro preguntas, toca "Declaro" y su ficha muestra la declaración vigente con su fecha de vencimiento.
2. El personal registra la declaración de un productor sin cuenta, descarga la hoja, la carga firmada y el productor queda listo.
3. Un productor que contrata gente ve las preguntas de trabajo; uno que trabaja con su familia no las ve.
4. Un producto marcado como "No figura" aparece en la ficha del productor, como alerta en sus parcelas y como hallazgo en el DEX.
5. Un DEX nuevo trae la sección "Declaraciones de los productores", con los totales y una fila por productor.
6. Las parcelas de un productor sin declaración aparecen como `observada`, con el motivo a la vista.

## 14. Lecturas del orientador y decisiones pendientes

### Diferencias dentro del orientador

| Punto | Qué dice | Cómo se tomó aquí |
| --- | --- | --- |
| 7.1, de quién es | La tabla principal dice "El exportador"; el Anexo 2, "El productor" | Aquí, la parte del productor. La del exportador va en la adenda de la organización |
| 7.1, montos | La tabla principal usa 75 UIT. El Anexo 2 describe los tramos de 30 y 140 UIT de los socios de cooperativas, con una retención que hace la cooperativa | Al productor se le pregunta por 75 UIT. La retención es de la organización |
| 4.3, redacción | El Anexo 2 dice que el salario "no debe ser superior al mínimo" | Se lee "inferior", como la tabla principal |
| 4.6, las 5 ha | Habla de "polígonos de 5 ha o más" | Suma de las parcelas activas del productor |
| 2.3, documento | La tabla pone la Ficha Técnica Ambiental para más de 10 ha | Ya lo cubre `instrumento_ambiental`, de la adenda 4 |
| 2.7, plan de residuos | La tabla lo pide sobre 10 ha; el Anexo 2 menciona 5 ha | No se pide al productor. Va con el instrumento ambiental de la parcela |
| 5.2, familia | Dice que la edad mínima de 18 años en la actividad agraria no tiene excepciones, tampoco en el trabajo familiar | La pregunta incluye a la familia |
| 5.5 | Pide políticas y canales de queja | Adenda de la organización |

### Antes de programar

1. Claude Code lee la Ley N.º 31110 y su reglamento, y confirma la edad mínima de 18 años y la jornada de 8 horas diarias o 48 semanales. Si difieren de este texto, se detiene y pregunta.
2. Claude Code lee en el Decreto Supremo N.º 001-2015-MINAGRI la regla de disposición de envases vacíos de plaguicidas, y la compara con el literal h del Anexo A. Si difiere, se detiene y pregunta.
3. Claude Code confirma que las dos direcciones de consulta de SENASA responden.

> **Lectura de las normas y decisiones del equipo del 9 de octubre de 2026.**
> 1. **Ley N.º 31110 y su reglamento (Decreto Supremo N.º 005-2021-MIDAGRI).** Confirman la jornada de 8 horas diarias o 48 semanales (artículo 3, literal b, de la ley) y la edad mínima de 18 años (artículo 6, literal a, de la ley y artículo 21 del reglamento). Pero la ley no comprende a los productores organizados en asociaciones (artículo 2, literal d), y el reglamento no se aplica a los socios de asociaciones, comités o cooperativas que no superen cada uno 5 ha de producción (artículo 3.4). Para ellos la edad mínima sale del Código de los Niños y Adolescentes (15 años en labores agrícolas no industriales, con autorización), y la jornada de 8 horas, del artículo 25 de la Constitución. El equipo decidió: **18 años para todos**, como dice el orientador. Cualquier menor deja `menores_de_edad` por atender, también en el trabajo familiar. La cláusula segunda, literal a, del Anexo A se ajusta para no atribuir esa edad a toda la ley: la Ley N.º 31110 la fija en el régimen laboral agrario y la organización la aplica en todas sus parcelas, siguiendo el orientador.
> 2. **Decreto Supremo N.º 001-2015-MINAGRI, artículo 46.** Coincide en lo principal con el literal h del Anexo A: triple lavado, entrega en un centro de acopio, sin quemar, enterrar, abandonar en el campo ni usar en casa. El reglamento pide además inutilizar el envase por medios mecánicos después del triple lavado (46.4), entregarlo a un centro de acopio autorizado sin almacenarlo innecesariamente (46.5) y guardar en lugar seguro los que no se pueden lavar (46.6). El equipo decidió **dejar el literal h y las reglas como están**: `triple_lavado_y_guarda` no deja nada por atender.
> 3. **SENASA.** Las dos consultas respondieron (HTTP 200). Son pantallas web que cargan sus datos por dentro; no hay un servicio documentado, así que el sistema no consulta a SENASA.
> 4. **`kilos_12_meses`** suma el peso seco equivalente de las tandas validadas, el mismo dato que usa el tope por hectárea, porque las tandas llegan en baba o en seco.

### Decisiones pendientes del equipo

- [ ] Confirmar que ninguna respuesta bloquea, tampoco `menores_trabajan = si_contratados` ni `pueden_dejar_el_trabajo = no`.
- [ ] Confirmar que la declaración registrada por el personal no vale sin la hoja firmada.
- [ ] Confirmar los 12 meses de vigencia.
- [ ] Confirmar que un productor sin declaración deja sus parcelas en `observada`.
- [ ] Un asesor legal revisa el texto del Anexo A y la redacción de la pregunta sobre menores antes de usarlos con productores reales.
- [ ] El mismo asesor confirma que el texto de consentimiento vigente cubre compartir la declaración con el comprador en el DEX. Si no la cubre, hace falta una versión nueva del consentimiento.
- [ ] Registrar el valor de la UIT y, con el contador, el jornal de referencia.
- [ ] Volver a cargar las declaraciones de los productores de la simulación, que quedarán sin ella tras la migración.

## 15. Construcción (9 de octubre de 2026)

Registro de Claude Code. Rama `feat/adenda-5-productor`, migración 0017.

### Confirmado antes de construir

Las tres comprobaciones de la sección 14 y las decisiones del equipo están en el recuadro de "Antes de programar": 18 años para todos, el literal h tal cual y `kilos_12_meses` en peso seco equivalente.

### Decisiones de construcción por confirmar

La adenda no las dice.

1. **Ante qué organización.** La declaración se busca ante la organización de la afiliación activa del productor, como ya hace el análisis con `_cooperativa_de`. Si no hay afiliación activa, se usa la organización que registró la parcela.
2. **Lo que el sistema calcula.**
   - `area_total_ha` es la suma de todas las parcelas activas del productor, igual que en su ficha.
   - El `contexto` guarda además los códigos de esas parcelas, para que la hoja y su copia digan siempre lo mismo.
   - `kilos_12_meses` cuenta las tandas validadas en la organización desde el mismo día de hace 12 meses, sin las de DOP anulado.
3. **Estado con dos declaraciones.** Si hay una vigente y otra por firmar, la ficha muestra el estado de la vigente y aparte la por firmar.
   - Los pendientes, el filtro de la lista y el grupo del inicio cuentan a ese productor solo como "por firmar". Así los cuatro casos no se repiten.
   - Una declaración vencida suma el pendiente `sin_declaracion_anual`.
4. **Papeles.**
   - La relación de trabajadores se acepta solo con `quien_trabaja = permanentes`.
   - La declaración de renta se acepta solo si las ventas no son `no`.
   - Otro caso responde 400.
   - Se cargan a la declaración vigente o a la por firmar. El productor carga los suyos desde su cuenta, a su vigente.
   - La hoja firmada no se anula a mano.
5. **Revisión de productos.**
   - La revisión se copia solo al registrar la declaración. Se toma la más reciente de la organización con el mismo nombre normalizado y el mismo tipo, revisada en los últimos 12 meses.
   - La copia conserva la fecha de la consulta original.
   - Cambiar a mano una revisión copiada le quita la marca de copiada.
   - El número de registro de SENASA se guarda solo con "Figura".
6. **Seguimiento.** La nota se escribe sobre la declaración guardada como vigente y va de 50 a 2 000 caracteres.
7. **Requisitos.**
   - Lo que falta se calcula aunque el requisito esté por atender. Por eso un productor con permanentes sin seguro y sin relación deja dos hallazgos (sección 6).
   - Las alertas siguen el estado de cada requisito (sección 8, regla 3).
   - Un requisito es `documentado` solo con un papel cargado. La revisión en SENASA lo deja `sustentado` sin cambiar su nivel.
   - La pantalla muestra la insignia de nivel solo cuando es `documentado`, porque una respuesta siempre es declarada.
   - El jornal se compara con la referencia guardada en el `contexto` de la declaración, no con la de hoy (sección 9, regla 2).
8. **Cuestionario.**
   - Las condiciones de cada pregunta son datos (`cuando`, con cinco reglas). La interfaz repite esas reglas en `frontend/js/declaracion.js` y la API vuelve a validar.
   - Cada pregunta tiene una ayuda en tercera persona para el personal (`ayuda_personal`). No cambia preguntas ni valores: el cuestionario sigue en la versión 1.
9. **Pantalla del productor.**
   - Para renovar, trae marcadas las respuestas de su última declaración.
   - Antes de "Declaro" muestra las cláusulas segunda a sexta y la frase final del Anexo A.
10. **Hoja.**
    - Las preguntas van en tercera persona (de usted).
    - La copia no lleva líneas de firma y dice quién la declaró, cuándo y hasta cuándo vale.
    - El archivo se llama `declaracion-anual-{dni}-para-firmar.pdf` o `-copia.pdf`.
11. **Hallazgos.**
    - Viven en `services/hallazgos/productor.py`.
    - Las referencias de `condiciones_de_trabajo_por_atender` son las de los hechos declarados (de 4.2 a 4.7).
    - El informe no usa la palabra "seguro" (prueba de valoraciones de la Parte 9). Por eso el hecho dice "afiliadas a EsSalud o al SIS".
12. **DOP, versión 6.**
    - `productor.declaracion` va sin la nota de seguimiento, porque el productor ve sus DOP.
    - "No verificado" suma: "La declaración anual es la palabra del productor: la organización no la comprobó en campo."
13. **DEX, versión 3.**
    - El bloque `productores` lleva por productor su nombre, sus parcelas en el lote, su peso, el mismo bloque del DOP y la nota de seguimiento.
    - No lleva DNI. De sus papeles van solo el tipo y la huella.
    - En el cuadro de totales, "Con algo por atender" cuenta los productores con un requisito `por_atender`, no los que están sin sustento.
14. **Configuración de plataforma.**
    - `PUT /admin/configuracion` cambia solo los campos que recibe. La pantalla envía la clasificación del país y los valores de referencia por separado.
    - La UIT va con su año y el jornal con su nota, o ninguno de los dos.
15. **Rutas adicionales.** `GET /productores?declaracion=` acepta `vencida`, `por_vencer`, `por_firmar` y `sin_declaracion`. En la interfaz, `#/productores/{id}/declaracion` abre la ficha en la pestaña Declaración.
16. **Migración.** El trigger de `declaraciones_productor` también impide cambiar `vigente_hasta` una vez puesta.
17. **Escenario de demostración y simulación.**
    - Cada productor queda con la declaración de cuatro preguntas (familia, sin menores, sin agroquímicos y ventas de hasta 75 UIT), registrada por el operador y con la hoja firmada del día.
    - El paquete de simulación suma una hoja de muestra por productor y dos pasos del guion: registrar la declaración y cargar la hoja firmada.

### Para el equipo

1. Al desplegar, el comando de inicio de Render aplica la migración 0017. Ningún productor recibe una declaración: sus parcelas habilitadas pasan a observadas hasta que declare (sección 8, regla 5). Eso incluye las de la simulación, cuyo guion ya trae los pasos.
2. Registrar en Plataforma › Configuración el valor de la UIT y, con el contador, el jornal de referencia.
3. Los pendientes de la sección 14.

## Anexo A — Declaración jurada anual del productor

Versión 1, redactada para revisión de un asesor legal. Lo que va entre llaves lo llena el sistema; las líneas, el productor. El productor que declara desde su cuenta lee las cláusulas segunda a sexta antes de tocar "Declaro".

> **DECLARACIÓN JURADA ANUAL DEL PRODUCTOR**
> **sobre el trabajo en sus parcelas, el uso de agroquímicos y sus obligaciones tributarias**
>
> Yo, {nombres y apellidos del productor}, identificado(a) con DNI N.º {dni}, con domicilio en {dirección postal}, productor(a) que entrega cacao a {razón social de la organización}, con RUC N.º {ruc de la organización}, y que conduce {número} parcela(s) registrada(s) con los códigos {códigos de las parcelas}, que suman {área total} hectáreas, en pleno uso de mis facultades y de manera libre y voluntaria, **DECLARO BAJO JURAMENTO** lo siguiente:
>
> **PRIMERO. De mis respuestas.** A las preguntas que me formuló la organización sobre los últimos doce meses, respondo:
>
> {tabla con cada pregunta mostrada y su respuesta}
>
> **SEGUNDO. De la información que recibí.** La organización me ha informado, y así lo entiendo, que de acuerdo con la legislación peruana:
>
> a) en el régimen laboral agrario no debe trabajar ninguna persona menor de dieciocho (18) años, y la organización aplica esa edad en todas sus parcelas, también al trabajo de la familia;
>
> b) la jornada de trabajo no debe pasar de ocho (8) horas diarias o cuarenta y ocho (48) horas semanales;
>
> c) quien contrata trabajadores, aunque sea por días y de palabra, debe pagarles no menos que la remuneración mínima vigente, afiliarlos al seguro de salud y contratarles el seguro de vida de ley;
>
> d) quien contrata trabajadores debe darles condiciones seguras y el equipo de protección que su labor requiera, en especial cuando aplican agroquímicos;
>
> e) toda persona es libre de dejar su trabajo, y nadie puede ser obligado a trabajar ni retenido por deudas, documentos o pagos pendientes;
>
> f) a igual trabajo corresponde igual pago, sin distinción entre hombres y mujeres, y la madre y el padre trabajadores tienen derecho a su descanso por el nacimiento de un hijo;
>
> g) solo deben usarse plaguicidas y fertilizantes registrados ante el SENASA;
>
> h) los envases vacíos de plaguicidas no se queman, no se entierran, no se botan ni se reutilizan: se someten al triple lavado y se entregan en un centro de acopio.
>
> **TERCERO. De mis compromisos.** Me comprometo a: (i) comunicar a la organización cualquier cambio en lo declarado, dentro de los treinta (30) días calendario de ocurrido; (ii) entregar los documentos que sustenten mis respuestas cuando la organización me los pida; y (iii) recibir las visitas que la organización programe a mis parcelas para conocer lo declarado.
>
> **CUARTO. De la finalidad.** Formulo esta declaración para que {razón social de la organización} sustente la legalidad de la producción del cacao que le entrego. Autorizo que la conserve y la ponga a disposición de sus compradores y de las autoridades competentes, para los fines de la diligencia debida que exige el Reglamento (UE) 2023/1115.
>
> **QUINTO. De la vigencia.** Esta declaración vale por doce (12) meses desde su fecha. La renovaré al vencer ese plazo o antes, si lo declarado cambia.
>
> **SEXTO. De la veracidad.** Lo declarado responde a la verdad. Conozco que, de comprobarse su falsedad, asumo las responsabilidades civiles y penales que correspondan según la legislación peruana, y que la organización podrá dejar de recibir mi cacao.
>
> Esta declaración no reemplaza las obligaciones del declarante ante las autoridades de trabajo, tributarias, sanitarias ni ambientales.
>
> __________, ____ de __________ de 20____.
>
> Firma: ______________________   Huella dactilar: [    ]
> {nombres y apellidos del productor} · DNI N.º {dni}
>
> **Testigo a ruego** (solo si el declarante no sabe o no puede firmar; el declarante pone su huella)
> Nombre: ______________________   DNI N.º __________   Firma: __________
>
> **Recibido por la organización**
> Nombre: ______________________   Cargo: ______________   Fecha: ____/____/______   Firma: __________
>
> Referencias: Ley N.º 31110, Ley del régimen laboral agrario, y su reglamento, Decreto Supremo N.º 005-2021-MIDAGRI; Decreto Supremo N.º 001-2015-MINAGRI, Reglamento del Sistema Nacional de Plaguicidas de Uso Agrícola; Documento orientador para la diligencia debida de la legalidad del café y cacao en el marco del EUDR, requisitos 2.3, 2.7, 4.1 a 4.7, 5.2 a 5.4 y 7.1. Versión 1.

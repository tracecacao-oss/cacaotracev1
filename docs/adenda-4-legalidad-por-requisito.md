# Adenda 4 — Legalidad de la parcela por requisito (Partes 4 y 9)

Fecha: 9 de octubre de 2026. Decisión del equipo.

Esta adenda modifica la parte documentaria de la parcela en `docs/especificacion.md`: su expediente legal y su compuerta (Parte 4), y lo que de la parcela llega a los hallazgos y al DEX (Parte 9). Donde difiera de la especificación o de las adendas anteriores, manda esta adenda.

Cubre solo la parcela. Lo que el orientador pide al productor y a la organización va en adendas posteriores. Hasta entonces no cambian el requisito `productor_listo`, el expediente de la organización ni los documentos de embarque.

No cambia el análisis de cobertura forestal, la regla que decide cuándo salta una alerta, la revisión de imágenes ni la exclusión de una parcela.

La fuente es el "Documento orientador para la diligencia debida de la legalidad del café y cacao en el marco del EUDR" (MIDAGRI, MINCETUR y ADEX; European Forest Institute, 2026). En adelante, "el orientador". El propio documento dice que no es jurídicamente vinculante ni asesoría legal.

## 1. Qué cambia y por qué

Hoy toda parcela tiene las mismas 7 casillas y lo que no aplica se llena con una exención. El orientador dice otra cosa: cada requisito legal aplica solo en ciertos casos, y pide más o menos prueba según qué tan bien se cumple en el Perú.

| Antes | Ahora |
| --- | --- |
| 7 casillas fijas por parcela | Requisitos que se activan según el perfil legal de la parcela |
| Exención motivada para lo que no aplica | El sistema calcula "no aplica" desde el perfil. Ya no hay exenciones |
| Tenencia: título inscrito o constancia de posesión | Tenencia: un sustento de una lista más amplia, que incluye una declaración jurada con plantilla |
| Casillas `sunafil`, `sunat` y `zonificacion` | Salen de la parcela. La zonificación la responde el cruce con el mapa de SERFOR. Lo laboral y lo tributario pasan a la adenda del productor |
| Nada se cruza con mapas oficiales | Cinco preguntas del perfil las responde el sistema cruzando la parcela con seis capas oficiales |

## 2. Cómo valora el orientador cada requisito

El orientador revisa 40 requisitos legales en siete categorías y los pasa por tres preguntas.

1. **¿Es pertinente?** Lo es si aplica a la zona de producción, si se ajusta a un sector de pequeños productores y si tiene normas claras y exigibles. Lo que ya está cubierto por otro requisito más preciso se descarta. Quedan 32 pertinentes; uno de ellos es solo para café.
2. **¿Cuál es su nivel de implementación en el Perú?** Alto, si en general se respeta y los incumplimientos son esporádicos. Bajo, si hay ilegalidad frecuente o si no hay datos suficientes.
3. **¿Qué diligencia pide?** Aligerada si el nivel es alto. Estándar si es bajo.

| Nivel | Diligencia | Qué hace CacaoTrace |
| --- | --- | --- |
| Alto | Aligerada | Mira una señal del perfil. Solo si la señal se activa pide un sustento |
| Bajo | Estándar | Pide la información siempre, por documento o por declaración |
| No pertinente | Ninguna | No pide nada |

### Regla de efecto

Decisión del equipo del 9 de octubre de 2026. Una parcela no se habilita solo en tres casos:

1. Le falta la base: el perfil legal o un sustento de tenencia.
2. Le falta un permiso obligatorio: acuerdo de conservación dentro de un área natural protegida, título habilitante en tierra forestal o de protección, o acuerdo con la comunidad en tierra comunal.
3. Tiene una incidencia de tenencia abierta.

Todo lo demás no bloquea. Se muestra, exige nota al habilitar y llega al informe de hallazgos.

El sistema sigue sin concluir. Ningún texto dice que una parcela "cumple" la legalidad: dice qué requisitos le aplican y con qué se sustentan.

## 3. Los 40 requisitos del orientador

La numeración es la del Anexo 2 del orientador. La sección 14 lista las diferencias entre ese anexo y su tabla principal.

### 3.1 Requisitos de la parcela

| Ref. | Requisito | Nivel y diligencia | Señal que lo activa | Sustento | Si falta |
| --- | --- | --- | --- | --- | --- |
| 1.1 | Tenencia individual por propiedad o posesión | Alto, aligerada | Siempre | Título, constancia de posesión, certificado de información catastral o declaración jurada | Bloquea si no hay ninguno |
| 1.2 | Uso de tierra privada ajena por contrato escrito o verbal | Alto, aligerada | `tenencia_tipo = uso_por_acuerdo` | Contrato de arrendamiento, comodato o cesión en uso, o declaración jurada | Bloquea si no hay ninguno |
| 1.3 | Tenencia colectiva de la comunidad | Alto, aligerada | `en_tierra_comunal = si` | Dato: nombre de la comunidad y si está inscrita | No bloquea. Hallazgo |
| 1.4 | Producir en tierra comunal por acuerdo con la comunidad | Alto, aligerada | `en_tierra_comunal = si` | Miembro: constancia de la comunidad o declaración jurada. No miembro: acta de asamblea, contrato o constancia de la comunidad | Bloquea |
| 2.1 | Dentro de un área natural protegida, con acuerdo de conservación | Alto, aligerada | `en_anp = dentro` | Acuerdo de conservación firmado por la jefatura del área | Bloquea |
| 2.2 | En tierra de aptitud forestal o de protección, con título habilitante | Bajo, estándar | `en_tierra_forestal = si` | CCUSAF | Bloquea, salvo la excepción de la sección 5.2 |
| 2.4 | Riego con licencia o permiso de agua | Alto, aligerada | `usa_riego = si` | Licencia o permiso de uso de agua, o certificado de la organización de usuarios | No bloquea. Hallazgo |
| 2.5 | No cultivar en fajas marginales | Alto, aligerada | `junto_a_cuerpo_de_agua = si` | Ninguno. Nota con la distancia del cultivo al agua | No bloquea. Hallazgo |
| 2.10 y 2.11 | Conversión de tierras en los plazos y condiciones de ley | Estándar | `en_tierra_forestal = si` | Autorización de cambio de uso, o título o constancia anteriores al 10 de enero de 2024 | Se evalúa junto con 2.2 |
| 2.12 | Instrumento de gestión ambiental cuando la ley lo exige | Alto, aligerada | Área total de 10 ha o más | De 10 a 50 ha: Ficha Técnica Ambiental. Más de 50 ha: DIA, EIA-sd, EIA-d o PAMA | No bloquea. Hallazgo |
| 2.13 | No afectar especies amenazadas ni biodiversidad | Alto, aligerada | `en_anp` distinto de `no` | Ninguno | Se informa dentro del hallazgo del área protegida |
| 3.1 | Respeto del patrimonio cultural | Alto, aligerada | `en_patrimonio_cultural = si` | Ninguno. Nota | No bloquea. Hallazgo |
| 3.3 | El instrumento ambiental es público | Alto, aligerada | La misma de 2.12 | El de 2.12 | Sin efecto propio |
| 3.4 | Reparar los daños ambientales causados | Alto, aligerada | Incidencia ambiental registrada | Nota de cómo se resolvió | No bloquea. Hallazgo |

### 3.2 Requisitos que quedan para otras adendas

Esta adenda construye solo lo de la parcela.

| Ref. | De quién son | Dónde se tratarán |
| --- | --- | --- |
| 2.3, 2.7, 4.1 a 4.7, 5.2 a 5.5 y 7.1 | Del productor: agroquímicos, envases, trabajadores, menores de edad y tributos | Adenda del productor |
| 7.1, 7.2 y 7.3 | De la organización y del lote: tributos, aduanas e integridad | Adenda de la organización y el lote |

### 3.3 Requisitos que no se piden

| Ref. | Requisito | Por qué |
| --- | --- | --- |
| 1.5 | Expropiación conforme a ley | No pertinente: no hay expropiaciones para cultivar café o cacao |
| 2.6 | Vertimientos a fuentes de agua | Solo para café |
| 2.8 | Estándares de calidad ambiental de suelo | No pertinente: lo cubre 2.12 |
| 2.9 | Emisiones dentro de los límites | No pertinente: no hay límite para la actividad agrícola |
| 3.2 | Derecho de las comunidades a un ambiente sano | No pertinente: lo cubre la categoría 2 |
| 3.4 bis | Instrumento ambiental con participación ciudadana | No pertinente: las parcelas están bajo el umbral de 50 ha |
| 4.8 | Libertad sindical | No pertinente: agricultura familiar sin relación de subordinación |
| 5.1 | Respeto general de los derechos humanos | No pertinente: lo cubren otros requisitos |
| 6.1 | Consulta previa | No pertinente: el Estado no autoriza cambios de uso para café o cacao |

## 4. Perfil legal de la parcela

El perfil son nueve datos. De ellos sale qué requisitos aplican. Sin perfil completo la parcela no se habilita.

| Variable | Pregunta en pantalla | Valores | Fuente que nombra el orientador |
| --- | --- | --- | --- |
| `tenencia_tipo` | ¿Qué derecho tiene el productor sobre esta tierra? | `propietario`, `poseedor`, `uso_por_acuerdo`, `comunal_miembro`, `comunal_tercero`, `titulo_habilitante` | Ninguna. Se declara |
| `en_anp` | ¿La parcela está en un área natural protegida? | `no`, `zona_de_amortiguamiento`, `dentro` | Visor de SERNANP |
| `en_tierra_forestal` | ¿Está en tierra de aptitud forestal o de protección? | `no`, `si`, `sin_zonificacion` | GeoSERFOR e IDE-i de SERFOR |
| `en_tierra_comunal` | ¿Está en tierra de una comunidad campesina o nativa? | `no`, `si` | Sistema de Catastro Rural y Base de Datos de Pueblos Indígenas |
| `junto_a_cuerpo_de_agua` | ¿Colinda con un río, quebrada, lago o laguna? | `no`, `si` | Mapa de fajas marginales de la ANA |
| `en_patrimonio_cultural` | ¿Se superpone con un sitio arqueológico o de patrimonio cultural? | `no`, `si` | SIGDA, del Ministerio de Cultura |
| `usa_riego` | ¿Riega el cultivo o depende solo de la lluvia? | `no`, `si` | Encuesta |
| `anio_instalacion_cultivo` | ¿En qué año se instaló el cacao en esta parcela? | Año de 4 dígitos | "Evaluar el año de antigüedad de las parcelas" |
| `reserva_bosque_30` | ¿Mantiene con bosque al menos 30 % del área? | `si`, `no`, `sin_bosque` | Ley N.º 31973 |

1. `reserva_bosque_30` solo se pregunta cuando aplica la excepción de la sección 5.2.
2. Con `en_tierra_comunal = si` se guardan además el nombre de la comunidad y su tipo (`campesina` o `nativa`), que trae la capa cuando el valor viene del cruce. Si está inscrita en Registros Públicos (`si`, `no`, `no_se_sabe`) lo declara una persona.
3. Con `en_anp` distinto de `no` se guarda el nombre y la categoría del área, que trae la capa.
4. Con `en_anp = dentro` o `en_tierra_forestal = si`, la interfaz avisa si `tenencia_tipo` no es `titulo_habilitante`. No lo impide.
5. El área total no se pregunta. En un polígono la calcula el sistema desde la geometría, como hoy (`area_calculada_ha`). Solo en una parcela de tipo punto es el área que se declaró al registrarla.

### Cómo se mide cada variable

Cinco variables las responde el sistema, cruzando la geometría de la parcela con mapas oficiales: `en_anp`, `en_tierra_forestal`, `en_tierra_comunal`, `junto_a_cuerpo_de_agua` y `en_patrimonio_cultural`. Las otras cuatro las declara una persona, porque ningún mapa las conoce.

| Origen | Significado | Nivel de verificación |
| --- | --- | --- |
| `cruce` | Lo calculó el sistema con una capa oficial. Guarda la capa, la fecha de consulta y lo que encontró | `verificado_en_fuente` |
| `declarado` | Lo respondió una persona | `declarado` |

1. El cruce corre solo al guardar la parcela y cada vez que cambia su geometría. Lo define la sección 10.
2. Si el cruce de una variable falla porque el servicio no responde, una persona puede declararla para no detener el trabajo. La tarea diaria vuelve a intentar el cruce.
3. Los mapas oficiales están incompletos. Por eso, cuando el cruce dice `no`, una persona puede declarar `si`, con una nota. Cuando el cruce dice `si` o `dentro`, nadie puede bajarlo a `no`: quien crea que el mapa se equivoca registra una incidencia de tipo `otra`.
4. Entre un cruce y una declaración vigentes manda el valor más exigente. Se guardan y se muestran los dos.
5. Declaran el `admin_cooperativa` y el `operador`. El productor ve su perfil y no lo edita.
6. Cada valor nuevo guarda una fila nueva y conserva la anterior. La compuerta se evalúa otra vez.

### Tabla `parcela_variables`

| Columna | Tipo | Regla |
| --- | --- | --- |
| `parcela_id` | uuid | Referencia a `parcelas` |
| `variable` | text | Uno de los nueve códigos |
| `valor` | text | Un valor admitido por la variable |
| `detalle` | jsonb | Datos adicionales: comunidad, nombre del área protegida |
| `origen` | text | `declarado` o `cruce` |
| `fuente` | text | Capa y fecha de consulta, cuando el origen es `cruce` |
| `registrada_por`, `registrada_en` | uuid, timestamptz | Quién y cuándo. `registrada_por` es nulo si lo calculó el sistema |
| `vigente` | boolean | Solo una fila vigente por parcela y variable |

Las filas no se editan ni se borran. Una fila nueva deja la anterior con `vigente = false`.

## 5. Requisitos de la parcela: catálogo y estados

El catálogo vive en `backend/app/catalogos/requisitos_legales.py`. Cada requisito lleva su código, las referencias del orientador, el nivel, la diligencia, si bloquea y los tipos de documento que lo sustentan.

| Código | Ref. | Aplica cuando | Bloquea | Sustentos aceptados |
| --- | --- | --- | --- | --- |
| `tenencia` | 1.1, 1.2 | Siempre | Sí | Según `tenencia_tipo`, sección 5.1 |
| `acuerdo_comunal` | 1.3, 1.4 | `en_tierra_comunal = si` | Sí | `constancia_comunal`, `acta_comunal` o `contrato_de_uso`. Con `tenencia_tipo = comunal_miembro` también vale `declaracion_jurada_tenencia`, porque el orientador no exige documento formal al miembro |
| `area_protegida` | 2.1, 2.13 | `en_anp = dentro` | Sí | `acuerdo_conservacion` |
| `tierra_forestal` | 2.2, 2.10, 2.11 | `en_tierra_forestal = si` | Sí | `cusaf`, `autorizacion_cambio_uso`, o la excepción de la sección 5.2 |
| `agua_de_riego` | 2.4 | `usa_riego = si` | No | `licencia_agua` |
| `instrumento_ambiental` | 2.12, 3.3 | Área total de 10 ha o más | No | `ficha_tecnica_ambiental` hasta 50 ha; `instrumento_ambiental` sobre 50 ha |
| `faja_marginal` | 2.5 | `junto_a_cuerpo_de_agua = si` | No | Ninguno. Nota obligatoria |
| `patrimonio_cultural` | 3.1 | `en_patrimonio_cultural = si` y sin `cusaf` vigente | No | Ninguno. Nota obligatoria |

### Estados de un requisito

| Estado | Condición |
| --- | --- |
| `sin_dato` | Falta la variable del perfil que lo decide |
| `no_aplica` | El perfil dice que no aplica |
| `sustentado` | Tiene un sustento vigente, o la nota cuando no pide documento |
| `por_vencer` | Su sustento vence en 30 días o menos |
| `vencido` | Solo tiene sustentos vencidos |
| `sin_sustento` | Aplica y no tiene sustento |

1. El estado se calcula al consultar, con la fecha del día, como hoy las casillas.
2. Cada requisito sustentado lleva su nivel de verificación: `declarado`, `documentado` o `verificado_en_fuente`.
3. Las palabras "cumple", "conforme" y "aprobado" no se usan para un requisito.
4. `en_anp = zona_de_amortiguamiento` no activa `area_protegida`. Genera una alerta, porque el orientador pide atención especial en esas zonas.

### 5.1 Sustentos de tenencia

| `tenencia_tipo` | Significado | Sustentos aceptados |
| --- | --- | --- |
| `propietario` | Dueño de la tierra | `titulo_sunarp`, `titulo_no_inscrito`, `certificado_catastral`, `declaracion_jurada_tenencia` |
| `poseedor` | La posee, con constancia o sin ella | `constancia_posesion`, `certificado_catastral`, `declaracion_jurada_tenencia` |
| `uso_por_acuerdo` | Usa tierra privada de otro por arrendamiento, préstamo, cesión o acuerdo familiar | `contrato_de_uso`, `declaracion_jurada_tenencia` |
| `comunal_miembro` | Es miembro de la comunidad dueña de la tierra | `constancia_comunal`, `declaracion_jurada_tenencia` |
| `comunal_tercero` | No es miembro y usa tierra de la comunidad | `acta_comunal`, `contrato_de_uso` |
| `titulo_habilitante` | Tierra pública con cesión en uso o acuerdo de conservación | `cusaf`, `acuerdo_conservacion` |

1. Basta un sustento vigente. Cuenta el de mejor nivel.
2. Una declaración jurada es un archivo cargado, pero su nivel es `declarado`: es la palabra del productor.
3. Con `declaracion_jurada_tenencia` como único sustento, la parcela recibe la alerta `tenencia_sin_documento_formal`.
4. La alerta `tenencia_solo_posesion` se mantiene para la constancia de posesión sin título.
5. Un `comunal_tercero` no puede sustentarse con declaración jurada: el orientador pide la decisión de la asamblea.

### 5.2 Tierra forestal: excepción de la Ley N.º 31973

El orientador recoge que los predios privados con título o constancia de posesión emitidos antes del 10 de enero de 2024, sin masa boscosa y con actividad agropecuaria, quedan exentos de la clasificación de tierras. Si tienen masa boscosa deben reservar 30 % del área.

1. Con `en_tierra_forestal = si`, `tierra_forestal` queda `sustentado` si hay un `cusaf` o una `autorizacion_cambio_uso` vigentes.
2. También queda `sustentado` si hay un `titulo_sunarp`, un `titulo_no_inscrito` o una `constancia_posesion` vigentes con `fecha_emision` anterior al 10 de enero de 2024. En ese caso se pregunta `reserva_bosque_30` y la parcela recibe la alerta `tierra_forestal_por_excepcion`.
3. En cualquier otro caso queda `sin_sustento` y bloquea.
4. Con `en_tierra_forestal = sin_zonificacion` el requisito queda `no_aplica` y la parcela recibe la alerta `zonificacion_forestal_desconocida`.
5. Antes de programar esta regla, Claude Code lee la disposición complementaria final de la Ley N.º 31973 en El Peruano y confirma la fecha y las condiciones. Si difieren de este texto, se detiene y pregunta.

> **Lectura de la ley y decisiones del equipo del 9 de octubre de 2026.** La única disposición complementaria final de la Ley N.º 31973 (El Peruano, 11 de enero de 2024) difiere de este texto en tres puntos. El equipo decidió:
> 1. **Fecha de corte.** La ley habla de títulos o constancias emitidos "con anterioridad a la vigencia de la presente ley". Se dio el 10 y se publicó el 11 de enero de 2024, así que rige desde el 12 de enero de 2024. Valen los documentos con `fecha_emision` anterior al **12 de enero de 2024**, no al 10.
> 2. **Ley N.º 31145.** La ley también exceptúa a los predios "que se encuentren dentro de los alcances de la Ley 31145" (saneamiento físico-legal y formalización de predios rurales a cargo de los gobiernos regionales), sin fecha. Se agrega el documento `constancia_saneamiento_31145`: la constancia del gobierno regional de que el predio está en ese saneamiento. Sustenta la excepción igual que un título anterior a la fecha de corte.
> 3. **Quién emite.** La ley pide títulos o constancias "emitidas por la autoridad competente". Sustentan la excepción el `titulo_sunarp`, la `constancia_posesion` y el `titulo_no_inscrito` cuando es un **título de formalización**. Una minuta o escritura privada no la sustenta: el `titulo_no_inscrito` guarda su clase (`titulo_formalizacion`, `escritura_publica` o `minuta`) y solo `titulo_formalizacion` cuenta.
> 4. La ley exige además que el predio "no contenga masa boscosa" y "desarrolle actividad agropecuaria", y dice que la reserva de 30 %, si falta, "deberá ser compensada de manera progresiva". El sistema no lo comprueba: lo pregunta (`reserva_bosque_30`) y lo lleva al hallazgo `tierra_forestal_por_excepcion`.

### 5.3 Incidencias de la parcela

El orientador pide consultar si hay conflictos, litigios o denuncias, y solo entonces profundizar. El sistema guarda lo que la organización encuentre.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `parcela_id` | uuid | Referencia a `parcelas` |
| `tipo` | text | `tenencia`, `ambiental` u `otra` |
| `descripcion` | text | Qué se encontró. Mínimo 50 caracteres |
| `fuente` | text | De dónde salió: autoridad local, Defensoría del Pueblo, OEFA, prensa, vecino |
| `estado` | text | `abierta` o `cerrada` |
| `registrada_por`, `registrada_en` | uuid, timestamptz | Quién y cuándo |
| `cierre_nota`, `cerrada_por`, `cerrada_en` | text, uuid, timestamptz | Cómo se resolvió. La nota es obligatoria al cerrar |

1. La tabla se llama `parcela_incidencias`. Registra el `operador` o el `admin_cooperativa`; cierra solo el `admin_cooperativa`.
2. Una incidencia de tipo `tenencia` en estado `abierta` impide habilitar y pasa la parcela a `observada`.
3. Una incidencia `ambiental` u `otra` abierta no bloquea. Genera alerta y hallazgo.
4. Las incidencias no se borran.

## 6. Tipos de documento

### Parcela

| Código | Documento | Registro consultable |
| --- | --- | --- |
| `titulo_sunarp` | Título de propiedad inscrito en SUNARP. Se mantiene | Sí |
| `titulo_no_inscrito` | Título de propiedad no inscrito: escritura, minuta o título de formalización | No |
| `constancia_posesion` | Constancia de posesión. Se mantiene | No |
| `certificado_catastral` | Certificado de información catastral del ente de formalización regional | No |
| `contrato_de_uso` | Contrato de arrendamiento, comodato o cesión en uso | No |
| `declaracion_jurada_tenencia` | Declaración jurada de tenencia firmada por el productor | No |
| `constancia_comunal` | Constancia de la comunidad sobre el uso de su tierra | No |
| `acta_comunal` | Acta de asamblea comunal que autoriza el uso | No |
| `acuerdo_conservacion` | Acuerdo de conservación con la jefatura del área protegida | No |
| `cusaf` | Contrato de cesión en uso para sistemas agroforestales. Se mantiene | Sí |
| `autorizacion_cambio_uso` | Autorización de cambio de uso o de desbosque. Reemplaza a `autorizacion_serfor` | No |
| `constancia_saneamiento_31145` | Constancia del gobierno regional de que el predio está en saneamiento por la Ley N.º 31145. Decisión del 9 de octubre de 2026, sección 5.2 | No |
| `licencia_agua` | Licencia o permiso de uso de agua, o certificado de la organización de usuarios | No |
| `ficha_tecnica_ambiental` | Ficha Técnica Ambiental | No |
| `instrumento_ambiental` | DIA, EIA-sd, EIA-d o PAMA | No |

1. Los valores de "Registro consultable" son iniciales. Claude Code los confirma con fuentes oficiales antes de fijarlos, como hizo el 5 de octubre.
2. `declaracion_jurada_tenencia`, `constancia_comunal` y `acta_comunal` no exigen número. Sí exigen fecha de emisión, que es la fecha de firma.
3. `declaracion_jurada_tenencia` vence sola a los 12 meses de su firma, según `DECLARACION_VIGENCIA_MESES`.
4. Los documentos `sunafil`, `sunat` y `zonificacion` ya cargados se conservan y se ven como "documentos anteriores". No sustentan ningún requisito y no se pueden cargar nuevos. Hasta la adenda del productor, lo laboral y lo tributario no se piden.
5. Las exenciones ya declaradas se conservan como historial. No se pueden declarar nuevas y ya no cubren nada.

## 7. Declaración jurada de tenencia: plantilla para firmar

Decisión del equipo: cuando el productor no tiene un documento formal, el sistema le da la declaración lista para firmar.

1. En el requisito `tenencia`, si no hay un sustento formal, aparece el botón "Descargar declaración jurada para firmar".
2. `GET /parcelas/{id}/plantillas/declaracion-jurada-tenencia` devuelve un PDF con los datos del productor, de la parcela y de la organización ya escritos, y con la opción de la cláusula segunda marcada según `tenencia_tipo`.
3. El PDF se arma con fpdf2 en `backend/app/pdf/declaracion_tenencia.py`. Lo que el sistema no sabe queda como línea en blanco.
4. La plantilla solo se ofrece para `propietario`, `poseedor`, `uso_por_acuerdo` y `comunal_miembro`.
5. El productor la firma y pone su huella. La copia firmada se carga, en foto o escaneada, como `declaracion_jurada_tenencia`.
6. La descargan el personal y el productor desde su cuenta. La plantilla no se guarda como documento; la que cuenta es la firmada.
7. El texto es el del Anexo A, versión 1, y vive en un archivo de textos con su número de versión. El PDF imprime la versión al pie.
8. `GET /parcelas/{id}/plantillas/constancia-comunal` hace lo mismo con el Anexo B, para toda parcela con `en_tierra_comunal = si`.
9. En una cooperativa de demostración, la plantilla lleva la misma marca de agua que los demás PDF.

## 8. Compuerta de habilitación

El requisito `expediente_completo` se reemplaza por estos cuatro. Los demás requisitos de la compuerta, incluido `productor_listo`, no cambian.

| Requisito | Se cumple cuando |
| --- | --- |
| `perfil_legal_completo` | Las ocho variables base tienen valor vigente, y `reserva_bosque_30` cuando aplica |
| `tenencia_sustentada` | El requisito `tenencia` está `sustentado` o `por_vencer` |
| `permisos_obligatorios` | `acuerdo_comunal`, `area_protegida` y `tierra_forestal` están `no_aplica`, `sustentado` o `por_vencer` |
| `sin_conflicto_de_tenencia` | No hay incidencias de tipo `tenencia` en estado `abierta` |

1. Los requisitos que no bloquean aparecen como alertas cuando están `sin_sustento` o `vencido`. Con cualquier alerta, la nota al habilitar sigue siendo obligatoria, con 50 caracteres como mínimo.
2. Una parcela `habilitada` pasa a `observada` cuando deja de cumplir cualquiera de estos requisitos: vence un sustento, cambia una variable o se abre una incidencia de tenencia.
3. Las alertas nuevas de la parcela son `tenencia_sin_documento_formal`, `tierra_forestal_por_excepcion`, `zonificacion_forestal_desconocida`, `en_zona_de_amortiguamiento`, `requisito_sin_sustento` e `incidencia_abierta`.
4. Tras la migración, las parcelas ya habilitadas no tienen perfil y pasan a `observada` hasta completarlo. Los DOP ya emitidos no se tocan.

## 9. Datos y migración

1. Tablas nuevas: `parcela_variables` y `parcela_incidencias`. Las dos con RLS activado y sin políticas.
2. Variables nuevas del backend: `DECLARACION_VIGENCIA_MESES`, con valor inicial 12; `DISTANCIA_CUERPO_AGUA_M`, con valor inicial 100; y `CAPAS_LEGALES_ACTIVAS`, con las seis capas de la sección 10.
3. Se agregan los tipos de documento de la sección 6.
4. `autorizacion_serfor` se renombra a `autorizacion_cambio_uso` sin perder archivos.
5. El servicio nuevo `backend/app/services/legalidad.py` calcula el perfil, los requisitos y sus estados. `services/expediente.py` conserva solo el cotejo en fuente y la validación de datos legales.
6. La migración no inventa valores: ninguna parcela recibe un perfil por defecto.

## 10. Cruce automático con capas oficiales

El cruce es parte de esta adenda, no una etapa posterior. Los seis servicios de la tabla son públicos, no piden clave y respondieron el 9 de octubre de 2026 a consultas de prueba hechas fuera del sistema. Antes de integrarlos, Claude Code los confirma desde su entorno, lee el metadato de cada capa (`?f=pjson`) y revisa sus condiciones de uso. Si alguno difiere de esta tabla, se detiene y pregunta.

| Variable | Capa oficial | Servicio y capas | Regla |
| --- | --- | --- | --- |
| `en_anp` | Áreas naturales protegidas de administración nacional y zonas reservadas, de SERNANP | `https://geoservicios.sernanp.gob.pe/arcgis/rest/services/sernanp_visor/servicio_descarga/MapServer`, capas 1 y 2 | Si se superpone: `dentro`, con el nombre y la categoría del área |
| `en_anp` | Zonas de amortiguamiento, de SERNANP | El mismo servicio, capa 8 | Si no está dentro y se superpone: `zona_de_amortiguamiento` |
| `en_tierra_forestal` | Zonificación forestal, de SERFOR | `https://geo.serfor.gob.pe/geoservicios/rest/services/Servicios_OGC/Zonificacion_Forestal/MapServer`, capa 0 | Si se superpone: `si`, con categoría, subcategoría y resolución. Si no se superpone y su departamento tiene zonificación en la capa: `no`. Si su departamento no tiene: `sin_zonificacion`. Ver la nota de abajo |
| `en_tierra_comunal` | Comunidades nativas y campesinas, en el geoportal de la IDEP (IGN) | `https://www.idep.gob.pe/geoportal/rest/services/INSTITUCIONALES/COMUNIDADES_NATIVAS/MapServer`, capas 0 y 1 | Si se superpone: `si`, con el nombre y el tipo de comunidad |
| `junto_a_cuerpo_de_agua` | Hidrografía de la carta nacional 1:100 000, del IGN | `https://www.idep.gob.pe/geoportal/rest/services/SERVICIOS_IGN/HIDROGRAFIA_100K/MapServer`, capas 0, 1 y 2 | Si el lindero está a `DISTANCIA_CUERPO_AGUA_M` metros o menos de un río o un lago: `si`, con la distancia y el nombre |
| `en_patrimonio_cultural` | Monumentos arqueológicos prehispánicos delimitados, del SIGDA del Ministerio de Cultura | `https://sigda.cultura.gob.pe/sigda/rest/services/v_3/maps_delimitado/MapServer`, capa 0 | Si se superpone: `si`, con el nombre del monumento |

> **Lectura de los metadatos y decisiones del equipo del 9 de octubre de 2026 sobre la zonificación forestal.**
> 1. La capa clasifica todo el territorio de un departamento zonificado, también las chacras. Tiene cinco categorías (`CATZFO`) con sus subcategorías (`SCAZFO`), y sus significados están en el metadato de la capa (`types`). Las parcelas agrícolas de la simulación caen en la 605, "Área agropecuaria".
> 2. Solo cuentan como tierra de aptitud forestal o de protección las categorías **601 a 604**: producción permanente, protección y conservación ecológica, recuperación y tratamiento especial. Quedan fuera la **605** (área agropecuaria) y la subcategoría **60402** (producción agroforestal y silvopastoril). Superponerse solo con esas da `en_tierra_forestal = no`, y la categoría se guarda en `detalle` y se muestra como dato.
> 3. La regla vale para todo el país. Un departamento "tiene zonificación en la capa" si la capa le clasifica también las chacras: si tiene polígonos de la categoría 605. El sistema lo pregunta a la propia capa, sin una lista fija. El 9 de octubre eran San Martín (RM N.º 039-2020-MINAM) y Ucayali (RM N.º 0046-2024-MIDAGRI-DM). Amazonas, Huánuco, Junín, Loreto y Madre de Dios solo tenían polígonos de protección (602) o de reservas indígenas (60401): ahí una parcela sin superposición queda `sin_zonificacion`.

### Reglas del cruce

1. Hay superposición cuando el área común es de al menos 0,05 ha o de al menos 5 % de la parcela, igual que entre parcelas. Menos que eso se guarda como roce de lindero y no cambia la variable.
2. Una parcela de tipo punto se cruza como círculo con su área declarada, y el valor queda marcado como aproximación.
3. El cruce corre en la cola del trabajador que ya existe, al crear la parcela y al cambiar su geometría. El botón "Volver a cruzar" lo repite a pedido.
4. La tarea diaria repite los cruces con más de `ANALISIS_VIGENCIA_DIAS` días y los que fallaron. Un cruce antiguo no bloquea: conserva su valor y su fecha.
5. Cada resultado guarda una fila en `parcela_variables` con `origen = cruce`, la capa y la fecha en `fuente`, y en `detalle` lo que encontró: nombre, categoría, área común o distancia.
6. A los servicios se envía solo la geometría. Nunca nombres, DNI ni datos de la organización.
7. Cada capa vive en su módulo, en `backend/app/services/capas_legales/`, con la misma interfaz. Las pruebas las simulan con `httpx.MockTransport`, como las fuentes de cobertura.
8. El significado de los códigos de la zonificación forestal (`CATZFO` y `SCAZFO`) sale del metadato de la capa. No se inventa.
9. El sistema nunca dice que una parcela "no está" en una zona. Dice que no figura en la capa consultada, con el nombre de la capa y la fecha.
10. Todo dentro de los planes gratuitos.

### Cruces de apoyo

No deciden ninguna variable. Agregan información al perfil.

| Capa | Servicio | Para qué |
| --- | --- | --- |
| Áreas de conservación regional y privada, de SERNANP | El servicio de SERNANP, capas 3 y 4 | Se guarda en `detalle` y genera el hallazgo `en_area_de_conservacion`. No activa `area_protegida` |
| Cesiones en uso y autorizaciones de cambio de uso, de SERFOR | `https://geo.serfor.gob.pe/geoservicios/rest/services/Servicios_OGC/Modalidad_Acceso/MapServer`, capas 1 y 3 | Si la parcela se superpone con un contrato registrado, se muestra su número junto al requisito `tierra_forestal`, para compararlo con el documento cargado. No reemplaza al documento |
| Fajas marginales delimitadas, de la ANA | `https://geosnirh.ana.gob.pe/server/rest/services/Público/FajaMarginal/MapServer` | Este servicio no se pudo probar. Si responde desde el sistema, su resultado se guarda en `detalle` de `junto_a_cuerpo_de_agua`. El 9 de octubre de 2026 respondió desde el entorno de Claude Code, con una sola capa, la 127 |

De la capa de cesiones en uso no se guardan ni se muestran los nombres de los titulares.

### Comprobación

`backend/scripts/check_capas_legales.py` consulta cada capa con una geometría conocida y dice cuáles responden. Lo corre una persona del equipo, sin claves.

| Geometría de prueba | Debe devolver |
| --- | --- |
| Punto en longitud -77.35, latitud -7.75 | El Parque Nacional del Río Abiseo, en la capa 1 de SERNANP |
| Punto en longitud -76.75, latitud -7.25 | Un polígono de zonificación forestal de San Martín, aprobado por Resolución Ministerial N.º 039-2020-MINAM |

### Lo que el cruce no prueba

1. Hay comunidades que no están georreferenciadas. Que la parcela no figure en la capa no descarta tierra comunal.
2. El SIGDA trae los monumentos delimitados, no todos los sitios arqueológicos.
3. La hidrografía a escala 1:100 000 tiene decenas de metros de imprecisión. La distancia a un río es aproximada.
4. La zonificación forestal está aprobada solo en algunos departamentos.

## 11. Pantallas

1. En la parcela, la pestaña del expediente pasa a llamarse "Legalidad" y tiene tres bloques: Perfil, Requisitos e Incidencias.
2. Perfil: primero lo que respondió el cruce, cada dato con su capa, su fecha y lo que encontró; después las preguntas que declara una persona, con su ayuda de una línea. El mapa de la parcela dibuja lo que cruzó, con su nombre. Si el cruce está en cola o falló, lo dice y ofrece declarar.
3. Requisitos: una fila por requisito, con por qué aplica, el nivel y la diligencia del orientador, el estado, el sustento y la acción que sigue. Los que no aplican se ven al final, plegados, con su motivo.
4. Cada requisito tiene la ayuda "Qué pide el orientador", con el texto corto de la sección 3 y su referencia.
5. Los estados se muestran como "Sustentado", "Sin sustento", "No aplica", "Por vencer", "Vencido" y "Falta el dato".

## 12. DOP, DEX e informe de hallazgos

### DOP y DEX

1. El DOP sube de versión. Su bloque de expediente se reemplaza por el bloque `legalidad`: el perfil con el origen de cada variable, los requisitos con su estado, su sustento y su nivel, y las incidencias. Los DOP anteriores se leen como hoy.
2. En el DEX, "Respaldo por parcela" muestra ese mismo bloque en lugar de las siete casillas.
3. El DEX cita el orientador como marco y repite que no es jurídicamente vinculante.

### Temas del artículo 10

1. Se agrega el tema 11, "Otra información sobre la legalidad de la producción (art. 10.2, letra m)".
2. El título del cuadro pasa a ser "Los 14 criterios del artículo 10, apartado 2, agrupados en 11 temas".

### Hallazgos nuevos

Regla de grupo: un requisito sin sustento va a Requiere atención si su diligencia es estándar, y a No verificado si es aligerada. Un hecho que el orientador pide mirar con atención va siempre a Requiere atención.

| Código | Se genera cuando | Tema | Grupo |
| --- | --- | --- | --- |
| `tenencia_sin_documento_formal` | La tenencia se sustenta solo con declaración jurada | 4 | No verificado |
| `perfil_declarado_sin_cruce` | Una variable que tiene capa oficial quedó declarada, porque el cruce falló o porque una persona declaró `si` sobre un cruce `no`. Lista cuáles | 5 | No verificado |
| `en_area_de_conservacion` | La parcela se superpone con un área de conservación regional o privada | 1 | Requiere atención |
| `tierra_forestal_por_excepcion` | La parcela está en tierra forestal y se sustenta con título o constancia anteriores al 10 de enero de 2024. Incluye la respuesta sobre la reserva de 30 % | 4 | Requiere atención |
| `zonificacion_forestal_desconocida` | `en_tierra_forestal = sin_zonificacion` | 4 | No verificado |
| `en_area_protegida` | La parcela está dentro de un área protegida, con su acuerdo, o en zona de amortiguamiento | 1 | Requiere atención |
| `comunidad_no_inscrita` | La comunidad no está inscrita o no se sabe | 4 | No verificado |
| `riego_sin_licencia` | `agua_de_riego` sin sustento | 11 | No verificado |
| `instrumento_ambiental_sin_sustento` | `instrumento_ambiental` sin sustento. Reemplaza a `diez_hectareas_o_mas` | 11 | No verificado |
| `junto_a_cuerpo_de_agua` | `junto_a_cuerpo_de_agua = si`. Incluye la nota | 11 | Requiere atención |
| `en_patrimonio_cultural` | `en_patrimonio_cultural = si`. Incluye la nota | 4 | Requiere atención |
| `incidencia_registrada` | La parcela tiene una incidencia abierta que no es de tenencia, o una cerrada. Incluye la nota de cierre | 4 si es de tenencia; 11 en los demás casos | Requiere atención |

1. `exencion_declarada` deja de generarse en los DEX nuevos.
2. Cada hallazgo de requisito lleva en sus datos la referencia del orientador, el nivel y la diligencia.
3. Los textos van en `es.json` y `en.json`, con las mismas claves.
4. Todo hallazgo que sale de un cruce cita la capa y la fecha de consulta.
5. El DEX lista, por parcela, las seis capas consultadas con su fecha y su resultado, también cuando el resultado es que no figura.

## 13. Pruebas mínimas y aceptación

### Pruebas automáticas

| Caso | Resultado esperado |
| --- | --- |
| Parcela sin perfil | No se habilita: `perfil_legal_completo` no se cumple |
| `poseedor` con constancia de posesión | `tenencia` sustentado; alerta `tenencia_solo_posesion` |
| `poseedor` solo con declaración jurada vigente | Se puede habilitar con nota; alerta `tenencia_sin_documento_formal`; nivel `declarado` |
| `poseedor` sin ningún sustento | No se habilita |
| Declaración jurada de hace 13 meses | `tenencia` vencido; la parcela pasa a `observada` |
| `comunal_tercero` con declaración jurada | `tenencia` sin sustento |
| `en_anp = dentro` sin acuerdo de conservación | No se habilita |
| `en_anp = zona_de_amortiguamiento` | No pide documento; alerta `en_zona_de_amortiguamiento` |
| `en_tierra_forestal = si` con CCUSAF vigente | `tierra_forestal` sustentado |
| `en_tierra_forestal = si` con constancia del 2019 | Sustentado por excepción; pregunta `reserva_bosque_30`; alerta |
| `en_tierra_forestal = si` con constancia del 2025 y sin CCUSAF | No se habilita |
| `en_tierra_forestal = no` | `tierra_forestal` no aplica y no se pide CCUSAF |
| `comunal_tercero` sin acta, contrato ni constancia de la comunidad | No se habilita |
| `comunal_miembro` solo con declaración jurada | Se puede habilitar con nota; alerta `tenencia_sin_documento_formal` |
| `propietario` con `en_tierra_comunal = si` y sin constancia de la comunidad | No se habilita |
| Parcela de 12 ha sin Ficha Técnica Ambiental | Se puede habilitar con nota; hallazgo `instrumento_ambiental_sin_sustento` |
| `usa_riego = no` | `agua_de_riego` no aplica |
| Incidencia de tenencia abierta | La parcela pasa a `observada`; al cerrarla con nota puede habilitarse |
| Plantilla de declaración jurada | El PDF trae los datos del productor y de la parcela y la opción marcada |
| Textos | Ningún texto nuevo usa las palabras prohibidas de la Parte 4 |
| DOP emitido antes de la migración | Su contenido y su huella no cambian |
| Aislamiento | Otra organización recibe 404 en perfil, incidencias y plantillas |
| Cruce que devuelve un área protegida | `en_anp = dentro` con `origen = cruce`, nombre y categoría del área |
| Cruce sin resultado en un departamento con zonificación | `en_tierra_forestal = no` con `origen = cruce` |
| Cruce sin resultado en un departamento sin zonificación | `en_tierra_forestal = sin_zonificacion` |
| Superposición de 0,01 ha con una comunidad | La variable queda `no`; el roce se guarda en `detalle` |
| Servicio caído | La variable queda sin cruce; una persona puede declararla; la tarea diaria reintenta |
| Cruce `no` y declaración `si` | Manda `si`; hallazgo `perfil_declarado_sin_cruce` |
| Declarar `no` sobre un cruce `si` | 422 |
| Parcela de tipo punto | Se cruza como círculo y queda marcada como aproximación |
| Río a 60 m del lindero, con el valor inicial de 100 m | `junto_a_cuerpo_de_agua = si`, con la distancia |
| Lo que se envía a cada servicio | Solo la geometría |

### Criterios de aceptación en producción

1. Al guardar una parcela nueva, su perfil muestra las cinco respuestas del cruce, cada una con su capa y su fecha, sin que nadie las escriba.
2. Una parcela fuera de tierra forestal no muestra el CCUSAF como pendiente.
3. Un productor sin documento formal descarga la declaración jurada, se carga firmada y la parcela se habilita con nota.
4. Una parcela que el cruce ubica dentro de un área protegida no se habilita hasta cargar el acuerdo de conservación.
5. Un DEX nuevo muestra, por parcela, el perfil, las seis capas consultadas y los requisitos con su referencia del orientador, y el cuadro de 11 temas.
6. `check_capas_legales.py`, corrido por el equipo, informa que las seis capas responden.

## 14. Lecturas del orientador y decisiones pendientes

### Diferencias dentro del orientador

| Punto | Qué dice | Cómo se tomó aquí |
| --- | --- | --- |
| Numeración de 2.4 a 2.7 | La tabla principal y el Anexo 2 no numeran igual residuos, agua, fajas y vertimientos | Numeración del Anexo 2 |
| 2.8, calidad de suelo | La tabla lo trae como nivel alto; el Anexo 2, como no pertinente | No pertinente |
| 2.10 y 2.11 | La tabla dice nivel alto y diligencia estándar | Estándar, como su flujograma |
| 2.12, umbral | Unas partes dicen "más de 10 ha" y otras "10 ha o más" | 10 ha o más, como la alerta actual |
| 2.1, zona de amortiguamiento | El flujograma la trata igual que el interior del área; el texto pide solo atención especial | Documento solo dentro del área |
| 3.4 | El Anexo 2 numera dos requisitos como 3.4 | El no pertinente figura aquí como "3.4 bis" |

### Decisiones pendientes del equipo

- [ ] Un asesor legal revisa los textos de los Anexos A y B antes de usarlos con productores reales.
- [ ] Confirmar los 12 meses de vigencia de la declaración jurada.
- [ ] Correr `check_capas_legales.py` y confirmar que las seis capas responden también desde el servidor de producción.
- [ ] Confirmar los 100 metros de `DISTANCIA_CUERPO_AGUA_M`.
- [ ] Confirmar que las áreas de conservación regional y privada solo generen hallazgo y no bloqueen.
- [ ] Volver a cargar el perfil de las parcelas de la simulación, que quedarán `observada` tras la migración.

## 15. Construcción (9 de octubre de 2026)

Registro de Claude Code. Rama `feat/adenda-4-legalidad`, migración 0016.

### Confirmado antes de construir

1. La disposición complementaria final de la Ley N.º 31973 se leyó en El Peruano. Difería en tres puntos y el equipo decidió (sección 5.2): corte el 12 de enero de 2024, la constancia de la Ley N.º 31145 y solo el título de formalización entre los no inscritos.
2. Los seis servicios de la sección 10 se confirmaron con su metadato (`?f=pjson`) el 9 de octubre de 2026: existen con esos números de capa, aceptan consultas espaciales y por distancia, entregan GeoJSON y traen los campos que se guardan. No se encontraron condiciones de uso publicadas. El servidor de SERFOR a veces responde vacío: cada consulta se reintenta tres veces. La ANA respondió con una sola capa, la 127.
3. "Registro consultable": queda `sí` solo en `titulo_sunarp` (SUNARP) y `cusaf` (GeoSERFOR publica las cesiones en uso). La capa de cambio de uso de GeoSERFOR tenía solo 2 registros, la capa "Acuerdo" de SERNANP estaba vacía y la ANA no publica un buscador de licencias.

### Decisiones de construcción por confirmar

La adenda no las dice.

1. **Cola del cruce.** Vive en dos columnas de `parcelas` (`cruce_solicitado_en` y `cruce_estado`), no en una tabla propia. Si una capa falla, el cruce se repite a los 5 minutos y a la hora. Después lo retoma la tarea diaria.
2. **Cambio de geometría.** Los cruces de la geometría anterior dejan de valer: `vigente = false`, y la parcela vuelve a la cola. Lo mismo pasa al cambiar el área declarada de un punto. Cambiar el departamento solo vuelve a cruzar.
3. **Una fila vigente por origen.** La regla "solo una fila vigente por parcela y variable" se aplica por parcela, variable y origen, porque el cruce y la declaración se guardan y se muestran juntos (sección 4, regla 4).
4. **Declaraciones frente al cruce.**
   - Declarar un valor menos exigente que el cruce vigente responde 422.
   - Declarar un valor distinto del cruce exige una nota.
   - Con una declaración de igual valor, manda el cruce.
5. **Notas de faja marginal y patrimonio cultural.** Se guardan como una declaración del mismo valor vigente, con la nota en su `detalle` (`POST /parcelas/{id}/requisitos/{codigo}/nota`). Exigen 10 caracteres como mínimo.
6. **`reserva_bosque_30`.** Solo se puede declarar mientras la tierra forestal se sustenta por la excepción.
7. **Sustentos que cuentan.**
   - Si hay varios sustentos, cuenta el de mejor nivel, y entre esos el de mejor estado y vencimiento más lejano.
   - Un mismo documento puede sustentar dos requisitos. Por ejemplo, un CCUSAF de un `titulo_habilitante` sustenta la tenencia y la tierra forestal.
   - Para el miembro de la comunidad, la declaración jurada sustenta también el acuerdo comunal.
8. **Instrumento ambiental.**
   - De 10 a 50 ha vale también el instrumento mayor.
   - Sobre 50 ha solo vale el instrumento mayor.
   - El área total es la calculada en un polígono y la declarada en un punto.
9. **Patrimonio cultural.** "Sin CCUSAF vigente" (sección 5) se lee así: con un CCUSAF vigente, el requisito queda "no aplica" y lo dice en su motivo.
10. **Declaración jurada.**
    - Su `fecha_vencimiento` se calcula al cargarla: la firma más `DECLARACION_VIGENCIA_MESES`.
    - La declaración jurada, la constancia comunal y el acta comunal no piden número ni entidad emisora.
    - El título no inscrito exige su clase. Los tipos anteriores no se cargan y responden 422.
11. **Exenciones.** `POST /parcelas/{id}/exenciones` responde 422 (`exenciones_sin_efecto`), y retirar una exención ya no tiene ruta. Las exenciones anteriores se ven como historial en la pestaña Legalidad.
12. **Rutas de la legalidad.**
    - `GET /parcelas/{id}/expediente` se reemplaza por `GET /parcelas/{id}/legalidad`. El productor lo ve en `/mi/parcelas/{id}/legalidad`.
    - Las plantillas se descargan en `/parcelas/{id}/plantillas/{nombre}` y en `/mi/parcelas/{id}/plantillas/{nombre}`. Responden 400 si no aplican.
13. **Plantillas.** El texto de los Anexos A y B va tal cual, en `app/textos/plantillas_legales.json`.
    - El sistema llena solo lo que va entre llaves. El nombre de la comunidad del Anexo A queda en blanco, porque en el anexo es una línea.
    - El Anexo B marca "es miembro" o "no es miembro" según `tenencia_tipo`.
    - El texto usa "conforme a" en su sentido legal ("conforme a sus estatutos", "conforme a la legislación peruana"). Por eso la prueba de palabras prohibidas no lo lee: lo revisa el asesor legal.
14. **Alertas.**
    - `expediente_incompleto` deja de calcularse; su insignia queda para las decisiones ya registradas.
    - `documento_por_vencer` y `documento_vencido` siguen, ahora por requisito.
    - `requisito_sin_sustento` junta los requisitos que no bloquean y están sin sustento o vencidos.
15. **Hallazgos.**
    - `tenencia_solo_posesion`, `documento_por_vencer`, `documento_sin_registro_consultable` y `documento_sin_cotejar` ahora miran los sustentos que cuentan. La declaración jurada tiene su propio hallazgo.
    - `exencion_declarada` y `diez_hectareas_o_mas` siguen en el catálogo para los DEX ya emitidos, pero no se generan.
    - `perfil_declarado_sin_cruce` también salta cuando el cruce todavía no corrió: la variable quedó declarada.
    - `comunidad_no_inscrita` salta también cuando nadie respondió si la comunidad está inscrita.
16. **Temas en la interfaz.** El informe y el PDF del DEX dicen "Tema" en lugar de "Criterio". El cuadro del DEX titula "Los 14 criterios del artículo 10, apartado 2, agrupados en 11 temas".
17. **Mapa de la pestaña Legalidad.** Dibuja cada capa con la operación `export` de su servicio. Solo le envía el recuadro visible del mapa. Se encienden las capas en las que la parcela figura. Al lado, en texto, lista lo que encontró el cruce, con sus nombres.
18. **Zonificación forestal.**
    - Solo se pide la geometría de los polígonos forestales (601 a 604, salvo 60402), para medir el área común.
    - De los demás basta saber que tocan la parcela, porque la 605 abarca departamentos enteros.
    - El departamento se toma del de la parcela, por su código del INEI, y de los polígonos que toca.
19. **Escenario de demostración y simulación.**
    - El escenario de la cooperativa Prueba carga solo el título y declara el perfil. PA-00008 queda con el perfil incompleto, y lo que se anula al final es el título de PA-00007.
    - La simulación carga solo el título y su guion pide declarar el perfil.
    - Las variables de mapa se declaran "no" solo si el cruce no respondió.

### Para el equipo

1. Correr `backend/scripts/check_capas_legales.py` en local y en el servidor de producción.
2. Aplicar la migración 0016 en producción. Pone en la cola del cruce las parcelas activas no excluidas; ninguna recibe un perfil por defecto.
3. Al aplicarla, las parcelas habilitadas pasan a observada hasta completar su perfil (sección 8, regla 4). Eso incluye las de la simulación.
4. Los pendientes de la sección 14.

## Anexo A — Declaración jurada de tenencia y conducción de parcela

Versión 1, redactada para revisión de un asesor legal. Lo que va entre llaves lo llena el sistema; las líneas, el productor.

> **DECLARACIÓN JURADA DE TENENCIA Y CONDUCCIÓN DE PARCELA AGRÍCOLA**
>
> Yo, {nombres y apellidos del productor}, identificado(a) con DNI N.º {dni}, con domicilio en ______________________, distrito de __________, provincia de __________, departamento de __________, en pleno uso de mis facultades y de manera libre y voluntaria, **DECLARO BAJO JURAMENTO** lo siguiente:
>
> **PRIMERO. De la parcela.** Conduzco de manera directa la parcela agrícola denominada "{nombre de la parcela}", registrada con el código {código de la parcela}, ubicada en {centro poblado}, distrito de {distrito}, provincia de {provincia}, departamento de {departamento}, con un área aproximada de {área} hectáreas. Su ubicación es la que consta en el plano o en las coordenadas registradas con ese código.
>
> Colindantes: por el norte, __________; por el sur, __________; por el este, __________; por el oeste, __________.
>
> **SEGUNDO. De la forma de tenencia.** Ejerzo sobre la parcela el siguiente derecho (se marca una sola opción):
>
> ( ) **Propiedad**, sin título inscrito en los Registros Públicos. La adquirí por __________ (compraventa, herencia, adjudicación u otro) en el año ______.
>
> ( ) **Posesión** directa, continua, pacífica y pública, como propietario, desde el año ______, sin contar a la fecha con constancia de posesión.
>
> ( ) **Uso por acuerdo** con su propietario o poseedor, don/doña ______________________, con DNI N.º __________, en calidad de __________ (arrendamiento, préstamo, cesión en uso o acuerdo familiar), desde el año ______, sin contrato escrito.
>
> ( ) **Uso de tierras de la comunidad** ______________________, de la que soy miembro, conforme a sus estatutos y a los acuerdos de su asamblea.
>
> **TERCERO. De la actividad.** En la parcela cultivo cacao desde el año ______ y la trabajo de manera personal, con mi familia o con las personas que contrato.
>
> **CUARTO. De la ausencia de conflictos.** A la fecha no existe, que yo conozca, proceso judicial, procedimiento administrativo, denuncia ni reclamo de terceros, de comunidades campesinas o nativas, ni de entidad pública alguna, que cuestione mi derecho sobre la parcela o sus linderos. Si lo hubiera en adelante, me obligo a comunicarlo a {razón social de la organización} dentro de los quince (15) días calendario de haberlo conocido.
>
> **QUINTO. De los documentos.** No cuento a la fecha con un documento formal que acredite el derecho declarado, o este se encuentra en trámite ante ______________________. Me comprometo a entregar copia del documento cuando lo obtenga.
>
> **SEXTO. De la finalidad.** Formulo esta declaración para que {razón social de la organización}, con RUC N.º {ruc}, sustente el origen legal del cacao que le entrego. Autorizo que la conserve y la ponga a disposición de sus compradores y de las autoridades competentes, para los fines de la diligencia debida que exige el Reglamento (UE) 2023/1115.
>
> **SÉPTIMO. De la veracidad.** Lo declarado responde a la verdad. Conozco que, de comprobarse su falsedad, asumo las responsabilidades civiles y penales que correspondan conforme a la legislación peruana, y que la organización podrá dejar de recibir el cacao de esta parcela.
>
> Esta declaración no constituye título de propiedad ni constancia de posesión, y no reemplaza los procedimientos de formalización ante la autoridad competente.
>
> __________, ____ de __________ de 20____.
>
> Firma: ______________________   Huella dactilar: [    ]
> {nombres y apellidos del productor} · DNI N.º {dni}
>
> **Da fe de que el declarante conduce la parcela descrita** (opcional: autoridad local o colindante)
> Nombre: ______________________   Cargo: ______________   DNI N.º __________   Firma: __________
>
> **Propietario o poseedor que cede el uso** (solo en la tercera opción)
> Nombre: ______________________   DNI N.º __________   Firma: __________
>
> **Recibido por la organización**
> Nombre: ______________________   Cargo: ______________   Fecha: ____/____/______   Firma: __________
>
> Referencias: Código Civil, artículos 896 (posesión), 1352 (los contratos se perfeccionan por el consentimiento) y 1666 (arrendamiento). Documento orientador para la diligencia debida de la legalidad del café y cacao en el marco del EUDR, requisitos 1.1 a 1.4. Versión 1.

## Anexo B — Constancia de uso de tierra comunal

Versión 1, redactada para revisión de un asesor legal. La firma la autoridad de la comunidad.

> **CONSTANCIA DE USO DE TIERRA COMUNAL**
>
> La Junta Directiva de la Comunidad ( ) Campesina ( ) Nativa ______________________, ( ) inscrita en la Partida N.º __________ del Registro de Personas Jurídicas de __________ ( ) en proceso de inscripción, representada por su presidente(a) o jefe(a), don/doña ______________________, con DNI N.º __________, **DEJA CONSTANCIA** de lo siguiente:
>
> **PRIMERO.** {nombres y apellidos del productor}, con DNI N.º {dni} (se marca una sola opción):
>
> ( ) es miembro de la comunidad;
>
> ( ) no es miembro de la comunidad y usa la tierra en virtud del acuerdo de asamblea de fecha ____/____/______, que consta en el folio ______ del libro de actas.
>
> **SEGUNDO.** Usa la parcela denominada "{nombre de la parcela}", de aproximadamente {área} hectáreas, en el sector __________, dentro del territorio de la comunidad, para el cultivo de cacao, desde el año ______.
>
> **TERCERO.** Ese uso es conforme a los estatutos y a los acuerdos de la comunidad, y a la fecha no existe reclamo pendiente sobre la parcela.
>
> Se expide a solicitud del interesado, para que {razón social de la organización} sustente el origen legal del cacao que recibe de esta parcela.
>
> __________, ____ de __________ de 20____.
>
> Firma y sello: ______________________
> Nombre: ______________________   Cargo: ______________   DNI N.º __________
>
> Referencias: Ley N.º 24656, Ley General de Comunidades Campesinas; Decreto Ley N.º 22175, Ley de Comunidades Nativas y de Desarrollo Agrario de la Selva y Ceja de Selva; Documento orientador, requisitos 1.3 y 1.4. Versión 1.

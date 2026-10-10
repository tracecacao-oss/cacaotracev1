// Textos y etiquetas compartidas. Cada nivel de verificación tiene una etiqueta propia y
// constante en toda la aplicación: declarado en gris y documentado en esmeralda.

import { h } from "./ui.js";

const NIVELES = {
  declarado: ["", "Declarado"],
  documentado: ["ok", "Documentado"],
  verificado_en_fuente: ["info", "Verificado en fuente"],
  no_registrado: ["", "No registrado"],
  no_registrada: ["", "No registrada"],
};

export function insigniaNivel(nivel) {
  const [clase, texto] = NIVELES[nivel] ?? ["", nivel];
  return h("span", { class: `badge nivel ${clase}`, title: "Nivel de verificación" }, h("span", { class: "dot" }), texto);
}

export const PENDIENTES_PERSONAL = {
  sin_documento_dni: "Falta la copia del DNI",
  sin_consentimiento: "Falta el consentimiento de datos",
  sin_parcelas: "No tiene parcelas registradas",
  // Adenda 5
  sin_declaracion_anual: "Falta la declaración anual",
  declaracion_por_firmar: "Falta la hoja firmada de la declaración",
  declaracion_por_vencer: "La declaración anual vence pronto",
};

// Para el productor, en lenguaje simple.
export const PENDIENTES_PRODUCTOR = {
  sin_documento_dni: "Falta subir la foto de tu DNI",
  sin_consentimiento: "Falta aceptar el uso de tus datos",
  sin_parcelas: "Falta registrar tus parcelas",
  // Adenda 5
  sin_declaracion_anual: "Falta tu declaración anual",
  declaracion_por_firmar: "Tu declaración anual espera tu firma",
  declaracion_por_vencer: "Tu declaración anual vence pronto",
};

export const ALERTAS = {
  area_discrepante: "El área declarada difiere más de 20 % de la calculada",
  diez_hectareas_o_mas: "Parcela de 10 ha o más: MIDAGRI recomienda acciones adicionales",
  superposicion: "Se superpone con otra parcela",
  sin_sustento_midagri: "Falta el sustento del estado en MIDAGRI",
  // Parte 4
  sin_analisis_vigente: "Falta un análisis de cobertura vigente",
  analisis_requiere_revision: "Una fuente o un conjunto de datos pide que una persona revise la parcela",
  analisis_con_error: "El último análisis de una fuente falló",
  expediente_incompleto: "El expediente legal está incompleto",
  documento_por_vencer: "Un documento legal vence pronto",
  documento_vencido: "Un documento legal está vencido",
  tenencia_solo_posesion: "La tenencia se apoya solo en una constancia de posesión",
  superposicion_con_excluida: "Se superpone con una parcela excluida",
  // Adenda 4: legalidad por requisito.
  tenencia_sin_documento_formal: "La tenencia se sustenta solo con una declaración jurada",
  tierra_forestal_por_excepcion: "En tierra forestal, sustentada por la excepción de la Ley N.º 31973",
  zonificacion_forestal_desconocida: "La capa de zonificación forestal no clasifica su departamento",
  en_zona_de_amortiguamiento: "Está en la zona de amortiguamiento de un área protegida",
  requisito_sin_sustento: "Un requisito legal que no bloquea está sin sustento o vencido",
  incidencia_abierta: "Tiene una incidencia abierta",
  // Adenda 5: la declaración anual del productor.
  productor_por_atender: "El productor declaró algo que queda por atender",
  productor_sin_sustento: "A la declaración del productor le falta un papel o una revisión",
};
const ALERTAS_GRAVES = new Set(["superposicion", "superposicion_con_excluida", "documento_vencido", "analisis_con_error"]);

// ---------- Parte 4: habilitación ----------

export const ESTADOS_HABILITACION = {
  pendiente: ["", "Pendiente"],
  habilitada: ["ok", "Habilitada"],
  observada: ["warn", "Observada"],
  excluida: ["bad", "Excluida"],
};

export function insigniaHabilitacion(estadoHabilitacion) {
  const [clase, texto] = ESTADOS_HABILITACION[estadoHabilitacion] ?? ["", estadoHabilitacion];
  return h("span", { class: `badge ${clase}` }, h("span", { class: "dot" }), texto);
}

export const REQUISITOS = {
  parcela_activa: "Parcela activa",
  sin_superposiciones_abiertas: "Sin superposiciones abiertas",
  analisis_vigente: "Análisis de cobertura vigente",
  revision_atendida: "Revisión de imágenes atendida",
  // Antes de la adenda 4; queda para las decisiones ya registradas.
  expediente_completo: "Expediente legal completo",
  perfil_legal_completo: "Perfil legal completo",
  tenencia_sustentada: "Tenencia con sustento",
  permisos_obligatorios: "Permisos obligatorios con sustento",
  sin_conflicto_de_tenencia: "Sin incidencias de tenencia abiertas",
  productor_listo: "Productor con DNI documentado, consentimiento y declaración anual vigente",
};

// Para el productor, en lenguaje simple.
export const REQUISITOS_PRODUCTOR = {
  parcela_activa: "La parcela está inactiva",
  sin_superposiciones_abiertas: "Se cruza con otra parcela: la cooperativa lo revisa",
  analisis_vigente: "Falta el análisis de bosque, que hace la cooperativa",
  revision_atendida: "Falta que la cooperativa revise imágenes satelitales de tu parcela",
  expediente_completo: "Faltan documentos de tu parcela, como el título o la constancia de posesión",
  perfil_legal_completo: "Faltan datos de tu parcela que la cooperativa registra en la pestaña Legalidad",
  tenencia_sustentada: "Falta el documento de tu derecho sobre la tierra, o la declaración jurada firmada",
  permisos_obligatorios: "Falta un permiso de tu parcela: acuerdo con la comunidad, acuerdo de conservación o contrato forestal",
  sin_conflicto_de_tenencia: "Hay un reclamo sobre tu tierra que la cooperativa está revisando",
  productor_listo: "Falta la foto de tu DNI, aceptar el uso de tus datos o tu declaración anual",
};

// Adenda 4: estados de un requisito legal. Dicen con qué se sustenta, nunca que se cumple.
export const ESTADOS_REQUISITO = {
  sustentado: ["ok", "Sustentado"],
  sin_sustento: ["bad", "Sin sustento"],
  no_aplica: ["info", "No aplica"],
  por_vencer: ["warn", "Por vencer"],
  vencido: ["bad", "Vencido"],
  sin_dato: ["", "Falta el dato"],
};

export const ESTADOS_CASILLA = {
  vigente: ["ok", "Vigente"],
  por_vencer: ["warn", "Por vencer"],
  vencido: ["bad", "Vencido"],
  no_aplica: ["info", "No aplica"],
  // Solo en tenencia: el otro documento de tenencia ya la cubre (pedido del 2026-10-07).
  no_requerida: ["", "No requerida"],
  faltante: ["", "Falta"],
};

// Adenda 2: las visitas ya no se registran. Esta lista solo nombra el motivo de las del historial.
export const MOTIVOS_VISITA = [
  ["analisis_requiere_revision", "Una fuente pidió revisión"],
  ["verificacion_de_coordenadas", "Verificar las coordenadas"],
  ["otro", "Otro"],
];

// ---------- Adenda 2: imágenes de la parcela y revisión de imágenes ----------

export const OBSERVACIONES_2020 = [
  ["bosque", "Bosque"],
  ["cultivo_o_uso_agricola", "Cultivo o uso agrícola"],
  ["mixto", "Mixto"],
  ["no_se_distingue", "No se distingue"],
];

export const OBSERVACIONES_CAMBIO = [
  ["sin_cambio_visible", "Sin cambio visible"],
  ["cambio_visible", "Cambio visible"],
  ["no_se_distingue", "No se distingue"],
];

export const PAPELES_IMAGEN = {
  anterior_al_corte: "Anterior al corte",
  anual: "Imagen del año",
  reciente: "Reciente",
  alta_resolucion: "Alta resolución",
  externa: "Imagen externa",
};

export const FUENTES = { whisp: "Whisp (FAO)", gfw: "Global Forest Watch", mapbiomas: "MapBiomas Perú" };

export const ESTADOS_MIDAGRI = [
  ["no_registrada", "No registrada"],
  ["sin_observacion", "Sin observación"],
  ["en_revision", "En revisión"],
  ["validado", "Validado"],
];

export const TIPOS_DOCUMENTO = {
  dni: "Copia del DNI",
  constancia_ppa: "Constancia del PPA",
  sustento_midagri: "Sustento de MIDAGRI",
  archivo_geometria: "Archivo de geometría",
  titulo_sunarp: "Título inscrito en SUNARP",
  constancia_posesion: "Constancia de posesión",
  cusaf: "CUSAF",
  autorizacion_serfor: "Autorización forestal",
  sunafil: "Sustento ante SUNAFIL",
  sunat: "Sustento de SUNAT",
  zonificacion: "Sustento de zonificación forestal",
  foto_visita: "Foto de la visita",
  respuesta_analisis: "Respuesta del análisis",
  imagen_satelital: "Imagen satelital",
  imagen_externa: "Imagen externa",
  certificacion: "Certificación",
  // Adenda 5: los papeles de la declaración anual del productor.
  hoja_declaracion_productor: "Hoja firmada de la declaración anual",
  relacion_trabajadores: "Relación de trabajadores permanentes",
  declaracion_renta: "Declaración anual del impuesto a la renta",
  // Adenda 6: la evidencia de una actuación de diligencia y la declaración aduanera del lote.
  evidencia_actuacion: "Evidencia de la actuación",
  dam: "Declaración aduanera",
};

export function insigniaAlerta(codigo) {
  return h("span", { class: `badge ${ALERTAS_GRAVES.has(codigo) ? "bad" : "warn"}`, title: ALERTAS[codigo] }, h("span", { class: "dot" }), ALERTAS[codigo] ?? codigo);
}

export function hectareas(valor) {
  if (valor === null || valor === undefined) return "—";
  return `${Number(valor).toLocaleString("es-PE", { maximumFractionDigits: 4 })} ha`;
}

// ---------- Parte 5: recepción de la tanda y DOP ----------

export const ESTADOS_TANDA = {
  registrada: ["info", "Registrada"],
  observada: ["warn", "Observada"],
  validada: ["ok", "Validada"],
  anulada: ["", "Anulada"],
};

export function insigniaTanda(estadoTanda) {
  const [clase, texto] = ESTADOS_TANDA[estadoTanda] ?? ["", estadoTanda];
  return h("span", { class: `badge ${clase}` }, h("span", { class: "dot" }), texto);
}

export function insigniaDop(estadoDop) {
  return estadoDop === "vigente"
    ? h("span", { class: "badge ok" }, h("span", { class: "dot" }), "DOP vigente")
    : h("span", { class: "badge bad" }, h("span", { class: "dot" }), "DOP anulado");
}

export const REQUISITOS_TANDA = {
  parcela_habilitada: "Parcela habilitada",
  productor_afiliado: "Productor afiliado y con consentimiento",
  datos_completos: "Pesaje y cosecha completos",
  documento_entrega_completo: "Documento de entrega completo",
  guia_completa: "Guía de remisión completa", // decisiones anteriores a la adenda 3
  configuracion_lista: "Tope de kilos por hectárea configurado",
};

export const ALERTAS_TANDA = {
  volumen_acumulado_excede_tope: "El volumen de la parcela en 365 días supera el tope por hectárea",
  dias_cosecha_entrega_altos: "Pasaron más días de los configurados entre la cosecha y la entrega",
  peso_difiere_del_documento: "El peso del documento de entrega difiere del peso en balanza más que la tolerancia",
  documento_usado_por_otro_productor: "El mismo documento de entrega aparece en una tanda de otro productor",
  liquidacion_con_productor_con_ruc: "Liquidación de compra a un productor que tiene RUC",
  // Decisiones y DOP anteriores a la adenda 3.
  peso_difiere_de_guia: "El peso de la guía difiere del peso en balanza más que la tolerancia",
  guia_usada_por_otro_productor: "La misma guía aparece en una tanda de otro productor",
  parcela_con_alertas: "La parcela está habilitada pero tiene alertas vigentes",
};

export function insigniaAlertaTanda(codigo) {
  return h("span", { class: "badge warn", title: ALERTAS_TANDA[codigo] }, h("span", { class: "dot" }), ALERTAS_TANDA[codigo] ?? codigo);
}

// El mismo catálogo que backend/app/catalogos/variedades.py.
export const VARIEDADES = [
  ["ccn_51", "CCN-51"],
  ["ics_95", "ICS-95"],
  ["imc_67", "IMC-67"],
  ["tsh_565", "TSH-565"],
  ["trinitario", "Trinitario"],
  ["chuncho", "Chuncho"],
  ["sin_variedad", "Sin variedad específica"],
  ["otra", "Otra"],
];

export const TIPOS_LUGAR = [
  ["cancha_acopio", "Cancha de acopio"],
  ["planta", "Planta"],
  ["almacen", "Almacén"],
  ["otro", "Otro"],
];

export const PRODUCTO = { baba: "Cacao en baba", seco: "Cacao seco" };

TIPOS_DOCUMENTO.documento_entrega = "Documento de entrega";

// Adenda 3 de la Parte 5: los mismos tipos que backend/app/catalogos/documento_entrega.py. El Comprobante
// de Operaciones de la Ley N.° 29972 no está: esa ley fue derogada por la Ley N.° 31335.
export const TIPOS_DOC_ENTREGA = [
  {
    codigo: "guia_remision",
    nombre: "Guía de remisión",
    emisor: "La emite el productor, la organización que recibe o el transportista",
    cuando: "Cuando el traslado se hizo con guía",
    ejemplo: "T001-123",
    emiteLaOrganizacion: false,
  },
  {
    codigo: "liquidacion_compra",
    nombre: "Liquidación de compra",
    emisor: "La emite la organización que recibe",
    cuando: "Cuando compra a un productor que no da comprobante por no tener RUC",
    ejemplo: "L001-123",
    emiteLaOrganizacion: true,
  },
];

export const nombreDocEntrega = (codigo) => TIPOS_DOC_ENTREGA.find((x) => x.codigo === codigo)?.nombre ?? "Documento de entrega";

export const TIPOS_ORGANIZACION = [
  ["cooperativa_agraria", "Cooperativa agraria"],
  ["asociacion", "Asociación de productores"],
  ["empresa", "Empresa acopiadora o exportadora"],
];
TIPOS_DOCUMENTO.dop_pdf = "PDF del DOP";
TIPOS_DOCUMENTO.dpp_pdf = "PDF del DPP";
// Parte 8: expediente legal de la cooperativa y documentos de embarque del lote.
Object.assign(TIPOS_DOCUMENTO, {
  rnca: "Constancia de inscripción en el Registro Nacional de Cooperativas Agrarias",
  partida_sunarp: "Partida registral en SUNARP",
  // Adenda 6: la declaración de renta y la política de la organización.
  renta_anual: "Declaración anual del impuesto a la renta",
  politica_organizacion: "Política de la organización",
  ficha_ruc: "Ficha RUC",
  vigencia_poderes: "Vigencia de poderes",
  ruc_comercio_exterior: "Sustento del RUC para comercio exterior",
  registro_aduanas: "Registro de exportador en SUNAT Aduanas",
  factura_comercial: "Factura comercial",
  packing_list: "Lista de empaque",
  certificado_origen: "Certificado de origen",
  certificado_fitosanitario: "Certificado fitosanitario",
});

/** Pesos siempre con dos decimales y su unidad. */
export function kilos(valor) {
  if (valor === null || valor === undefined || valor === "") return "—";
  return `${Number(valor).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kg`;
}

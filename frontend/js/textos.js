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
};

// Para el productor, en lenguaje simple.
export const PENDIENTES_PRODUCTOR = {
  sin_documento_dni: "Falta subir la foto de tu DNI",
  sin_consentimiento: "Falta aceptar el uso de tus datos",
  sin_parcelas: "Falta registrar tus parcelas",
};

export const ALERTAS = {
  area_discrepante: "El área declarada difiere más de 20 % de la calculada",
  diez_hectareas_o_mas: "Parcela de 10 ha o más: MIDAGRI recomienda acciones adicionales",
  superposicion: "Se superpone con otra parcela",
  sin_sustento_midagri: "Falta el sustento del estado en MIDAGRI",
  // Parte 4
  sin_analisis_vigente: "Falta un análisis de cobertura vigente",
  analisis_requiere_revision: "Una fuente pide que una persona revise la parcela",
  analisis_con_error: "El último análisis de una fuente falló",
  expediente_incompleto: "El expediente legal está incompleto",
  documento_por_vencer: "Un documento legal vence pronto",
  documento_vencido: "Un documento legal está vencido",
  tenencia_solo_posesion: "La tenencia se apoya solo en una constancia de posesión",
  superposicion_con_excluida: "Se superpone con una parcela excluida",
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
  revision_atendida: "Revisión atendida en campo",
  expediente_completo: "Expediente legal completo",
  productor_listo: "Productor con DNI documentado y consentimiento",
};

// Para el productor, en lenguaje simple.
export const REQUISITOS_PRODUCTOR = {
  parcela_activa: "La parcela está inactiva",
  sin_superposiciones_abiertas: "Se cruza con otra parcela: la cooperativa lo revisa",
  analisis_vigente: "Falta el análisis de bosque, que hace la cooperativa",
  revision_atendida: "Falta la visita de un técnico a tu parcela",
  expediente_completo: "Faltan documentos de tu parcela, como el título o la constancia de posesión",
  productor_listo: "Falta la foto de tu DNI o aceptar el uso de tus datos",
};

export const ESTADOS_CASILLA = {
  vigente: ["ok", "Vigente"],
  por_vencer: ["warn", "Por vencer"],
  vencido: ["bad", "Vencido"],
  no_aplica: ["info", "No aplica"],
  faltante: ["", "Falta"],
};

export const MOTIVOS_VISITA = [
  ["analisis_requiere_revision", "Una fuente pidió revisión"],
  ["verificacion_de_coordenadas", "Verificar las coordenadas"],
  ["otro", "Otro"],
];

export const USOS_OBSERVADOS = [
  ["cacao_bajo_sombra", "Cacao bajo sombra"],
  ["cacao_sin_sombra", "Cacao sin sombra"],
  ["bosque", "Bosque"],
  ["otro_cultivo", "Otro cultivo"],
  ["mixto", "Mixto"],
];

export const FUENTES = { whisp: "Whisp (FAO)", gfw: "Global Forest Watch" };

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
};

export function insigniaAlerta(codigo) {
  return h("span", { class: `badge ${ALERTAS_GRAVES.has(codigo) ? "bad" : "warn"}`, title: ALERTAS[codigo] }, h("span", { class: "dot" }), ALERTAS[codigo] ?? codigo);
}

export function hectareas(valor) {
  if (valor === null || valor === undefined) return "—";
  return `${Number(valor).toLocaleString("es-PE", { maximumFractionDigits: 4 })} ha`;
}

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
};

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
};

export function insigniaAlerta(codigo) {
  return h("span", { class: `badge ${codigo === "superposicion" ? "bad" : "warn"}`, title: ALERTAS[codigo] }, h("span", { class: "dot" }), ALERTAS[codigo] ?? codigo);
}

export function hectareas(valor) {
  if (valor === null || valor === undefined) return "—";
  return `${Number(valor).toLocaleString("es-PE", { maximumFractionDigits: 4 })} ha`;
}

// Texto de consentimiento de datos personales. Vive en un solo archivo, con su versión en la
// primera línea ("Versión: N"). Desde la versión 1 lo redactó Claude Code a pedido del equipo
// (2026-10-06), según la Ley N.° 29733 y su Reglamento; falta la revisión de un asesor legal.
// Los marcadores {cooperativa}, {ruc} y {domicilio} nombran a la cooperativa del productor, que es la
// titular del banco de datos (art. 18 de la ley).

import { lugares } from "./ubigeo.js";

let enCache = null;

export async function textoConsentimiento() {
  if (enCache) return enCache;
  const respuesta = await fetch("textos/consentimiento.md", { cache: "no-cache" });
  if (!respuesta.ok) throw new Error("No se pudo cargar el texto de consentimiento.");
  const [primera, ...resto] = (await respuesta.text()).replace(/\r/g, "").split("\n");
  const version = primera.replace(/^versi[oó]n:\s*/i, "").trim();
  enCache = { version, texto: resto.join("\n").trim() };
  return enCache;
}

/** Pone en el texto el nombre, el RUC y el domicilio de la cooperativa del productor. */
export function completarTexto(texto, cooperativa) {
  if (!cooperativa) {
    return texto.replace("{cooperativa} (RUC {ruc}), con domicilio en {domicilio},", "La cooperativa que te registró").replaceAll("{cooperativa}", "la cooperativa que te registró");
  }
  const lugar = lugares(cooperativa.distrito, cooperativa.provincia, cooperativa.departamento);
  const domicilio = [cooperativa.direccion_postal, lugar].filter(Boolean).join(", ") || "el domicilio que figura en su RUC";
  return texto.replaceAll("{cooperativa}", cooperativa.razon_social).replaceAll("{ruc}", cooperativa.ruc).replaceAll("{domicilio}", domicilio);
}

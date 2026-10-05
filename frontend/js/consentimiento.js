// Texto de consentimiento de datos personales. Vive en un solo archivo, con su versión en la
// primera línea ("Versión: N"). El texto legal lo entrega el equipo; Claude Code no lo redacta.

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

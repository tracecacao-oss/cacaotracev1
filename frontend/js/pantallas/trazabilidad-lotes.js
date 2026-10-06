// Genealogía por lote (Trazabilidad): se elige un lote confirmado y se ve de qué parcelas viene, con el
// diagrama, la tabla y el mapa enlazados.

import { llamarApi } from "../api.js";
import { ESTADOS_LOTE, seccionesTrazabilidad, vistaGenealogia } from "../exportacion.js";
import { kilos } from "../textos.js";
import { cargando, errorDeCarga, h, reemplazar, seccion, vacio } from "../ui.js";

let elegido = null;

export default async function trazabilidadLotes() {
  const lotes = (await llamarApi("/lotes")).filter((l) => l.estado !== "en_armado");
  const caja = h("div", {});
  const selector = h(
    "select",
    { class: "select", "aria-label": "Lote", onchange: (e) => mostrar(e.target.value) },
    h("option", { value: "" }, lotes.length ? "Elige un lote…" : "No hay lotes confirmados"),
    lotes.map((l) => h("option", { value: l.id }, `${l.codigo} · ${l.importador} · ${kilos(l.masa_neta_kg)}${l.estado === "anulado" ? ` (${ESTADOS_LOTE.anulado[1].toLowerCase()})` : ""}`)),
  );

  async function mostrar(id) {
    elegido = id || null;
    if (!elegido) {
      reemplazar(caja, h("p", { class: "panel-sub" }, "Elige un lote para ver de qué parcelas viene su cacao."));
      return;
    }
    reemplazar(caja, cargando());
    try {
      const g = await llamarApi(`/lotes/${elegido}/genealogia`);
      reemplazar(caja, h("p", {}, h("a", { href: `#/lotes-exportacion/${g.lote.id}`, class: "mono" }, g.lote.codigo), ` · ${kilos(g.masa_neta_kg)} de ${g.por_parcela.length} ${g.por_parcela.length === 1 ? "parcela" : "parcelas"}`), vistaGenealogia(g));
    } catch (error) {
      reemplazar(caja, errorDeCarga(error));
    }
  }
  if (elegido && lotes.some((l) => l.id === elegido)) selector.value = elegido;
  else elegido = null;
  await mostrar(elegido);

  return {
    titulo: "Genealogía por lote",
    antetitulo: "Trazabilidad",
    descripcion: "De los kilos de un lote, cuántos vienen de cada parcela. Se calcula al confirmar el lote; no se estima ni se edita.",
    migas: [["Trazabilidad", "#/trazabilidad"], ["Genealogía por lote"]],
    secciones: seccionesTrazabilidad(),
    contenido: h(
      "section",
      { class: "panel inspector" },
      lotes.length ? h("div", { class: "barra-lista" }, selector) : null,
      seccion({ titulo: "Genealogía", contenido: lotes.length ? caja : vacio({ titulo: "Sin lotes confirmados", texto: "La genealogía aparece cuando se confirma un lote de exportación." }) }),
    ),
  };
}

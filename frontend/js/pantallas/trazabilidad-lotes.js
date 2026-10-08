// Genealogía por lote (Trazabilidad), con la composición del diseño de referencia: buscador "Trazar" con los
// lotes recientes, una línea de resumen y la genealogía en columnas; debajo, la tabla por parcela y el mapa.
// Se busca por el código del lote (LE-…) o de su orden (OC-…).

import { llamarApi } from "../api.js";
import { resumenLote, vistaGenealogia } from "../exportacion.js";
import { cargando, errorDeCarga, h, icono, reemplazar, vacio } from "../ui.js";

let elegido = null;

export default async function trazabilidadLotes() {
  const lotes = (await llamarApi("/lotes")).filter((l) => l.estado !== "en_armado");
  const entrada = h("input", { placeholder: "Código del lote (LE-…) o de su orden (OC-…)", spellcheck: "false", autocomplete: "off", "aria-label": "Código del lote o de su orden" });
  const resumen = h("div", { class: "trace-sum", hidden: true });
  const genealogia = h("div", {});
  const recientes = h(
    "div",
    { class: "trace-quick" },
    lotes.length > 0 && h("span", {}, "Recientes"),
    lotes.slice(0, 5).map((l) => h("button", { class: "qchip", type: "button", onclick: () => trazar(l.codigo) }, l.codigo)),
  );

  async function mostrar(lote) {
    elegido = lote.id;
    entrada.value = lote.codigo;
    reemplazar(genealogia, cargando());
    try {
      const g = await llamarApi(`/lotes/${lote.id}/genealogia`);
      reemplazar(resumen, resumenLote(lote, g));
      resumen.hidden = false;
      reemplazar(genealogia, vistaGenealogia(g, { lote }));
    } catch (error) {
      resumen.hidden = true;
      reemplazar(genealogia, errorDeCarga(error));
    }
  }

  function trazar(texto) {
    const q = texto.trim().toUpperCase();
    const lote = lotes.find((l) => l.codigo === q || l.orden.codigo === q);
    if (lote) return mostrar(lote);
    resumen.hidden = false;
    reemplazar(resumen, h("span", { class: "alerta bad" }, q ? `No hay un lote confirmado con el código ${q}.` : "Escribe el código de un lote o de su orden."));
  }

  const formulario = h(
    "form",
    {
      class: "trace-bar",
      autocomplete: "off",
      onsubmit: (e) => {
        e.preventDefault();
        trazar(entrada.value);
      },
    },
    h("label", { class: "trace-in" }, icono("branch"), entrada, h("button", { class: "btn btn-primary btn-sm", type: "submit" }, "Trazar")),
    recientes,
  );

  const anterior = lotes.find((l) => l.id === elegido) ?? lotes[0];
  if (anterior) await mostrar(anterior);

  return {
    titulo: "Genealogía por lote",
    antetitulo: "Trazabilidad",
    descripcion: "De un lote de exportación hasta las parcelas de origen, con los kilos y la proporción de cada una. Se calcula al confirmar el lote; no se estima ni se edita.",
    migas: [["Trazabilidad", "#/trazabilidad"], ["Genealogía por lote"]],
    contenido: lotes.length
      ? [h("section", { class: "panel" }, formulario, resumen), genealogia]
      : h("section", { class: "panel" }, vacio({ titulo: "Sin lotes confirmados", texto: "La genealogía aparece cuando se confirma un lote de exportación." })),
  };
}

// Mis parcelas (productor, desde el celular): lista con alertas y el asistente de 3 pasos.

import { llamarApi } from "../api.js";
import { hectareas, insigniaAlerta } from "../textos.js";
import { h, icono, vacio } from "../ui.js";

export default async function misParcelas({ navegar }) {
  const parcelas = await llamarApi("/mi/parcelas");
  const nueva = h("button", { class: "btn btn-primary", type: "button", onclick: () => navegar("#/mis-parcelas/nueva") }, icono("mas"), "Nueva parcela");
  return {
    titulo: "Mis parcelas",
    accion: nueva,
    contenido: parcelas.length
      ? h(
          "div",
          { class: "lista-tarjetas" },
          parcelas.map((p) =>
            h(
              "a",
              { class: "panel tarjeta-parcela", href: `#/mis-parcelas/${p.id}` },
              h("b", {}, p.nombre),
              h("span", { class: "sec mono" }, `${p.codigo} · ${hectareas(p.area_total_ha)}`),
              p.alertas.length ? h("div", { class: "fila-acciones" }, p.alertas.map((a) => insigniaAlerta(a))) : h("span", { class: "sec" }, "Sin alertas"),
            ),
          ),
        )
      : h(
          "section",
          { class: "panel" },
          vacio({
            titulo: "Todavía no registras parcelas",
            texto: "Registra cada parcela por separado: dibújala en el mapa tocando cada vértice o sube un archivo.",
            accion: h("button", { class: "btn btn-primary", type: "button", onclick: () => navegar("#/mis-parcelas/nueva") }, "Registrar mi primera parcela"),
          }),
        ),
  };
}

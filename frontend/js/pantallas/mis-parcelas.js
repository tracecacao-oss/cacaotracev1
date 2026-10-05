// Mis parcelas (productor, desde el celular): lista con alertas y el asistente de 3 pasos.

import { llamarApi } from "../api.js";
import { hectareas, insigniaAlerta } from "../textos.js";
import { h, icono, vacio } from "../ui.js";

export default async function misParcelas({ navegar }) {
  const parcelas = await llamarApi("/mi/parcelas");
  const nueva = h("button", { class: "btn btn-primary", type: "button", onclick: () => navegar("#/mis-parcelas/nueva") }, icono("mas"), "Nueva parcela");
  return {
    titulo: "Mis parcelas",
    descripcion: "Cada parcela donde cultivas cacao, con su área y sus alertas.",
    accion: nueva,
    contenido: parcelas.length
      ? h(
          "div",
          { class: "lista-tarjetas" },
          parcelas.map((p) =>
            h(
              "a",
              { class: "panel tarjeta-parcela", href: `#/mis-parcelas/${p.id}` },
              h(
                "span",
                { class: "tarjeta-r" },
                h("b", {}, p.nombre),
                p.alertas.length
                  ? h("span", { class: "badge warn" }, h("span", { class: "dot" }), p.alertas.length === 1 ? "1 alerta" : `${p.alertas.length} alertas`)
                  : h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Sin alertas"),
              ),
              h("span", { class: "tarjeta-r mono" }, h("span", {}, p.codigo), h("span", {}, hectareas(p.area_total_ha))),
              h("span", { class: "sec" }, `${p.distrito}, ${p.provincia}`),
              p.alertas.length ? h("div", { class: "fila-acciones" }, p.alertas.map((a) => insigniaAlerta(a))) : null,
            ),
          ),
        )
      : h(
          "section",
          { class: "panel" },
          vacio({
            titulo: "Todavía no registras parcelas",
            texto: "Registra cada parcela por separado: dibújala en el mapa, sube un archivo o escribe sus coordenadas.",
            accion: h("button", { class: "btn btn-primary", type: "button", onclick: () => navegar("#/mis-parcelas/nueva") }, "Registrar mi primera parcela"),
          }),
        ),
  };
}

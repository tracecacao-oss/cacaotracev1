// Mis parcelas (productor, desde el celular): lista con su estado de habilitación, lo que le falta
// a cada una en lenguaje simple, sus alertas y el asistente de 3 pasos.

import { llamarApi } from "../api.js";
import { REQUISITOS_PRODUCTOR, hectareas, insigniaAlerta, insigniaHabilitacion } from "../textos.js";
import { h, icono, vacio } from "../ui.js";

// Alertas que ya se dicen, en lenguaje simple, en la lista de lo que falta.
const DICHAS_EN_REQUISITOS = { sin_analisis_vigente: "analisis_vigente", expediente_incompleto: "expediente_completo" };
const alertasSinRepetir = (p) => p.alertas.filter((a) => !p.requisitos_pendientes.includes(DICHAS_EN_REQUISITOS[a]));

export default async function misParcelas({ navegar }) {
  const parcelas = await llamarApi("/mi/parcelas");
  const nueva = h("button", { class: "btn btn-primary", type: "button", onclick: () => navegar("#/mis-parcelas/nueva") }, icono("mas"), "Nueva parcela");
  return {
    titulo: "Mis parcelas",
    descripcion: "Cada parcela donde cultivas cacao, con su área, su estado y lo que le falta.",
    accion: nueva,
    contenido: parcelas.length
      ? h(
          "div",
          { class: "lista-tarjetas" },
          parcelas.map((p) =>
            h(
              "a",
              { class: "panel tarjeta-parcela", href: `#/mis-parcelas/${p.id}` },
              h("span", { class: "tarjeta-r" }, h("b", {}, p.nombre), insigniaHabilitacion(p.habilitacion_estado)),
              h("span", { class: "tarjeta-r mono" }, h("span", {}, p.codigo), h("span", {}, hectareas(p.area_total_ha))),
              h("span", { class: "sec" }, `${p.distrito}, ${p.provincia}`),
              p.requisitos_pendientes.length
                ? h("ul", { class: "lista-simple" }, p.requisitos_pendientes.map((r) => h("li", {}, REQUISITOS_PRODUCTOR[r] ?? r)))
                : null,
              alertasSinRepetir(p).length ? h("div", { class: "fila-acciones" }, alertasSinRepetir(p).map((a) => insigniaAlerta(a))) : null,
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

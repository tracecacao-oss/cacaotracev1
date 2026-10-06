// Mis entregas (productor, desde el celular): sus tandas con fecha, parcela, peso y estado, el PDF del DOP
// de cada una y, desde la Parte 6, en qué fase del proceso está su cacao o si ya entró al stock. Solo
// lectura: la recepción la registra la cooperativa en su balanza.

import { llamarApi } from "../api.js";
import { PRODUCTO, insigniaDop, insigniaTanda, kilos } from "../textos.js";
import { descargarPdf } from "../tandas.js";
import { fecha, h, icono, vacio } from "../ui.js";

export default async function misEntregas() {
  const tandas = await llamarApi("/mi/tandas");
  return {
    titulo: "Mis entregas",
    descripcion: "El cacao que entregaste a la cooperativa, con su DOP cuando la entrega se valida.",
    contenido: tandas.length
      ? h(
          "div",
          { class: "lista-tarjetas" },
          tandas.map((t) =>
            h(
              "article",
              { class: "panel tarjeta-parcela" },
              h("span", { class: "tarjeta-r" }, h("b", {}, fecha(t.recibida_en, { hora: true })), insigniaTanda(t.estado)),
              h("span", { class: "tarjeta-r mono" }, h("span", {}, kilos(t.peso_kg)), h("span", {}, t.codigo)),
              h("span", { class: "sec" }, `${PRODUCTO[t.estado_producto]} · ${t.parcela.nombre} (${t.parcela.codigo}) · ${t.lugar_nombre}`),
              t.proceso &&
                h(
                  "span",
                  { class: `badge ${t.proceso.estado === "consolidada" ? "ok" : "info"}` },
                  h("span", { class: "dot" }),
                  t.proceso.estado === "consolidada" ? "Procesado: ya entró al stock" : `En proceso: ${t.proceso.fase_nombre.toLowerCase()}`,
                ),
              t.dop
                ? h(
                    "div",
                    { class: "fila-acciones" },
                    insigniaDop(t.dop.estado),
                    h("span", { class: "mono sec" }, t.dop.codigo),
                    h("button", { class: "btn btn-sm", type: "button", onclick: () => descargarPdf(`/mi/dops/${t.dop.id}/pdf`) }, icono("download"), "Descargar PDF"),
                  )
                : t.estado !== "anulada" && h("span", { class: "sec" }, "El DOP se emite cuando la cooperativa valida la entrega."),
            ),
          ),
        )
      : h("section", { class: "panel" }, vacio({ titulo: "Todavía no tienes entregas", texto: "Cuando la cooperativa pese tu cacao en su balanza, la entrega aparecerá aquí." })),
  };
}

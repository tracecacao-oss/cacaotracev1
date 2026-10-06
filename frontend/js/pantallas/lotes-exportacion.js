// Lotes (segunda sección de Exportación): código, orden, masa, número de parcelas y estado.

import { llamarApi } from "../api.js";
import { estadoLote, insigniaFifo, seccionesExportacion } from "../exportacion.js";
import { kilos } from "../textos.js";
import { cargando, errorDeCarga, fecha, h, reemplazar, seccion, vacio } from "../ui.js";

const FILTROS = [
  ["", "Todos"],
  ["en_armado", "En armado"],
  ["armado", "Armados"],
  ["bloqueado", "Bloqueados"],
  ["listo", "Listos"],
  ["cerrado", "Cerrados"],
  ["anulado", "Anulados"],
];
let filtro = "";

function tabla(lotes) {
  if (!lotes.length) return vacio({ titulo: "Sin lotes", texto: "Un lote se arma desde su orden de compra, con el botón \"Armar lote\"." });
  return h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "Lote"), h("th", {}, "Orden"), h("th", { class: "num" }, "Masa"), h("th", { class: "num" }, "Parcelas"), h("th", {}, "Estado"))),
      h(
        "tbody",
        {},
        lotes.map((l) =>
          h(
            "tr",
            {},
            h("td", {}, h("a", { href: `#/lotes-exportacion/${l.id}`, class: "mono" }, l.codigo), h("span", { class: "sec" }, l.armado_en ? `Armado el ${fecha(l.armado_en, { hora: true })}` : `Creado el ${fecha(l.creado_en, { hora: true })}`)),
            h("td", {}, h("a", { href: `#/ordenes/${l.orden.id}`, class: "mono" }, l.orden.codigo), h("span", { class: "sec" }, `${l.importador} · ${l.calidad}`)),
            h("td", { class: "num" }, h("span", { class: "mono" }, kilos(l.masa_neta_kg ?? l.seleccionado_kg)), !l.masa_neta_kg && h("span", { class: "sec" }, `seleccionado de ${kilos(l.cantidad_kg)}`)),
            h("td", { class: "num mono" }, l.numero_parcelas ?? "—"),
            h("td", {}, estadoLote(l.estado), l.desviacion_fifo && insigniaFifo()),
          ),
        ),
      ),
    ),
  );
}

export default async function lotesExportacion() {
  const lista = h("div", {}, cargando());
  const chips = h("div", { class: "fchips", role: "group", "aria-label": "Estado del lote" });
  async function cargar() {
    for (const b of chips.children) b.setAttribute("aria-pressed", String(b.dataset.valor === filtro));
    reemplazar(lista, cargando());
    try {
      reemplazar(lista, tabla(await llamarApi("/lotes", { parametros: { estado: filtro } })));
    } catch (error) {
      reemplazar(lista, errorDeCarga(error));
    }
  }
  for (const [valor, texto] of FILTROS) {
    chips.append(h("button", { class: "fchip", type: "button", "data-valor": valor, onclick: () => ((filtro = valor), cargar()) }, texto));
  }
  await cargar();
  return {
    titulo: "Lotes",
    antetitulo: "Exportación",
    descripcion: "Cada lote reúne el stock que cumple una orden. Al confirmarse descuenta los saldos y calcula de qué parcelas viene.",
    migas: [["Exportación", "#/exportacion"], ["Lotes"]],
    secciones: seccionesExportacion(),
    contenido: h("section", { class: "panel inspector" }, h("div", { class: "barra-lista" }, chips), seccion({ titulo: "Lotes de exportación", contenido: lista })),
  };
}

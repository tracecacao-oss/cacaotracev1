// Órdenes (primera sección de Exportación): código, importador, cantidad, calidad, entrega y estado, con
// filtro por estado y el botón "Nueva orden".

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { estadoLote, estadoOrden, seccionesExportacion } from "../exportacion.js";
import { kilos } from "../textos.js";
import { cargando, errorDeCarga, fecha, h, icono, reemplazar, seccion, vacio } from "../ui.js";

const FILTROS = [
  ["", "Todas"],
  ["abierta", "Abiertas"],
  ["con_lote", "Con lote"],
  ["cerrada", "Cerradas"],
  ["anulada", "Anuladas"],
];
let filtro = "";

function tabla(ordenes) {
  if (!ordenes.length) {
    return vacio({ titulo: "Sin órdenes", texto: "Registra la orden de compra de un importador para armar su lote de exportación." });
  }
  return h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla" },
      h(
        "thead",
        {},
        h("tr", {}, h("th", {}, "Orden"), h("th", {}, "Importador"), h("th", { class: "num" }, "Cantidad"), h("th", { class: "ocultar-sm" }, "Calidad"), h("th", { class: "ocultar-sm" }, "Entrega"), h("th", {}, "Estado")),
      ),
      h(
        "tbody",
        {},
        ordenes.map((o) =>
          h(
            "tr",
            {},
            h("td", {}, h("a", { href: `#/ordenes/${o.id}`, class: "mono" }, o.codigo), o.referencia_importador && h("span", { class: "sec" }, `Ref. ${o.referencia_importador}`)),
            h("td", {}, o.importador.razon_social, h("span", { class: "sec" }, `${o.lugar_destino}, ${o.pais_destino}`)),
            h("td", { class: "num" }, h("span", { class: "mono" }, kilos(o.cantidad_kg)), Number(o.tolerancia_pct) > 0 && h("span", { class: "sec" }, `± ${o.tolerancia_pct} %`)),
            h("td", { class: "ocultar-sm" }, o.calidad),
            h("td", { class: "ocultar-sm" }, fecha(o.fecha_entrega)),
            h("td", {}, estadoOrden(o.estado), o.lote && h("a", { href: `#/lotes-exportacion/${o.lote.id}`, class: "sec mono" }, o.lote.codigo), o.lote && o.lote.estado === "en_armado" && estadoLote(o.lote.estado)),
          ),
        ),
      ),
    ),
  );
}

export default async function ordenes() {
  const lista = h("div", {}, cargando());
  const chips = h("div", { class: "fchips", role: "group", "aria-label": "Estado de la orden" });
  async function cargar() {
    for (const b of chips.children) b.setAttribute("aria-pressed", String(b.dataset.valor === filtro));
    reemplazar(lista, cargando());
    try {
      reemplazar(lista, tabla(await llamarApi("/ordenes", { parametros: { estado: filtro } })));
    } catch (error) {
      reemplazar(lista, errorDeCarga(error));
    }
  }
  for (const [valor, texto] of FILTROS) {
    chips.append(h("button", { class: "fchip", type: "button", "data-valor": valor, onclick: () => ((filtro = valor), cargar()) }, texto));
  }
  await cargar();
  const opera = ["admin_cooperativa", "operador"].includes(rolEfectivo());
  return {
    titulo: "Órdenes",
    antetitulo: "Exportación",
    descripcion: "Cada orden de compra pide una cantidad y una calidad. Su lote de exportación toma el stock del más antiguo al más nuevo.",
    migas: [["Exportación", "#/exportacion"], ["Órdenes"]],
    secciones: seccionesExportacion(),
    accion: opera && h("a", { class: "btn btn-primary", href: "#/exportacion/ordenes/nueva" }, icono("plus"), "Nueva orden"),
    contenido: h("section", { class: "panel inspector" }, h("div", { class: "barra-lista" }, chips), seccion({ titulo: "Órdenes de compra", contenido: lista })),
  };
}

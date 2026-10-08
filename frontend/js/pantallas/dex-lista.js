// DEX (sección de Exportación, Parte 9): los expedientes emitidos, con código, lote, importador, masa, fecha
// y estado. Cada fila lleva a la pestaña DEX de su lote, donde están la huella, el código QR y las descargas.

import { llamarApi } from "../api.js";
import { insignia } from "../exportacion.js";
import { kilos } from "../textos.js";
import { cargando, errorDeCarga, fecha, h, reemplazar, seccion, vacio } from "../ui.js";

const FILTROS = [
  ["", "Todos"],
  ["vigente", "Vigentes"],
  ["anulado", "Anulados"],
];
const ESTADOS = { vigente: ["ok", "Vigente"], anulado: ["bad", "Anulado"] };
const filtros = { estado: "", importador_id: "" };

function tabla(lista) {
  if (!lista.length) return vacio({ titulo: "Sin DEX", texto: "El DEX se emite desde un lote listo, en su pestaña DEX." });
  return h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "DEX"), h("th", {}, "Lote"), h("th", { class: "ocultar-sm" }, "Importador"), h("th", { class: "num" }, "Masa"), h("th", {}, "Emitido"), h("th", {}, "Estado"))),
      h(
        "tbody",
        {},
        lista.map((d) =>
          h(
            "tr",
            {},
            h("td", {}, h("a", { href: `#/lotes-exportacion/${d.lote_id}/dex`, class: "mono" }, d.codigo), h("span", { class: "sec mono" }, `${d.contenido_sha256.slice(0, 16)}…`)),
            h("td", { class: "sin-corte" }, h("a", { href: `#/lotes-exportacion/${d.lote_id}`, class: "mono" }, d.lote_codigo), h("span", { class: "sec mono" }, d.orden_codigo)),
            h("td", { class: "ocultar-sm" }, d.importador),
            h("td", { class: "num mono" }, kilos(d.masa_neta_kg)),
            h("td", { class: "sin-corte" }, fecha(d.emitido_en)),
            h("td", {}, insignia(ESTADOS[d.estado] ?? ["", d.estado])),
          ),
        ),
      ),
    ),
  );
}

export default async function dexLista() {
  const lista = h("div", {}, cargando());
  const chips = h("div", { class: "fchips", role: "group", "aria-label": "Estado del DEX", "data-etiqueta": "Estado" });
  const importadores = await llamarApi("/importadores").catch(() => []);
  async function cargar() {
    for (const b of chips.children) b.setAttribute("aria-pressed", String(b.dataset.valor === filtros.estado));
    reemplazar(lista, cargando());
    try {
      reemplazar(lista, tabla(await llamarApi("/dex", { parametros: filtros })));
    } catch (error) {
      reemplazar(lista, errorDeCarga(error));
    }
  }
  for (const [valor, texto] of FILTROS) {
    chips.append(h("button", { class: "fchip", type: "button", "data-valor": valor, onclick: () => ((filtros.estado = valor), cargar()) }, texto));
  }
  const selector = h(
    "select",
    { class: "select", "aria-label": "Importador", onchange: (e) => ((filtros.importador_id = e.target.value), cargar()) },
    h("option", { value: "" }, "Todos los importadores"),
    importadores.map((i) => h("option", { value: i.id }, i.razon_social)),
  );
  selector.value = filtros.importador_id;
  await cargar();
  return {
    titulo: "DEX",
    antetitulo: "Exportación",
    descripcion: "El expediente que la cooperativa descarga y envía al importador. No declara un nivel de riesgo ni reemplaza la DDS.",
    migas: [["Exportación", "#/exportacion"], ["DEX"]],
    contenido: h("section", { class: "panel inspector" }, h("div", { class: "barra-lista" }, chips, selector), seccion({ titulo: "Expedientes emitidos", contenido: lista })),
  };
}

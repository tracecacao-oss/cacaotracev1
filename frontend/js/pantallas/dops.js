// DOP (segunda sección de Lotes y proceso): lista con código, productor, parcela, peso, fecha y estado.

import { llamarApi } from "../api.js";
import { PRODUCTO, insigniaDop, kilos } from "../textos.js";
import { seccionesLotes } from "../tandas.js";
import { cargando, errorDeCarga, fecha, h, reemplazar, seccion, vacio } from "../ui.js";

const FILTROS = [
  ["", "Todos"],
  ["vigente", "Vigentes"],
  ["anulado", "Anulados"],
];
let filtro = "";

function tabla(dops) {
  if (!dops.length) {
    return vacio({ titulo: "Sin DOP", texto: "Cada tanda validada en Recepción emite su DOP, que aparece aquí." });
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
        h("tr", {}, h("th", {}, "DOP"), h("th", {}, "Productor"), h("th", { class: "ocultar-sm" }, "Parcela"), h("th", { class: "num" }, "Peso"), h("th", {}, "Estado")),
      ),
      h(
        "tbody",
        {},
        dops.map((d) =>
          h(
            "tr",
            {},
            h("td", {}, h("a", { href: `#/dops/${d.id}`, class: "mono" }, d.codigo), h("span", { class: "sec" }, `${fecha(d.emitido_en, { hora: true })} · `, h("span", { class: "mono" }, d.tanda_codigo))),
            h("td", {}, `${d.productor.nombres} ${d.productor.apellidos}`, h("span", { class: "sec mono" }, `DNI ${d.productor.dni}`)),
            h("td", { class: "ocultar-sm" }, h("span", { class: "mono" }, d.parcela_codigo), h("span", { class: "sec" }, d.parcela_nombre)),
            h("td", { class: "num" }, h("span", { class: "mono" }, kilos(d.peso_kg)), h("span", { class: "sec" }, PRODUCTO[d.estado_producto])),
            h("td", {}, insigniaDop(d.estado)),
          ),
        ),
      ),
    ),
  );
}

export default async function dops() {
  const lista = h("div", {}, cargando());
  const chips = h("div", { class: "fchips", role: "group", "aria-label": "Estado del DOP" });

  async function cargar() {
    for (const b of chips.children) b.setAttribute("aria-pressed", String(b.dataset.valor === filtro));
    reemplazar(lista, cargando());
    try {
      reemplazar(lista, tabla(await llamarApi("/dops", { parametros: { estado: filtro } })));
    } catch (error) {
      reemplazar(lista, errorDeCarga(error));
    }
  }
  for (const [valor, texto] of FILTROS) {
    chips.append(h("button", { class: "fchip", type: "button", "data-valor": valor, onclick: () => ((filtro = valor), cargar()) }, texto));
  }
  await cargar();

  return {
    titulo: "DOP",
    antetitulo: "Lotes y proceso",
    descripcion: "Cada DOP es la copia sellada de lo que respaldaba una tanda al validarse. No cambia; solo se anula, con motivo.",
    migas: [["Lotes y proceso", "#/lotes"], ["DOP"]],
    secciones: seccionesLotes(),
    contenido: h("section", { class: "panel inspector" }, h("div", { class: "barra-lista" }, chips), seccion({ titulo: "Documentos de origen", contenido: lista })),
  };
}

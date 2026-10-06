// Stock (cuarta sección de Lotes y proceso): las tandas finales con código, calidad, peso, saldo, fecha de
// ingreso y almacén. Filtros por estado y por calidad.

import { llamarApi } from "../api.js";
import { ESTADOS_TANDA_FINAL, insignia } from "../proceso.js";
import { kilos } from "../textos.js";
import { seccionesLotes } from "../tandas.js";
import { cargando, errorDeCarga, fecha, h, reemplazar, seccion, vacio } from "../ui.js";

const FILTROS = [
  ["en_stock", "En stock"],
  ["agotada", "Agotadas"],
  ["anulada", "Anuladas"],
  ["", "Todas"],
];
const filtro = { estado: "en_stock", calidad_id: "" };

function tabla(finales) {
  if (!finales.length) {
    return vacio({ titulo: "Sin tandas finales", texto: "Cada corrida consolidada deja aquí su tanda final, con su DPP." });
  }
  const total = finales.filter((f) => f.estado === "en_stock").reduce((s, f) => s + Number(f.saldo_kg), 0);
  return [
    total > 0 && h("p", { class: "panel-sub" }, `Saldo en stock: ${kilos(total)}.`),
    h(
      "div",
      { class: "tbl-box" },
      h(
        "table",
        { class: "tabla" },
        h(
          "thead",
          {},
          h("tr", {}, h("th", {}, "Tanda final"), h("th", {}, "Calidad"), h("th", { class: "num" }, "Peso"), h("th", { class: "num" }, "Saldo"), h("th", { class: "ocultar-sm" }, "Ingreso"), h("th", { class: "ocultar-sm" }, "Almacén"), h("th", {}, "Estado")),
        ),
        h(
          "tbody",
          {},
          finales.map((f) =>
            h(
              "tr",
              {},
              h("td", {}, h("a", { href: `#/tandas-finales/${f.id}`, class: "mono" }, f.codigo), h("span", { class: "sec mono" }, [f.corrida_codigo, f.dpp?.codigo].filter(Boolean).join(" · "))),
              h("td", {}, f.calidad, h("span", { class: "sec" }, `${f.numero_sacos} ${f.numero_sacos === 1 ? "saco" : "sacos"}`)),
              h("td", { class: "num mono" }, kilos(f.peso_seco_kg)),
              h("td", { class: "num mono" }, kilos(f.saldo_kg)),
              h("td", { class: "ocultar-sm" }, fecha(f.ingreso_stock_en, { hora: true })),
              h("td", { class: "ocultar-sm" }, f.lugar_nombre),
              h("td", {}, insignia(ESTADOS_TANDA_FINAL[f.estado] ?? ["", f.estado])),
            ),
          ),
        ),
      ),
    ),
  ];
}

export default async function stock() {
  const calidades = await llamarApi("/calidades");
  const lista = h("div", {}, cargando());
  const chips = h("div", { class: "fchips", role: "group", "aria-label": "Estado de la tanda final" });
  const selector = h(
    "select",
    { class: "select", "aria-label": "Calidad", onchange: (e) => ((filtro.calidad_id = e.target.value), cargar()) },
    h("option", { value: "" }, "Todas las calidades"),
    calidades.map((c) => h("option", { value: c.id }, c.activo ? c.nombre : `${c.nombre} (inactiva)`)),
  );
  selector.value = filtro.calidad_id;

  async function cargar() {
    for (const b of chips.children) b.setAttribute("aria-pressed", String(b.dataset.valor === filtro.estado));
    reemplazar(lista, cargando());
    try {
      reemplazar(lista, tabla(await llamarApi("/tandas-finales", { parametros: filtro })));
    } catch (error) {
      reemplazar(lista, errorDeCarga(error));
    }
  }
  for (const [valor, texto] of FILTROS) {
    chips.append(h("button", { class: "fchip", type: "button", "data-valor": valor, onclick: () => ((filtro.estado = valor), cargar()) }, texto));
  }
  await cargar();

  return {
    titulo: "Stock",
    antetitulo: "Lotes y proceso",
    descripcion: "Las tandas finales de las corridas consolidadas: grano seco listo para las órdenes de compra.",
    migas: [["Lotes y proceso", "#/lotes"], ["Stock"]],
    secciones: seccionesLotes(),
    contenido: h("section", { class: "panel inspector" }, h("div", { class: "barra-lista" }, chips, calidades.length > 0 && selector), seccion({ titulo: "Tandas finales", contenido: lista })),
  };
}

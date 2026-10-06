// Corridas (tercera sección de Lotes y proceso): tablero de cinco columnas, una por fase. Las tarjetas no se
// arrastran: una corrida cambia de columna sola cuando se registran sus etapas.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { ALERTAS_CORRIDA, ESTADOS_CORRIDA, FASES, RUTAS, etiqueta, insignia, insigniaManejo } from "../proceso.js";
import { kilos } from "../textos.js";
import { seccionesLotes } from "../tandas.js";
import { fecha, h, icono, seccion } from "../ui.js";

function tarjeta(c) {
  return h(
    "a",
    { class: "lot tarjeta-corrida", href: `#/corridas/${c.id}`, "aria-label": `Abrir la corrida ${c.codigo}` },
    h("span", { class: "lot-h" }, h("b", { class: "lot-id" }, c.codigo), insigniaManejo(c.tipo_manejo)),
    h(
      "span",
      { class: "lot-facts" },
      h("span", {}, h("b", { class: "mono" }, kilos(c.entrada_kg)), "de entrada"),
      h("span", {}, h("b", {}, `${c.numero_tandas} ${c.numero_tandas === 1 ? "tanda" : "tandas"}`), `ruta ${etiqueta(RUTAS, c.ruta).toLowerCase()}`),
    ),
    h(
      "span",
      { class: "lot-f" },
      c.estado === "abierta"
        ? insignia(ESTADOS_CORRIDA.abierta)
        : h("span", {}, c.etapa_actual ? `Etapa ${c.etapa_actual}: ${c.etapa_actual_nombre}` : "Lista para consolidar"),
      c.alertas.length > 0 && h("span", { class: "badge warn", title: c.alertas.map((a) => ALERTAS_CORRIDA[a] ?? a).join(". ") }, h("span", { class: "dot" }), c.alertas.length === 1 ? "1 alerta" : `${c.alertas.length} alertas`),
    ),
  );
}

export default async function corridas() {
  const [activas, recientes] = await Promise.all([
    llamarApi("/corridas").then((lista) => lista.filter((c) => ["abierta", "en_proceso"].includes(c.estado))),
    llamarApi("/corridas", { parametros: { estado: "consolidada" } }),
  ]);
  const opera = ["admin_cooperativa", "operador"].includes(rolEfectivo());
  const tablero = h(
    "div",
    { class: "kanban tablero" },
    FASES.map(([clave, nombre], i) => {
      const columna = activas.filter((c) => c.fase === clave);
      const kg = columna.reduce((s, c) => s + Number(c.entrada_kg), 0);
      return h(
        "section",
        { class: "kcol", "aria-label": `Fase ${i + 1}: ${nombre}` },
        h("header", { class: "kcol-h" }, h("span", { class: "kcol-n" }, String(i + 1)), h("div", {}, h("h3", {}, nombre), h("p", {}, `${kilos(kg)} de entrada`)), h("span", { class: "count mono" }, String(columna.length))),
        h("div", { class: "kcol-b" }, columna.length ? columna.map(tarjeta) : h("div", { class: "kcol-empty" }, "Sin corridas en esta fase.")),
      );
    }),
  );
  return {
    titulo: "Corridas",
    antetitulo: "Lotes y proceso",
    descripcion: "Cada corrida lleva una o varias tandas validadas por las 23 etapas del proceso hasta el stock.",
    migas: [["Lotes y proceso", "#/lotes"], ["Corridas"]],
    secciones: seccionesLotes(),
    accion: opera && h("a", { class: "btn btn-primary", href: "#/lotes/corridas/nueva" }, icono("plus"), "Nueva corrida"),
    contenido: [
      tablero,
      recientes.length > 0 &&
        h(
          "section",
          { class: "panel inspector" },
          seccion({
            titulo: "Consolidadas recientes",
            sub: "Ya entraron al stock con su DPP.",
            contenido: h(
              "div",
              { class: "tbl-box" },
              h(
                "table",
                { class: "tabla" },
                h("thead", {}, h("tr", {}, h("th", {}, "Corrida"), h("th", {}, "Manejo"), h("th", { class: "num" }, "Entrada"), h("th", {}, "DPP"))),
                h(
                  "tbody",
                  {},
                  recientes.slice(0, 20).map((c) =>
                    h(
                      "tr",
                      {},
                      h("td", {}, h("a", { href: `#/corridas/${c.id}`, class: "mono" }, c.codigo), h("span", { class: "sec" }, fecha(c.consolidada_en, { hora: true }))),
                      h("td", {}, insigniaManejo(c.tipo_manejo)),
                      h("td", { class: "num mono" }, kilos(c.entrada_kg)),
                      h("td", {}, c.dpp ? h("a", { href: `#/dpps/${c.dpp.id}`, class: "mono" }, c.dpp.codigo) : "—"),
                    ),
                  ),
                ),
              ),
            ),
          }),
        ),
    ],
  };
}

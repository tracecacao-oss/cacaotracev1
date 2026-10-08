// Detalle de una tanda final: lo que entró al stock y su composición, es decir, qué DOP la componen y
// cuántos kilos de grano seco corresponden a cada uno (proporción por el peso seco de la tanda final).

import { llamarApi } from "../api.js";
import { ESTADOS_TANDA_FINAL, insignia } from "../proceso.js";
import { kilos } from "../textos.js";
import { cabeceraFicha, fecha, h, icono, rejilla, seccion } from "../ui.js";

export default async function tandaFinal({ parametros: [id] }) {
  const f = await llamarApi(`/tandas-finales/${id}`);
  const porcentaje = (p) => `${(Number(p) * 100).toLocaleString("es-PE", { maximumFractionDigits: 4 })} %`;
  return {
    titulo: f.codigo,
    migas: [["Lotes y proceso", "#/lotes"], ["Stock", "#/lotes/stock"], [f.codigo]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("sack")),
        titulo: f.codigo,
        codigo: true,
        insignias: [insignia(ESTADOS_TANDA_FINAL[f.estado] ?? ["", f.estado])],
        detalle: [`${f.calidad} · ${f.lugar_nombre} · ingresó el ${fecha(f.ingreso_stock_en, { hora: true })}`],
        cifra: kilos(f.saldo_kg),
        cifraTexto: `de saldo · de ${kilos(f.peso_seco_kg)}`,
      }),
      seccion({
        titulo: "Tanda final",
        contenido: rejilla([
          { etiqueta: "Corrida", valor: h("a", { href: `#/corridas/${f.corrida_id}`, class: "mono" }, f.corrida_codigo) },
          { etiqueta: "DPP", valor: f.dpp && h("a", { href: `#/dpps/${f.dpp.id}`, class: "mono" }, f.dpp.codigo) },
          { etiqueta: "Peso seco", valor: kilos(f.peso_seco_kg), mono: true },
          { etiqueta: "Saldo", valor: kilos(f.saldo_kg), mono: true },
          { etiqueta: "Humedad", valor: f.humedad_pct == null ? null : `${f.humedad_pct} %`, mono: true },
          { etiqueta: "Calidad", valor: f.calidad },
          { etiqueta: "Sacos", valor: String(f.numero_sacos), mono: true },
          { etiqueta: "Almacén", valor: f.lugar_nombre },
        ]),
      }),
      seccion({
        titulo: "Composición",
        sub: "Los DOP que la componen. Los kilos atribuibles son la proporción de cada tanda sobre la masa de entrada, por el peso seco de la tanda final.",
        contenido: h(
          "div",
          { class: "tbl-box" },
          h(
            "table",
            { class: "tabla" },
            h(
              "thead",
              {},
              h("tr", {}, h("th", {}, "DOP"), h("th", {}, "Productor"), h("th", { class: "ocultar-sm" }, "Parcela"), h("th", { class: "num ocultar-sm" }, "Entrada"), h("th", { class: "num" }, "Proporción"), h("th", { class: "num" }, "Kilos atribuibles")),
            ),
            h(
              "tbody",
              {},
              f.composicion.map((c) =>
                h(
                  "tr",
                  {},
                  h("td", {}, c.dop ? h("a", { href: `#/dops/${c.dop.id}`, class: "mono" }, c.dop.codigo) : "—", h("a", { href: `#/tandas/${c.tanda_id}`, class: "sec mono" }, c.tanda_codigo)),
                  h("td", {}, `${c.productor.nombres} ${c.productor.apellidos}`, h("span", { class: "sec mono" }, `DNI ${c.productor.dni}`)),
                  h("td", { class: "ocultar-sm" }, h("span", { class: "mono" }, c.parcela_codigo), h("span", { class: "sec" }, c.parcela_nombre)),
                  h("td", { class: "num mono ocultar-sm" }, kilos(c.peso_entrada_kg)),
                  h("td", { class: "num mono" }, porcentaje(c.proporcion)),
                  h("td", { class: "num mono" }, kilos(c.kg_atribuibles)),
                ),
              ),
            ),
          ),
        ),
      }),
    ),
  };
}

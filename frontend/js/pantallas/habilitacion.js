// Habilitación (cuarta sección de Productores): cuántas parcelas hay en cada estado, qué le falta a
// cada una y qué documentos legales vencen pronto. La decisión se toma en el detalle de la parcela.

import { llamarApi } from "../api.js";
import { ESTADOS_CASILLA, ESTADOS_HABILITACION, REQUISITOS, insigniaAlerta } from "../textos.js";
import { fecha, h, icono, reemplazar, seccion, vacio } from "../ui.js";

const ORDEN = ["pendiente", "observada", "habilitada", "excluida"];
const ICONO = { pendiente: "clock", observada: "alert", habilitada: "check", excluida: "x" };
const TONO = { pendiente: "", observada: "is-warn", habilitada: "is-ok", excluida: "is-bad" };
let filtro = "pendiente";

function tablaParcelas(parcelas, estadoElegido) {
  if (!parcelas.length) {
    return vacio({ titulo: `Sin parcelas ${ESTADOS_HABILITACION[estadoElegido][1].toLowerCase()}s`, texto: "No hay parcelas de la cooperativa en este estado." });
  }
  return h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "Parcela"), h("th", {}, "Productor"), h("th", {}, estadoElegido === "habilitada" ? "Alertas" : "Lo que falta"))),
      h(
        "tbody",
        {},
        parcelas.map((p) =>
          h(
            "tr",
            {},
            h("td", {}, h("a", { href: `#/parcelas/${p.id}`, class: "mono" }, p.codigo), h("span", { class: "sec" }, p.nombre), p.estado === "inactiva" && h("span", { class: "sec" }, "Inactiva")),
            h("td", {}, h("a", { href: `#/productores/${p.productor.id}` }, `${p.productor.nombres} ${p.productor.apellidos}`)),
            h(
              "td",
              {},
              estadoElegido === "excluida"
                ? h("span", { class: "sec" }, "Exclusión definitiva")
                : p.requisitos_pendientes.length
                  ? h("ul", { class: "lista-simple" }, p.requisitos_pendientes.map((r) => h("li", {}, REQUISITOS[r] ?? r)))
                  : estadoElegido === "habilitada"
                    ? p.alertas.length
                      ? h("div", { class: "fila-acciones" }, p.alertas.map((a) => insigniaAlerta(a)))
                      : h("span", { class: "sec" }, "Sin alertas")
                    : h("span", { class: "sec" }, "Cumple los requisitos: falta la decisión del administrador"),
            ),
          ),
        ),
      ),
    ),
  );
}

function tablaPorVencer(porVencer) {
  if (!porVencer.length) return vacio({ titulo: "Nada por vencer", texto: "Ningún documento legal vigente vence en los próximos 30 días." });
  return h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "Documento"), h("th", {}, "Parcela"), h("th", {}, "Productor"), h("th", {}, "Vence"))),
      h(
        "tbody",
        {},
        porVencer.map((d) => {
          const [clase, texto] = ESTADOS_CASILLA[d.estado] ?? ["", d.estado];
          return h(
            "tr",
            {},
            h("td", {}, d.tipo_nombre),
            h("td", {}, h("a", { href: `#/parcelas/${d.parcela_id}`, class: "mono" }, d.parcela_codigo), h("span", { class: "sec" }, d.parcela_nombre)),
            h("td", {}, d.productor_nombre),
            h("td", { class: "fecha" }, fecha(d.vence_en), " ", h("span", { class: `badge ${clase}` }, h("span", { class: "dot" }), texto)),
          );
        }),
      ),
    ),
  );
}

export default async function habilitacion() {
  const [resumen, parcelas] = await Promise.all([llamarApi("/habilitacion/resumen"), llamarApi("/parcelas")]);
  const lista = h("div");
  const tarjetas = h("section", { class: "kpis", "aria-label": "Parcelas por estado" });

  function mostrar() {
    for (const b of tarjetas.children) b.setAttribute("aria-pressed", String(b.dataset.estado === filtro));
    reemplazar(
      lista,
      seccion({
        titulo: ESTADOS_HABILITACION[filtro][1],
        contenido: tablaParcelas(
          parcelas.filter((p) => p.habilitacion_estado === filtro),
          filtro,
        ),
      }),
    );
  }
  for (const e of ORDEN) {
    const n = resumen.por_estado[e] ?? 0;
    tarjetas.append(
      h(
        "button",
        { class: `kpi ${TONO[e]}`, type: "button", "data-estado": e, onclick: () => ((filtro = e), mostrar()) },
        h("span", { class: "kpi-ic" }, icono(ICONO[e])),
        h("span", { class: "kpi-l" }, ESTADOS_HABILITACION[e][1]),
        h("span", { class: "kpi-v" }, String(n), h("small", {}, n === 1 ? "parcela" : "parcelas")),
      ),
    );
  }
  mostrar();

  return {
    titulo: "Habilitación",
    antetitulo: "Productores",
    descripcion: "Parcelas por estado de habilitación, lo que le falta a cada una y los documentos legales que vencen pronto.",
    migas: [["Productores", "#/productores"], ["Habilitación"]],
    contenido: [
      tarjetas,
      h("section", { class: "panel inspector" }, lista),
      h("section", { class: "panel inspector" }, seccion({ titulo: "Documentos por vencer", sub: "Documentos legales vigentes que vencen en los próximos 30 días.", contenido: tablaPorVencer(resumen.por_vencer) })),
    ],
  };
}

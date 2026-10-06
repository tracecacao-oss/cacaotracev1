// Detalle de un lote de exportación con pestañas Selección, Genealogía e Indicadores. Un lote con desviación
// FIFO muestra su etiqueta y su motivo. Se anula con motivo; un lote armado devuelve sus saldos al stock.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { estadoLote, insigniaFifo, seccionesExportacion, tarjetasIndicadores, vistaGenealogia } from "../exportacion.js";
import { kilos } from "../textos.js";
import { abrirModal, cabeceraFicha, cargando, enviarCon, errorDeCarga, fecha, h, icono, reemplazar, seccion, toast } from "../ui.js";

const PESTANAS = [
  ["seleccion", "Selección"],
  ["genealogia", "Genealogía"],
  ["indicadores", "Indicadores"],
];
let recordada = { id: null, clave: "seleccion" };

function abrirAnulacion(l, alAnular) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-lote" }, "Anular lote");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-lote" },
    h(
      "p",
      { class: "alerta warn" },
      l.estado === "armado"
        ? "Los kilos vuelven al saldo de cada tanda final, las agotadas vuelven al stock y la orden queda abierta para otro lote. La genealogía se conserva como historial."
        : "La selección se descarta y la orden queda abierta para otro lote.",
    ),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, maxlength: 200, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular lote", subtitulo: l.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/lotes/${l.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("Lote anulado.", "warn");
    alAnular();
  });
}

function pestanaSeleccion(l, opera, recargar) {
  const total = l.asignaciones.reduce((s, a) => s + Number(a.kg_asignados), 0);
  return seccion({
    titulo: "Selección",
    sub: l.estado === "en_armado" ? "La selección todavía puede cambiar. Los saldos se descuentan al confirmar." : "Los kilos que el lote tomó de cada tanda final.",
    acciones: opera &&
      ["en_armado", "armado"].includes(l.estado) && [
        l.estado === "en_armado" && h("a", { class: "btn btn-sm", href: `#/lotes-exportacion/${l.id}/armar` }, icono("layers"), "Cambiar la selección"),
        h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirAnulacion(l, recargar) }, "Anular lote"),
      ],
    contenido: l.asignaciones.length
      ? h(
          "div",
          { class: "tbl-box" },
          h(
            "table",
            { class: "tabla" },
            h("thead", {}, h("tr", {}, h("th", {}, "Tanda final"), h("th", { class: "ocultar-sm" }, "Ingreso al stock"), h("th", { class: "num" }, "Saldo actual"), h("th", { class: "num" }, "Kilos del lote"))),
            h(
              "tbody",
              {},
              l.asignaciones.map((a) =>
                h(
                  "tr",
                  {},
                  h("td", {}, h("a", { href: `#/tandas-finales/${a.tanda_final_id}`, class: "mono" }, a.codigo), h("span", { class: "sec" }, [a.corrida_codigo, a.dpp?.codigo].filter(Boolean).join(" · "))),
                  h("td", { class: "ocultar-sm" }, fecha(a.ingreso_stock_en, { hora: true })),
                  h("td", { class: "num mono" }, kilos(a.saldo_kg)),
                  h("td", { class: "num mono" }, kilos(a.kg_asignados)),
                ),
              ),
            ),
            h("tfoot", {}, h("tr", {}, h("th", { colspan: 3 }, "Total"), h("th", { class: "num mono" }, kilos(total)))),
          ),
        )
      : h("p", { class: "panel-sub" }, "Sin tandas finales seleccionadas."),
  });
}

function pestanaGenealogia(l) {
  if (l.estado === "en_armado") return seccion({ titulo: "Genealogía", contenido: h("p", { class: "panel-sub" }, "La genealogía se calcula al confirmar el lote.") });
  const caja = h("div", {}, cargando());
  llamarApi(`/lotes/${l.id}/genealogia`)
    .then((g) => reemplazar(caja, vistaGenealogia(g, { lote: l, incrustada: true })))
    .catch((error) => reemplazar(caja, errorDeCarga(error)));
  return [seccion({ titulo: "Genealogía", sub: "De los kilos del lote, cuántos vienen de cada parcela, con las proporciones que fijó cada corrida." }), caja];
}

function pestanaIndicadores(l) {
  if (!l.indicadores) return seccion({ titulo: "Indicadores", contenido: h("p", { class: "panel-sub" }, "Los indicadores se calculan al confirmar el lote.") });
  return seccion({
    titulo: "Indicadores",
    sub: "Se calculan y se muestran tal cual. Ninguno aprueba ni desaprueba el lote: todos pasan al informe de hallazgos.",
    contenido: tarjetasIndicadores(l.indicadores),
  });
}

export default async function loteExportacion({ parametros: [id], recargar }) {
  const l = await llamarApi(`/lotes/${id}`);
  const opera = ["admin_cooperativa", "operador"].includes(rolEfectivo());
  if (recordada.id !== id) recordada = { id, clave: "seleccion" };
  const cuerpo = h("div", { class: "contenido-pestana" });
  const barra = h("div", { class: "seg", role: "tablist", "aria-label": "Secciones del lote" });
  const generadores = { seleccion: () => pestanaSeleccion(l, opera, recargar), genealogia: () => pestanaGenealogia(l), indicadores: () => pestanaIndicadores(l) };
  function mostrar(clave) {
    recordada = { id, clave };
    for (const b of barra.children) b.setAttribute("aria-selected", String(b.dataset.clave === clave));
    reemplazar(cuerpo, generadores[clave]());
  }
  for (const [clave, texto] of PESTANAS) barra.append(h("button", { type: "button", role: "tab", "data-clave": clave, onclick: () => mostrar(clave) }, texto));
  mostrar(recordada.clave);

  return {
    titulo: l.codigo,
    migas: [["Exportación", "#/exportacion"], ["Lotes", "#/exportacion/lotes"], [l.codigo]],
    secciones: seccionesExportacion(),
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("container")),
        titulo: l.codigo,
        codigo: true,
        insignias: [estadoLote(l.estado), l.desviacion_fifo && insigniaFifo()],
        detalle: ["Orden ", h("a", { href: `#/ordenes/${l.orden.id}`, class: "mono" }, l.orden.codigo), ` · ${l.importador} · ${l.calidad}`, l.armado_en ? ` · armado el ${fecha(l.armado_en, { hora: true })} por ${l.armado_por_nombre ?? "—"}` : ""],
        cifra: kilos(l.masa_neta_kg ?? l.seleccionado_kg),
        cifraTexto: l.masa_neta_kg ? `masa neta · ${l.numero_parcelas} ${l.numero_parcelas === 1 ? "parcela" : "parcelas"}` : `seleccionado de ${kilos(l.cantidad_kg)}`,
        accion: opera && l.estado === "en_armado" && h("a", { class: "btn btn-primary", href: `#/lotes-exportacion/${l.id}/armar` }, icono("layers"), "Armar lote"),
      }),
      l.desviacion_fifo && h("div", { class: "verif warn" }, icono("alert"), h("div", {}, h("b", {}, "La selección se apartó del orden FIFO"), h("span", {}, `Motivo: ${l.motivo_desviacion}`))),
      l.estado === "anulado" && h("div", { class: "verif bad" }, icono("alert"), h("div", {}, h("b", {}, `Lote anulado el ${fecha(l.anulado_en, { hora: true })}${l.anulado_por_nombre ? ` por ${l.anulado_por_nombre}` : ""}`), h("span", {}, `Motivo: ${l.motivo_anulacion}`))),
      h("div", { class: "ins-tabs seg-scroll" }, barra),
      cuerpo,
    ),
  };
}

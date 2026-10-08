// Detalle de una orden de compra: sus datos y el botón "Armar lote". Una orden abierta se edita y se anula;
// con un lote confirmado ya no se edita.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { estadoLote, estadoOrden } from "../exportacion.js";
import { kilos } from "../textos.js";
import { abrirModal, cabeceraFicha, campo, enviarCon, fecha, h, icono, rejilla, seccion, toast } from "../ui.js";

async function abrirEdicion(o, alGuardar) {
  const [importadores, calidades] = await Promise.all([llamarApi("/importadores"), llamarApi("/calidades")]);
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-orden" }, "Guardar");
  const formulario = h(
    "form",
    { class: "form", id: "form-orden" },
    campo({ etiqueta: "Importador", name: "importador_id", required: true, value: o.importador.id, opciones: importadores.filter((i) => i.activo || i.id === o.importador.id).map((i) => [i.id, i.razon_social]) }),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Cantidad (kg)", name: "cantidad_kg", type: "number", step: "0.01", min: "0.01", required: true, value: o.cantidad_kg, class: "input mono" }),
      campo({ etiqueta: "Tolerancia (%)", name: "tolerancia_pct", type: "number", step: "0.1", min: "0", max: "100", required: true, value: o.tolerancia_pct, class: "input mono" }),
    ),
    campo({ etiqueta: "Calidad", name: "calidad_id", required: true, value: o.calidad_id, opciones: calidades.filter((c) => c.activo || c.id === o.calidad_id).map((c) => [c.id, c.nombre]) }),
    h("div", { class: "grid2" }, campo({ etiqueta: "País de destino", name: "pais_destino", required: true, value: o.pais_destino }), campo({ etiqueta: "Puerto o ciudad de destino", name: "lugar_destino", required: true, value: o.lugar_destino })),
    h("div", { class: "grid2" }, campo({ etiqueta: "Fecha de entrega", name: "fecha_entrega", type: "date", required: true, value: o.fecha_entrega }), campo({ etiqueta: "Referencia del importador", name: "referencia_importador", value: o.referencia_importador ?? "" })),
  );
  const { cerrar } = abrirModal({ titulo: "Editar orden", subtitulo: o.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (d) => {
    await llamarApi(`/ordenes/${o.id}`, { metodo: "PATCH", cuerpo: { ...d, referencia_importador: d.referencia_importador.trim() || null } });
    cerrar();
    toast("Orden actualizada.");
    alGuardar();
  });
}

function abrirAnulacion(o, alAnular) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-orden" }, "Anular orden");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-orden" },
    o.lote?.estado === "en_armado" && h("p", { class: "alerta warn" }, `El lote ${o.lote.codigo}, que está en armado, se anula con la orden.`),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, maxlength: 200, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular orden", subtitulo: o.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/ordenes/${o.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("Orden anulada.", "warn");
    alAnular();
  });
}

export default async function orden({ parametros: [id], navegar, recargar }) {
  const o = await llamarApi(`/ordenes/${id}`);
  const opera = ["admin_cooperativa", "operador"].includes(rolEfectivo());
  const abierta = o.estado === "abierta";

  async function armar(e) {
    if (o.lote) return navegar(`#/lotes-exportacion/${o.lote.id}/armar`);
    e.currentTarget.classList.add("is-loading");
    try {
      const lote = await llamarApi(`/ordenes/${o.id}/lote`, { metodo: "POST" });
      navegar(`#/lotes-exportacion/${lote.id}/armar`);
    } catch (error) {
      toast(error.message, "bad");
      e.target.closest("button")?.classList.remove("is-loading");
    }
  }

  let accion = null;
  if (o.lote && o.lote.estado !== "en_armado") {
    accion = h("a", { class: "btn btn-primary", href: `#/lotes-exportacion/${o.lote.id}` }, "Ver el lote");
  } else if (opera && abierta) {
    accion = h("button", { class: "btn btn-primary", type: "button", onclick: armar }, icono("layers"), "Armar lote");
  }

  return {
    titulo: o.codigo,
    migas: [["Exportación", "#/exportacion"], ["Órdenes", "#/exportacion/ordenes"], [o.codigo]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("ship")),
        titulo: o.codigo,
        codigo: true,
        insignias: [estadoOrden(o.estado)],
        detalle: [`${o.importador.razon_social} · ${o.calidad} · entrega el ${fecha(o.fecha_entrega)}`],
        cifra: kilos(o.cantidad_kg),
        cifraTexto: Number(o.tolerancia_pct) > 0 ? `± ${o.tolerancia_pct} % (${kilos(o.minimo_kg)} a ${kilos(o.maximo_kg)})` : "sin tolerancia",
        accion,
      }),
      o.estado === "anulada" && h("div", { class: "verif bad" }, icono("alert"), h("div", {}, h("b", {}, `Orden anulada el ${fecha(o.anulada_en, { hora: true })}`), h("span", {}, `Motivo: ${o.motivo_anulacion}`))),
      seccion({
        titulo: "Orden de compra",
        acciones:
          opera &&
          abierta && [
            h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirEdicion(o, recargar) }, "Editar"),
            h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirAnulacion(o, recargar) }, "Anular orden"),
          ],
        contenido: rejilla([
          { etiqueta: "Importador", valor: `${o.importador.razon_social} (${o.importador.pais})` },
          { etiqueta: "Referencia del importador", valor: o.referencia_importador, mono: true },
          { etiqueta: "Cantidad", valor: kilos(o.cantidad_kg), mono: true },
          { etiqueta: "Tolerancia", valor: `${o.tolerancia_pct} %`, mono: true, extra: `Admite de ${kilos(o.minimo_kg)} a ${kilos(o.maximo_kg)}.` },
          { etiqueta: "Calidad", valor: o.calidad },
          { etiqueta: "Partida del Sistema Armonizado", valor: `${o.partida_sa}, cacao en grano`, mono: true },
          { etiqueta: "Destino", valor: `${o.lugar_destino}, ${o.pais_destino}` },
          { etiqueta: "Fecha de entrega", valor: fecha(o.fecha_entrega) },
          { etiqueta: "Registró", valor: `${o.creada_por_nombre ?? "—"} el ${fecha(o.creada_en, { hora: true })}` },
        ]),
      }),
      seccion({
        titulo: "Lote de exportación",
        sub: "Una orden tiene un solo lote. Los anulados quedan en el historial.",
        contenido: [
          o.lote
            ? h("p", {}, h("a", { href: `#/lotes-exportacion/${o.lote.id}`, class: "mono" }, o.lote.codigo), " ", estadoLote(o.lote.estado), o.lote.masa_neta_kg && ` · ${kilos(o.lote.masa_neta_kg)}`)
            : h("p", { class: "panel-sub" }, abierta ? "Todavía no tiene lote. \"Armar lote\" propone el stock del más antiguo al más nuevo." : "Sin lote."),
          o.lotes_anulados.length > 0 && h("ul", { class: "lista-simple" }, o.lotes_anulados.map((l) => h("li", {}, h("a", { href: `#/lotes-exportacion/${l.id}`, class: "mono" }, l.codigo), " ", estadoLote(l.estado)))),
        ],
      }),
    ),
  };
}

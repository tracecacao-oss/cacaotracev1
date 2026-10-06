// Inicio (Parte 8): ya no es solo un saludo. Muestra lo que hay que atender en la cooperativa, agrupado por
// tipo y con enlace al registro: primero lo vencido, luego lo que está por vencer y al final lo demás. El
// productor tiene su propio inicio (Mi perfil) y no ve estos pendientes.

import { llamarApi } from "../api.js";
import { enConsulta, estado, nombreCooperativa } from "../estado.js";
import { fecha, h, icono, seccion, vacio } from "../ui.js";

const HORA_LIMA = new Intl.DateTimeFormat("es-PE", { timeZone: "America/Lima", hour: "numeric", hourCycle: "h23" });
const ORDEN = ["vencido", "por_vencer", "otro"];
const TONO = { vencido: "is-bad", por_vencer: "is-warn", otro: "" };
const ICONO = {
  documentos_parcelas_vencidos: "file",
  documentos_cooperativa_vencidos: "shield",
  documentos_parcelas_por_vencer: "clock",
  documentos_cooperativa_por_vencer: "clock",
  lotes_bloqueados: "container",
  lotes_por_entregar: "ship",
  exclusion_posterior_al_cierre: "alert",
  parcelas_observadas: "pin",
  tandas_sin_validar: "sack",
};

function saludo() {
  const hora = Number(HORA_LIMA.format(new Date()));
  return hora < 12 ? "Buenos días" : hora < 19 ? "Buenas tardes" : "Buenas noches";
}

function grupo(g) {
  return h(
    "section",
    { class: `panel pendientes-grupo ${TONO[g.prioridad]}`.trim() },
    h("header", { class: "pendientes-h" }, h("span", { class: "kpi-ic" }, icono(ICONO[g.clave] ?? "bell")), h("h3", {}, g.titulo), h("span", { class: "count mono" }, String(g.cantidad))),
    h(
      "ul",
      { class: "pendientes-lista" },
      g.items.map((p) => h("li", {}, h("a", { href: p.enlace }, h("b", {}, p.titulo), p.detalle && h("span", { class: "sec" }, p.detalle)), p.fecha && h("span", { class: "sec mono" }, fecha(p.fecha)))),
    ),
    g.cantidad > g.items.length && h("p", { class: "panel-sub" }, `Y ${g.cantidad - g.items.length} más.`),
  );
}

export default async function inicio() {
  const [{ total }, pendientes] = await Promise.all([llamarApi("/productores", { parametros: { por_pagina: 1 } }), llamarApi("/pendientes")]);
  const titulo = enConsulta() ? "Consulta de la cooperativa" : `${saludo()}, ${estado.usuario.nombres}`;
  const grupos = [...pendientes.grupos].sort((a, b) => ORDEN.indexOf(a.prioridad) - ORDEN.indexOf(b.prioridad));
  const cuenta = (prioridad) => grupos.filter((g) => g.prioridad === prioridad).reduce((s, g) => s + g.cantidad, 0);

  return {
    titulo,
    migas: [["Inicio"]],
    antetitulo: nombreCooperativa(),
    descripcion: pendientes.total ? "Lo que hay que atender, de lo vencido a lo demás. Cada pendiente lleva al registro donde se resuelve." : null,
    contenido: [
      h(
        "section",
        { class: "kpis", "aria-label": "Indicadores" },
        h("a", { class: "kpi is-ok", href: "#/productores" }, h("span", { class: "kpi-ic" }, icono("users")), h("span", { class: "kpi-l" }, "Productores afiliados"), h("span", { class: "kpi-v" }, String(total), h("small", {}, total === 1 ? "productor" : "productores")), h("span", { class: "kpi-s" }, "Ver el padrón")),
        h("div", { class: `kpi ${cuenta("vencido") ? "is-bad" : "is-ok"}` }, h("span", { class: "kpi-ic" }, icono("alert")), h("span", { class: "kpi-l" }, "Vencidos"), h("span", { class: "kpi-v" }, String(cuenta("vencido")), h("small", {}, cuenta("vencido") === 1 ? "documento" : "documentos")), h("span", { class: "kpi-s" }, "Parcelas y cooperativa")),
        h("div", { class: `kpi ${cuenta("por_vencer") ? "is-warn" : "is-ok"}` }, h("span", { class: "kpi-ic" }, icono("clock")), h("span", { class: "kpi-l" }, "Por vencer"), h("span", { class: "kpi-v" }, String(cuenta("por_vencer")), h("small", {}, cuenta("por_vencer") === 1 ? "documento" : "documentos")), h("span", { class: "kpi-s" }, "En los próximos días")),
        h("div", { class: "kpi" }, h("span", { class: "kpi-ic" }, icono("bell")), h("span", { class: "kpi-l" }, "Otros pendientes"), h("span", { class: "kpi-v" }, String(cuenta("otro")), h("small", {}, "por atender")), h("span", { class: "kpi-s" }, "Lotes, parcelas y tandas")),
      ),
      grupos.length
        ? h("div", { class: "pendientes" }, grupos.map(grupo))
        : h("section", { class: "panel" }, seccion({ titulo: "Pendientes", contenido: vacio({ titulo: "Sin pendientes", texto: "No hay documentos vencidos ni por vencer, parcelas observadas, tandas sin validar ni lotes bloqueados." }) })),
    ],
  };
}

// Recepción (primera sección de Lotes y proceso): tandas agrupadas por estado, con buscador, y el
// botón "Nueva tanda". Sin tope configurado, ni código de cooperativa, ni cancha de acopio activa,
// muestra qué falta y no deja crear tandas.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { ESTADOS_TANDA, PRODUCTO, kilos } from "../textos.js";
import { seccionesLotes } from "../tandas.js";
import { buscador, cargando, conRetraso, errorDeCarga, fecha, h, icono, reemplazar, seccion, vacio } from "../ui.js";

const ORDEN = ["registrada", "observada", "validada", "anulada"];
const ICONO = { registrada: "clock", observada: "alert", validada: "check", anulada: "x" };
const TONO = { registrada: "is-info", observada: "is-warn", validada: "is-ok", anulada: "" };
let filtro = "registrada";

function tabla(tandas, estadoElegido) {
  if (!tandas.length) {
    return vacio({ titulo: `Sin tandas ${ESTADOS_TANDA[estadoElegido][1].toLowerCase()}s`, texto: "No hay tandas en este estado con esa búsqueda." });
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
        h("tr", {}, h("th", {}, "Tanda"), h("th", {}, "Productor"), h("th", { class: "ocultar-sm" }, "Parcela"), h("th", { class: "num" }, "Peso"), h("th", { class: "ocultar-sm" }, "DOP")),
      ),
      h(
        "tbody",
        {},
        tandas.map((t) =>
          h(
            "tr",
            {},
            h("td", {}, h("a", { href: `#/tandas/${t.id}`, class: "mono" }, t.codigo), h("span", { class: "sec" }, fecha(t.recibida_en, { hora: true }))),
            h("td", {}, `${t.productor.nombres} ${t.productor.apellidos}`, h("span", { class: "sec mono" }, `DNI ${t.productor.dni}`)),
            h("td", { class: "ocultar-sm" }, h("span", { class: "mono" }, t.parcela.codigo), h("span", { class: "sec" }, t.parcela.nombre)),
            h("td", { class: "num" }, h("span", { class: "mono" }, kilos(t.peso_kg)), h("span", { class: "sec" }, PRODUCTO[t.estado_producto])),
            h(
              "td",
              { class: "ocultar-sm" },
              t.dop ? h("a", { href: `#/dops/${t.dop.id}`, class: "mono" }, t.dop.codigo) : h("span", { class: "sec" }, "—"),
              t.dop?.estado === "anulado" && h("span", { class: "sec" }, "Anulado"),
            ),
          ),
        ),
      ),
    ),
  );
}

/** Lo que falta para recibir tandas, con enlace a donde se arregla. */
function avisoSinConfigurar(configuracion, canchas) {
  const faltas = [];
  if (configuracion.tope_kg_seco_ha_anio == null) {
    faltas.push(["Falta el tope de kilos por hectárea al año.", "Configúralo", "#/cooperativa/configuracion"]);
  }
  if (!configuracion.codigo_cooperativa) {
    faltas.push(["Falta el código de la cooperativa, que va en cada DOP. Lo fija el equipo CacaoTrace.", null, null]);
  }
  if (!canchas.length) faltas.push(["No hay ninguna cancha de acopio activa.", "Regístrala en Lugares", "#/cooperativa/lugares"]);
  if (!faltas.length) return null;
  return h(
    "div",
    { class: "verif warn" },
    icono("alert"),
    h(
      "div",
      {},
      h("b", {}, "Todavía no se pueden recibir tandas"),
      faltas.map(([texto, enlace, destino]) => h("div", { class: "sec" }, texto, enlace && [" ", h("a", { href: destino }, enlace), "."])),
    ),
  );
}

export default async function recepcion({ hash, navegar }) {
  if (hash === "#/lotes") {
    navegar("#/lotes/recepcion");
    return { titulo: "Recepción", contenido: h("div") };
  }
  const [configuracion, canchas] = await Promise.all([
    llamarApi("/configuracion"),
    llamarApi("/lugares", { parametros: { tipo: "cancha_acopio", activos: true } }),
  ]);
  const aviso = avisoSinConfigurar(configuracion, canchas);
  const puedeRegistrar = ["admin_cooperativa", "operador"].includes(rolEfectivo());

  const tarjetas = h("section", { class: "kpis kpis-estados", "aria-label": "Tandas por estado" });
  const lista = h("div", {}, cargando());
  let busqueda = "";
  let tandas = [];

  function pintar() {
    for (const b of tarjetas.children) b.setAttribute("aria-pressed", String(b.dataset.estado === filtro));
    reemplazar(
      lista,
      tabla(
        tandas.filter((t) => t.estado === filtro),
        filtro,
      ),
    );
  }
  async function cargar() {
    try {
      tandas = await llamarApi("/tandas", { parametros: { q: busqueda } });
    } catch (error) {
      reemplazar(lista, errorDeCarga(error));
      return;
    }
    tarjetas.replaceChildren(
      ...ORDEN.map((e) => {
        const n = tandas.filter((t) => t.estado === e).length;
        return h(
          "button",
          { class: `kpi ${TONO[e]}`, type: "button", "data-estado": e, onclick: () => ((filtro = e), pintar()) },
          h("span", { class: "kpi-ic" }, icono(ICONO[e])),
          h("span", { class: "kpi-l" }, ESTADOS_TANDA[e][1] + "s"),
          h("span", { class: "kpi-v" }, String(n), h("small", {}, n === 1 ? "tanda" : "tandas")),
        );
      }),
    );
    pintar();
  }
  await cargar();
  // Al entrar se abre el primer estado que tenga tandas.
  if (!tandas.some((t) => t.estado === filtro)) {
    filtro = ORDEN.find((e) => tandas.some((t) => t.estado === e)) ?? filtro;
    pintar();
  }

  return {
    titulo: "Recepción",
    antetitulo: "Lotes y proceso",
    descripcion: "Las tandas que la cooperativa pesa en cancha. Cada tanda viene de una sola parcela y, al validarse, emite su DOP.",
    migas: [["Lotes y proceso", "#/lotes"], ["Recepción"]],
    secciones: seccionesLotes(),
    accion:
      puedeRegistrar &&
      !aviso &&
      h("button", { class: "btn btn-primary", type: "button", onclick: () => navegar("#/lotes/recepcion/nueva") }, icono("mas"), "Nueva tanda"),
    contenido: [
      aviso,
      tarjetas,
      h(
        "section",
        { class: "panel inspector" },
        h(
          "div",
          { class: "barra-lista" },
          buscador({
            placeholder: "Buscar por código, DNI, productor o parcela",
            alEscribir: conRetraso((texto) => {
              busqueda = texto.trim();
              cargar();
            }),
          }),
        ),
        seccion({ titulo: "Tandas", contenido: lista }),
      ),
    ],
  };
}

// Nueva corrida: elección de ruta y tipo de manejo, lista de tandas disponibles para marcar y botón
// "Iniciar". En una corrida segregada, al marcar la primera tanda solo quedan las de su productor.

import { llamarApi } from "../api.js";
import { MANEJOS, RUTAS } from "../proceso.js";
import { PRODUCTO, kilos } from "../textos.js";
import { cargando, errorDeCarga, fecha, h, icono, reemplazar, seccion, toast, vacio } from "../ui.js";

function opciones(nombre, lista, valor, alCambiar) {
  return h(
    "div",
    { class: "opciones", role: "radiogroup" },
    lista.map(([codigo, titulo, ayuda]) =>
      h(
        "label",
        { class: "opcion opcion-doc" },
        h("input", { type: "radio", name: nombre, value: codigo, checked: codigo === valor, onchange: () => alCambiar(codigo) }),
        h("span", {}, h("b", {}, titulo), h("span", { class: "sec" }, ayuda)),
      ),
    ),
  );
}

export default async function corridaNueva({ navegar }) {
  const st = { ruta: "completa", manejo: "mezclado", disponibles: [], marcadas: new Set() };
  const lista = h("div", {}, cargando());
  const resumen = h("p", { class: "panel-sub", "aria-live": "polite" });
  const iniciar = h("button", { class: "btn btn-primary", type: "button", disabled: true, onclick: () => crear() }, icono("check"), "Iniciar corrida");

  function productorFijo() {
    if (st.manejo !== "segregado") return null;
    const primera = st.disponibles.find((t) => st.marcadas.has(t.tanda_id));
    return primera?.productor.id ?? null;
  }

  function pintar() {
    const fijo = productorFijo();
    const visibles = st.disponibles.filter((t) => !fijo || t.productor.id === fijo);
    const total = st.disponibles.filter((t) => st.marcadas.has(t.tanda_id)).reduce((s, t) => s + Number(t.peso_kg), 0);
    resumen.textContent = st.marcadas.size ? `${st.marcadas.size} ${st.marcadas.size === 1 ? "tanda marcada" : "tandas marcadas"} · ${kilos(total)} de entrada` : "Marca las tandas que entran a la corrida.";
    iniciar.disabled = st.marcadas.size === 0;
    if (!visibles.length) {
      reemplazar(lista, vacio({ titulo: "Sin tandas disponibles", texto: `No hay tandas validadas ${st.ruta === "completa" ? "en baba" : "secas"}, con DOP vigente, fuera de otra corrida.` }));
      return;
    }
    reemplazar(
      lista,
      h(
        "div",
        { class: "tbl-box" },
        h(
          "table",
          { class: "tabla" },
          h("thead", {}, h("tr", {}, h("th", {}, h("span", { class: "sr-only" }, "Marcar")), h("th", {}, "Tanda"), h("th", {}, "Productor"), h("th", { class: "ocultar-sm" }, "Parcela"), h("th", { class: "num" }, "Peso"))),
          h(
            "tbody",
            {},
            visibles.map((t) =>
              h(
                "tr",
                {},
                h(
                  "td",
                  {},
                  h("input", {
                    type: "checkbox",
                    "aria-label": `Marcar ${t.codigo}`,
                    checked: st.marcadas.has(t.tanda_id),
                    onchange: (e) => {
                      if (e.target.checked) st.marcadas.add(t.tanda_id);
                      else st.marcadas.delete(t.tanda_id);
                      pintar();
                    },
                  }),
                ),
                h("td", {}, h("span", { class: "mono" }, t.codigo), h("span", { class: "sec" }, `${fecha(t.recibida_en, { hora: true })} · ${t.dop.codigo}`)),
                h("td", {}, `${t.productor.nombres} ${t.productor.apellidos}`, h("span", { class: "sec mono" }, `DNI ${t.productor.dni}`)),
                h(
                  "td",
                  { class: "ocultar-sm" },
                  h("span", { class: "mono" }, t.parcela.codigo),
                  h("span", { class: "sec" }, t.parcela.nombre),
                  t.parcela_observada && h("span", { class: "badge warn" }, h("span", { class: "dot" }), "Parcela observada: entra con alerta"),
                ),
                h("td", { class: "num" }, h("span", { class: "mono" }, kilos(t.peso_kg)), h("span", { class: "sec" }, PRODUCTO[t.estado_producto])),
              ),
            ),
          ),
        ),
      ),
    );
  }

  async function cargar() {
    st.marcadas.clear();
    reemplazar(lista, cargando());
    try {
      st.disponibles = await llamarApi("/corridas/tandas-disponibles", { parametros: { ruta: st.ruta } });
      pintar();
    } catch (error) {
      reemplazar(lista, errorDeCarga(error));
    }
  }

  async function crear() {
    iniciar.classList.add("is-loading");
    iniciar.disabled = true;
    let corrida = null;
    try {
      corrida = await llamarApi("/corridas", { metodo: "POST", cuerpo: { ruta: st.ruta, tipo_manejo: st.manejo } });
      for (const id of st.marcadas) {
        await llamarApi(`/corridas/${corrida.id}/tandas`, { metodo: "POST", cuerpo: { tanda_id: id } });
      }
      corrida = await llamarApi(`/corridas/${corrida.id}/iniciar`, { metodo: "POST" });
      toast(`Corrida ${corrida.codigo} iniciada.`);
      navegar(`#/corridas/${corrida.id}`);
    } catch (error) {
      toast(error.message, "bad");
      // Si la corrida se creó pero no se pudo iniciar, queda abierta: se abre su detalle para corregirla.
      if (corrida) navegar(`#/corridas/${corrida.id}`);
      iniciar.classList.remove("is-loading");
      iniciar.disabled = st.marcadas.size === 0;
    }
  }

  await cargar();
  return {
    titulo: "Nueva corrida",
    antetitulo: "Corridas",
    descripcion: "Elige la ruta y el tipo de manejo, marca las tandas e inicia. Una tanda entra completa a una sola corrida.",
    migas: [["Lotes y proceso", "#/lotes"], ["Corridas", "#/lotes/corridas"], ["Nueva"]],
    contenido: h(
      "section",
      { class: "panel inspector" },
      seccion({
        titulo: "Ruta",
        sub: "Una corrida no mezcla baba con seco.",
        contenido: opciones("ruta", RUTAS, st.ruta, (v) => {
          st.ruta = v;
          cargar();
        }),
      }),
      seccion({
        titulo: "Tipo de manejo",
        contenido: opciones("manejo", MANEJOS, st.manejo, (v) => {
          st.manejo = v;
          st.marcadas.clear();
          pintar();
        }),
      }),
      seccion({ titulo: "Tandas disponibles", sub: "Validadas, con DOP vigente y fuera de otra corrida.", contenido: [resumen, lista], acciones: iniciar }),
    ),
  };
}

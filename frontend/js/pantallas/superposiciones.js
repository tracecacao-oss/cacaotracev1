// Superposiciones: cada una muestra en el mapa las parcelas visibles y el área común, y se
// acepta con una nota. Dentro de la cooperativa la acepta su administrador; entre
// cooperativas, solo el equipo CacaoTrace (#/plataforma/superposiciones).

import { llamarApi } from "../api.js";
import { estado, rolEfectivo } from "../estado.js";
import { COLORES, capaGeojson, crearMapa, encuadrar, estilo } from "../mapa.js";
import { hectareas } from "../textos.js";
import { abrirModal, campo, cargando, enviarCon, fecha, h, reemplazar, toast, vacio } from "../ui.js";
import { seccionesProductores } from "./productores.js";

const ESTADOS = [
  ["abierta", "Abiertas"],
  ["aceptada", "Aceptadas"],
  ["resuelta", "Resueltas"],
];

function aceptar(s, ruta, alAceptar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-aceptar" }, "Aceptar superposición");
  const formulario = h(
    "form",
    { class: "form", id: "form-aceptar" },
    h("p", {}, "Acepta solo si revisaste el caso y la superposición está justificada. La nota queda en la auditoría."),
    campo({ etiqueta: "Nota que explica el caso", name: "nota", required: true, maxlength: 500 }),
  );
  const { cerrar } = abrirModal({
    titulo: "Aceptar superposición",
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(ruta, { metodo: "POST", cuerpo: { nota } });
    cerrar();
    toast("Superposición aceptada.");
    alAceptar();
  });
}

export async function tarjetaSuperposicion(s, { puedeAceptar, rutaAceptar, alCambiar }) {
  const contenedor = h("div", { class: "mapa mapa-chico" });
  const tarjeta = h(
    "article",
    { class: "panel superposicion" },
    contenedor,
    h(
      "div",
      { class: "panel-b form" },
      h(
        "div",
        {},
        h("b", {}, s.entre_cooperativas && s.aviso ? s.aviso : s.parcelas.map((p) => `${p.codigo} «${p.nombre}»`).join(" y ")),
        h(
          "span",
          { class: "sec" },
          s.tipo === "punto_en_poligono" ? "Un punto cae dentro de un polígono" : `${hectareas(s.area_ha)} en común · ${s.porcentaje} % de la parcela más pequeña`,
          ` · detectada el ${fecha(s.creado_en)}`,
        ),
      ),
      h(
        "ul",
        { class: "lista-simple" },
        s.parcelas.map((p) =>
          h("li", {}, h("a", { href: `#/parcelas/${p.id}` }, `${p.codigo} · ${p.nombre}`), ` · ${p.productor_nombre}`, p.cooperativa_nombre ? ` · ${p.cooperativa_nombre}` : ""),
        ),
      ),
      s.nota && h("p", { class: "alerta info" }, `Nota: ${s.nota}`),
      puedeAceptar && s.estado === "abierta" && h("button", { class: "btn btn-sm", type: "button", onclick: () => aceptar(s, rutaAceptar(s), alCambiar) }, "Aceptar con nota"),
    ),
  );
  const { L, mapa } = await crearMapa(contenedor, { coordenadas: false });
  const grupo = L.featureGroup().addTo(mapa);
  for (const p of s.parcelas) capaGeojson(L, p.geometria, { style: estilo(COLORES.con_alertas, 0.15) }).addTo(grupo);
  if (s.interseccion) capaGeojson(L, s.interseccion, { style: estilo(COLORES.interseccion, 0.5) }).addTo(grupo);
  encuadrar(mapa, grupo);
  return tarjeta;
}

export default async function superposiciones() {
  let filtro = "abierta";
  const lista = h("div", { class: "lista-tarjetas" }, cargando());
  const puedeAceptar = rolEfectivo() === "admin_cooperativa";

  async function cargar() {
    const datos = await llamarApi("/superposiciones", { parametros: { estado: filtro } });
    if (!datos.length) {
      lista.replaceChildren(vacio({ titulo: "Sin superposiciones", texto: filtro === "abierta" ? "Ninguna parcela de la cooperativa se superpone con otra." : "No hay superposiciones en este estado." }));
      return;
    }
    const tarjetas = [];
    for (const s of datos) {
      tarjetas.push(
        await tarjetaSuperposicion(s, {
          puedeAceptar: puedeAceptar && !s.entre_cooperativas,
          rutaAceptar: (x) => `/superposiciones/${x.id}/aceptar`,
          alCambiar: cargar,
        }),
      );
    }
    reemplazar(lista, tarjetas);
  }
  const selector = h(
    "select",
    { class: "select", "aria-label": "Estado", onchange: (e) => ((filtro = e.target.value), cargar()) },
    ESTADOS.map(([v, t]) => h("option", { value: v }, t)),
  );
  cargar();

  return {
    titulo: "Superposiciones",
    migas: [["Productores", "#/productores"], ["Superposiciones"]],
    secciones: seccionesProductores(),
    contenido: [
      h(
        "div",
        { class: "barra-lista panel" },
        selector,
        h("span", { class: "panel-sub" }, estado.usuario.rol === "admin_cooperativa" ? "Una superposición con otra cooperativa solo la acepta el equipo CacaoTrace." : "Solo el administrador de la cooperativa acepta superposiciones."),
      ),
      lista,
    ],
  };
}

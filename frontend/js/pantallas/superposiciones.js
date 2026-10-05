// Superposiciones: cada una muestra en el mapa las parcelas visibles y el área común, y se
// acepta con una nota. Dentro de la cooperativa la acepta su administrador; entre
// cooperativas, solo el equipo CacaoTrace (#/plataforma/superposiciones).

import { llamarApi } from "../api.js";
import { estado, rolEfectivo } from "../estado.js";
import { COLORES, capaGeojson, crearMapa, encuadrar, estilo } from "../mapa.js";
import { hectareas } from "../textos.js";
import { abrirModal, campo, cargando, enviarCon, fecha, h, icono, reemplazar, toast, vacio } from "../ui.js";
import { seccionesProductores } from "./productores.js";

const ESTADOS = [
  ["abierta", "Abiertas"],
  ["aceptada", "Aceptadas"],
  ["resuelta", "Resueltas"],
];
const INSIGNIA = { abierta: ["bad", "Abierta"], aceptada: ["info", "Aceptada"], resuelta: ["ok", "Resuelta"] };

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

/** Tarjeta con el estilo de las observaciones del diseño: cabecera, mapa, aviso y acción. */
export async function tarjetaSuperposicion(s, { puedeAceptar, rutaAceptar, alCambiar }) {
  const contenedor = h("div", { class: "mapa mapa-chico" });
  const [tono, texto] = INSIGNIA[s.estado] ?? ["", s.estado];
  const tarjeta = h(
    "article",
    { class: "panel obs" },
    h(
      "div",
      { class: "obs-h" },
      h("b", { class: "mono" }, s.parcelas.map((p) => p.codigo).join(" · ")),
      h("span", { class: `badge ${tono}` }, h("span", { class: "dot" }), texto),
    ),
    contenedor,
    h(
      "div",
      { class: "obs-b" },
      h(
        "div",
        { class: `alertbox ${s.estado === "abierta" ? "bad" : ""}` },
        icono("layers"),
        h(
          "div",
          {},
          s.entre_cooperativas && s.aviso
            ? s.aviso
            : s.tipo === "punto_en_poligono"
              ? "Un punto cae dentro de un polígono"
              : `${hectareas(s.area_ha)} en común · ${s.porcentaje} % de la parcela más pequeña`,
          h("small", {}, `Detectada el ${fecha(s.creado_en)}`),
        ),
      ),
      h(
        "ul",
        { class: "lista-simple" },
        s.parcelas.map((p) =>
          h(
            "li",
            {},
            h("a", { href: `#/parcelas/${p.id}` }, `${p.codigo} · ${p.nombre}`),
            h("span", { class: "sec" }, [p.productor_nombre, p.cooperativa_nombre].filter(Boolean).join(" · ")),
          ),
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
  // Filtro por estado con los chips del diseño.
  const selector = h(
    "div",
    { class: "fchips", role: "group", "aria-label": "Estado" },
    ESTADOS.map(([v, t]) =>
      h(
        "button",
        {
          class: "fchip",
          type: "button",
          "aria-pressed": String(v === filtro),
          onclick: (e) => {
            filtro = v;
            for (const b of selector.children) b.setAttribute("aria-pressed", String(b === e.currentTarget));
            cargar();
          },
        },
        t,
      ),
    ),
  );
  cargar();

  return {
    titulo: "Superposiciones",
    antetitulo: "Productores",
    descripcion:
      estado.usuario.rol === "admin_cooperativa"
        ? "Parcelas que se cruzan. Una superposición con otra cooperativa solo la acepta el equipo CacaoTrace."
        : "Parcelas que se cruzan. Solo el administrador de la cooperativa acepta superposiciones.",
    migas: [["Productores", "#/productores"], ["Superposiciones"]],
    secciones: seccionesProductores(),
    contenido: [h("div", {}, selector), lista],
  };
}

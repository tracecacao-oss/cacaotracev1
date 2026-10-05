// Mapa de parcelas: todas las parcelas activas de la cooperativa; al tocar una se abre su detalle.
// Sin alertas, con alertas y con superposición abierta se distinguen por color y leyenda.

import { llamarApi } from "../api.js";
import { COLORES, agregarLeyenda, capaGeojson, crearMapa, encuadrar, estilo } from "../mapa.js";
import { hectareas } from "../textos.js";
import { h } from "../ui.js";
import { seccionesProductores } from "./productores.js";

export default async function mapaParcelas({ navegar }) {
  const contenedor = h("div", { class: "mapa mapa-grande" });
  const resumen = h("span", {}, "Cargando parcelas…");
  const { L, mapa } = await crearMapa(contenedor);
  agregarLeyenda(L, mapa);

  const coleccion = await llamarApi("/parcelas", { parametros: { formato: "geojson", estado: "activa" } });
  const capa = capaGeojson(L, coleccion, {
    style: (f) => estilo(COLORES[f.properties.estado_mapa], 0.3),
    pointToLayer: (f, latlng) => L.circleMarker(latlng, { radius: 8, ...estilo(COLORES[f.properties.estado_mapa], 0.6) }),
    onEachFeature: (f, layer) => {
      const p = f.properties;
      const contenido = h(
        "div",
        { class: "popup" },
        h("b", {}, `${p.codigo} · ${p.nombre}`),
        h("span", {}, p.productor),
        h("span", {}, hectareas(p.area_ha)),
        h("a", { href: `#/parcelas/${p.parcela_id}` }, "Ver detalle"),
      );
      layer.bindPopup(contenido);
      layer.on("dblclick", () => navegar(`#/parcelas/${p.parcela_id}`));
    },
  }).addTo(mapa);
  encuadrar(mapa, capa);

  const cuenta = (estado) => coleccion.features.filter((f) => f.properties.estado_mapa === estado).length;
  resumen.textContent = coleccion.features.length
    ? `${coleccion.features.length} parcelas activas · ${cuenta("sin_alertas")} sin alertas · ${cuenta("con_alertas")} con alertas · ${cuenta("superposicion")} con superposición abierta`
    : "Todavía no hay parcelas registradas en la cooperativa.";

  return {
    titulo: "Mapa de parcelas",
    antetitulo: "Productores",
    descripcion: resumen,
    migas: [["Productores", "#/productores"], ["Mapa de parcelas"]],
    secciones: seccionesProductores(),
    contenido: h("section", { class: "panel panel-mapa" }, contenedor),
  };
}

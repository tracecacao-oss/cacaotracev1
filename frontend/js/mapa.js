// Mapa con Leaflet 1.9.4 y Leaflet-Geoman 2.20.2 (versión gratuita), cargados desde CDN con
// versión fija e integridad verificada. Capa de calles de OpenStreetMap y capa satelital de
// Esri World Imagery, que solo se activa si hay una clave en config.js.

import { ESRI_API_KEY } from "../config.js";
import { h } from "./ui.js";

const RECURSOS = [
  {
    tipo: "css",
    url: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css",
    sri: "sha384-c6Rcwz4e4CITMbu/NBmnNS8yN2sC3cUElMEMfP3vqqKFp7GOYaaBBCqmaWBjmkjb",
  },
  {
    tipo: "js",
    url: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js",
    sri: "sha384-NElt3Op+9NBMCYaef5HxeJmU4Xeard/Lku8ek6hoPTvYkQPh3zLIrJP7KiRocsxO",
  },
  {
    tipo: "css",
    url: "https://cdn.jsdelivr.net/npm/@geoman-io/leaflet-geoman-free@2.20.2/dist/leaflet-geoman.css",
    sri: "sha384-++juJE6hRzkkV4Ri9H2C+3yjCTdEk4PaZxptm3cpgKKjuMcAHErn35Q/0sGitZCR",
  },
  {
    tipo: "js",
    url: "https://cdn.jsdelivr.net/npm/@geoman-io/leaflet-geoman-free@2.20.2/dist/leaflet-geoman.js",
    sri: "sha384-smcfdVnOMup31VRg3qwcAAOj5JHZs5+Q1IX3dUWwtjU2VvQWRaDr6JYC1o0OIgsl",
  },
];

export const COLORES = {
  sin_alertas: "#059669",
  con_alertas: "#d97706",
  superposicion: "#e11d48",
  nueva: "#0284c7",
  interseccion: "#e11d48",
};

const PERU = [-9.2, -75.0];
let cargando = null;

function cargarRecurso({ tipo, url, sri }) {
  return new Promise((resolver, rechazar) => {
    const elemento =
      tipo === "css"
        ? Object.assign(document.createElement("link"), { rel: "stylesheet", href: url })
        : Object.assign(document.createElement("script"), { src: url });
    elemento.integrity = sri;
    elemento.crossOrigin = "anonymous";
    elemento.onload = resolver;
    elemento.onerror = () => rechazar(new Error("No se pudo cargar el mapa. Revisa tu conexión."));
    document.head.append(elemento);
  });
}

export function cargarMapas() {
  cargando ??= (async () => {
    for (const recurso of RECURSOS) await cargarRecurso(recurso);
    return window.L;
  })().catch((error) => {
    cargando = null;
    throw error;
  });
  return cargando;
}

export const satelitalDisponible = Boolean(ESRI_API_KEY);

/** Crea un mapa en el contenedor, con capas de satélite (si hay clave) y calles. */
export async function crearMapa(contenedor, { coordenadas = true } = {}) {
  const L = await cargarMapas();
  const mapa = L.map(contenedor, { zoomControl: true, maxZoom: 19 }).setView(PERU, 5);
  const calles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  });
  const capas = { Calles: calles };
  if (satelitalDisponible) {
    capas["Satélite"] = L.tileLayer(
      "https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token={token}",
      {
        token: ESRI_API_KEY,
        maxNativeZoom: 17,
        maxZoom: 19,
        attribution:
          'Powered by <a href="https://www.esri.com">Esri</a> | Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community',
      },
    );
    capas["Satélite"].addTo(mapa);
  } else {
    calles.addTo(mapa);
  }
  L.control.layers(capas, null, { position: "topright" }).addTo(mapa);
  if (coordenadas) agregarIrACoordenadas(L, mapa);
  // Las pantallas crean el mapa antes de insertarlo en la página: se ajusta cuando el
  // contenedor obtiene tamaño (y cada vez que cambia, por ejemplo al girar el celular).
  new ResizeObserver(() => mapa.invalidateSize()).observe(contenedor);
  return { L, mapa };
}

function agregarIrACoordenadas(L, mapa) {
  const Control = L.Control.extend({
    options: { position: "bottomleft" },
    onAdd() {
      const lat = h("input", { class: "input", type: "number", step: "any", placeholder: "Latitud", "aria-label": "Latitud" });
      const lon = h("input", { class: "input", type: "number", step: "any", placeholder: "Longitud", "aria-label": "Longitud" });
      const ir = h("button", { class: "btn btn-sm", type: "button" }, "Ir");
      ir.addEventListener("click", () => {
        const a = Number(lat.value);
        const b = Number(lon.value);
        if (Number.isFinite(a) && Number.isFinite(b) && Math.abs(a) <= 90 && Math.abs(b) <= 180) {
          mapa.setView([a, b], 17);
        }
      });
      const caja = h("div", { class: "mapa-control mapa-coordenadas" }, h("b", {}, "Ir a coordenadas"), lat, lon, ir);
      L.DomEvent.disableClickPropagation(caja);
      L.DomEvent.disableScrollPropagation(caja);
      return caja;
    },
  });
  new Control().addTo(mapa);
}

export function agregarLeyenda(L, mapa) {
  const Control = L.Control.extend({
    options: { position: "bottomleft" },
    onAdd() {
      const fila = (color, texto) => h("span", { class: "leyenda-i" }, h("i", { style: `background:${color}` }), texto);
      return h(
        "div",
        { class: "mapa-control leyenda" },
        fila(COLORES.sin_alertas, "Sin alertas"),
        fila(COLORES.con_alertas, "Con alertas"),
        fila(COLORES.superposicion, "Superposición abierta"),
      );
    },
  });
  new Control().addTo(mapa);
}

export function estilo(color, relleno = 0.2) {
  return { color, weight: 2, fillColor: color, fillOpacity: relleno };
}

/** Dibuja geometrías GeoJSON. Los puntos se muestran como círculos del mismo color. */
export function capaGeojson(L, datos, opciones = {}) {
  return L.geoJSON(datos, {
    pointToLayer: (_, latlng) => L.circleMarker(latlng, { radius: 8 }),
    ...opciones,
  });
}

export function encuadrar(mapa, capa) {
  const limites = capa.getBounds?.();
  if (!limites?.isValid()) return;
  const ajustar = () => mapa.fitBounds(limites.pad(0.3), { maxZoom: 17 });
  // Sin tamaño todavía (contenedor fuera de la página): se encuadra al obtenerlo.
  if (mapa.getSize().x === 0) mapa.once("resize", ajustar);
  else ajustar();
}

/** Área geodésica aproximada en hectáreas; la definitiva la calcula la API. */
export function areaAproximadaHa(latlngs) {
  const R = 6378137;
  const rad = (g) => (g * Math.PI) / 180;
  let area = 0;
  for (let i = 0; i < latlngs.length; i++) {
    const p1 = latlngs[i];
    const p2 = latlngs[(i + 1) % latlngs.length];
    area += rad(p2.lng - p1.lng) * (2 + Math.sin(rad(p1.lat)) + Math.sin(rad(p2.lat)));
  }
  return Math.abs((area * R * R) / 2) / 10000;
}

/**
 * Editor de una sola geometría (polígono o punto) con Geoman.
 * alCambiar(geometriaGeoJSON | null) se llama al crear, editar o borrar.
 */
const CONTROLES_DIBUJO = {
  position: "topleft",
  drawMarker: true,
  drawPolygon: true,
  editMode: true,
  removalMode: true,
  drawCircleMarker: false,
  drawPolyline: false,
  drawRectangle: false,
  drawCircle: false,
  drawText: false,
  dragMode: false,
  cutPolygon: false,
  rotateMode: false,
};

export function editorGeometria(L, mapa, { alCambiar, inicial }) {
  mapa.pm.setLang("es");
  mapa.pm.addControls(CONTROLES_DIBUJO);
  mapa.pm.setPathOptions(estilo(COLORES.nueva, 0.25));

  const area = h("div", { class: "mapa-control mapa-area", hidden: true });
  const ControlArea = L.Control.extend({ options: { position: "bottomright" }, onAdd: () => area });
  new ControlArea().addTo(mapa);

  let actual = null;
  const mostrarArea = (latlngs) => {
    if (!latlngs || latlngs.length < 3) {
      area.hidden = true;
      return;
    }
    area.textContent = `Área aproximada: ${areaAproximadaHa(latlngs).toFixed(2)} ha`;
    area.hidden = false;
  };
  const avisar = () => {
    if (!actual) {
      area.hidden = true;
      alCambiar(null);
      return;
    }
    if (actual instanceof L.Polygon) mostrarArea(actual.getLatLngs()[0]);
    else area.hidden = true;
    alCambiar(actual.toGeoJSON().geometry);
  };
  const tomar = (capa) => {
    if (actual && actual !== capa) mapa.removeLayer(actual);
    actual = capa;
    capa.on("pm:edit", avisar);
    avisar();
  };

  mapa.on("pm:drawstart", ({ workingLayer }) => {
    workingLayer.on("pm:vertexadded", () => mostrarArea(workingLayer.getLatLngs()));
  });
  mapa.on("pm:create", ({ layer }) => tomar(layer));
  mapa.on("pm:remove", ({ layer }) => {
    if (layer === actual) {
      actual = null;
      avisar();
    }
  });

  if (inicial) {
    const capa = capaGeojson(L, inicial, { style: estilo(COLORES.nueva, 0.25) }).getLayers()[0];
    capa.addTo(mapa);
    tomar(capa);
    encuadrar(mapa, L.featureGroup([capa]));
  }
  return {
    mostrarControles() {
      mapa.pm.addControls(CONTROLES_DIBUJO);
    },
    reemplazar(geometria) {
      if (actual) mapa.removeLayer(actual);
      actual = null;
      if (geometria) {
        const capa = capaGeojson(L, geometria, { style: estilo(COLORES.nueva, 0.25) }).getLayers()[0];
        capa.addTo(mapa);
        tomar(capa);
        encuadrar(mapa, L.featureGroup([capa]));
      } else {
        avisar();
      }
    },
  };
}

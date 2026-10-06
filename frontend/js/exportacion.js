// Piezas de la Parte 7 que comparten Exportación y Trazabilidad: secciones de los dos módulos, estados,
// indicadores del lote y la vista de genealogía (diagrama de cinco columnas, tabla por parcela y mapa), donde
// tocar una parcela en cualquiera de las tres la resalta en las otras dos.

import { capaGeojson, crearMapa, encuadrar, estilo } from "./mapa.js";
import { kilos } from "./textos.js";
import { h } from "./ui.js";

export function seccionesExportacion() {
  return [
    ["Órdenes", "#/exportacion/ordenes"],
    ["Lotes", "#/exportacion/lotes"],
    ["Importadores", "#/exportacion/importadores"],
  ];
}

export function seccionesTrazabilidad() {
  return [
    ["Genealogía por lote", "#/trazabilidad/lotes"],
    ["Rastreo por origen", "#/trazabilidad/origen"],
  ];
}

export const ESTADOS_ORDEN = {
  abierta: ["info", "Abierta"],
  con_lote: ["ok", "Con lote"],
  cerrada: ["", "Cerrada"],
  anulada: ["bad", "Anulada"],
};
export const ESTADOS_LOTE = {
  en_armado: ["warn", "En armado"],
  armado: ["ok", "Armado"],
  anulado: ["bad", "Anulado"],
};

export function insignia([clase, texto]) {
  return h("span", { class: `badge ${clase}`.trim() }, h("span", { class: "dot" }), texto);
}

export const estadoOrden = (e) => insignia(ESTADOS_ORDEN[e] ?? ["", e]);
export const estadoLote = (e) => insignia(ESTADOS_LOTE[e] ?? ["", e]);

/** Etiqueta visible de un lote que se apartó del orden FIFO (regla 2 de la interfaz). */
export function insigniaFifo() {
  return h("span", { class: "badge warn", title: "La selección se apartó del orden FIFO" }, h("span", { class: "dot" }), "Fuera de FIFO");
}

/** Proporción (0 a 1) como porcentaje con un decimal. */
export function porcentaje(proporcion) {
  return `${(Number(proporcion) * 100).toLocaleString("es-PE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
}

/** Un porcentaje que ya viene en 0 a 100, con un decimal. */
export function pct(valor) {
  return `${Number(valor).toLocaleString("es-PE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
}

export const nombreProductor = (p) => `${p.nombres} ${p.apellidos}`;

// ---------- Indicadores ----------

function valorIndicador(i) {
  const v = i.valor;
  switch (i.clave) {
    case "balance_masa":
      return [h("b", { class: "mono" }, kilos(v.diferencia_kg)), h("span", { class: "sec" }, `de diferencia · masa ${kilos(v.masa_neta_kg)} · atribuido ${kilos(v.suma_atribuida_kg)}`)];
    case "corridas_mezcladas":
      return [h("b", { class: "mono" }, String(v.mezcladas)), h("span", { class: "sec" }, `de ${v.corridas} ${v.corridas === 1 ? "corrida" : "corridas"} de origen`)];
    case "cobertura_genealogia_pct":
    case "concentracion_mayor_parcela_pct":
    case "concentracion_tres_parcelas_pct":
      return h("b", { class: "mono" }, pct(v));
    case "desviacion_fifo":
      return v.desviacion ? [h("b", {}, "Sí"), h("span", { class: "sec" }, `Motivo: ${v.motivo}`)] : h("b", {}, "No");
    default:
      return h("b", { class: "mono" }, String(v));
  }
}

/** Cifras con su nombre y una frase que explica qué miden, sin colores que califiquen el lote. */
export function tarjetasIndicadores(indicadores) {
  return h(
    "div",
    { class: "indicadores" },
    indicadores.map((i) => h("div", { class: "indicador" }, h("span", { class: "indicador-n" }, i.nombre), h("div", { class: "indicador-v" }, valorIndicador(i)), h("p", { class: "sec" }, i.explicacion))),
  );
}

// ---------- Diagrama de la genealogía ----------

const NS = "http://www.w3.org/2000/svg";
function svg(etiqueta, atributos = {}, texto) {
  const el = document.createElementNS(NS, etiqueta);
  for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, v);
  if (texto != null) el.textContent = texto;
  return el;
}

/** Nodos y enlaces de las cinco columnas a partir de las filas de la genealogía. */
function grafo(g) {
  const columnas = [new Map(), new Map(), new Map(), new Map(), new Map()];
  const enlaces = new Map();
  const orden = new Map(g.por_parcela.map((p, i) => [p.parcela_id, i]));
  const filas = [...g.filas].sort((a, b) => (orden.get(a.parcela_id) ?? 0) - (orden.get(b.parcela_id) ?? 0));
  const nodo = (col, id, etiqueta, parcela) => {
    const m = columnas[col];
    if (!m.has(id)) m.set(id, { id, col, etiqueta, kg: 0, parcelas: new Set() });
    const n = m.get(id);
    if (parcela) n.parcelas.add(parcela);
    return n;
  };
  const enlace = (a, b, kg, parcela) => {
    const clave = `${a.col}:${a.id}>${b.id}`;
    if (!enlaces.has(clave)) enlaces.set(clave, { a, b, kg: 0, parcelas: new Set() });
    const e = enlaces.get(clave);
    e.kg += kg;
    e.parcelas.add(parcela);
  };
  for (const f of filas) {
    const kg = Number(f.kg_atribuidos);
    const p = nodo(0, f.parcela_id, f.parcela_codigo, f.parcela_id);
    const t = nodo(1, f.tanda.id, f.tanda.codigo, f.parcela_id);
    const c = nodo(2, f.corrida.id, f.corrida.codigo, f.parcela_id);
    const tf = nodo(3, f.tanda_final.id, f.tanda_final.codigo, f.parcela_id);
    const l = nodo(4, g.lote.id, g.lote.codigo, f.parcela_id);
    for (const n of [p, t, c, tf, l]) n.kg += kg;
    enlace(p, t, kg, f.parcela_id);
    enlace(t, c, kg, f.parcela_id);
    enlace(c, tf, kg, f.parcela_id);
    enlace(tf, l, kg, f.parcela_id);
  }
  return { columnas: columnas.map((m) => [...m.values()]), enlaces: [...enlaces.values()] };
}

function diagrama(g, alElegir) {
  const { columnas, enlaces } = grafo(g);
  const ANCHO = 1150;
  const NODO = 14;
  const SEP = 10;
  const masa = Number(g.masa_neta_kg) || 1;
  const maxNodos = Math.max(...columnas.map((c) => c.length));
  const ALTO = Math.max(260, maxNodos * 34);
  const escala = (ALTO - 40 - (maxNodos - 1) * SEP) / masa;
  const xs = [170, 370, 565, 760, 950];
  const titulos = ["Parcelas", "Tandas", "Corridas", "Tandas finales", "Lote"];
  const lienzo = svg("svg", { viewBox: `0 0 ${ANCHO} ${ALTO}`, class: "sankey", role: "img", "aria-label": "Diagrama de la genealogía del lote, de las parcelas al lote" });
  titulos.forEach((t, i) => lienzo.append(svg("text", { x: xs[i] + NODO / 2, y: 14, "text-anchor": "middle", class: "sankey-col" }, t)));
  columnas.forEach((col, i) => {
    const total = col.reduce((s, n) => s + n.kg * escala, 0) + (col.length - 1) * SEP;
    let y = 24 + (ALTO - 24 - total) / 2;
    for (const n of col) {
      n.x = xs[i];
      n.y = y;
      n.alto = Math.max(n.kg * escala, 1.5);
      n.salida = n.y;
      n.entrada = n.y;
      y += n.alto + SEP;
    }
  });
  const bandas = svg("g", { class: "sankey-enlaces" });
  for (const e of enlaces) {
    const grosor = Math.max(e.kg * escala, 1);
    const x0 = e.a.x + NODO;
    const x1 = e.b.x;
    const y0 = e.a.salida;
    const y1 = e.b.entrada;
    e.a.salida += grosor;
    e.b.entrada += grosor;
    const xm = (x0 + x1) / 2;
    const d = `M${x0},${y0}C${xm},${y0} ${xm},${y1} ${x1},${y1}L${x1},${y1 + grosor}C${xm},${y1 + grosor} ${xm},${y0 + grosor} ${x0},${y0 + grosor}Z`;
    const camino = svg("path", { d, class: "sankey-enlace" });
    camino.dataset.parcelas = [...e.parcelas].join(" ");
    camino.append(svg("title", {}, `${e.a.etiqueta} → ${e.b.etiqueta}: ${kilos(e.kg)}`));
    bandas.append(camino);
  }
  lienzo.append(bandas);
  const nodos = svg("g", { class: "sankey-nodos" });
  columnas.forEach((col, i) => {
    for (const n of col) {
      const grupo = svg("g", { class: `sankey-nodo${i === 0 ? " es-parcela" : ""}` });
      grupo.dataset.parcelas = [...n.parcelas].join(" ");
      grupo.append(svg("rect", { x: n.x, y: n.y, width: NODO, height: n.alto, rx: 2 }));
      const izquierda = i === 0;
      grupo.append(
        svg("text", { x: izquierda ? n.x - 6 : n.x + NODO + 6, y: n.y + n.alto / 2, "text-anchor": izquierda ? "end" : "start", "dominant-baseline": "middle" }, `${n.etiqueta} · ${Number(n.kg).toLocaleString("es-PE", { maximumFractionDigits: 2 })} kg`),
      );
      if (izquierda) {
        grupo.setAttribute("tabindex", "0");
        grupo.setAttribute("role", "button");
        grupo.setAttribute("aria-label", `Resaltar la parcela ${n.etiqueta}`);
        grupo.addEventListener("click", () => alElegir(n.id));
        grupo.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            alElegir(n.id);
          }
        });
      }
      nodos.append(grupo);
    }
  });
  lienzo.append(nodos);
  return lienzo;
}

/**
 * Vista de genealogía de un lote: diagrama, tabla por parcela (de mayor a menor) y mapa. Devuelve el nodo; el
 * mapa se crea al insertarse.
 */
export function vistaGenealogia(g) {
  let elegida = null;
  const capas = new Map();
  const filasTabla = new Map();
  let lienzo;

  function resaltar(parcelaId) {
    elegida = elegida === parcelaId ? null : parcelaId;
    for (const el of lienzo.querySelectorAll("[data-parcelas]")) {
      const toca = !elegida || el.dataset.parcelas.split(" ").includes(elegida);
      el.classList.toggle("apagado", !toca);
      el.classList.toggle("elegido", Boolean(elegida) && toca);
    }
    for (const [id, tr] of filasTabla) tr.classList.toggle("fila-elegida", id === elegida);
    for (const [id, capa] of capas) {
      capa.setStyle(estilo(id === elegida ? "#d97706" : "#059669", id === elegida ? 0.5 : 0.25));
      if (id === elegida) capa.bringToFront();
    }
  }

  lienzo = diagrama(g, resaltar);
  const tabla = h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "Parcela"), h("th", {}, "Productor"), h("th", { class: "num" }, "Kilos en el lote"), h("th", { class: "num" }, "Proporción"))),
      h(
        "tbody",
        {},
        g.por_parcela.map((p) => {
          const tr = h(
            "tr",
            { class: "fila-tocable", tabindex: "0", onclick: () => resaltar(p.parcela_id), onkeydown: (e) => (e.key === "Enter" ? resaltar(p.parcela_id) : null) },
            h("td", {}, h("a", { href: `#/parcelas/${p.parcela_id}`, class: "mono", onclick: (e) => e.stopPropagation() }, p.codigo), h("span", { class: "sec" }, p.nombre)),
            h("td", {}, nombreProductor(p.productor), h("span", { class: "sec mono" }, `DNI ${p.productor.dni}`)),
            h("td", { class: "num mono" }, kilos(p.kg)),
            h("td", { class: "num mono" }, porcentaje(p.proporcion)),
          );
          filasTabla.set(p.parcela_id, tr);
          return tr;
        }),
      ),
      h("tfoot", {}, h("tr", {}, h("th", { colspan: 2 }, "Total"), h("th", { class: "num mono" }, kilos(g.masa_neta_kg)), h("th", { class: "num mono" }, porcentaje(1)))),
    ),
  );
  const contenedorMapa = h("div", { class: "mapa mapa-genealogia" });
  crearMapa(contenedorMapa, { coordenadas: false }).then(({ L, mapa }) => {
    const coleccion = { type: "FeatureCollection", features: g.por_parcela.map((p) => ({ type: "Feature", geometry: p.geometria, properties: { parcela_id: p.parcela_id, codigo: p.codigo, kg: p.kg } })) };
    const capa = capaGeojson(L, coleccion, {
      style: () => estilo("#059669", 0.25),
      pointToLayer: (_, latlng) => L.circleMarker(latlng, { radius: 8, ...estilo("#059669", 0.5) }),
      onEachFeature: (f, layer) => {
        capas.set(f.properties.parcela_id, layer);
        layer.bindTooltip(`${f.properties.codigo} · ${kilos(f.properties.kg)}`);
        layer.on("click", () => resaltar(f.properties.parcela_id));
      },
    }).addTo(mapa);
    encuadrar(mapa, capa);
    // El contenedor cambia de tamaño al insertarse la vista: se vuelve a encuadrar con el tamaño final.
    mapa.on("resize", () => encuadrar(mapa, capa));
  });
  return h(
    "div",
    { class: "genealogia" },
    g.anulada && h("p", { class: "alerta warn" }, "Lote anulado: la genealogía queda como historial."),
    h("div", { class: "sankey-caja" }, lienzo),
    h("p", { class: "panel-sub" }, "El grosor de cada enlace es proporcional a los kilos. Toca una parcela en el diagrama, la tabla o el mapa para resaltarla en los tres."),
    h("div", { class: "genealogia-pie" }, tabla, contenedorMapa),
  );
}

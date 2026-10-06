// Piezas de la Parte 7 que comparten Exportación y Trazabilidad: secciones de los dos módulos, estados,
// indicadores del lote y la vista de genealogía con la composición del diseño de referencia (columnas
// numeradas unidas por cintas proporcionales a los kilos), más la tabla por parcela y el mapa; tocar una
// parcela en cualquiera de las tres vistas la resalta en las otras dos.

import { capaGeojson, crearMapa, encuadrar, estilo } from "./mapa.js";
import { kilos } from "./textos.js";
import { avatar, h, icono } from "./ui.js";

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

// ---------- Genealogía ----------

const NS = "http://www.w3.org/2000/svg";
const f1 = (n) => n.toFixed(1);
const kg2 = (v) => `${Number(v).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kg`;

/** Nodos de las columnas 2 a 4 y enlaces de las cinco: parcelas, tandas, corridas, tandas finales y lote. */
function grafo(g) {
  const orden = new Map(g.por_parcela.map((p, i) => [p.parcela_id, i]));
  const filas = [...g.filas].sort((a, b) => (orden.get(a.parcela_id) ?? 0) - (orden.get(b.parcela_id) ?? 0));
  const columnas = [new Map(), new Map(), new Map()];
  const enlaces = new Map();
  const nodo = (col, id, datos, parcela, kg) => {
    const m = columnas[col];
    if (!m.has(id)) m.set(id, { id, kg: 0, parcelas: new Set(), ...datos });
    const n = m.get(id);
    n.kg += kg;
    n.parcelas.add(parcela);
  };
  const enlace = (a, b, kg, parcela) => {
    const clave = `${a}>${b}`;
    if (!enlaces.has(clave)) enlaces.set(clave, { a, b, kg: 0, parcelas: new Set() });
    const e = enlaces.get(clave);
    e.kg += kg;
    e.parcelas.add(parcela);
  };
  for (const f of filas) {
    const kg = Number(f.kg_atribuidos);
    nodo(0, f.tanda.id, { tanda: f.tanda, dop: f.dop }, f.parcela_id, kg);
    nodo(1, f.corrida.id, { corrida: f.corrida, tipo_manejo: f.tipo_manejo }, f.parcela_id, kg);
    nodo(2, f.tanda_final.id, { tanda_final: f.tanda_final, dpp: f.dpp }, f.parcela_id, kg);
    enlace(f.parcela_id, f.tanda.id, kg, f.parcela_id);
    enlace(f.tanda.id, f.corrida.id, kg, f.parcela_id);
    enlace(f.corrida.id, f.tanda_final.id, kg, f.parcela_id);
    enlace(f.tanda_final.id, g.lote.id, kg, f.parcela_id);
  }
  return { tandas: [...columnas[0].values()], corridas: [...columnas[1].values()], finales: [...columnas[2].values()], enlaces: [...enlaces.values()] };
}

const kv = (filas) => h("dl", { class: "kv" }, filas.filter(Boolean).map(([a, b]) => h("div", {}, h("dt", {}, a), h("dd", { class: "mono" }, b))));

function columna(paso, titulo, detalle, cuerpo) {
  return h("div", { class: "gnode" }, h("div", { class: "gnode-h" }, h("span", { class: "gstep" }, String(paso)), h("h3", {}, titulo), detalle && h("span", {}, detalle)), h("div", { class: "gnode-b" }, cuerpo));
}

function caja({ id, parcelas, icono: ic, tono = "", etiqueta, codigo, filas, pie }) {
  const el = h(
    "div",
    { class: "gbox", "data-id": id },
    h("div", { class: "gbox-t" }, h("span", { class: `gbox-ic ${tono}`.trim() }, icono(ic, "ic-lg")), h("span", { class: "gbox-tt" }, h("span", {}, etiqueta), h("b", { class: "mono" }, codigo))),
    kv(filas),
    pie && h("div", { class: "gsub" }, pie),
  );
  el.dataset.parcelas = [...parcelas].join(" ");
  return el;
}

/**
 * Cintas con grosor proporcional a los kilos y, encima, la línea punteada del recorrido, como el diseño.
 * En pantallas angostas las columnas se apilan y se unen con un enlace vertical.
 */
function dibujarEnlaces(envoltura, lienzo, enlaces, masa, enfocada) {
  const R = envoltura.getBoundingClientRect();
  if (!R.width) return;
  lienzo.setAttribute("viewBox", `0 0 ${f1(R.width)} ${f1(R.height)}`);
  const rel = (el) => {
    const b = el.getBoundingClientRect();
    return { l: b.left - R.left, r: b.right - R.left, t: b.top - R.top, b: b.bottom - R.top, cx: (b.left + b.right) / 2 - R.left, cy: (b.top + b.bottom) / 2 - R.top };
  };
  const elementos = new Map([...envoltura.querySelectorAll("[data-id]")].map((el) => [el.dataset.id, el]));
  const columnas = [...envoltura.querySelectorAll(".gnode-b")].map(rel);
  const trazos = [];
  const camino = (d, ancho, parcelas, principal) => {
    for (const clase of ["gl-rib", "gl-flow"]) {
      const p = document.createElementNS(NS, "path");
      p.setAttribute("d", d);
      p.setAttribute("class", `${clase}${principal ? " main" : ""}${enfocada && parcelas.includes(enfocada) ? " is-on" : ""}`);
      if (clase === "gl-rib") p.setAttribute("stroke-width", f1(ancho));
      p.dataset.parcelas = parcelas.join(" ");
      trazos.push(p);
    }
  };
  if (columnas.length > 1 && columnas[1].l < columnas[0].r - 4) {
    for (let i = 0; i < columnas.length - 1; i++) {
      const a = columnas[i];
      const b = columnas[i + 1];
      camino(`M${f1(a.cx)} ${f1(a.b)}L${f1(b.cx)} ${f1(b.t - 32)}`, 10, [], true);
    }
  } else {
    const BANDA = 44;
    const ancho = (kg) => Math.max(2.5, (kg / masa) * BANDA);
    const salida = new Map();
    const entrada = new Map();
    for (const e of enlaces) {
      salida.set(e.a, (salida.get(e.a) ?? 0) + ancho(e.kg));
      entrada.set(e.b, (entrada.get(e.b) ?? 0) + ancho(e.kg));
    }
    const cursorSalida = new Map();
    const cursorEntrada = new Map();
    for (const e of enlaces) {
      const a = elementos.get(e.a);
      const b = elementos.get(e.b);
      if (!a || !b) continue;
      const ra = rel(a);
      const rb = rel(b);
      const w = ancho(e.kg);
      const ya = (cursorSalida.get(e.a) ?? ra.cy - salida.get(e.a) / 2) + w / 2;
      const yb = (cursorEntrada.get(e.b) ?? rb.cy - entrada.get(e.b) / 2) + w / 2;
      cursorSalida.set(e.a, ya + w / 2);
      cursorEntrada.set(e.b, yb + w / 2);
      const m = (ra.r + rb.l) / 2;
      camino(`M${f1(ra.r)} ${f1(ya)}C${f1(m)} ${f1(ya)} ${f1(m)} ${f1(yb)} ${f1(rb.l)} ${f1(yb)}`, w, [...e.parcelas], e.parcelas.size > 1);
    }
  }
  lienzo.replaceChildren(...trazos);
}

/**
 * Vista de genealogía de un lote: columnas numeradas (origen por parcela, tandas y DOP, corridas, tandas
 * finales y lote) unidas por cintas proporcionales a los kilos; debajo, la tabla por parcela y el mapa.
 * `lote` (opcional) es el lote de la lista o del detalle, para mostrar su orden, su importador y su calidad.
 * `incrustada` la pinta sin paneles propios, para ir dentro de otro panel (la pestaña del detalle del lote).
 */
export function vistaGenealogia(g, { lote = null, incrustada = false } = {}) {
  const { tandas, corridas, finales, enlaces } = grafo(g);
  const masa = Number(g.masa_neta_kg) || 1;
  const capas = new Map();
  const filasTabla = new Map();
  let enfocada = null;

  const lienzo = document.createElementNS(NS, "svg");
  lienzo.setAttribute("class", "genea-links");
  lienzo.setAttribute("aria-hidden", "true");

  const origen = h(
    "div",
    { class: "gprods" },
    g.por_parcela.map((p) => {
      const boton = h(
        "button",
        { class: "gprod", type: "button", "data-id": p.parcela_id, "aria-label": `${nombreProductor(p.productor)}, parcela ${p.codigo}: ${kg2(p.kg)}`, onclick: () => enfocar(p.parcela_id) },
        avatar(p.productor.nombres, p.productor.apellidos, "sm"),
        h("span", { class: "gprod-t" }, h("span", { class: "gprod-n" }, nombreProductor(p.productor)), h("span", { class: "gprod-p" }, h("span", { class: "mono" }, p.codigo), ` · ${p.nombre}`)),
        h("span", { class: "gprod-k" }, h("b", { class: "mono" }, kg2(p.kg)), h("span", { class: "mono" }, porcentaje(p.proporcion))),
      );
      boton.dataset.parcelas = p.parcela_id;
      return boton;
    }),
  );
  const columnaTandas = h(
    "div",
    { class: "gitems" },
    tandas.map((t) => {
      const el = h(
        "a",
        { class: "gitem", href: `#/tandas/${t.tanda.id}`, "data-id": t.tanda.id },
        h("span", { class: "gitem-t" }, h("b", { class: "mono" }, t.tanda.codigo), h("span", { class: "mono" }, t.dop.codigo)),
        h("span", { class: "gitem-k mono" }, kg2(t.kg)),
      );
      el.dataset.parcelas = [...t.parcelas].join(" ");
      return el;
    }),
  );
  const columnaCorridas = h(
    "div",
    { class: "gitems" },
    corridas.map((c) =>
      caja({
        id: c.corrida.id,
        parcelas: c.parcelas,
        icono: "flask",
        tono: "sky",
        etiqueta: "Corrida",
        codigo: c.corrida.codigo,
        filas: [["Manejo", c.tipo_manejo === "segregado" ? "Segregada" : "Mezclada"], ["Kilos en el lote", kg2(c.kg)]],
        pie: h("a", { class: "btn btn-sm btn-block", href: `#/corridas/${c.corrida.id}` }, "Ver la corrida"),
      }),
    ),
  );
  const columnaFinales = h(
    "div",
    { class: "gitems" },
    finales.map((f) =>
      caja({
        id: f.tanda_final.id,
        parcelas: f.parcelas,
        icono: "sack",
        tono: "amber",
        etiqueta: "Tanda final",
        codigo: f.tanda_final.codigo,
        filas: [["DPP", f.dpp.codigo], ["Kilos tomados", kg2(f.kg)]],
        pie: h("a", { class: "btn btn-sm btn-block", href: `#/dpps/${f.dpp.id}` }, icono("file", "ic-sm"), "Ver el DPP"),
      }),
    ),
  );
  const columnaLote = caja({
    id: g.lote.id,
    parcelas: new Set(g.por_parcela.map((p) => p.parcela_id)),
    icono: "ship",
    etiqueta: "Lote de exportación",
    codigo: g.lote.codigo,
    filas: [
      ["Masa neta", kg2(g.masa_neta_kg)],
      lote && ["Orden", lote.orden.codigo],
      lote && ["Importador", lote.importador],
      lote && ["Calidad", lote.calidad],
      ["Estado", ESTADOS_LOTE[g.lote.estado]?.[1] ?? g.lote.estado],
    ],
    pie: lote && h("a", { class: "btn btn-sm btn-block", href: `#/lotes-exportacion/${g.lote.id}` }, "Ver el lote"),
  });

  const envoltura = h(
    "div",
    { class: "genea" },
    lienzo,
    columna(1, "Origen", `${g.por_parcela.length} ${g.por_parcela.length === 1 ? "parcela" : "parcelas"}`, origen),
    columna(2, "Tandas y DOP", `${tandas.length}`, columnaTandas),
    columna(3, "Corridas", null, columnaCorridas),
    columna(4, "Tandas finales", null, columnaFinales),
    columna(5, "Lote", null, columnaLote),
  );
  const redibujar = () => dibujarEnlaces(envoltura, lienzo, enlaces, masa, enfocada);
  new ResizeObserver(() => requestAnimationFrame(redibujar)).observe(envoltura);

  function enfocar(parcelaId) {
    enfocada = enfocada === parcelaId ? null : parcelaId;
    envoltura.classList.toggle("has-focus", Boolean(enfocada));
    for (const el of envoltura.querySelectorAll("[data-parcelas]")) {
      el.classList.toggle("is-on", Boolean(enfocada) && el.dataset.parcelas.split(" ").includes(enfocada));
    }
    for (const [id, tr] of filasTabla) tr.classList.toggle("fila-elegida", id === enfocada);
    for (const [id, capa] of capas) {
      capa.setStyle(estilo(id === enfocada ? "#d97706" : "#059669", id === enfocada ? 0.5 : 0.25));
      if (id === enfocada) capa.bringToFront();
    }
  }

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
            { class: "fila-tocable", tabindex: "0", onclick: () => enfocar(p.parcela_id), onkeydown: (e) => (e.key === "Enter" ? enfocar(p.parcela_id) : null) },
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
        layer.on("click", () => enfocar(f.properties.parcela_id));
      },
    }).addTo(mapa);
    encuadrar(mapa, capa);
    // El contenedor cambia de tamaño al insertarse la vista: se vuelve a encuadrar con el tamaño final.
    mapa.on("resize", () => encuadrar(mapa, capa));
  });

  const bloque = (clase, atributos, ...hijos) => h(incrustada ? "div" : "section", { class: incrustada ? clase : `panel ${clase}`, ...atributos }, ...hijos);
  return h(
    "div",
    { class: incrustada ? "genealogia incrustada" : "genealogia" },
    g.anulada && h("p", { class: "alerta warn" }, "Lote anulado: la genealogía queda como historial."),
    bloque("genea-card", { "aria-label": "Genealogía del lote" }, envoltura),
    bloque(
      "genea-detalle",
      {},
      h("div", { class: "sect-t" }, h("div", {}, h("h3", {}, "Por parcela"), h("p", { class: "panel-sub" }, "Kilos de cada parcela en el lote, de mayor a menor. Toca una parcela aquí, en el diagrama o en el mapa para resaltarla en los tres."))),
      h("div", { class: "genealogia-pie" }, tabla, contenedorMapa),
    ),
  );
}

/** Resumen del lote bajo el buscador, como la línea del diseño. */
export function resumenLote(l, g) {
  const productores = new Set(g.por_parcela.map((p) => p.productor.id)).size;
  return [
    h("span", { class: "lead" }, l.codigo),
    estadoLote(l.estado),
    l.desviacion_fifo && insigniaFifo(),
    h("span", {}, h("b", { class: "mono" }, String(g.por_parcela.length)), ` ${g.por_parcela.length === 1 ? "parcela" : "parcelas"} · `, h("b", { class: "mono" }, String(productores)), ` ${productores === 1 ? "productor" : "productores"}`),
    h("span", {}, h("b", { class: "mono" }, kg2(g.masa_neta_kg)), " de masa neta · orden ", h("b", { class: "mono" }, l.orden.codigo)),
    h("span", {}, `${l.importador} · ${l.calidad}`),
  ];
}

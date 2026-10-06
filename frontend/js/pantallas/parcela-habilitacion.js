// Parte 4 en el detalle de la parcela: pestañas Cobertura forestal, Expediente y Habilitación (la de
// Imágenes, de la adenda 2, está en parcela-imagenes.js). El operador y el productor arman el expediente;
// el administrador decide.
// Principio: exponer, no concluir. Cada tarjeta dice quién afirma qué y cuándo.

import { llamarApi } from "../api.js";
import { verDocumento } from "../documentos.js";
import { rolEfectivo } from "../estado.js";
import {
  ESTADOS_CASILLA,
  FUENTES,
  OBSERVACIONES_CAMBIO,
  REQUISITOS,
  REQUISITOS_PRODUCTOR,
  hectareas,
  insigniaAlerta,
  insigniaHabilitacion,
  insigniaNivel,
} from "../textos.js";
import { abrirModal, campo, cargando, enviarCon, errorDeCarga, fecha, h, icono, reemplazar, seccion, toast } from "../ui.js";

const hoy = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Lima" }).format(new Date());

function insignia(clase, texto) {
  return h("span", { class: `badge ${clase}` }, h("span", { class: "dot" }), texto);
}

/** ctx: { p, base, delProductor, recargar } — base es /parcelas/{id} o /mi/parcelas/{id}. */
function permisos(ctx) {
  const rol = rolEfectivo();
  const activa = ctx.p.estado === "activa" && ctx.p.habilitacion_estado !== "excluida";
  return {
    registro: activa && ["admin_cooperativa", "operador"].includes(rol),
    admin: activa && rol === "admin_cooperativa",
    // El productor carga documentos legales de sus propias parcelas.
    cargaDocumentos: activa && (ctx.delProductor || ["admin_cooperativa", "operador"].includes(rol)),
  };
}

// ---------- Cobertura forestal ----------

const INDICADORES_WHISP = {
  risk_pcrop: "Riesgo para cultivos permanentes (incluye cacao)",
  Ind_01_treecover: "Cobertura arbórea al 2020",
  Ind_02_commodities: "Cultivos o agricultura al 2020",
  Ind_03_disturbance_before_2020: "Perturbación antes de 2020",
  Ind_04_disturbance_after_2020: "Perturbación desde 2021",
  EUFO_2020: "Bosque al 2020 según JRC",
  GLAD_Primary: "Bosque primario (GLAD)",
  TMF_undist: "Bosque tropical no perturbado (TMF)",
  Cocoa_ETH: "Cacao (ETH)",
  Cocoa_FDaP: "Cacao (FDaP)",
  Cocoa_2024_FDaP: "Cacao 2024 (FDaP)",
  Area: "Área analizada",
  Country: "País",
  In_waterbody: "Dentro de un cuerpo de agua",
};

function valorIndicador(clave, valor, unidad) {
  if (valor === "yes") return "sí";
  if (valor === "no") return "no";
  if (typeof valor === "boolean") return valor ? "sí" : "no";
  if (typeof valor === "number" && !["Country"].includes(clave)) return `${valor.toLocaleString("es-PE", { maximumFractionDigits: 4 })}${unidad ? ` ${unidad}` : ""}`;
  return String(valor);
}

function indicadoresWhisp(ind) {
  const unidad = ind.Unit === "percent" ? "%" : "ha";
  return Object.entries(INDICADORES_WHISP)
    .filter(([clave]) => clave in ind)
    .map(([clave, etiqueta]) => h("div", {}, h("dt", {}, etiqueta, h("span", { class: "campo-fuente mono" }, clave)), h("dd", {}, valorIndicador(clave, ind[clave], unidad))));
}

const PREGUNTAS = [
  ["estado_2020", "Al 31 de diciembre de 2020"],
  ["cambio_posterior", "Después de 2020"],
  ["cultivo", "Cultivos"],
  ["otra", "Otras capas"],
];

function numero(valor) {
  return typeof valor === "number" ? valor.toLocaleString("es-PE", { maximumFractionDigits: 4 }) : String(valor);
}

function conUnidad(valor, unidad) {
  return `${numero(valor)}${typeof valor === "number" && unidad ? ` ${unidad}` : ""}`;
}

/** Detalle por capa de Whisp (adenda): qué conjuntos vieron bosque en 2020 y cuáles vieron cambios. */
function capasWhisp(capas) {
  if (!capas?.length) return null;
  return h(
    "details",
    { class: "capas-detalle" },
    h("summary", {}, `Detalle por capa (${capas.length} capas)`),
    PREGUNTAS.map(([pregunta, titulo]) => {
      const grupo = capas.filter((c) => c.pregunta === pregunta);
      if (!grupo.length) return null;
      // Primero las que miden algo distinto de cero.
      const orden = [...grupo].sort((a, b) => Number(b.valor !== 0) - Number(a.valor !== 0));
      const distintas = grupo.filter((c) => typeof c.valor === "number" && c.valor !== 0).length;
      return h(
        "div",
        { class: "capas-grupo" },
        h("b", {}, titulo, h("span", { class: "sec" }, ` · ${grupo.length} capas, ${distintas} distintas de cero`)),
        h(
          "div",
          { class: "tbl-box" },
          h(
            "table",
            { class: "tabla tabla-compacta" },
            h("thead", {}, h("tr", {}, h("th", {}, "Capa"), h("th", {}, "Conjunto de datos"), h("th", { class: "num" }, "Valor"))),
            h(
              "tbody",
              {},
              orden.map((c) =>
                h(
                  "tr",
                  {},
                  h("td", { class: "mono" }, c.nombre),
                  h("td", {}, c.conjunto_nombre ?? h("span", { class: "sec" }, "Fuera del catálogo")),
                  h("td", { class: "num mono" }, conUnidad(c.valor, c.unidad)),
                ),
              ),
            ),
          ),
        ),
      );
    }),
  );
}

function indicadoresGfw(ind) {
  const filas = [
    ["Alertas integradas de deforestación", ind.alertas_desde_2021 != null ? String(ind.alertas_desde_2021) : "—"],
    ["Pérdida de cobertura arbórea", hectareas(ind.perdida_ha_total)],
    ind.bosque_natural_2020_ha != null && ["Bosque natural en 2020 (SBTN)", hectareas(ind.bosque_natural_2020_ha)],
    ind.alertas_dist_desde_2021 != null && ["Alertas DIST desde 2021", String(ind.alertas_dist_desde_2021)],
    ...Object.entries(ind.perdida_ha_por_anio ?? {}).map(([anio, ha]) => [`Pérdida en ${anio}`, hectareas(ha)]),
    ["Rango consultado", ind.desde ? `${ind.desde} a ${ind.hasta}` : "—"],
    ["Umbral de densidad arbórea 2000", ind.umbral_densidad_2000_porcentaje != null ? `${ind.umbral_densidad_2000_porcentaje} %` : "—"],
  ].filter(Boolean);
  return filas.map(([etiqueta, valor]) => h("div", {}, h("dt", {}, etiqueta), h("dd", {}, valor)));
}

function indicadoresMapbiomas(ind) {
  return [
    ["Clase predominante en 2020", ind.clase_predominante_2020 ?? "—"],
    ["Bosque en 2020", hectareas(ind.bosque_2020_ha)],
    [`Pasó de bosque a otra clase (2020 a ${ind.ultimo_anio ?? "—"})`, hectareas(ind.cambio_bosque_a_no_bosque_ha)],
    ["Píxeles de 30 m en la parcela", ind.pixeles != null ? String(ind.pixeles) : "—"],
  ].map(([etiqueta, valor]) => h("div", {}, h("dt", {}, etiqueta), h("dd", {}, valor)));
}

/** Historial de uso del suelo: hectáreas por clase, año por año. */
function historialMapbiomas(ind) {
  const anios = Object.keys(ind.anios ?? {}).sort();
  if (!anios.length) return null;
  const en2020 = ind.anios["2020"] ?? {};
  const clases = Object.keys(ind.clases ?? {}).sort((a, b) => (en2020[b] ?? 0) - (en2020[a] ?? 0));
  const bosque = new Set(ind.clases_bosque ?? []);
  return h(
    "details",
    { class: "capas-detalle" },
    h("summary", {}, "Uso del suelo por año (ha)"),
    h(
      "div",
      { class: "tbl-box tabla-desliza" },
      h(
        "table",
        { class: "tabla tabla-compacta" },
        h("thead", {}, h("tr", {}, h("th", {}, "Clase"), anios.map((a) => h("th", { class: a === "2020" ? "num col-2020" : "num" }, a)))),
        h(
          "tbody",
          {},
          clases.map((c) =>
            h(
              "tr",
              {},
              h("td", {}, ind.clases[c], bosque.has(c) && h("span", { class: "sec" }, "bosque")),
              anios.map((a) => h("td", { class: a === "2020" ? "num mono col-2020" : "num mono" }, ind.anios[a]?.[c] ? numero(ind.anios[a][c]) : "—")),
            ),
          ),
        ),
      ),
    ),
  );
}

function detalleFuente(codigo, ind) {
  if (codigo === "whisp") return [h("dl", { class: "kv" }, indicadoresWhisp(ind)), capasWhisp(ind.capas)];
  if (codigo === "gfw") return h("dl", { class: "kv" }, indicadoresGfw(ind));
  if (codigo === "mapbiomas") return [h("dl", { class: "kv" }, indicadoresMapbiomas(ind)), historialMapbiomas(ind)];
  return null;
}

const ESTADO_ANALISIS = {
  pendiente: ["info", "En proceso"],
  en_proceso: ["info", "En proceso"],
  completado: ["ok", "Completado"],
  error: ["bad", "Error"],
};

async function descargarRespuesta(analisis) {
  try {
    const { respuesta_url: url } = await llamarApi(`/analisis/${analisis.id}`);
    if (!url) throw new Error("La respuesta completa no está disponible.");
    // La URL firmada trae "download": el navegador guarda el archivo y la página no cambia.
    window.location.assign(url);
  } catch (error) {
    toast(error.message, "bad");
  }
}

/**
 * Lo que hizo que esta fuente pida revisión, y nada más: las cifras distintas de cero de su propia regla.
 * La regla vive en la API (requiere_revision); aquí solo se señalan las cifras.
 */
function motivosRevision(codigo, ind, bosque) {
  const motivos = [];
  if (codigo === "whisp") {
    // El riesgo ya lo dice la línea del resultado; aquí van las capas que vieron bosque o cambios.
    const capas = (ind.capas ?? []).filter((c) => ["estado_2020", "cambio_posterior"].includes(c.pregunta) && typeof c.valor === "number" && c.valor > 0 && !c.serie);
    for (const c of capas) {
      motivos.push(`${c.pregunta === "estado_2020" ? "Al 31/12/2020" : "Después de 2020"}: ${conUnidad(c.valor, c.unidad)} según ${c.conjunto_nombre ?? c.nombre}.`);
    }
  } else if (codigo === "gfw") {
    const cifra = (valor, texto) => (valor == null ? `${texto}: sin cifra.` : valor > 0 ? `${texto}: ${numero(valor)}.` : null);
    motivos.push(
      cifra(ind.alertas_desde_2021, "Alertas integradas desde 2021"),
      ind.perdida_ha_total == null ? "Pérdida de cobertura arbórea: sin cifra." : ind.perdida_ha_total > 0 ? `Pérdida de cobertura arbórea: ${hectareas(ind.perdida_ha_total)}.` : null,
      ...Object.entries(ind.perdida_ha_por_anio ?? {})
        .filter(([, ha]) => ha > 0)
        .map(([anio, ha]) => `Pérdida en ${anio}: ${hectareas(ha)}.`),
      bosque.hay && "alertas_dist_desde_2021" in ind ? cifra(ind.alertas_dist_desde_2021, "Alertas DIST desde 2021") : null,
    );
  } else if (codigo === "mapbiomas") {
    motivos.push(
      ind.cambio_bosque_a_no_bosque_ha == null
        ? "Cambio de bosque a otra clase: sin cifra."
        : `${hectareas(ind.cambio_bosque_a_no_bosque_ha)} pasaron de bosque a otra clase entre 2020 y ${ind.ultimo_anio ?? "su último año"}.`,
    );
  }
  return motivos.filter(Boolean);
}

/**
 * Decisión del equipo del 2026-10-05: las alertas DIST marcan cualquier cambio de la vegetación (poda,
 * cosecha, renovación del cultivo) sin decir la causa. Si ningún mapa vio bosque en la parcela el
 * 31/12/2020, no piden revisión; se muestran como dato, con esta explicación.
 */
function notaDistSinBosque(ind, bosque) {
  const n = ind.alertas_dist_desde_2021;
  if (bosque.hay || !(n > 0)) return null;
  const cuantos = bosque.filas.length
    ? `solo ${bosque.filas.length === 1 ? "1 mapa vio" : `${bosque.filas.length} mapas vieron`} bosque en la parcela el ${CORTE} (hacen falta ${bosque.minimo})`
    : `ningún mapa vio bosque en la parcela el ${CORTE}`;
  return `${n === 1 ? "1 alerta DIST" : `${numero(n)} alertas DIST`} desde 2021, pero ${cuantos}: no piden revisión. Estas alertas marcan cualquier cambio de la vegetación, como poda, cosecha o renovación del cultivo.`;
}

/**
 * Decisión del equipo del 2026-10-05: hubo bosque el 31/12/2020 si al menos 3 conjuntos lo registran. La
 * API lo dice en `hubo_bosque_2020`; un mapa solo se muestra como dato.
 */
function estadoBosque(tabla) {
  const filas = (tabla?.filas ?? []).filter((f) => f.registra_bosque_2020);
  const minimo = tabla?.mapas_minimos_bosque_2020 ?? 3;
  return { filas, minimo, hay: tabla?.hubo_bosque_2020 ?? filas.length >= minimo };
}

function notaBosqueSuelto(bosque, areaHa) {
  if (bosque.hay || !bosque.filas.length) return null;
  const cuales = bosque.filas.map((f) => {
    const mayor = numeros(f.al_2020 ?? [])
      .filter((m) => m.mide_bosque)
      .sort((a, b) => (b.unidad === a.unidad ? b.valor - a.valor : 0))[0];
    return mayor ? `${f.nombre} (${cifra(mayor, areaHa)})` : f.nombre;
  });
  const n = bosque.filas.length;
  return `${n === 1 ? "1 mapa vio" : `${n} mapas vieron`} bosque o árboles el ${CORTE}: ${cuales.join("; ")}. Se pide revisar imágenes cuando ${bosque.minimo} o más mapas lo ven, porque uno solo puede estar viendo árboles de sombra, frutales o cercos vivos.`;
}

/** Notas sobre cómo se obtuvo el resultado; van dentro del detalle. */
function notasFuente(codigo, ultimo, ind) {
  return [
    ultimo.es_aproximacion && h("p", { class: "panel-sub" }, "La parcela es un punto: esta fuente analizó un círculo con el área declarada."),
    ind.pocos_pixeles && h("p", { class: "alerta info" }, "La parcela tiene menos de 10 píxeles de 30 m: las cifras de esta fuente salen de pocos píxeles."),
    codigo === "mapbiomas" && h("p", { class: "panel-sub" }, `Esta fuente no ve lo ocurrido después de ${ind.ultimo_anio ?? "su último año"}.`),
  ];
}

function botonRespuesta(ultimo, ctx) {
  return !ctx.delProductor && ultimo.respuesta_documento_id && h("button", { class: "linkbtn", type: "button", onclick: () => descargarRespuesta(ultimo) }, "Descargar la respuesta completa");
}

/**
 * Una tarjeta por fuente: quién dice qué y cuándo, en pocas líneas. Si la fuente pide revisión, se ven
 * solo las cifras que la piden; los indicadores completos, el detalle por capa y la descarga quedan
 * plegados en "Ver indicadores y detalle".
 */
function tarjetaFuente(codigo, analisis, configurada, ctx, bosque) {
  const ultimo = analisis.find((a) => a.fuente === codigo);
  const nombre = FUENTES[codigo];
  if (!ultimo) {
    return h(
      "article",
      { class: "fuente" },
      h("div", { class: "fuente-h" }, h("b", {}, nombre), configurada === false ? insignia("", "Fuente no configurada") : insignia("", "Sin análisis")),
      h("p", { class: "panel-sub" }, configurada === false ? "Falta la clave de esta fuente en el servidor: no se crean análisis." : "Todavía no hay un análisis de esta fuente para la parcela."),
    );
  }
  const completado = ultimo.estado === "completado";
  const [clase, texto] = ESTADO_ANALISIS[ultimo.estado];
  const marcas = [
    completado ? (ultimo.requiere_revision ? insignia("warn", "Pide revisión") : insignia("ok", "No pide revisión")) : insignia(clase, texto),
    completado && ultimo.obsoleto && insignia("warn", "Obsoleto: la geometría cambió"),
    completado && !ultimo.obsoleto && !ultimo.vigente && insignia("warn", "Vencido"),
    ultimo.es_aproximacion && insignia("info", "Aproximación"),
  ];
  const ind = ultimo.indicadores ?? {};
  const motivos = completado && ultimo.requiere_revision && !ultimo.error_detalle ? motivosRevision(codigo, ind, bosque) : [];
  const notaDist = completado && codigo === "gfw" ? notaDistSinBosque(ind, bosque) : null;
  return h(
    "article",
    { class: `fuente${ultimo.requiere_revision || ultimo.estado === "error" ? " fuente-atencion" : ""}` },
    h("div", { class: "fuente-h" }, h("b", {}, nombre), h("span", { class: "fila-acciones" }, marcas)),
    h(
      "p",
      { class: "fuente-meta" },
      ultimo.completado_en ? `Analizado el ${fecha(ultimo.completado_en, { hora: true })}` : `Solicitado el ${fecha(ultimo.solicitado_en, { hora: true })}`,
      ultimo.version_fuente && ` · versión ${ultimo.version_fuente}`,
    ),
    completado && h("p", { class: "fuente-resultado" }, ultimo.resultado_texto ?? `${nombre}: sin resultado`),
    ultimo.estado === "error" && h("p", { class: "alerta bad" }, ultimo.error_detalle ?? "La fuente falló."),
    completado &&
      ultimo.error_detalle &&
      h("p", { class: "alerta warn" }, `${ultimo.error_detalle}. La respuesta completa quedó guardada; una persona debe revisar la parcela.`),
    motivos.length > 0 && h("ul", { class: "motivos-revision" }, motivos.map((m) => h("li", {}, m))),
    notaDist && h("p", { class: "nota-dist" }, notaDist),
    !completado && ultimo.estado !== "error" && h("p", { class: "panel-sub" }, `Consultando a ${nombre}… intento ${Math.max(ultimo.intentos, 1)}.`),
    completado &&
      h(
        "details",
        { class: "fuente-detalle" },
        h("summary", {}, "Ver indicadores y detalle"),
        notasFuente(codigo, ultimo, ind),
        detalleFuente(codigo, ind),
        botonRespuesta(ultimo, ctx),
      ),
    ultimo.estado === "error" && botonRespuesta(ultimo, ctx),
  );
}

function medidas(lista) {
  if (!lista) return null; // ese conjunto no mide esa pregunta: celda vacía
  // Las columnas por año de Whisp ya están en su agregado; se ven en el detalle por capa.
  const visibles = lista.filter((m) => !m.serie);
  return h(
    "ul",
    { class: "medidas" },
    (visibles.length ? visibles : lista).map((m) => h("li", {}, h("span", { class: "mono" }, conUnidad(m.valor, m.unidad)), h("span", { class: "sec" }, `${m.nombre} · ${m.via}`))),
  );
}

function fechasDe(fila) {
  const dias = fila.vias.map((v) => fecha(fila.fechas[v]));
  if (new Set(dias).size === 1) return dias[0];
  return fila.vias.map((v, i) => h("span", { class: "sec" }, `${v}: ${dias[i]}`));
}

// La fecha de corte del Reglamento (UE) 2023/1115: lo que importa es si había bosque ese día y si
// cambió desde el 1 de enero de 2021. Lo de 2020 o antes no cuenta como cambio.
const CORTE = "31/12/2020";
const ALERTAS_SATELITE = new Set(["gfw_integrated_alerts", "umd_glad_dist", "umd_glad_l", "umd_glad_s2", "wur_radd"]);
const AREA_QUEMADA = new Set(["esa_firecci", "modis_fire"]);
const VIA = { whisp: "Whisp", gfw: "GFW", mapbiomas: "MapBiomas" };

function tablaDeFilas(filas) {
  return h(
    "div",
    { class: "tbl-box tabla-desliza" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "Conjunto de datos"), h("th", {}, "Consultado vía"), h("th", {}, "Fecha"), h("th", {}, "Al 31 de diciembre de 2020"), h("th", {}, "Después de 2020"))),
      h(
        "tbody",
        {},
        filas.map((f) =>
          h(
            "tr",
            {},
            h("td", {}, f.nombre),
            h("td", {}, f.vias.join(" y ")),
            h("td", { class: "fecha" }, fechasDe(f)),
            h("td", {}, medidas(f.al_2020), f.registra_bosque_2020 && insignia("warn", `Bosque el ${CORTE}`)),
            h("td", {}, medidas(f.despues_2020), f.registra_cambio && insignia("warn", "Cambios desde 2021")),
          ),
        ),
      ),
    ),
  );
}

/**
 * Tabla de convergencia (adenda): una fila por conjunto de datos y una frase que solo cuenta. A la vista,
 * la frase y solo las filas que registran algo; la tabla completa queda plegada.
 */
function tablaConvergencia(tabla) {
  if (!tabla?.filas.length) return null;
  const marcadas = tabla.filas.filter((f) => f.registra_bosque_2020 || f.registra_cambio);
  return h(
    "div",
    { class: "convergencia" },
    h("h4", {}, "Conjuntos de datos y las dos preguntas del Reglamento"),
    h("p", { class: "frase-conteo" }, tabla.frase),
    h(
      "p",
      { class: "panel-sub" },
      `"Registran bosque en 2020" quiere decir que el mapa vio bosque en la parcela el ${CORTE}, la fecha de corte: es la foto de ese día, no una pérdida. Se pide revisar imágenes cuando ${tabla.mapas_minimos_bosque_2020 ?? 3} o más mapas lo ven. Los cambios cuentan solo desde el 1 de enero de 2021.`,
    ),
    marcadas.length > 0 && tablaDeFilas(marcadas),
    h(
      "details",
      { class: "capas-detalle" },
      h("summary", {}, `Ver los ${tabla.filas.length} conjuntos de datos`),
      h(
        "p",
        { class: "panel-sub" },
        `Un conjunto registra bosque en 2020 si su medida de bosque alcanza el ${tabla.umbral_bosque_2020_pct} % del área de la parcela, y registra cambios si alguna de sus medidas desde 2021 es mayor que cero.`,
      ),
      tablaDeFilas(tabla.filas),
    ),
  );
}

const numeros = (lista) => lista.filter((m) => !m.serie && typeof m.valor === "number");

/** Una cifra en palabras: hectáreas con su parte de la parcela, porcentaje o número de alertas. */
function cifra(m, areaHa) {
  if (m.unidad === "alertas") return m.valor === 1 ? "1 alerta" : `${numero(m.valor)} alertas`;
  if (m.unidad === "ha") {
    // La fuente mide sobre su propia lectura del polígono: si supera el área calculada, no se da la parte.
    const pct = areaHa ? Math.round((m.valor / areaHa) * 100) : null;
    const parte = pct != null && pct <= 100 ? ` (${pct} % de la parcela)` : "";
    return `${numero(m.valor)} ha${parte}`;
  }
  if (m.unidad === "%") return `${numero(m.valor)} % de la parcela`;
  return conUnidad(m.valor, m.unidad);
}

/** Lo que hay que revisar, conjunto por conjunto, en palabras. Cada punto dice qué vio, cuánto y cuándo. */
function hallazgos(ultimos, tabla, bosque) {
  const areaHa = tabla?.area_ha;
  const puntos = [];
  let cambios = false;
  const pide = (via) => ultimos.some((a) => VIA[a.fuente] === via && a.estado === "completado" && a.requiere_revision);
  const whisp = ultimos.find((a) => a.fuente === "whisp" && a.estado === "completado" && a.requiere_revision && !a.error_detalle);
  if (whisp) {
    const riesgo = (whisp.resultado_texto ?? "").replace(/^Whisp: /, "") || "sin valor";
    puntos.push([FUENTES.whisp, `Calificó el riesgo para cultivos permanentes, como el cacao, como "${riesgo}". Cuando no da "riesgo bajo", pide que alguien mire la parcela.`]);
  }
  for (const f of tabla?.filas ?? []) {
    if (f.registra_bosque_2020 && bosque.hay) {
      const medidas = numeros(f.al_2020 ?? []).filter((m) => m.mide_bosque);
      const mayor = medidas.sort((a, b) => (b.unidad === a.unidad ? b.valor - a.valor : 0))[0];
      puntos.push([f.nombre, `Vio bosque o árboles el ${CORTE}${mayor ? `: ${cifra(mayor, areaHa)}` : ""}.`]);
    }
    const cuenta = bosque.hay || (f.conjunto !== "umd_glad_dist" && f.vias.some(pide));
    if (f.registra_cambio && cuenta) {
      cambios = true;
      const medidas = numeros(f.despues_2020 ?? []).filter((m) => m.valor > 0);
      const que = ALERTAS_SATELITE.has(f.conjunto)
        ? "Son avisos del satélite de que la vegetación cambió; no dicen la causa."
        : AREA_QUEMADA.has(f.conjunto)
          ? "Marca área quemada."
          : "Marca pérdida o cambio de la cobertura.";
      puntos.push([f.nombre, `Registró ${medidas.map((m) => cifra(m, areaHa)).join(" y ") || "cambios"} desde el 1 de enero de 2021. ${que}`]);
    }
  }
  for (const a of ultimos) {
    if (a.estado === "error") puntos.push([FUENTES[a.fuente], 'La consulta falló. Prueba con "Repetir análisis".']);
    else if (a.estado === "completado" && a.error_detalle) puntos.push([FUENTES[a.fuente], "Su respuesta no trae las cifras esperadas; quedó guardada para revisarla."]);
  }
  return { puntos, cambios };
}

/** Arriba de las tarjetas: qué revisar, en palabras, o que nada pide revisión. */
function resumenCobertura(codigos, analisis, tabla, ctx) {
  const ultimos = codigos.map((c) => analisis.find((a) => a.fuente === c)).filter(Boolean);
  if (!ultimos.length) return null;
  const enCurso = ultimos.filter((a) => a.estado === "pendiente" || a.estado === "en_proceso");
  const bosque = estadoBosque(tabla);
  const { puntos, cambios: hayCambios } = hallazgos(ultimos, tabla, bosque);
  const gfw = ultimos.find((a) => a.fuente === "gfw" && a.estado === "completado");
  const notaDist = gfw ? notaDistSinBosque(gfw.indicadores ?? {}, bosque) : null;
  const notaBosque = notaBosqueSuelto(bosque, tabla?.area_ha);
  // Una fuente que pide revisión sin cifra en la tabla (por ejemplo, una cifra que no llegó).
  for (const a of ultimos) {
    if (a.estado === "completado" && a.requiere_revision && !puntos.some(([t]) => t === FUENTES[a.fuente]) && a.fuente !== "whisp" && !(tabla?.filas ?? []).some((f) => (f.registra_cambio || (f.registra_bosque_2020 && bosque.hay)) && f.vias.includes(VIA[a.fuente]))) {
      puntos.push([FUENTES[a.fuente], "Pide revisión: mira el detalle en su tarjeta."]);
    }
  }
  if (!puntos.length) {
    if (enCurso.length) {
      return h("div", { class: "verif neutro" }, icono("clock"), h("div", {}, h("b", {}, "Análisis en curso"), h("span", {}, `Consultando a ${enCurso.map((a) => FUENTES[a.fuente]).join(", ")}.`)));
    }
    return h(
      "div",
      { class: "verif" },
      icono("check"),
      h(
        "div",
        { class: "hallazgos" },
        h("b", {}, "Ninguna fuente ni conjunto de datos pide revisión"),
        notaBosque && h("p", {}, notaBosque),
        notaDist && h("p", {}, `GFW registró ${notaDist}`),
        h("p", {}, "El detalle de cada fuente queda plegado en su tarjeta."),
      ),
    );
  }
  return h(
    "div",
    { class: "verif warn" },
    icono("alert"),
    h(
      "div",
      { class: "hallazgos" },
      h("b", {}, "Qué revisar en esta parcela"),
      h("ol", {}, puntos.map(([titulo, texto]) => h("li", {}, h("b", {}, `${titulo}: `), texto))),
      bosque.hay &&
        h(
          "p",
          {},
          `Por qué importa el ${CORTE}: es la fecha de corte del Reglamento (UE) 2023/1115. Que hubiera bosque ese día no es una pérdida; es la foto de cómo estaba la parcela. Si ese día había bosque y hoy hay cacao, hay que confirmar en las imágenes que no se taló después. El cacao bajo sombra suele verse como bosque desde el satélite.`,
        ),
      hayCambios && h("p", {}, "Los cambios cuentan solo desde el 1 de enero de 2021, después de la fecha de corte; lo ocurrido en 2020 o antes no se cuenta aquí."),
      notaBosque && h("p", {}, `Además, ${notaBosque.charAt(0).toLowerCase()}${notaBosque.slice(1)}`),
      notaDist && h("p", {}, `Además, GFW registró ${notaDist}`),
      enCurso.length > 0 && h("p", {}, `Todavía se consulta a ${enCurso.map((a) => FUENTES[a.fuente]).join(", ")}.`),
      h(
        "p",
        { class: "hallazgos-accion" },
        ctx.delProductor
          ? "La cooperativa revisará imágenes satelitales de tu parcela."
          : "Qué hacer: el administrador revisa las imágenes de la parcela en la pestaña Imágenes y registra lo que observa. Con esa revisión decide en Habilitación.",
      ),
    ),
  );
}

export async function pestanaCobertura(ctx) {
  const { p, base } = ctx;
  const [analisis, fuentes, tabla] = await Promise.all([
    llamarApi(`${base}/analisis`),
    ctx.delProductor ? Promise.resolve(null) : llamarApi("/analisis/fuentes"),
    llamarApi(`${base}/convergencia`),
  ]);
  const configurada = Object.fromEntries((fuentes ?? []).map((f) => [f.fuente, f.configurada]));
  // El personal ve las fuentes del servidor; el productor, las que analizaron su parcela.
  const codigos = fuentes ? fuentes.map((f) => f.fuente) : [...new Set(["whisp", "gfw", ...analisis.map((a) => a.fuente)])];
  const puedo = permisos(ctx);
  const repetir =
    puedo.registro &&
    h(
      "button",
      {
        class: "btn btn-sm",
        type: "button",
        onclick: async (e) => {
          e.currentTarget.classList.add("is-loading");
          try {
            await llamarApi(`/parcelas/${p.id}/analisis`, { metodo: "POST" });
            toast("Análisis solicitado. Se actualiza solo cuando las fuentes respondan.");
            ctx.recargarPestana();
          } catch (error) {
            toast(error.message, "bad");
          }
        },
      },
      icono("rotate"),
      "Repetir análisis",
    );
  // Mientras haya consultas en curso, la pestaña se refresca sola.
  const enCurso = analisis.some((a) => a.estado === "pendiente" || a.estado === "en_proceso");
  if (enCurso) {
    setTimeout(() => ctx.contenedor.isConnected && ctx.pestanaActual() === "cobertura" && ctx.recargarPestana(), 5000);
  }
  // Parte 10: la cola atiende una consulta a la vez en toda la plataforma; se dice cuántas esperan.
  const cola = enCurso && !ctx.delProductor ? await llamarApi("/analisis/cola").catch(() => null) : null;
  return seccion({
    titulo: "Cobertura forestal",
    sub: "Lo que dice cada fuente sobre la parcela, con su fecha y su versión. CacaoTrace no emite veredictos ni combina fuentes.",
    acciones: repetir,
    contenido: [
      cola &&
        cola.en_cola > 0 &&
        h(
          "p",
          { class: "nota-cola" },
          icono("clock"),
          `${cola.en_cola === 1 ? "Hay 1 consulta" : `Hay ${cola.en_cola} consultas`} en la cola de la plataforma. Se atienden de a una: con muchas parcelas el mismo día, pueden tardar desde minutos hasta más de una hora.`,
        ),
      resumenCobertura(codigos, analisis, tabla, ctx),
      h("div", { class: "fuentes" }, codigos.map((c) => tarjetaFuente(c, analisis, configurada[c], ctx, estadoBosque(tabla)))),
      tablaConvergencia(tabla),
      analisis.length > 0 &&
        h(
          "details",
          { class: "historial-analisis" },
          h("summary", {}, `Historial de análisis (${analisis.length})`),
          h(
            "div",
            { class: "tbl-box" },
            h(
              "table",
              { class: "tabla" },
              h("thead", {}, h("tr", {}, h("th", {}, "Fuente"), h("th", {}, "Solicitado"), h("th", {}, "Estado"), h("th", {}, "Resultado"))),
              h(
                "tbody",
                {},
                analisis.map((a) =>
                  h(
                    "tr",
                    {},
                    h("td", {}, FUENTES[a.fuente], a.solicitado_por_nombre ? h("span", { class: "sec" }, a.solicitado_por_nombre) : h("span", { class: "sec" }, "Sistema")),
                    h("td", { class: "fecha" }, fecha(a.solicitado_en, { hora: true })),
                    h("td", {}, insignia(...ESTADO_ANALISIS[a.estado]), a.obsoleto && h("span", { class: "sec" }, "obsoleto")),
                    h("td", {}, a.resultado_texto ?? (a.error_detalle ? h("span", { class: "sec" }, a.error_detalle) : "—")),
                  ),
                ),
              ),
            ),
          ),
        ),
    ],
  });
}

// ---------- Expediente legal ----------

function abrirCargaLegal(casilla, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-legal" }, "Cargar documento");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true });
  const formulario = h(
    "form",
    { class: "form", id: "form-legal" },
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Número (partida, constancia o contrato)", name: "numero", required: true, maxlength: 200 }),
      campo({ etiqueta: "Entidad emisora", name: "entidad_emisora", required: true, maxlength: 200 }),
    ),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Fecha de emisión", name: "fecha_emision", type: "date", max: hoy(), required: true }),
      campo({ etiqueta: "Fecha de vencimiento (si tiene)", name: "fecha_vencimiento", type: "date" }),
    ),
    h("label", { class: "field" }, "Archivo (foto o PDF, hasta 10 MB)", archivo),
  );
  const { cerrar } = abrirModal({ titulo: `Cargar: ${casilla.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = new FormData();
    cuerpo.append("tipo", casilla.codigo);
    for (const clave of ["numero", "entidad_emisora", "fecha_emision", "fecha_vencimiento"]) if (datos[clave]) cuerpo.append(clave, datos[clave]);
    cuerpo.append("archivo", archivo.files[0]);
    await llamarApi(`${ctx.base}/documentos`, { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast("Documento cargado.");
    ctx.recargar();
  });
}

function abrirCotejo(documento, casilla, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-cotejo" }, "Registrar cotejo");
  const formulario = h(
    "form",
    { class: "form", id: "form-cotejo" },
    h("p", {}, `Cotejar es comprobar el documento en el registro público de quien lo emitió. Queda constancia de quién lo hizo y cuándo.`),
    h("label", { class: "field" }, "Qué consultaste y qué encontraste", h("textarea", { class: "input texto-libre", name: "nota", required: true, minlength: 10, maxlength: 4000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: `Cotejar: ${casilla.nombre}`, subtitulo: `N.º ${documento.numero ?? "—"} · ${documento.entidad_emisora ?? ""}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(`/documentos/${documento.id}/cotejo`, { metodo: "POST", cuerpo: { nota } });
    cerrar();
    toast("Cotejo registrado.");
    ctx.recargar();
  });
}

function abrirExencion(casilla, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-exencion" }, "Declarar que no aplica");
  const formulario = h(
    "form",
    { class: "form", id: "form-exencion" },
    h("p", {}, "La exención declara que este documento no aplica a la parcela. Aparecerá, con su motivo, en el informe de hallazgos."),
    h("label", { class: "field" }, "Por qué no aplica (mínimo 30 caracteres)", h("textarea", { class: "input texto-libre", name: "motivo", required: true, minlength: 30, maxlength: 4000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: `No aplica: ${casilla.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/parcelas/${ctx.p.id}/exenciones`, { metodo: "POST", cuerpo: { tipo: casilla.codigo, motivo } });
    cerrar();
    toast("Exención declarada.");
    ctx.recargar();
  });
}

function filaCasilla(c, ctx, puedo, tenenciaCubierta) {
  // La tenencia se cumple con el título o con la constancia: la otra no falta.
  const [clase, texto] = c.tenencia && c.estado === "faltante" && tenenciaCubierta ? ["", "No necesaria"] : ESTADOS_CASILLA[c.estado];
  const vigentes = c.documentos.filter((d) => d.vigente);
  const exencion = c.exencion && !c.exencion.retirada_en ? c.exencion : null;
  return h(
    "li",
    { class: "casilla" },
    h(
      "div",
      { class: "casilla-h" },
      h("div", {}, h("b", {}, c.nombre), h("span", { class: "sec" }, `${c.grupo}${c.registro_consultable ? " · con registro público" : " · sin registro público consultable"}`)),
      h("span", { class: "fila-acciones" }, insignia(clase, texto), c.nivel && insigniaNivel(c.nivel), c.vence_en && h("span", { class: "badge" }, `vence ${fecha(c.vence_en)}`)),
    ),
    vigentes.map((d) =>
      h(
        "div",
        { class: "casilla-doc" },
        h("span", {}, `N.º ${d.numero ?? "—"} · ${d.entidad_emisora ?? "—"} · emitido ${fecha(d.fecha_emision)}${d.fecha_vencimiento ? ` · vence ${fecha(d.fecha_vencimiento)}` : ""}`),
        d.cotejado_en && h("span", { class: "sec" }, `Cotejado el ${fecha(d.cotejado_en)}: ${d.cotejo_nota}`),
        h(
          "span",
          { class: "fila-acciones" },
          h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(d) }, icono("eye"), "Ver"),
          puedo.registro && c.registro_consultable && !d.cotejado_en && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirCotejo(d, c, ctx) }, "Cotejar en fuente"),
        ),
      ),
    ),
    exencion &&
      h(
        "div",
        { class: "casilla-doc" },
        h("span", {}, `No aplica: ${exencion.motivo}`),
        h("span", { class: "sec" }, `Declarada el ${fecha(exencion.declarada_en)}${exencion.declarada_por_nombre ? ` por ${exencion.declarada_por_nombre}` : ""}`),
        puedo.admin &&
          h(
            "button",
            {
              class: "btn btn-sm btn-ghost",
              type: "button",
              onclick: async () => {
                try {
                  await llamarApi(`/exenciones/${exencion.id}/retirar`, { metodo: "POST" });
                  toast("Exención retirada.");
                  ctx.recargar();
                } catch (error) {
                  toast(error.message, "bad");
                }
              },
            },
            "Retirar exención",
          ),
      ),
    h(
      "div",
      { class: "fila-acciones" },
      puedo.cargaDocumentos && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirCargaLegal(c, ctx) }, icono("upload"), vigentes.length ? "Cargar otro" : "Cargar documento"),
      puedo.admin && c.admite_exencion && !exencion && !vigentes.length && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirExencion(c, ctx) }, "Declarar que no aplica"),
    ),
  );
}

export async function pestanaExpediente(ctx) {
  const exp = await llamarApi(`${ctx.base}/expediente`);
  const puedo = permisos(ctx);
  const nombres = Object.fromEntries(exp.casillas.map((c) => [c.codigo, c.nombre]));
  return seccion({
    titulo: "Expediente legal",
    sub: "La tenencia exige el título o la constancia de posesión. Las otras cinco casillas se cubren con un documento o con una exención motivada.",
    acciones: insignia(exp.estado === "completo" ? "ok" : "warn", exp.estado === "completo" ? "Completo" : "Incompleto"),
    contenido: [
      exp.faltan.length > 0 && h("p", { class: "alerta warn" }, `Falta: ${exp.faltan.map((c) => (c === "tenencia" ? "tenencia (título o constancia de posesión)" : nombres[c])).join(", ")}.`),
      exp.tenencia_solo_posesion && h("p", { class: "alerta info" }, "La tenencia se apoya solo en una constancia de posesión, que no tiene registro público contra el cual cotejarse."),
      h("ul", { class: "casillas" }, exp.casillas.map((c) => filaCasilla(c, ctx, puedo, !exp.faltan.includes("tenencia")))),
    ],
  });
}

// ---------- Habilitación ----------

function abrirHabilitar(hab, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-habilitar" }, "Habilitar parcela");
  const formulario = h(
    "form",
    { class: "form", id: "form-habilitar" },
    h("p", {}, "Habilitar no declara que la parcela cumple el Reglamento: es la decisión de la cooperativa de aceptar cacao de ella, con las evidencias a la vista."),
    hab.alertas.length > 0 && h("div", { class: "fila-acciones" }, hab.alertas.map((a) => insigniaAlerta(a))),
    h(
      "label",
      { class: "field" },
      hab.nota_obligatoria ? "Nota (obligatoria, mínimo 50 caracteres): por qué se habilita a pesar de las alertas o del cambio visible en las imágenes" : "Nota (opcional)",
      h("textarea", { class: "input texto-libre", name: "nota", required: hab.nota_obligatoria, minlength: hab.nota_obligatoria ? 50 : 0, maxlength: 4000, rows: 4 }),
    ),
  );
  const { cerrar } = abrirModal({ titulo: "Habilitar parcela", subtitulo: `${ctx.p.codigo} · ${ctx.p.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(`/parcelas/${ctx.p.id}/habilitar`, { metodo: "POST", cuerpo: { nota: nota || null } });
    cerrar();
    toast("Parcela habilitada.");
    ctx.recargar();
  });
}

async function abrirExcluir(ctx) {
  const [revisiones, analisis] = await Promise.all([llamarApi(`${ctx.base}/revisiones-imagenes`), llamarApi(`${ctx.base}/analisis`)]);
  const etiquetaCambio = (valor) => OBSERVACIONES_CAMBIO.find(([v]) => v === valor)?.[1] ?? valor;
  const evidencias = [
    ["", "Elige la evidencia…"],
    ...revisiones.filter((r) => !r.anulada_en).map((r) => [`revision:${r.id}`, `Revisión de imágenes del ${fecha(r.revisada_en)} · ${etiquetaCambio(r.observacion_cambio)} · ${r.revisada_por_nombre ?? ""}`]),
    ...analisis.filter((a) => a.estado === "completado").map((a) => [`analisis:${a.id}`, `${FUENTES[a.fuente]} del ${fecha(a.completado_en)} · ${a.resultado_texto ?? "sin resultado"}`]),
  ];
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-excluir" }, "Excluir definitivamente");
  const formulario = h(
    "form",
    { class: "form", id: "form-excluir" },
    h("p", { class: "alerta bad" }, "La exclusión es definitiva: nadie puede revertirla, tampoco el equipo CacaoTrace. La parcela ya no se edita, no recibe documentos ni respalda tandas nuevas. Su historial sigue visible."),
    h("p", {}, "El único motivo admitido es la deforestación confirmada después del 31 de diciembre de 2020. A una parcela a la que le falta un documento no se la excluye."),
    h("label", { class: "field" }, "Qué se confirmó (mínimo 50 caracteres)", h("textarea", { class: "input texto-libre", name: "descripcion", required: true, minlength: 50, maxlength: 4000, rows: 4 })),
    campo({ etiqueta: "Evidencia de esta parcela", name: "evidencia", opciones: evidencias, required: true }),
    campo({ etiqueta: "Escribe EXCLUIR para confirmar", name: "confirmacion", required: true, autocomplete: "off", pattern: "EXCLUIR" }),
  );
  const { cerrar } = abrirModal({ titulo: "Excluir parcela", subtitulo: `${ctx.p.codigo} · ${ctx.p.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ descripcion, evidencia, confirmacion }) => {
    const [tipo, id] = evidencia.split(":");
    await llamarApi(`/parcelas/${ctx.p.id}/excluir`, {
      metodo: "POST",
      cuerpo: { descripcion, confirmacion, [tipo === "revision" ? "evidencia_revision_id" : "evidencia_analisis_id"]: id },
    });
    cerrar();
    toast("Parcela excluida.", "warn");
    ctx.recargar();
  });
}

const DECISION = { habilitar: "Habilitó la parcela", observar: "La pasó a observada (sistema)", excluir: "Excluyó la parcela" };

export async function pestanaHabilitacion(ctx) {
  const hab = await llamarApi(`${ctx.base}/habilitacion`);
  const puedo = permisos(ctx);
  const faltan = hab.requisitos.filter((r) => !r.cumple);
  const botonHabilitar =
    puedo.admin &&
    hab.estado !== "habilitada" &&
    h(
      "button",
      {
        class: "btn btn-primary btn-sm",
        type: "button",
        disabled: !hab.puede_habilitar,
        title: hab.puede_habilitar ? "Habilitar la parcela" : `Falta: ${faltan.map((r) => REQUISITOS[r.codigo]).join(", ")}`,
        onclick: () => abrirHabilitar(hab, ctx),
      },
      icono("check"),
      "Habilitar",
    );
  const botonExcluir = puedo.admin && h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirExcluir(ctx) }, "Excluir");
  const lista = ctx.delProductor
    ? faltan.length
      ? h("ul", { class: "lista-simple" }, faltan.map((r) => h("li", {}, REQUISITOS_PRODUCTOR[r.codigo] ?? r.detalle)))
      : h("p", { class: "alerta info" }, hab.estado === "habilitada" ? "Tu parcela está habilitada." : "Tu parcela tiene todo lo necesario; falta que la cooperativa decida.")
    : h(
        "ul",
        { class: "requisitos" },
        hab.requisitos.map((r) =>
          h("li", { class: r.cumple ? "cumple" : "falta" }, h("span", { class: "requisito-marca", "aria-hidden": "true" }, icono(r.cumple ? "check" : "x")), h("div", {}, h("b", {}, REQUISITOS[r.codigo] ?? r.codigo), h("span", { class: "sec" }, r.detalle))),
        ),
      );
  return seccion({
    titulo: "Habilitación",
    sub: ctx.delProductor ? "Lo que le falta a tu parcela para recibir tu cacao." : "Solo un administrador decide. Habilitar o excluir queda registrado con los requisitos y las alertas del momento.",
    acciones: [insigniaHabilitacion(hab.estado), botonHabilitar, botonExcluir],
    contenido: [
      lista,
      !ctx.delProductor && hab.alertas.length > 0 && h("div", { class: "fila-acciones" }, hab.alertas.map((a) => insigniaAlerta(a))),
      hab.decisiones.length > 0 &&
        h(
          "ol",
          { class: "linea-tiempo" },
          hab.decisiones.map((d) =>
            h(
              "li",
              {},
              h("b", {}, DECISION[d.decision] ?? d.decision),
              h("span", { class: "sec" }, [fecha(d.decidida_en, { hora: true }), d.decidida_por_nombre].filter(Boolean).join(" · ")),
              d.nota && h("span", { class: "sec" }, d.nota),
            ),
          ),
        ),
    ],
  });
}

const pedidos = new WeakMap();

/** Contenedor de una pestaña que se carga al abrirla. Solo pinta la respuesta del último pedido. */
export function cargarPestana(contenedor, generador) {
  const turno = (pedidos.get(contenedor) ?? 0) + 1;
  pedidos.set(contenedor, turno);
  const pintar = (nodo) => pedidos.get(contenedor) === turno && reemplazar(contenedor, nodo);
  reemplazar(contenedor, h("div", { class: "sect" }, cargando()));
  generador()
    .then(pintar)
    .catch((error) => pintar(h("div", { class: "sect" }, errorDeCarga(error))));
}

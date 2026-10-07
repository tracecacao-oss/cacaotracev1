// Piezas de la Parte 6 que comparten el tablero, la nueva corrida, el detalle, el stock y el DPP: textos,
// símbolos del diagrama de análisis de proceso y el formulario corto de cada etapa.

import { llamarApi } from "./api.js";
import { estado } from "./estado.js";
import { momentoLima } from "./tandas.js";
import { abrirModal, campo, enviarCon, h, toast } from "./ui.js";

export const RUTAS = [
  ["completa", "Completa", "Cacao en baba: pasa por fermentación y secado."],
  ["seco", "Seco", "Grano entregado seco: va directo a selección y almacén."],
];
export const MANEJOS = [
  ["mezclado", "Mezclada", "Tandas de varios productores."],
  ["segregado", "Segregada", "Tandas de un solo productor."],
];
export const FASES = [
  ["ingreso", "Ingreso"],
  ["fermentacion", "Fermentación"],
  ["secado", "Secado"],
  ["seleccion", "Selección"],
  ["envasado", "Envasado y almacén"],
];
export const ESTADOS_CORRIDA = {
  abierta: ["info", "Abierta, sin iniciar"],
  en_proceso: ["warn", "En proceso"],
  consolidada: ["ok", "Consolidada"],
  anulada: ["bad", "Anulada"],
};
export const SITUACIONES = {
  pendiente: ["", "Pendiente"],
  registrada: ["ok", "Registrada"],
  no_aplica: ["", "No aplica"],
  no_ocurrio: ["info", "No ocurrió"],
};
export const ALERTAS_CORRIDA = {
  tanda_de_parcela_observada: "Entró una tanda de una parcela que pasó a observada después de su DOP",
  rendimiento_sobre_banda: "Salió más grano del que explica la baba registrada: pudo entrar cacao sin registro",
  rendimiento_bajo_banda: "Merma inusual, o salió grano que no se registró",
  peso_final_supera_entrada: "El peso final supera en más de 1 % el peso seco que entró",
};
export const ESTADOS_TANDA_FINAL = {
  en_stock: ["ok", "En stock"],
  agotada: ["", "Agotada"],
  anulada: ["bad", "Anulada"],
};

export function insignia([clase, texto]) {
  return h("span", { class: `badge ${clase}`.trim() }, h("span", { class: "dot" }), texto);
}

export const etiqueta = (lista, valor) => lista.find(([v]) => v === valor)?.[1] ?? valor;

/** Etiqueta visible de segregada o mezclada (regla 5 de la interfaz). */
export function insigniaManejo(tipo) {
  return h("span", { class: `badge ${tipo === "segregado" ? "info" : ""}`.trim() }, h("span", { class: "dot" }), etiqueta(MANEJOS, tipo));
}

/** Símbolo del diagrama de análisis de proceso: operación, inspección, transporte, espera o almacenamiento. */
export function simbolo(tipo, activo = true) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 20 20");
  svg.setAttribute("class", `simbolo-etapa ${activo ? "" : "inactivo"}`.trim());
  svg.setAttribute("aria-hidden", "true");
  const figura = {
    operacion: ["circle", { cx: 10, cy: 10, r: 7 }],
    inspeccion: ["rect", { x: 3, y: 3, width: 14, height: 14 }],
    transporte: ["path", { d: "M2 7.5h9V4l7 6-7 6v-3.5H2z" }],
    espera: ["path", { d: "M3 3h7a7 7 0 0 1 0 14H3z" }],
    almacenamiento: ["path", { d: "M2 3h16L10 17z" }],
  }[tipo];
  const nodo = document.createElementNS(ns, figura[0]);
  for (const [clave, valor] of Object.entries(figura[1])) nodo.setAttribute(clave, valor);
  svg.append(nodo);
  return svg;
}

export function horas(valor) {
  if (valor == null) return "";
  const n = Number(valor);
  if (n < 1) return `${Math.round(n * 60)} min`;
  return `${n.toLocaleString("es-PE", { maximumFractionDigits: 1 })} h`;
}

/** El dato propio de una etapa, en palabras. */
export function datoPropio(etapa) {
  const d = etapa.datos ?? {};
  switch (etapa.numero) {
    case 1:
      return d.tandas ? `${d.tandas.length} ${d.tandas.length === 1 ? "tanda" : "tandas"} · ${Number(d.peso_total_kg).toLocaleString("es-PE")} kg` : "";
    case 3:
      return d.dops ? `${d.codigo_corrida} · DOP ${d.dops.join(", ")}` : "";
    case 4:
      return d.tandas ? d.tandas.map((t) => `${t.codigo}: DOP ${t.dop_estado}, parcela ${t.habilitacion_estado}`).join(" · ") : "";
    case 5:
      return etiqueta(MANEJOS, d.tipo_manejo);
    case 9:
      return d.fechas_volteo?.length ? `${d.fechas_volteo.length} ${d.fechas_volteo.length === 1 ? "volteo" : "volteos"}` : "";
    case 10:
      return d.pct_bien_fermentados != null ? `${d.pct_bien_fermentados} % bien fermentados` : "";
    case 13:
      return d.humedad_pct != null ? `Humedad ${d.humedad_pct} %` : "";
    case 17:
      return d.calidad ?? "";
    case 18:
      return d.kg_descartados != null ? `${d.kg_descartados} kg descartados` : "";
    case 19:
      return d.peso_final_kg != null ? `Peso final ${d.peso_final_kg} kg` : "";
    case 21:
      return d.numero_sacos != null ? `${d.numero_sacos} sacos` : "";
    case 2:
      return d.observacion_calidad ?? "";
    default:
      return "";
  }
}

const conDesfase = (local) => (local ? `${local}:00-05:00` : null);

const OTRO = "__otro";

/**
 * Método de una etapa (decisión del 2026-10-06): se elige de los métodos sugeridos del catálogo o se escribe
 * en "Otro". El valor final va en un campo oculto con `name`, que es lo que lee el formulario. Sin métodos
 * sugeridos, es un campo de texto.
 */
export function campoMetodo({ metodos = [], valor, name, requerido = false, vacio = "Elige el método…", etiqueta = "Método" }) {
  if (!metodos.length) {
    return h("input", { class: "input", name, value: valor ?? "", maxlength: 200, required: requerido, "aria-label": etiqueta });
  }
  const enLista = Boolean(valor) && metodos.includes(valor);
  const oculto = h("input", { type: "hidden", name, value: valor ?? "" });
  const lista = h(
    "select",
    { class: "select", required: requerido, "aria-label": etiqueta },
    h("option", { value: "" }, vacio),
    metodos.map((m) => h("option", { value: m }, m)),
    h("option", { value: OTRO }, "Otro (escribir)"),
  );
  lista.value = !valor ? "" : enLista ? valor : OTRO;
  const otro = h("input", { class: "input", maxlength: 200, value: enLista ? "" : (valor ?? ""), placeholder: "Escribe el método", "aria-label": `${etiqueta}: otro` });
  const sincronizar = () => {
    const esOtro = lista.value === OTRO;
    otro.hidden = !esOtro;
    otro.required = requerido && esOtro;
    oculto.value = esOtro ? otro.value.trim() : lista.value;
  };
  lista.addEventListener("change", () => {
    sincronizar();
    if (lista.value === OTRO) otro.focus();
  });
  otro.addEventListener("input", sincronizar);
  sincronizar();
  return h("div", { class: "campo-metodo" }, lista, otro, oculto);
}

/** Suma horas a un "AAAA-MM-DDTHH:MM" de Lima. */
function masHoras(local, n) {
  const fecha = new Date(`${local}:00-05:00`);
  return momentoLima(new Date(fecha.getTime() + n * 3600_000));
}

/**
 * Formulario corto de una etapa, ya lleno con lo registrado o con la plantilla, que el operador confirma o
 * corrige (regla 2 de la interfaz). catalogo: la etapa del catálogo, con sus datos propios.
 */
export function abrirEtapa({ corrida, etapa, catalogo, lugares, calidades, alGuardar }) {
  const activos = lugares.filter((l) => l.activo || l.id === etapa.lugar_id);
  const anterior = corrida.etapas.filter((e) => e.numero < etapa.numero && e.fin).at(-1);
  const inicio = etapa.inicio ? momentoLima(etapa.inicio) : anterior ? momentoLima(anterior.fin) : momentoLima();
  const duracion = Number(etapa.plantilla?.duracion_horas ?? 1);
  const fin = etapa.fin ? momentoLima(etapa.fin) : masHoras(inicio, duracion) > momentoLima() ? momentoLima() : masHoras(inicio, duracion);
  const usuario = estado.usuario ? `${estado.usuario.nombres} ${estado.usuario.apellidos}`.trim() : "";
  const propios = catalogo.datos.map((d) => {
    const valor = etapa.datos?.[d.clave];
    if (d.tipo === "calidad") {
      return campo({ etiqueta: d.etiqueta, name: `dato_${d.clave}`, opciones: [["", "Elige la calidad…"], ...calidades.filter((c) => c.activo).map((c) => [c.id, c.nombre])], value: valor ?? "" });
    }
    if (d.tipo === "fechas") {
      return h(
        "label",
        { class: "field" },
        `${d.etiqueta} (una por línea, AAAA-MM-DD HH:MM)`,
        h("textarea", { class: "input mono", name: `dato_${d.clave}`, rows: 3, placeholder: "2026-10-06 08:00" }, (valor ?? []).map((f) => momentoLima(f).replace("T", " ")).join("\n")),
      );
    }
    if (d.tipo === "texto") {
      return h("label", { class: "field" }, d.etiqueta, h("textarea", { class: "input texto-libre", name: `dato_${d.clave}`, maxlength: 4000, rows: 2 }, valor ?? ""));
    }
    return campo({
      etiqueta: `${d.etiqueta}${d.unidad ? ` (${d.unidad})` : ""}`,
      name: `dato_${d.clave}`,
      type: "number",
      step: d.tipo === "entero" ? "1" : "0.01",
      min: d.minimo ?? "",
      max: d.maximo ?? "",
      inputmode: "decimal",
      value: valor ?? "",
      class: "input mono",
    });
  });
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-etapa" }, etapa.situacion === "pendiente" ? "Confirmar etapa" : "Guardar corrección");
  const formulario = h(
    "form",
    { class: "form", id: "form-etapa" },
    etapa.plantilla && h("p", { class: "panel-sub" }, "Los valores vienen de la plantilla de la cooperativa: confirma o corrige lo que cambió."),
    campo({ etiqueta: "Lugar", name: "lugar_id", required: true, opciones: [["", "Elige el lugar…"], ...activos.map((l) => [l.id, l.nombre])], value: etapa.lugar_id ?? "" }),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Inicio", name: "inicio", type: "datetime-local", required: true, value: inicio, max: momentoLima() }),
      campo({ etiqueta: "Fin", name: "fin", type: "datetime-local", required: true, value: fin, max: momentoLima() }),
    ),
    h("div", { class: "field" }, h("span", {}, "Método"), campoMetodo({ metodos: catalogo.metodos, valor: etapa.metodo, name: "metodo", requerido: true }), h("small", {}, "Elige cómo se hizo o escríbelo en \"Otro\".")),
    campo({ etiqueta: "Responsable", name: "responsable", required: true, maxlength: 200, value: etapa.responsable ?? usuario }),
    etapa.transporte && campo({ etiqueta: "Distancia (m, opcional)", name: "distancia_m", type: "number", step: "0.1", min: "0", inputmode: "decimal", value: etapa.distancia_m ?? "", class: "input mono" }),
    propios,
    h("label", { class: "field" }, "Observación (opcional)", h("textarea", { class: "input texto-libre", name: "observacion", maxlength: 4000, rows: 2 }, etapa.observacion ?? "")),
  );
  const pie = [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar")];
  if (catalogo.opcional) {
    pie.push(
      h(
        "button",
        {
          class: "btn",
          type: "button",
          onclick: async () => {
            try {
              alGuardar(await llamarApi(`/corridas/${corrida.id}/etapas/${etapa.numero}`, { metodo: "PATCH", cuerpo: { situacion: "no_ocurrio" } }));
              cerrar();
              toast("Etapa marcada como que no ocurrió.");
            } catch (error) {
              toast(error.message, "bad");
            }
          },
        },
        "No ocurrió",
      ),
    );
  }
  pie.push(boton);
  const { cerrar } = abrirModal({ titulo: `Etapa ${etapa.numero}: ${etapa.nombre}`, subtitulo: corrida.codigo, contenido: formulario, pie });
  enviarCon(formulario, boton, async (datos) => {
    if (datos.fin < datos.inicio) throw new Error("El fin no puede ser anterior al inicio.");
    const propiosCuerpo = {};
    for (const d of catalogo.datos) {
      const valor = (datos[`dato_${d.clave}`] ?? "").trim();
      if (!valor) continue;
      propiosCuerpo[d.clave] = d.tipo === "fechas" ? valor.split(/\n+/).map((l) => conDesfase(l.trim().replace(" ", "T"))).filter(Boolean) : valor;
    }
    const cuerpo = {
      lugar_id: datos.lugar_id,
      inicio: conDesfase(datos.inicio),
      fin: conDesfase(datos.fin),
      metodo: datos.metodo,
      responsable: datos.responsable,
      distancia_m: datos.distancia_m || null,
      observacion: datos.observacion?.trim() || null,
      datos: propiosCuerpo,
    };
    const actualizada = await llamarApi(`/corridas/${corrida.id}/etapas/${etapa.numero}`, { metodo: "PATCH", cuerpo });
    cerrar();
    toast(`Etapa ${etapa.numero} registrada.`);
    alGuardar(actualizada);
  });
}

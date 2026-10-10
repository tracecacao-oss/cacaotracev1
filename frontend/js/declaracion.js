// Adenda 5: la declaración anual del productor. Lo comparten la pestaña Declaración de la ficha (personal) y
// #/mi-declaracion (productor). Las cinco condiciones que abren una pregunta son las mismas de la API
// (backend/app/catalogos/declaracion_productor.py, CONDICIONES); la API vuelve a validar lo enviado. Ningún
// texto dice que un productor "cumple": dice qué declaró y qué falta.

import { llamarApi } from "./api.js";
import { anularDocumento, formularioCarga, verDocumento } from "./documentos.js";
import { campo, claseTono, fecha, h, icono, ordenarPorTono } from "./ui.js";

let cuestionarioCargado = null;

/** El catálogo vigente y los valores de referencia. Se pide una vez por sesión de la página. */
export async function cuestionario() {
  cuestionarioCargado ??= llamarApi("/declaraciones-productor/cuestionario", { sinConsulta: true }).catch((error) => {
    cuestionarioCargado = null;
    throw error;
  });
  return cuestionarioCargado;
}

export const ESTADO_DECLARACION = {
  sin_declaracion: ["warn", "Sin declaración"],
  por_firmar: ["warn", "Por firmar"],
  vigente: ["ok", "Vigente"],
  por_vencer: ["warn", "Por vencer"],
  vencida: ["bad", "Vencida"],
  reemplazada: ["", "Reemplazada"],
};

export const ESTADO_REQUISITO_PRODUCTOR = {
  sin_dato: ["", "Falta la declaración"],
  no_aplica: ["info", "No aplica"],
  declarado: ["info", "Declarado"],
  por_atender: ["warn", "Por atender"],
  sin_sustento: ["bad", "Sin sustento"],
  sustentado: ["ok", "Sustentado"],
};

export const NIVEL_ORIENTADOR = { alto: "alto", bajo: "bajo" };
export const DILIGENCIA = { aligerada: "aligerada", estandar: "estándar" };
export const PAPELES = {
  relacion_trabajadores: "Relación de trabajadores permanentes, con sus contratos o su planilla",
  declaracion_renta: "Declaración anual del impuesto a la renta, o la constancia de haberla presentado",
  hoja_declaracion_productor: "Hoja firmada de la declaración anual",
};

export function insignia([clase, texto]) {
  return h("span", { class: `badge ${clase}` }, h("span", { class: "dot" }), texto);
}

// ---------- Qué preguntas se muestran ----------

const contrata = (r) => r.quien_trabaja != null && r.quien_trabaja !== "solo_familia";
const CONDICIONES = {
  contrata: (r) => contrata(r),
  permanentes: (r) => r.quien_trabaja === "permanentes",
  cinco_ha: (r, c) => Number(c.area_total_ha ?? 0) >= c.umbral,
  menores: (r) => r.menores_trabajan != null && r.menores_trabajan !== "no",
  usa_agroquimicos: (r) => r.usa_agroquimicos === "si",
};

/** El contexto con que se deciden las preguntas: el área calculada y el umbral de agricultura familiar. */
export function contextoDe(cuest, calculados) {
  return { ...calculados, umbral: cuest.area_agricultura_familiar_ha };
}

/** Las preguntas que corresponden, en orden. Una respuesta de una pregunta oculta no abre otras. */
export function mostradas(cuest, respuestas, contexto) {
  const vistas = {};
  const lista = [];
  for (const p of cuest.preguntas) {
    if (!p.cuando.every((c) => CONDICIONES[c](vistas, contexto))) continue;
    lista.push(p);
    const valor = respuestas[p.codigo];
    if (valor != null && valor !== "") vistas[p.codigo] = valor;
  }
  return lista;
}

/** Solo las respuestas de las preguntas mostradas: la API rechaza las que sobran. */
export function soloMostradas(cuest, respuestas, contexto) {
  return Object.fromEntries(mostradas(cuest, respuestas, contexto).map((p) => [p.codigo, respuestas[p.codigo]]));
}

// ---------- Textos ----------

const soles = (valor) => `S/ ${Number(valor).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const kilos = (valor) => `${Number(valor).toLocaleString("es-PE", { maximumFractionDigits: 2 })} kg`;

/** La pregunta como la ve cada uno: de tú para el productor, en tercera persona para el personal. */
export function textoPregunta(p, { personal }) {
  return personal ? p.texto_personal : p.texto;
}

/** La ayuda de una línea. La de las 75 UIT suma el monto, si la UIT está registrada, y los kilos entregados. */
export function ayudaPregunta(p, cuest, calculados, { personal }) {
  const base = personal ? p.ayuda_personal : p.ayuda;
  if (p.codigo !== "ventas_superan_75_uit") return base;
  const partes = [base];
  if (cuest.uit_soles) partes.push(`75 UIT son ${soles(cuest.uit_soles * 75)} (UIT de ${cuest.uit_anio}: ${soles(cuest.uit_soles)}).`);
  if (calculados?.kilos_12_meses != null) {
    const n = kilos(calculados.kilos_12_meses);
    partes.push(personal ? `En los últimos 12 meses entregó ${n} de cacao (peso seco equivalente) a la organización.` : `En los últimos 12 meses entregaste ${n} de cacao (peso seco equivalente).`);
  }
  return partes.join(" ");
}

/** Lo respondido, como texto. */
export function etiquetaRespuesta(p, valor, cuest) {
  if (valor == null || valor === "") return "—";
  if (p.tipo === "opcion") return p.valores.find((v) => v.valor === valor)?.etiqueta ?? String(valor);
  if (p.tipo === "productos") {
    const tipos = Object.fromEntries(cuest.tipos_producto.map((t) => [t.valor, t.etiqueta.toLowerCase()]));
    return valor.map((x) => `${x.nombre} (${tipos[x.tipo] ?? x.tipo})`).join("; ");
  }
  if (p.codigo === "jornal_soles") return soles(valor);
  return String(valor);
}

/** Un texto con partes en negrita (**así**), sin HTML. */
export function conNegritas(texto) {
  return texto.split(/\*\*(.+?)\*\*/).map((parte, i) => (i % 2 ? h("b", {}, parte) : parte));
}

// ---------- Controles ----------

/** Editor de la lista de productos: nombre comercial (con los ya declarados como sugerencia) y tipo. */
export function editorProductos(cuest, valor, sugerencias = []) {
  const lista = h("div", { class: "productos-lista" });
  const idSugerencias = `sugerencias-productos-${Math.random().toString(36).slice(2, 8)}`;
  const datalist = h("datalist", { id: idSugerencias }, sugerencias.map((s) => h("option", { value: s })));
  const agregar = h("button", { class: "btn btn-sm", type: "button" }, "Agregar otro producto");
  const actualizar = () => {
    agregar.hidden = lista.children.length >= cuest.maximo_productos;
    for (const fila of lista.children) fila.querySelector("[data-quitar]").hidden = lista.children.length === 1;
  };
  const fila = (p = {}) => {
    const nodo = h(
      "div",
      { class: "producto-fila" },
      h("input", { class: "input", type: "text", "data-campo": "nombre", placeholder: "Nombre comercial", "aria-label": "Nombre comercial del producto", minlength: 2, maxlength: 80, required: true, value: p.nombre ?? "", list: idSugerencias }),
      h("select", { class: "select", "data-campo": "tipo", "aria-label": "Tipo de producto", required: true }, h("option", { value: "" }, "Tipo…"), cuest.tipos_producto.map((t) => h("option", { value: t.valor }, t.etiqueta))),
      h("button", { class: "btn btn-sm btn-ghost", type: "button", "data-quitar": "", "aria-label": "Quitar este producto", onclick: () => (nodo.remove(), actualizar()) }, "Quitar"),
    );
    nodo.querySelector("select").value = p.tipo ?? "";
    return nodo;
  };
  for (const p of valor?.length ? valor : [{}]) lista.append(fila(p));
  agregar.addEventListener("click", () => {
    lista.append(fila());
    actualizar();
    lista.lastElementChild.querySelector("input").focus();
  });
  actualizar();
  const editor = h("div", { class: "editor-productos" }, datalist, lista, agregar);
  editor.leer = () =>
    [...lista.children].map((f) => ({ nombre: f.querySelector("[data-campo=nombre]").value.trim(), tipo: f.querySelector("[data-campo=tipo]").value }));
  return editor;
}

/** El control de una pregunta. `grande`: opciones como botones anchos, para responder desde el celular. */
export function controlPregunta(p, valor, { cuest, sugerencias, grande = false, nombre = p.codigo }) {
  if (p.tipo === "opcion") {
    if (!grande) return campo({ etiqueta: null, name: nombre, "aria-label": p.texto_personal, value: valor ?? "", opciones: [["", "Elige…"], ...p.valores.map((v) => [v.valor, v.etiqueta])] });
    return h(
      "div",
      { class: "opciones-grandes", role: "radiogroup" },
      p.valores.map((v) =>
        h("label", { class: "opcion-grande" }, h("input", { type: "radio", name: nombre, value: v.valor, checked: valor === v.valor, required: true }), h("span", {}, v.etiqueta)),
      ),
    );
  }
  if (p.tipo === "productos") return editorProductos(cuest, valor, sugerencias);
  const entero = p.tipo === "entero";
  return h("input", {
    class: `input mono${grande ? " input-grande" : ""}`,
    type: "number",
    name: nombre,
    "aria-label": p.texto_personal,
    inputmode: entero ? "numeric" : "decimal",
    min: p.minimo,
    max: p.maximo,
    step: entero ? 1 : 0.01,
    required: true,
    value: valor ?? "",
  });
}

/** Lee el valor de un control armado con controlPregunta. */
export function leerControl(p, control) {
  if (p.tipo === "productos") return control.leer();
  if (p.tipo === "opcion") {
    const elegido = control.querySelector("input:checked") ?? control.querySelector("select");
    return elegido?.value || null;
  }
  const texto = (control.matches?.("input") ? control : control.querySelector("input")).value;
  return texto === "" ? null : Number(texto);
}

// ---------- Papeles que piden las respuestas (sección 3.3) ----------

/** [[tipo, nombre]] de los papeles que piden las respuestas de una declaración. */
export function papelesPedidos(declaracion) {
  const r = Object.fromEntries(declaracion.respuestas.map((x) => [x.codigo, x.valor]));
  return [
    r.quien_trabaja === "permanentes" && ["relacion_trabajadores", PAPELES.relacion_trabajadores],
    r.ventas_superan_75_uit && r.ventas_superan_75_uit !== "no" && ["declaracion_renta", PAPELES.declaracion_renta],
  ].filter(Boolean);
}

/** Una casilla por papel pedido: amarilla mientras falta (no impide habilitar) y verde cuando está cargado. */
export function casillasPapeles(declaracion, { ruta, puedeCargar, puedeAnular = false, alCambiar, textoBoton = "Cargar documento" }) {
  const pedidos = papelesPedidos(declaracion);
  if (!pedidos.length) return null;
  const vigentes = (tipo) => declaracion.documentos.filter((d) => d.tipo === tipo && d.vigente);
  const tono = ([tipo]) => (vigentes(tipo).length ? "listo" : "falta");
  return h(
    "ul",
    { class: "casillas" },
    ordenarPorTono(pedidos, tono).map(([tipo, nombre]) =>
      h(
        "li",
        { class: claseTono(tono([tipo])) },
        h("div", { class: "casilla-h" }, h("b", {}, nombre), insignia(vigentes(tipo).length ? ["ok", "Cargado"] : ["warn", "Falta"])),
        vigentes(tipo).map((d) =>
          h(
            "div",
            { class: "casilla-doc" },
            h("span", {}, `${d.nombre_original} · cargado el ${fecha(d.creado_en)}`),
            h(
              "span",
              { class: "fila-acciones" },
              h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(d) }, icono("eye"), "Ver"),
              puedeAnular && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => anularDocumento(d, alCambiar) }, "Anular"),
            ),
          ),
        ),
        puedeCargar && formularioCarga({ tipos: [[tipo, nombre]], ruta, alCargar: alCambiar, textoBoton }),
      ),
    ),
  );
}

// ---------- Bloques de lectura ----------

/** Las respuestas guardadas de una declaración, como filas pregunta – respuesta. */
export function filasRespuestas(declaracion) {
  return declaracion.respuestas.map((r) => ({ etiqueta: r.pregunta, valor: r.etiqueta }));
}

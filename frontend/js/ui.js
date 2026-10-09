// Piezas de interfaz reutilizables. Ningún texto se inserta como HTML: todo va por textContent.

import { completarAlEscribir, fechaLima, leerFecha, leerFechaHora, mostrarFecha, mostrarFechaHora, problemaFecha } from "./fechas.js";
import { ICONOS } from "./iconos.js";

/** Crea un elemento: h("button", { class: "btn", onclick }, "Texto", otroNodo). */
export function h(etiqueta, atributos = {}, ...hijos) {
  const elemento = document.createElement(etiqueta);
  for (const [nombre, valor] of Object.entries(atributos ?? {})) {
    if (valor === false || valor == null) continue;
    if (nombre.startsWith("on") && typeof valor === "function") {
      elemento.addEventListener(nombre.slice(2), valor);
    } else if (nombre === "value") {
      elemento.value = valor;
    } else if (nombre === "checked") {
      elemento.checked = Boolean(valor);
    } else {
      elemento.setAttribute(nombre, valor === true ? "" : valor);
    }
  }
  agregar(elemento, hijos);
  return elemento;
}

/** Reemplaza el contenido de un nodo; acepta nodos, textos y listas anidadas. */
export function reemplazar(elemento, ...contenido) {
  elemento.replaceChildren();
  agregar(elemento, contenido);
}

function agregar(elemento, hijos) {
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo == null || hijo === false) continue;
    elemento.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
}

// Íconos: los del diseño de referencia (iconos.js) y, donde el diseño no tiene uno, estos trazos.
const PROPIOS = {
  cooperativa: ["M3 21h18", "M5 21V8l7-5 7 5v13", "M9 21v-6h6v6"],
  plataforma: ["M4 4h16v6H4z", "M4 14h16v6H4z", "M8 7h.01", "M8 17h.01"],
  perfil: ["M20 21v-1a6 6 0 0 0-6-6h-4a6 6 0 0 0-6 6v1", "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8"],
  parcelas: ["M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z", "M9 3v15", "M15 6v15"],
  salir: ["M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4", "M16 17l5-5-5-5", "M21 12H9"],
};
// Nombres propios de la app -> ícono del diseño.
const ALIAS = {
  inicio: "home",
  productores: "users",
  lotes: "sack",
  trazabilidad: "branch",
  exportacion: "ship",
  entregas: "sack",
  cerrar: "x",
  copiar: "copy",
  mas: "plus",
  buscar: "search",
  ojo: "eye",
};

export function icono(nombre, clase = "") {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", `ic ${clase}`.trim());
  svg.setAttribute("aria-hidden", "true");
  const elementos = ICONOS[ALIAS[nombre] ?? nombre] ?? (PROPIOS[nombre] ?? []).map((d) => ["path", { d }]);
  for (const [etiqueta, atributos] of elementos) {
    const elemento = document.createElementNS(ns, etiqueta);
    for (const [clave, valor] of Object.entries(atributos)) elemento.setAttribute(clave, valor);
    svg.append(elemento);
  }
  return svg;
}

export function marca() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", "32");
  svg.setAttribute("height", "32");
  svg.setAttribute("viewBox", "0 0 32 32");
  svg.setAttribute("aria-hidden", "true");
  const fondo = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  Object.entries({ width: 32, height: 32, rx: 9, fill: "#059669" }).forEach(([k, v]) => fondo.setAttribute(k, v));
  const grano = document.createElementNS("http://www.w3.org/2000/svg", "path");
  grano.setAttribute("d", "M16 5.5c4.6 2.6 6.8 6.4 6.8 10.5S20.6 23.9 16 26.5c-4.6-2.6-6.8-6.4-6.8-10.5S11.4 8.1 16 5.5z");
  Object.entries({ fill: "none", stroke: "#fff", "stroke-width": 1.8 }).forEach(([k, v]) => grano.setAttribute(k, v));
  svg.append(fondo, grano);
  return h("span", { class: "brand" }, svg, h("span", { class: "brand-name" }, "Cacao", h("b", {}, "Trace")));
}

// ---------- Avisos ----------

const ICONO_AVISO = { ok: "check", bad: "alert", warn: "alert", info: "bell" };

/** Aviso flotante con ícono, como en el diseño. Se va solo o con la X. */
export function toast(mensaje, tipo = "ok") {
  const contenedor = document.getElementById("toasts");
  const quitar = () => {
    aviso.classList.add("is-out");
    setTimeout(() => aviso.remove(), 200);
  };
  const aviso = h(
    "div",
    { class: `toast ${tipo}`, role: tipo === "bad" ? "alert" : "status" },
    h("span", { class: "toast-ic" }, icono(ICONO_AVISO[tipo] ?? "check")),
    h("div", { class: "toast-b" }, h("b", {}, mensaje)),
    h("button", { class: "toast-x", type: "button", "aria-label": "Cerrar aviso", onclick: quitar }, icono("x")),
  );
  contenedor.append(aviso);
  setTimeout(quitar, 4500);
}

// ---------- Modal ----------

/** Abre un diálogo. contenido: nodo; pie: botones. Devuelve { cerrar, dialogo }. */
export function abrirModal({ titulo, subtitulo, contenido, pie = [], alCerrar }) {
  const dialogo = h(
    "dialog",
    { class: "modal", "aria-labelledby": "modal-titulo" },
    h(
      "div",
      { class: "modal-h" },
      h("div", {}, h("h2", { id: "modal-titulo" }, titulo), subtitulo && h("p", {}, subtitulo)),
      h("button", { class: "icon-btn", type: "button", "aria-label": "Cerrar", onclick: () => cerrar() }, icono("cerrar")),
    ),
    h("div", { class: "modal-b" }, contenido),
    pie.length ? h("div", { class: "modal-f" }, pie) : null,
  );
  function cerrar() {
    if (dialogo.open) dialogo.close();
  }
  dialogo.addEventListener("close", () => {
    dialogo.remove();
    alCerrar?.();
  });
  document.body.append(dialogo);
  dialogo.showModal();
  return { dialogo, cerrar };
}

export function confirmar({ titulo, texto, boton = "Confirmar", peligro = false }) {
  return new Promise((resolver) => {
    let decision = false;
    const { cerrar } = abrirModal({
      titulo,
      contenido: h("p", {}, texto),
      alCerrar: () => resolver(decision),
      pie: [
        h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"),
        h(
          "button",
          {
            class: `btn ${peligro ? "btn-danger" : "btn-primary"}`,
            type: "button",
            onclick: () => {
              decision = true;
              cerrar();
            },
          },
          boton,
        ),
      ],
    });
  });
}

/** La contraseña temporal se ve una sola vez: no se guarda en ningún lado. */
export function mostrarClaveTemporal({ titulo, persona, usuario }) {
  return ({ clave_temporal: clave }) => {
    const copiar = h(
      "button",
      {
        class: "btn btn-sm",
        type: "button",
        onclick: async () => {
          try {
            await navigator.clipboard.writeText(clave);
            copiar.lastChild.textContent = "Copiada";
          } catch {
            toast("No se pudo copiar. Anótala a mano.", "bad");
          }
        },
      },
      icono("copiar"),
      h("span", {}, "Copiar"),
    );
    const { cerrar } = abrirModal({
      titulo,
      subtitulo: persona,
      contenido: [
        usuario && h("p", {}, "Usuario: ", h("b", { class: "mono" }, usuario)),
        h("div", { class: "clave-temporal" }, h("span", { class: "mono" }, clave), copiar),
        h(
          "p",
          { class: "alerta warn" },
          "Esta contraseña no volverá a verse. Entrégala a la persona; en su primer ingreso deberá cambiarla.",
        ),
      ],
      pie: [h("button", { class: "btn btn-primary", type: "button", onclick: () => cerrar() }, "Listo, ya la copié")],
    });
  };
}

// ---------- Formularios ----------

/**
 * Campo con etiqueta. Con `opciones` ([valor, texto][]) es una lista desplegable. Con `type: "date"` o
 * `"datetime-local"` es un campo de fecha dd/mm/aaaa (con hora, dd/mm/aaaa hh:mm en 24 horas): ver
 * `controlFecha`.
 */
export function campo({ etiqueta, ayuda, opciones, value, ...atributos }) {
  const id = atributos.id ?? `c-${atributos.name}`;
  let control;
  if (opciones) {
    control = h("select", { class: "select", id, ...atributos }, opciones.map(([v, t]) => h("option", { value: v }, t)));
    if (value !== undefined) control.value = value;
  } else if (atributos.type === "date" || atributos.type === "datetime-local") {
    control = controlFecha({ ...atributos, id, value });
  } else {
    control = h("input", { class: "input", id, value, ...atributos });
  }
  return h("label", { class: "field", for: id }, etiqueta, control, ayuda && h("small", {}, ayuda));
}

/**
 * Fecha escrita dd/mm/aaaa (o dd/mm/aaaa hh:mm) sin el selector nativo, que cambia de formato con el idioma
 * del navegador. Son dos inputs y el primero es el oculto: lleva `name`, el valor ISO ("AAAA-MM-DD" o
 * "AAAA-MM-DDTHH:MM"), `min`, `max`, `required` y `disabled`, y se lee o se cambia como un input de fecha
 * nativo (`campo.querySelector("input")`). El visible lo sigue solo: muestra el valor, avisa en español si
 * la fecha no existe o se sale de los límites y, al escribir, actualiza el oculto antes de que el evento
 * `input` llegue a la etiqueta.
 */
function controlFecha({ type, id, value, name, min, max, required, disabled, class: clase, ...atributos }) {
  const hora = type === "datetime-local";
  const leer = hora ? leerFechaHora : leerFecha;
  const mostrar = hora ? mostrarFechaHora : mostrarFecha;
  const oculto = h("input", { type: "hidden", name, value: value ?? "", min, max, required, disabled, "data-fecha": type });
  const visible = h("input", {
    class: clase ?? "input mono",
    type: "text",
    inputmode: "numeric",
    autocomplete: "off",
    spellcheck: "false",
    placeholder: hora ? "dd/mm/aaaa hh:mm" : "dd/mm/aaaa",
    maxlength: hora ? 16 : 10,
    ...atributos,
    id,
    required,
    disabled,
    value: mostrar(value),
  });
  const validar = () =>
    visible.setCustomValidity(problemaFecha(visible.value, { hora, min: oculto.getAttribute("min"), max: oculto.getAttribute("max") }) ?? "");
  visible.addEventListener("input", (evento) => {
    if (evento.inputType?.startsWith("insert") && visible.selectionStart === visible.value.length) {
      const completo = completarAlEscribir(visible.value, { hora });
      if (completo !== visible.value) visible.value = completo;
    }
    oculto.value = leer(visible.value) ?? "";
    validar();
  });
  // Al salir del campo, la fecha válida queda con dos dígitos: 6/9/2026 pasa a 06/09/2026.
  visible.addEventListener("change", () => {
    if (leer(visible.value)) visible.value = mostrar(leer(visible.value));
  });
  // Lo que el código cambia en el oculto (valor, límites, obligatorio) se refleja en el visible.
  new MutationObserver(() => {
    visible.required = oculto.required;
    visible.disabled = oculto.disabled;
    if ((leer(visible.value) ?? "") !== oculto.value) visible.value = mostrar(oculto.value);
    validar();
  }).observe(oculto, { attributes: true, attributeFilter: ["value", "min", "max", "required", "disabled"] });
  validar();
  return [oculto, visible];
}

/** Envía un formulario con estado de carga y muestra el error de la API dentro del formulario. */
export function enviarCon(formulario, boton, accion) {
  const mensaje = h("p", { class: "alerta bad", role: "alert", hidden: true });
  formulario.append(mensaje);
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!formulario.reportValidity()) return;
    mensaje.hidden = true;
    boton.classList.add("is-loading");
    boton.disabled = true;
    try {
      await accion(Object.fromEntries(new FormData(formulario)));
    } catch (error) {
      mensaje.textContent = error.message || "Ocurrió un error.";
      mensaje.hidden = false;
    } finally {
      boton.classList.remove("is-loading");
      boton.disabled = false;
    }
  });
}

/** Buscador con lupa, como el del diseño. */
export function buscador({ placeholder, etiqueta, alEscribir }) {
  return h(
    "label",
    { class: "search" },
    icono("search"),
    h("input", { type: "search", placeholder, "aria-label": etiqueta ?? placeholder, autocomplete: "off", oninput: (e) => alEscribir(e.target.value) }),
  );
}

/** Limpia los textos opcionales vacíos para no enviar cadenas vacías. */
export function sinVacios(datos) {
  return Object.fromEntries(Object.entries(datos).filter(([, v]) => v !== ""));
}

// ---------- Fichas (inspector del diseño) ----------

/**
 * Cabecera de una ficha: avatar o ícono, título con insignias, una línea de detalle y una cifra
 * destacada a la derecha. `codigo` pone el título en letra monoespaciada (PA-00001, RUC…).
 */
export function cabeceraFicha({ inicio, titulo, codigo = false, insignias = [], detalle, cifra, cifraTexto, accion }) {
  return h(
    "header",
    { class: "ins-h" },
    inicio,
    h(
      "div",
      { class: "ins-h-t" },
      h("div", { class: "ins-id" }, h("h1", { class: codigo ? "mono" : null }, titulo), insignias),
      detalle && h("p", { class: "ins-who" }, detalle),
    ),
    cifra != null && h("div", { class: "ins-kg" }, h("b", {}, cifra), cifraTexto && h("span", {}, cifraTexto)),
    // El botón principal de la pantalla, si lo hay (nunca en modo consulta: lo decide quien llama).
    accion && h("div", { class: "ins-accion" }, accion),
  );
}

/** Bloque dentro de una ficha: título, acciones a la derecha y contenido. */
export function seccion({ titulo, sub, acciones, contenido, clase = "" }) {
  return h(
    "section",
    { class: `sect ${clase}`.trim() },
    h("div", { class: "sect-t" }, h("div", {}, h("h3", {}, titulo), sub && h("p", { class: "panel-sub" }, sub)), acciones && h("div", { class: "fila-acciones" }, acciones)),
    contenido,
  );
}

/** Rejilla de datos con bordes del diseño. items: { etiqueta, valor, mono, extra }. */
/**
 * Datos de una ficha (decisión del equipo del 2026-10-09): filas etiqueta–valor, como la lista `.kv` del diseño,
 * en vez de una rejilla de celdas. `extra` puede ser una insignia (va junto al valor) o una nota (texto, nodo o
 * lista: va debajo). Un elemento `{ grupo: "Título" }` abre un grupo con su título; los grupos van en columnas.
 */
export function rejilla(items) {
  const grupos = [];
  for (const item of items.filter(Boolean)) {
    if (item.grupo) grupos.push({ titulo: item.grupo, filas: [] });
    else {
      if (!grupos.length) grupos.push({ titulo: null, filas: [] });
      grupos.at(-1).filas.push(item);
    }
  }
  const esInsignia = (x) => x instanceof Element && x.classList.contains("badge");
  const fila = ({ etiqueta, valor, mono = false, extra }) => {
    const vacio = !valor;
    const clase = ["dato-valor", mono && "mono", vacio && "dato-vacio"].filter(Boolean).join(" ");
    const insignia = esInsignia(extra) ? extra : null;
    const nota = extra && !insignia ? h("span", { class: "dato-nota" }, Array.isArray(extra) ? extra.map((x) => h("span", {}, x)) : extra) : null;
    return h("div", { class: "dato" }, h("dt", {}, etiqueta), h("dd", {}, h("span", { class: clase }, vacio ? "—" : valor), insignia, nota));
  };
  const lista = (filas) => h("dl", { class: "datos" }, filas.map(fila));
  if (grupos.length === 1 && !grupos[0].titulo) return lista(grupos[0].filas);
  return h(
    "div",
    { class: "datos-grupos" },
    grupos.map((g) => h("section", { class: "datos-grupo" }, g.titulo && h("h4", {}, g.titulo), lista(g.filas))),
  );
}

// ---------- Listas ----------

export function vacio({ titulo, texto, accion }) {
  return h("div", { class: "empty" }, h("b", {}, titulo), h("span", {}, texto), accion ?? null);
}

export function paginador({ pagina, por_pagina, total }, irA) {
  const paginas = Math.max(1, Math.ceil(total / por_pagina));
  if (paginas <= 1) return null;
  return h(
    "div",
    { class: "paginador" },
    h("span", {}, `Página ${pagina} de ${paginas} · ${total} en total`),
    h(
      "div",
      {},
      h("button", { class: "btn btn-sm", type: "button", disabled: pagina <= 1, onclick: () => irA(pagina - 1) }, "Anterior"),
      " ",
      h("button", { class: "btn btn-sm", type: "button", disabled: pagina >= paginas, onclick: () => irA(pagina + 1) }, "Siguiente"),
    ),
  );
}

export function conRetraso(funcion, ms = 300) {
  let temporizador;
  return (...args) => {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => funcion(...args), ms);
  };
}

export function cargando() {
  return h("div", { class: "empty", role: "status" }, "Cargando…");
}

export function errorDeCarga(error) {
  return h("div", { class: "empty" }, h("b", {}, "No se pudo cargar"), h("span", {}, error.message));
}

// ---------- Formatos ----------

/** Las fechas llegan en UTC y se muestran en hora de Lima: dd/mm/aaaa y, con hora, dd/mm/aaaa hh:mm (24 h). */
export function fecha(valor, { hora = false } = {}) {
  if (!valor) return "—";
  return fechaLima(valor, { hora });
}

export function iniciales(nombres = "", apellidos = "") {
  return `${nombres.trim()[0] ?? ""}${apellidos.trim()[0] ?? ""}`.toUpperCase();
}

/** Círculo con iniciales; cada persona conserva su tono, calculado de su nombre. */
export function avatar(nombres = "", apellidos = "", tamano = "") {
  let tono = 0;
  for (const letra of `${nombres}${apellidos}`) tono = (tono * 31 + letra.charCodeAt(0)) % 360;
  return h("span", { class: `avatar ${tamano}`.trim(), style: `--h:${tono}`, "aria-hidden": "true" }, iniciales(nombres, apellidos));
}

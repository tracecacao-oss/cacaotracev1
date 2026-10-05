// Piezas de interfaz reutilizables. Ningún texto se inserta como HTML: todo va por textContent.

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

// Íconos de trazo, 24x24.
const TRAZOS = {
  inicio: ["M3 11l9-7 9 7", "M5 10v10h14V10", "M10 20v-6h4v6"],
  productores: ["M16 20v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1", "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8", "M22 20v-1a4 4 0 0 0-3-3.9", "M16 3.1a4 4 0 0 1 0 7.8"],
  lotes: ["M21 8l-9-5-9 5 9 5 9-5z", "M3 8v8l9 5 9-5V8", "M12 13v8"],
  trazabilidad: ["M6 3v12", "M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6", "M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6", "M18 9a9 9 0 0 1-9 9"],
  exportacion: ["M12 3v12", "M7 8l5-5 5 5", "M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4"],
  cooperativa: ["M3 21h18", "M5 21V8l7-5 7 5v13", "M9 21v-6h6v6"],
  plataforma: ["M4 4h16v6H4z", "M4 14h16v6H4z", "M8 7h.01", "M8 17h.01"],
  perfil: ["M20 21v-1a6 6 0 0 0-6-6h-4a6 6 0 0 0-6 6v1", "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8"],
  parcelas: ["M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z", "M9 3v15", "M15 6v15"],
  entregas: ["M3 7h11v10H3z", "M14 10h4l3 3v4h-7", "M7 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4", "M17 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4"],
  salir: ["M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4", "M16 17l5-5-5-5", "M21 12H9"],
  menu: ["M4 6h16", "M4 12h16", "M4 18h16"],
  cerrar: ["M18 6L6 18", "M6 6l12 12"],
  copiar: ["M9 9h11v11H9z", "M5 15H4V4h11v1"],
  mas: ["M12 5v14", "M5 12h14"],
  buscar: ["M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14", "M21 21l-4.3-4.3"],
  ojo: ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z", "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6"],
};

export function icono(nombre) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "ic");
  svg.setAttribute("aria-hidden", "true");
  for (const d of TRAZOS[nombre] ?? []) {
    const trazo = document.createElementNS("http://www.w3.org/2000/svg", "path");
    trazo.setAttribute("d", d);
    svg.append(trazo);
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

export function toast(mensaje, tipo = "ok") {
  const contenedor = document.getElementById("toasts");
  const aviso = h("div", { class: `toast ${tipo}`, role: tipo === "bad" ? "alert" : "status" }, mensaje);
  contenedor.append(aviso);
  setTimeout(() => aviso.remove(), 4500);
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

/** Campo con etiqueta. Con `opciones` ([valor, texto][]) es una lista desplegable. */
export function campo({ etiqueta, ayuda, opciones, value, ...atributos }) {
  const id = atributos.id ?? `c-${atributos.name}`;
  let control;
  if (opciones) {
    control = h("select", { class: "select", id, ...atributos }, opciones.map(([v, t]) => h("option", { value: v }, t)));
    if (value !== undefined) control.value = value;
  } else {
    control = h("input", { class: "input", id, value, ...atributos });
  }
  return h("label", { class: "field", for: id }, etiqueta, control, ayuda && h("small", {}, ayuda));
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

/** Limpia los textos opcionales vacíos para no enviar cadenas vacías. */
export function sinVacios(datos) {
  return Object.fromEntries(Object.entries(datos).filter(([, v]) => v !== ""));
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

const FECHA_LIMA = new Intl.DateTimeFormat("es-PE", {
  timeZone: "America/Lima",
  day: "2-digit",
  month: "short",
  year: "numeric",
});
const FECHA_HORA_LIMA = new Intl.DateTimeFormat("es-PE", {
  timeZone: "America/Lima",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** Las fechas llegan en UTC y se muestran en hora de Lima. */
export function fecha(valor, { hora = false } = {}) {
  if (!valor) return "—";
  const objeto = valor.length === 10 ? new Date(`${valor}T12:00:00Z`) : new Date(valor);
  return (hora ? FECHA_HORA_LIMA : FECHA_LIMA).format(objeto);
}

export function iniciales(nombres = "", apellidos = "") {
  return `${nombres.trim()[0] ?? ""}${apellidos.trim()[0] ?? ""}`.toUpperCase();
}

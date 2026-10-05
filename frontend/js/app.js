// Esqueleto de la Parte 1: pantalla de ingreso y pantalla de estado.
// La Parte 2 reemplaza esto por la estructura con barra lateral.

import { alEsperarServidor, ErrorApi, llamarApi } from "./api.js";
import { cerrarSesion, configurado, iniciarSesion, tokenActual } from "./sesion.js";

const raiz = document.getElementById("app");
const aviso = document.getElementById("aviso-servidor");
alEsperarServidor((visible) => {
  aviso.hidden = !visible;
});

// Crea elementos con textContent: ningún texto del servidor se interpreta como HTML.
function h(etiqueta, atributos = {}, ...hijos) {
  const elemento = document.createElement(etiqueta);
  for (const [nombre, valor] of Object.entries(atributos)) {
    if (nombre.startsWith("on")) elemento.addEventListener(nombre.slice(2), valor);
    else if (valor === true) elemento.setAttribute(nombre, "");
    else if (valor !== false && valor != null) elemento.setAttribute(nombre, valor);
  }
  for (const hijo of hijos.flat()) {
    if (hijo == null || hijo === false) continue;
    elemento.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return elemento;
}

function pantallaIngreso() {
  const mensaje = h("p", { class: "error", role: "alert", hidden: true });
  const boton = h("button", { type: "submit", disabled: !configurado }, "Ingresar");

  async function enviar(evento) {
    evento.preventDefault();
    const datos = new FormData(evento.target);
    mensaje.hidden = true;
    boton.disabled = true;
    boton.textContent = "Ingresando…";
    try {
      await iniciarSesion(String(datos.get("correo")).trim(), String(datos.get("clave")));
      window.location.hash = "#/estado";
    } catch (error) {
      mensaje.textContent = error.message;
      mensaje.hidden = false;
      boton.disabled = false;
      boton.textContent = "Ingresar";
    }
  }

  return h(
    "section",
    { class: "tarjeta" },
    h("h1", {}, "CacaoTrace"),
    h("p", { class: "subtitulo" }, "Inicia sesión para continuar"),
    !configurado &&
      h(
        "p",
        { class: "error" },
        "Falta configurar SUPABASE_URL y SUPABASE_PUBLISHABLE_KEY en frontend/config.js.",
      ),
    h(
      "form",
      { onsubmit: enviar },
      h("label", { for: "correo" }, "Correo"),
      h("input", { id: "correo", name: "correo", type: "email", autocomplete: "username", required: true }),
      h("label", { for: "clave" }, "Contraseña"),
      h("input", {
        id: "clave",
        name: "clave",
        type: "password",
        autocomplete: "current-password",
        required: true,
      }),
      boton,
      mensaje,
    ),
    h("p", { class: "nota" }, "¿Olvidaste tu contraseña? Pide a tu cooperativa que la restablezca."),
  );
}

function filaEstado(titulo) {
  const detalle = h("span", { class: "detalle" }, "Comprobando…");
  const fila = h("li", {}, h("span", { class: "punto" }), h("strong", {}, titulo), detalle);
  return {
    fila,
    ok(texto) {
      fila.className = "ok";
      detalle.textContent = texto;
    },
    falla(texto) {
      fila.className = "falla";
      detalle.textContent = texto;
    },
  };
}

async function comprobar(fila, llamada, describir) {
  try {
    fila.ok(describir(await llamada()));
  } catch (error) {
    fila.falla(error instanceof ErrorApi ? error.message : "Error inesperado.");
  }
}

function pantallaEstado(token) {
  const api = filaEstado("API");
  const base = filaEstado("Base de datos");
  const usuario = filaEstado("Usuario");

  comprobar(api, () => llamarApi("/health"), (d) => `En línea · versión ${d.version.slice(0, 7)}`);
  comprobar(base, () => llamarApi("/health/db"), (d) => `En línea · PostGIS ${d.postgis.split(" ")[0]}`);
  comprobar(usuario, () => llamarApi("/me", { token }), (d) => d.email ?? d.id);

  async function salir() {
    await cerrarSesion();
    window.location.hash = "#/ingreso";
  }

  return h(
    "section",
    { class: "tarjeta" },
    h("h1", {}, "Estado del sistema"),
    h("p", { class: "subtitulo" }, "Conexión de la interfaz con la API y la base de datos"),
    h("ul", { class: "estado" }, api.fila, base.fila, usuario.fila),
    h("button", { type: "button", class: "secundario", onclick: salir }, "Cerrar sesión"),
  );
}

async function mostrar() {
  const token = configurado ? await tokenActual() : null;
  const ruta = window.location.hash || "#/ingreso";

  if (!token && ruta !== "#/ingreso") {
    window.location.hash = "#/ingreso";
    return;
  }
  if (token && ruta !== "#/estado") {
    window.location.hash = "#/estado";
    return;
  }
  raiz.replaceChildren(token ? pantallaEstado(token) : pantallaIngreso());
}

window.addEventListener("hashchange", mostrar);
mostrar();

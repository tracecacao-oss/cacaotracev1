// Ingreso: el personal entra con correo; el productor con su DNI. Ambos con contraseña.

import { estado } from "../estado.js";
import { configurado, correoTecnico, iniciarSesion } from "../sesion.js";
import { campo, h, marca } from "../ui.js";

export default function ingreso({ navegar, recargarUsuario, salir, tomarAviso }) {
  let modo = "cooperativa";
  const aviso = tomarAviso();

  const mensaje = h("p", { class: "alerta bad", role: "alert", hidden: !aviso }, aviso ?? "");
  const usuario = h("div");
  const clave = campo({ etiqueta: "Contraseña", name: "clave", type: "password", autocomplete: "current-password", required: true });
  const boton = h("button", { class: "btn btn-primary btn-lg btn-block", type: "submit", disabled: !configurado }, "Ingresar");

  function pintarUsuario() {
    usuario.replaceChildren(
      modo === "cooperativa"
        ? campo({ etiqueta: "Correo", name: "usuario", type: "email", autocomplete: "username", required: true })
        : campo({
            etiqueta: "DNI",
            name: "usuario",
            type: "text",
            inputmode: "numeric",
            autocomplete: "username",
            pattern: "[0-9]{8}",
            maxlength: 8,
            title: "8 dígitos",
            placeholder: "8 dígitos",
            class: "input mono",
            required: true,
          }),
    );
    for (const b of selector.children) b.setAttribute("aria-pressed", String(b.dataset.modo === modo));
  }

  const selector = h(
    "div",
    { class: "seg2", role: "group", "aria-label": "Tipo de ingreso" },
    ["cooperativa", "productor"].map((m) =>
      h(
        "button",
        {
          type: "button",
          "data-modo": m,
          onclick: () => {
            modo = m;
            mensaje.hidden = true;
            pintarUsuario();
          },
        },
        m === "cooperativa" ? "Cooperativa" : "Productor",
      ),
    ),
  );
  pintarUsuario();

  const formulario = h(
    "form",
    { class: "form", novalidate: false },
    selector,
    usuario,
    clave,
    boton,
    mensaje,
  );
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!formulario.reportValidity()) return;
    const datos = new FormData(formulario);
    const valor = String(datos.get("usuario")).trim();
    mensaje.hidden = true;
    boton.classList.add("is-loading");
    boton.disabled = true;
    try {
      await iniciarSesion(modo === "productor" ? correoTecnico(valor) : valor.toLowerCase(), String(datos.get("clave")));
      try {
        await recargarUsuario();
      } catch (error) {
        // Sin perfil, desactivado o con la cooperativa suspendida: no entra.
        await salir(error.message);
        return;
      }
      if (modo === "productor" && estado.usuario.rol !== "productor") {
        await salir("Esta cuenta es del personal de la cooperativa. Elige “Cooperativa”.");
        return;
      }
      navegar("#/inicio");
    } catch (error) {
      mensaje.textContent = error.message;
      mensaje.hidden = false;
    } finally {
      boton.classList.remove("is-loading");
      boton.disabled = !configurado;
    }
  });

  return {
    titulo: "Ingreso",
    contenido: h(
      "main",
      { class: "pantalla-sola" },
      h(
        "section",
        { class: "panel tarjeta-sola", "aria-labelledby": "titulo-ingreso" },
        marca(),
        h("h1", { id: "titulo-ingreso" }, "Ingresa a CacaoTrace"),
        h("p", { class: "sub" }, "Trazabilidad del cacao, del productor a la exportación"),
        !configurado && h("p", { class: "alerta bad" }, "Falta configurar Supabase en frontend/config.js."),
        formulario,
        h("p", { class: "sub" }, "¿Olvidaste tu contraseña? Pide a tu cooperativa que la restablezca"),
      ),
    ),
  };
}

// Consentimiento de datos: solo productor, en su primer ingreso.

import { llamarApi } from "../api.js";
import { completarTexto, textoConsentimiento } from "../consentimiento.js";
import { estado } from "../estado.js";
import { h, marca } from "../ui.js";

export default async function consentimiento({ navegar, recargarUsuario, salir }) {
  const { version, texto } = await textoConsentimiento();
  const boton = h("button", { class: "btn btn-primary btn-lg btn-block", type: "button" }, "Acepto");
  const mensaje = h("p", { class: "alerta bad", role: "alert", hidden: true });

  boton.addEventListener("click", async () => {
    boton.classList.add("is-loading");
    mensaje.hidden = true;
    try {
      await llamarApi("/me/consentimiento", { metodo: "POST", cuerpo: { version_texto: version } });
      await recargarUsuario();
      navegar("#/mi-perfil");
    } catch (error) {
      mensaje.textContent = error.message;
      mensaje.hidden = false;
    } finally {
      boton.classList.remove("is-loading");
    }
  });

  return {
    titulo: "Consentimiento de datos",
    contenido: h(
      "main",
      { class: "pantalla-sola" },
      h(
        "section",
        { class: "panel tarjeta-sola", "aria-labelledby": "titulo-consentimiento" },
        marca(),
        h("h1", { id: "titulo-consentimiento" }, "Uso de tus datos personales"),
        h("p", { class: "sub" }, `Versión ${version}`),
        h("div", { class: "texto-legal", tabindex: "0" }, completarTexto(texto, estado.usuario?.cooperativa)),
        boton,
        mensaje,
        h("button", { class: "btn btn-ghost btn-block", type: "button", onclick: () => salir() }, "Cerrar sesión"),
      ),
    ),
  };
}

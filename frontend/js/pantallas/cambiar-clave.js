// Cambio de contraseña obligatorio: única pantalla accesible mientras sea obligatorio.

import { estado } from "../estado.js";
import { h, marca, toast } from "../ui.js";
import { formularioClave } from "./formulario-clave.js";

export default function cambiarClave({ navegar, recargarUsuario, salir }) {
  const obligatorio = estado.usuario?.debe_cambiar_clave;
  const formulario = formularioClave({
    textoBoton: "Guardar y continuar",
    alTerminar: async () => {
      await recargarUsuario();
      toast("Tu contraseña se cambió.");
      navegar("#/inicio");
    },
  });

  return {
    titulo: "Cambio de contraseña",
    contenido: h(
      "main",
      { class: "pantalla-sola" },
      h(
        "section",
        { class: "panel tarjeta-sola", "aria-labelledby": "titulo-clave" },
        marca(),
        h("h1", { id: "titulo-clave" }, "Crea tu contraseña"),
        h(
          "p",
          { class: "sub" },
          obligatorio
            ? "Estás usando una contraseña temporal. Cámbiala para continuar."
            : "Cambia tu contraseña de acceso.",
        ),
        formulario,
        h("button", { class: "btn btn-ghost btn-block", type: "button", onclick: () => salir() }, "Cerrar sesión"),
      ),
    ),
  };
}

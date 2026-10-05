// Mi perfil: datos propios y cambio de contraseña. Para el productor funciona a 360 px.

import { estado, nombreCooperativa, ROTULOS_ROL } from "../estado.js";
import { h, toast } from "../ui.js";
import { formularioClave } from "./formulario-clave.js";

function dato(etiqueta, valor, mono = false) {
  return h("div", {}, h("dt", {}, etiqueta), h("dd", { class: mono ? "mono" : null }, valor ?? "—"));
}

export default function miPerfil({ recargarUsuario, recargar }) {
  const u = estado.usuario;
  const productor = u.rol === "productor";

  return {
    titulo: "Mi perfil",
    contenido: [
      h(
        "section",
        { class: "panel" },
        h("div", { class: "panel-h" }, h("h2", {}, "Mis datos")),
        h(
          "dl",
          { class: "panel-b ficha" },
          dato("Nombres", u.nombres),
          dato("Apellidos", u.apellidos),
          productor ? dato("DNI", u.dni, true) : dato("Correo", u.correo),
          dato("Rol", ROTULOS_ROL[u.rol]),
          u.cooperativa && dato("Cooperativa", nombreCooperativa()),
        ),
      ),
      h(
        "section",
        { class: "panel" },
        h("div", { class: "panel-h" }, h("h2", {}, "Cambiar contraseña")),
        h(
          "div",
          { class: "panel-b" },
          formularioClave({
            alTerminar: async () => {
              await recargarUsuario();
              toast("Tu contraseña se cambió.");
              recargar();
            },
          }),
        ),
      ),
    ],
  };
}

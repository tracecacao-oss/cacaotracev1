// Módulo Cooperativa. El administrador entra a Usuarios; el operador y el lector no tienen
// secciones en esta parte (Configuración se construye en las Partes 5 y 8).

import { nombreCooperativa, rolEfectivo } from "../estado.js";
import { h, vacio } from "../ui.js";

export default function cooperativa({ navegar }) {
  if (["admin_cooperativa", "consulta"].includes(rolEfectivo())) {
    navegar("#/cooperativa/usuarios");
    return { titulo: "Cooperativa", contenido: h("div") };
  }
  return {
    titulo: "Cooperativa",
    contenido: h(
      "section",
      { class: "panel" },
      vacio({
        titulo: nombreCooperativa(),
        texto: "Los datos y documentos de la cooperativa llegan en las Partes 5 y 8. Usuarios y Auditoría son del administrador.",
      }),
    ),
  };
}

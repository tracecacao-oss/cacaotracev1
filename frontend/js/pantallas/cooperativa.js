// Módulo Cooperativa. El administrador entra a Usuarios; el operador y el lector, a Configuración,
// que pueden ver pero no cambiar.

import { rolEfectivo } from "../estado.js";
import { h } from "../ui.js";

export default function cooperativa({ navegar }) {
  navegar(["admin_cooperativa", "consulta"].includes(rolEfectivo()) ? "#/cooperativa/usuarios" : "#/cooperativa/configuracion");
  return { titulo: "Cooperativa", contenido: h("div") };
}

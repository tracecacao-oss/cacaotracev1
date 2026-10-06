// Módulo aún no construido: pantalla vacía con su nombre.

import { rolEfectivo } from "../estado.js";
import { h, vacio } from "../ui.js";

const MODULOS = {
  "#/trazabilidad": ["Trazabilidad", "Parte 7"],
  "#/exportacion": ["Exportación", "Partes 8 y 9"],
};

export default function pantallaVacia({ hash }) {
  const [titulo, parte] = MODULOS[hash] ?? ["Módulo", ""];
  return {
    titulo,
    migas: [[titulo]],
    contenido: h(
      "section",
      { class: "panel" },
      vacio({ titulo: "Todavía no disponible", texto: `Este módulo se construye en ${parte} de CacaoTrace.` }),
    ),
  };
}

/**
 * Usuarios y Auditoría son del administrador (el superadmin los consulta). Configuración y Lugares los
 * ve todo el personal; solo el administrador los cambia.
 */
export function seccionesCooperativa() {
  const comunes = [
    ["Configuración", "#/cooperativa/configuracion"],
    ["Lugares", "#/cooperativa/lugares"],
    ["Plantilla de proceso", "#/cooperativa/plantilla-proceso"],
  ];
  if (["admin_cooperativa", "consulta"].includes(rolEfectivo())) {
    return [["Usuarios", "#/cooperativa/usuarios"], ["Auditoría", "#/cooperativa/auditoria"], ...comunes];
  }
  return comunes;
}

// Secciones del módulo Cooperativa, que comparten sus pantallas.

import { rolEfectivo } from "../estado.js";

/**
 * Usuarios y Auditoría son del administrador (el superadmin los consulta). Configuración y Lugares los
 * ve todo el personal; solo el administrador los cambia.
 */
export function seccionesCooperativa() {
  const comunes = [
    ["Datos y expediente legal", "#/cooperativa/legal"],
    ["Configuración", "#/cooperativa/configuracion"],
    ["Lugares", "#/cooperativa/lugares"],
    ["Plantilla de proceso", "#/cooperativa/plantilla-proceso"],
  ];
  if (["admin_cooperativa", "consulta"].includes(rolEfectivo())) {
    return [["Usuarios", "#/cooperativa/usuarios"], ["Auditoría", "#/cooperativa/auditoria"], ...comunes];
  }
  return comunes;
}

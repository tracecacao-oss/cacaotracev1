// Módulo aún no construido: pantalla vacía con su nombre.

import { rolEfectivo } from "../estado.js";
import { h, vacio } from "../ui.js";

const MODULOS = {
  "#/lotes": ["Lotes y proceso", "Partes 5 y 6"],
  "#/trazabilidad": ["Trazabilidad", "Parte 7"],
  "#/exportacion": ["Exportación", "Partes 8 y 9"],
  "#/cooperativa/configuracion": ["Configuración", "Partes 5 y 8"],
  "#/mis-entregas": ["Mis entregas", "Parte 5"],
};

export default function pantallaVacia({ hash }) {
  const [titulo, parte] = MODULOS[hash] ?? ["Módulo", ""];
  const configuracion = hash === "#/cooperativa/configuracion";
  return {
    titulo,
    migas: configuracion ? [["Cooperativa", "#/cooperativa"], ["Configuración"]] : null,
    secciones: configuracion ? seccionesCooperativa() : null,
    contenido: h(
      "section",
      { class: "panel" },
      vacio({ titulo, texto: `Este módulo todavía no está disponible. Se construye en ${parte} de CacaoTrace.` }),
    ),
  };
}

/** Usuarios, Auditoría y Configuración son solo del administrador; el superadmin consulta las dos primeras. */
export function seccionesCooperativa() {
  const rol = rolEfectivo();
  if (rol === "admin_cooperativa") {
    return [
      ["Usuarios", "#/cooperativa/usuarios"],
      ["Auditoría", "#/cooperativa/auditoria"],
      ["Configuración", "#/cooperativa/configuracion"],
    ];
  }
  if (rol === "consulta") {
    return [
      ["Usuarios", "#/cooperativa/usuarios"],
      ["Auditoría", "#/cooperativa/auditoria"],
    ];
  }
  return [];
}

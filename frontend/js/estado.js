// Estado compartido de la interfaz: el usuario de GET /me y la cooperativa que consulta el
// superadministrador. Ningún permiso se decide aquí: la API es la que decide.

export const ROTULOS_ROL = {
  superadmin: "Equipo CacaoTrace",
  admin_cooperativa: "Administrador",
  operador: "Operador",
  lector: "Lector",
  productor: "Productor",
};

export const estado = {
  usuario: null,
  consulta: leerConsulta(),
};

function leerConsulta() {
  try {
    return JSON.parse(sessionStorage.getItem("consulta") || "null");
  } catch {
    return null;
  }
}

/** Superadministrador viendo una cooperativa en solo lectura. */
export function fijarConsulta(cooperativa) {
  estado.consulta = cooperativa
    ? { id: cooperativa.id, nombre: cooperativa.nombre, es_demo: Boolean(cooperativa.es_demo) }
    : null;
  try {
    if (estado.consulta) sessionStorage.setItem("consulta", JSON.stringify(estado.consulta));
    else sessionStorage.removeItem("consulta");
  } catch {
    // Sin almacenamiento la consulta dura hasta recargar la página.
  }
}

export function enConsulta() {
  return estado.usuario?.rol === "superadmin" && Boolean(estado.consulta);
}

/** Rol efectivo para la navegación: "consulta" cuando el superadmin ve una cooperativa. */
export function rolEfectivo() {
  return enConsulta() ? "consulta" : estado.usuario?.rol;
}

const PERMISOS = {
  registrarProductores: ["admin_cooperativa", "operador"],
  gestionarAccesos: ["admin_cooperativa", "operador"],
  gestionarUsuarios: ["admin_cooperativa"],
};

/** Solo decide qué botones se muestran; la API rechaza igual lo que el rol no puede hacer. */
export function puede(accion) {
  return PERMISOS[accion]?.includes(rolEfectivo()) ?? false;
}

/** Parte 10: cuenta de una cooperativa de demostración, o el superadmin consultando una. */
export function esDemo() {
  return enConsulta() ? Boolean(estado.consulta.es_demo) : Boolean(estado.usuario?.es_demo);
}

export function nombreCooperativa() {
  if (enConsulta()) return estado.consulta.nombre;
  const coop = estado.usuario?.cooperativa;
  return coop ? coop.nombre_comercial || coop.razon_social : null;
}

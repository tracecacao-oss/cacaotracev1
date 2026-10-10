// Navegación por hash. Cada pantalla es un módulo en js/pantallas/ que devuelve su vista.
// La interfaz oculta lo que el rol no puede usar, pero la API es la que decide.

import { alPerderLaSesion, llamarApi } from "./api.js";
import { estado, fijarConsulta, rolEfectivo } from "./estado.js";
import { estructura } from "./layout.js";
import { cerrarSesion, configurado, tokenActual } from "./sesion.js";
import { errorDeCarga, h } from "./ui.js";

const PERSONAL = ["admin_cooperativa", "operador", "lector", "consulta"];
const TODOS = ["superadmin", "admin_cooperativa", "operador", "lector", "productor", "consulta"];

const RUTAS = [
  { patron: /^#\/ingreso$/, publica: true, cargar: () => import("./pantallas/ingreso.js") },
  { patron: /^#\/cambiar-clave$/, sola: true, roles: TODOS, cargar: () => import("./pantallas/cambiar-clave.js") },
  { patron: /^#\/consentimiento$/, sola: true, roles: ["productor"], cargar: () => import("./pantallas/consentimiento.js") },
  { patron: /^#\/inicio$/, roles: PERSONAL, cargar: () => import("./pantallas/inicio.js") },
  { patron: /^#\/productores$/, roles: PERSONAL, cargar: () => import("./pantallas/productores.js") },
  { patron: /^#\/productores\/mapa$/, roles: PERSONAL, cargar: () => import("./pantallas/mapa-parcelas.js") },
  { patron: /^#\/productores\/superposiciones$/, roles: PERSONAL, cargar: () => import("./pantallas/superposiciones.js") },
  { patron: /^#\/productores\/habilitacion$/, roles: PERSONAL, cargar: () => import("./pantallas/habilitacion.js") },
  { patron: /^#\/productores\/([0-9a-f-]{36})(?:\/(declaracion))?$/, roles: PERSONAL, cargar: () => import("./pantallas/productor.js") },
  { patron: /^#\/productores\/([0-9a-f-]{36})\/parcelas\/nueva$/, roles: ["admin_cooperativa", "operador"], cargar: () => import("./pantallas/parcela-nueva.js") },
  { patron: /^#\/parcelas\/([0-9a-f-]{36})$/, roles: PERSONAL, cargar: () => import("./pantallas/parcela.js") },
  { patron: /^#\/lotes(\/recepcion)?$/, roles: PERSONAL, cargar: () => import("./pantallas/recepcion.js") },
  { patron: /^#\/lotes\/recepcion\/nueva$/, roles: ["admin_cooperativa", "operador"], cargar: () => import("./pantallas/tanda-nueva.js") },
  { patron: /^#\/lotes\/dop$/, roles: PERSONAL, cargar: () => import("./pantallas/dops.js") },
  { patron: /^#\/tandas\/([0-9a-f-]{36})$/, roles: PERSONAL, cargar: () => import("./pantallas/tanda.js") },
  { patron: /^#\/dops\/([0-9a-f-]{36})$/, roles: PERSONAL, cargar: () => import("./pantallas/dop.js") },
  { patron: /^#\/lotes\/corridas$/, roles: PERSONAL, cargar: () => import("./pantallas/corridas.js") },
  { patron: /^#\/lotes\/corridas\/nueva$/, roles: ["admin_cooperativa", "operador"], cargar: () => import("./pantallas/corrida-nueva.js") },
  { patron: /^#\/corridas\/([0-9a-f-]{36})$/, roles: PERSONAL, cargar: () => import("./pantallas/corrida.js") },
  { patron: /^#\/lotes\/stock$/, roles: PERSONAL, cargar: () => import("./pantallas/stock.js") },
  { patron: /^#\/tandas-finales\/([0-9a-f-]{36})$/, roles: PERSONAL, cargar: () => import("./pantallas/tanda-final.js") },
  { patron: /^#\/dpps\/([0-9a-f-]{36})$/, roles: PERSONAL, cargar: () => import("./pantallas/dpp.js") },
  { patron: /^#\/trazabilidad(\/lotes)?$/, roles: PERSONAL, cargar: () => import("./pantallas/trazabilidad-lotes.js") },
  { patron: /^#\/trazabilidad\/origen$/, roles: PERSONAL, cargar: () => import("./pantallas/trazabilidad-origen.js") },
  { patron: /^#\/exportacion(\/ordenes)?$/, roles: PERSONAL, cargar: () => import("./pantallas/ordenes.js") },
  { patron: /^#\/exportacion\/ordenes\/nueva$/, roles: ["admin_cooperativa", "operador"], cargar: () => import("./pantallas/orden-nueva.js") },
  { patron: /^#\/exportacion\/lotes$/, roles: PERSONAL, cargar: () => import("./pantallas/lotes-exportacion.js") },
  { patron: /^#\/exportacion\/importadores$/, roles: PERSONAL, cargar: () => import("./pantallas/importadores.js") },
  { patron: /^#\/exportacion\/dex$/, roles: PERSONAL, cargar: () => import("./pantallas/dex-lista.js") },
  { patron: /^#\/ordenes\/([0-9a-f-]{36})$/, roles: PERSONAL, cargar: () => import("./pantallas/orden.js") },
  { patron: /^#\/lotes-exportacion\/([0-9a-f-]{36})(?:\/(hallazgos|dex))?$/, roles: PERSONAL, cargar: () => import("./pantallas/lote-exportacion.js") },
  { patron: /^#\/lotes-exportacion\/([0-9a-f-]{36})\/armar$/, roles: ["admin_cooperativa", "operador"], cargar: () => import("./pantallas/lote-armar.js") },
  { patron: /^#\/cooperativa$/, roles: PERSONAL, cargar: () => import("./pantallas/cooperativa.js") },
  { patron: /^#\/cooperativa\/usuarios$/, roles: ["admin_cooperativa", "consulta"], cargar: () => import("./pantallas/usuarios.js") },
  { patron: /^#\/cooperativa\/auditoria$/, roles: ["admin_cooperativa", "consulta"], cargar: () => import("./pantallas/auditoria.js") },
  { patron: /^#\/cooperativa\/configuracion$/, roles: PERSONAL, cargar: () => import("./pantallas/configuracion.js") },
  { patron: /^#\/cooperativa\/lugares$/, roles: PERSONAL, cargar: () => import("./pantallas/lugares.js") },
  { patron: /^#\/cooperativa\/plantilla-proceso$/, roles: PERSONAL, cargar: () => import("./pantallas/plantilla-proceso.js") },
  { patron: /^#\/cooperativa\/legal$/, roles: PERSONAL, cargar: () => import("./pantallas/cooperativa-legal.js") },
  { patron: /^#\/cooperativa\/diligencia$/, roles: PERSONAL, cargar: () => import("./pantallas/diligencia.js") },
  { patron: /^#\/cooperativa\/certificaciones$/, roles: PERSONAL, cargar: () => import("./pantallas/certificaciones.js") },
  { patron: /^#\/plataforma(\/cooperativas)?$/, roles: ["superadmin", "consulta"], cargar: () => import("./pantallas/cooperativas.js") },
  { patron: /^#\/plataforma\/superposiciones$/, roles: ["superadmin", "consulta"], cargar: () => import("./pantallas/superposiciones-plataforma.js") },
  { patron: /^#\/plataforma\/configuracion$/, roles: ["superadmin"], cargar: () => import("./pantallas/plataforma-configuracion.js") },
  { patron: /^#\/plataforma\/cooperativas\/([0-9a-f-]{36})$/, roles: ["superadmin", "consulta"], cargar: () => import("./pantallas/cooperativa-detalle.js") },
  { patron: /^#\/mi-perfil$/, roles: TODOS, cargar: () => import("./pantallas/mi-perfil.js") },
  { patron: /^#\/mis-parcelas$/, roles: ["productor"], cargar: () => import("./pantallas/mis-parcelas.js") },
  { patron: /^#\/mis-parcelas\/nueva$/, roles: ["productor"], cargar: () => import("./pantallas/parcela-nueva.js") },
  { patron: /^#\/mis-parcelas\/([0-9a-f-]{36})$/, roles: ["productor"], cargar: () => import("./pantallas/parcela.js") },
  { patron: /^#\/mis-entregas$/, roles: ["productor"], cargar: () => import("./pantallas/mis-entregas.js") },
  { patron: /^#\/mi-declaracion$/, roles: ["productor"], cargar: () => import("./pantallas/mi-declaracion.js") },
];

// Verificación pública del DOP, del DPP y del DEX: no pide sesión, no lleva barra lateral y no enlaza al resto.
const VERIFICACION = { patron: /^#\/verificar\/(dop|dpp|dex)\/([^/?#]{1,40})$/, cargar: () => import("./pantallas/verificar.js") };

const raiz = document.getElementById("app");
let avisoIngreso = null;
let turno = 0;

export function navegar(hash) {
  if (location.hash === hash) mostrar();
  else location.hash = hash;
}

function inicioDe(usuario) {
  if (usuario.rol === "productor") return "#/mi-perfil";
  if (usuario.rol === "superadmin") return rolEfectivo() === "consulta" ? "#/inicio" : "#/plataforma/cooperativas";
  return "#/inicio";
}

export async function recargarUsuario() {
  estado.usuario = await llamarApi("/me", { sinConsulta: true });
  if (estado.usuario.rol !== "superadmin") fijarConsulta(null);
  return estado.usuario;
}

export async function salir(aviso = null) {
  await cerrarSesion();
  estado.usuario = null;
  fijarConsulta(null);
  avisoIngreso = aviso;
  navegar("#/ingreso");
}

alPerderLaSesion((codigo, mensaje) => {
  if (codigo === "cambio_clave_requerido") {
    if (estado.usuario) estado.usuario.debe_cambiar_clave = true;
    navegar("#/cambiar-clave");
    return;
  }
  estado.usuario = null;
  avisoIngreso = mensaje;
  navegar("#/ingreso");
});

function pantallaDeError(error, reintentar) {
  return h(
    "div",
    { class: "pantalla-sola" },
    h("div", { class: "panel tarjeta-sola" }, errorDeCarga(error), h("button", { class: "btn btn-primary", type: "button", onclick: reintentar }, "Reintentar")),
  );
}

export async function mostrar() {
  const miTurno = ++turno;
  const vigente = () => miTurno === turno;
  const hash = location.hash || "#/ingreso";

  const publica = hash.match(VERIFICACION.patron);
  if (publica) {
    try {
      const vista = await (await VERIFICACION.cargar()).default({ parametros: publica.slice(1) });
      if (!vigente()) return;
      document.title = vista.titulo ? `${vista.titulo} · CacaoTrace` : "CacaoTrace";
      raiz.replaceChildren(vista.contenido);
    } catch (error) {
      if (vigente()) raiz.replaceChildren(pantallaDeError(error, mostrar));
    }
    return;
  }

  const token = configurado ? await tokenActual() : null;
  if (!vigente()) return;
  if (!token) {
    estado.usuario = null;
    if (hash !== "#/ingreso") return navegar("#/ingreso");
  } else if (!estado.usuario) {
    try {
      await recargarUsuario();
    } catch (error) {
      if (!vigente()) return;
      // Cuenta desactivada, cooperativa suspendida o sin perfil: se cierra la sesión.
      if (error.estado === 403) return salir(error.message);
      if (error.estado === 401) return;
      raiz.replaceChildren(pantallaDeError(error, mostrar));
      return;
    }
    if (!vigente()) return;
  }

  const usuario = estado.usuario;
  if (usuario) {
    if (usuario.debe_cambiar_clave && hash !== "#/cambiar-clave") return navegar("#/cambiar-clave");
    if (!usuario.debe_cambiar_clave && usuario.consentimiento_pendiente && hash !== "#/consentimiento") {
      return navegar("#/consentimiento");
    }
    if (hash === "#/ingreso") return navegar(inicioDe(usuario));
  }

  let parametros = [];
  const ruta = RUTAS.find((r) => {
    const coincide = hash.match(r.patron);
    if (coincide) parametros = coincide.slice(1);
    return coincide;
  });
  if (!ruta || (usuario && ruta.roles && !ruta.roles.includes(rolEfectivo()))) {
    return navegar(usuario ? inicioDe(usuario) : "#/ingreso");
  }

  const ctx = {
    hash,
    parametros,
    navegar,
    recargar: mostrar,
    recargarUsuario,
    salir,
    tomarAviso: () => {
      const aviso = avisoIngreso;
      avisoIngreso = null;
      return aviso;
    },
  };
  let vista;
  try {
    const modulo = await ruta.cargar();
    vista = await modulo.default(ctx);
  } catch (error) {
    if (!vigente()) return;
    raiz.replaceChildren(pantallaDeError(error, mostrar));
    return;
  }
  if (!vigente()) return;

  document.title = vista.titulo ? `${vista.titulo} · CacaoTrace` : "CacaoTrace";
  document.body.classList.remove("side-abierta");
  if (ruta.publica || ruta.sola) {
    raiz.replaceChildren(vista.contenido);
  } else {
    raiz.replaceChildren(...estructura(vista, hash, { alSalir: () => salir(), navegar }));
  }
  window.scrollTo(0, 0);
}

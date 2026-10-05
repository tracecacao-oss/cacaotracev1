// Estructura de toda pantalla: barra lateral, encabezado (título, ruta y como máximo un botón
// principal) y secciones como pestañas secundarias. Bajo 900 px la barra se pliega en un menú.

import { enConsulta, estado, fijarConsulta, nombreCooperativa, rolEfectivo, ROTULOS_ROL } from "./estado.js";
import { h, icono, iniciales, marca } from "./ui.js";

const MODULOS_COOPERATIVA = [
  { texto: "Inicio", ruta: "#/inicio", icono: "inicio" },
  { texto: "Productores", ruta: "#/productores", icono: "productores" },
  { texto: "Lotes y proceso", ruta: "#/lotes", icono: "lotes" },
  { texto: "Trazabilidad", ruta: "#/trazabilidad", icono: "trazabilidad" },
  { texto: "Exportación", ruta: "#/exportacion", icono: "exportacion" },
  { texto: "Cooperativa", ruta: "#/cooperativa", icono: "cooperativa" },
];
const MODULOS_PRODUCTOR = [
  { texto: "Mi perfil", ruta: "#/mi-perfil", icono: "perfil" },
  { texto: "Mis parcelas", ruta: "#/mis-parcelas", icono: "parcelas" },
  { texto: "Mis entregas", ruta: "#/mis-entregas", icono: "entregas" },
];
const PLATAFORMA = { texto: "Plataforma", ruta: "#/plataforma/cooperativas", icono: "plataforma" };

function gruposDeNavegacion() {
  const rol = estado.usuario?.rol;
  if (rol === "productor") return [{ items: MODULOS_PRODUCTOR }];
  if (rol === "superadmin") {
    const grupos = [{ items: [PLATAFORMA] }];
    if (enConsulta()) grupos.push({ titulo: "Consulta", items: MODULOS_COOPERATIVA });
    return grupos;
  }
  return [{ items: MODULOS_COOPERATIVA }];
}

function activo(ruta, hash) {
  const base = ruta === PLATAFORMA.ruta ? "#/plataforma" : ruta;
  // El detalle de una parcela pertenece al módulo Productores.
  if (ruta === "#/productores" && hash.startsWith("#/parcelas/")) return true;
  return hash === base || hash.startsWith(`${base}/`);
}

function cerrarMenu() {
  document.body.classList.remove("side-abierta");
}

function barraLateral(hash, alSalir) {
  const usuario = estado.usuario;
  const coop = nombreCooperativa();
  const enlaces = gruposDeNavegacion().map((grupo) => [
    grupo.titulo && h("div", { class: "side-g" }, grupo.titulo),
    grupo.items.map((item) =>
      h(
        "a",
        { class: "side-i", href: item.ruta, "aria-current": activo(item.ruta, hash) ? "page" : false, onclick: cerrarMenu },
        icono(item.icono),
        h("span", {}, item.texto),
      ),
    ),
  ]);

  return h(
    "aside",
    { class: "side", id: "barra-lateral", "aria-label": "Módulos" },
    h("div", { class: "side-h" }, marca(), coop && h("span", { class: "side-coop", title: coop }, coop)),
    h("nav", { class: "side-nav" }, enlaces),
    h(
      "div",
      { class: "side-f" },
      h(
        "div",
        { class: "side-user" },
        h("span", { class: "avatar", "aria-hidden": "true" }, iniciales(usuario.nombres, usuario.apellidos)),
        h(
          "span",
          { class: "side-user-t" },
          h("b", {}, `${usuario.nombres} ${usuario.apellidos}`),
          h("span", {}, ROTULOS_ROL[usuario.rol]),
        ),
      ),
      usuario.rol !== "productor" &&
        h("a", { class: "side-i", href: "#/mi-perfil", "aria-current": hash === "#/mi-perfil" ? "page" : false }, icono("perfil"), h("span", {}, "Mi perfil")),
      h("button", { class: "side-i", type: "button", onclick: alSalir }, icono("salir"), h("span", {}, "Cerrar sesión")),
    ),
  );
}

function franjaConsulta(alCambiar) {
  if (!enConsulta()) return null;
  return h(
    "div",
    { class: "franja", role: "status" },
    h("span", {}, `Modo consulta · ${estado.consulta.nombre} · solo lectura`),
    h(
      "button",
      {
        class: "btn btn-sm",
        type: "button",
        onclick: () => {
          fijarConsulta(null);
          alCambiar("#/plataforma/cooperativas");
        },
      },
      "Salir de la consulta",
    ),
  );
}

/** vista: { titulo, migas: [[texto, ruta?]], accion: Node, secciones: [[texto, ruta]], contenido } */
export function estructura(vista, hash, { alSalir, navegar }) {
  const migas = vista.migas?.length
    ? h(
        "nav",
        { class: "migas", "aria-label": "Ruta de navegación" },
        vista.migas.map(([texto, ruta], i) => [i > 0 && h("span", { "aria-hidden": "true" }, "/"), ruta ? h("a", { href: ruta }, texto) : h("span", {}, texto)]),
      )
    : null;

  const encabezado = h(
    "header",
    { class: "encabezado" },
    h(
      "button",
      {
        class: "icon-btn menu-btn",
        type: "button",
        "aria-label": "Abrir menú",
        "aria-controls": "barra-lateral",
        onclick: () => document.body.classList.add("side-abierta"),
      },
      icono("menu"),
    ),
    h("div", { class: "encabezado-t" }, migas, h("h1", {}, vista.titulo)),
    // Como máximo un botón principal, y nunca en modo consulta.
    rolEfectivo() === "consulta" ? null : (vista.accion ?? null),
  );

  const secciones = vista.secciones?.length
    ? h(
        "nav",
        { class: "secciones", "aria-label": "Secciones" },
        vista.secciones.map(([texto, ruta]) => h("a", { href: ruta, "aria-current": hash === ruta ? "page" : false }, texto)),
      )
    : null;

  return [
    barraLateral(hash, alSalir),
    h("button", { class: "side-scrim", type: "button", "aria-label": "Cerrar menú", onclick: cerrarMenu }),
    h(
      "main",
      { class: "principal" },
      franjaConsulta(navegar),
      encabezado,
      secciones,
      h("div", { class: "contenido" }, vista.contenido),
    ),
  ];
}

// Estructura de toda pantalla, con el aspecto del diseño de referencia: barra lateral (que se
// puede contraer), barra superior con la ruta de navegación, encabezado (título y como máximo
// un botón principal) y secciones como control segmentado. Bajo 900 px la barra se pliega en un menú.

import { enConsulta, estado, fijarConsulta, nombreCooperativa, rolEfectivo, ROTULOS_ROL } from "./estado.js";
import { alternarMenu, cambiarTema, menuContraido, temaActual } from "./preferencias.js";
import { avatar, h, icono, marca } from "./ui.js";

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
  // El detalle de una tanda o de un DOP pertenece al módulo Lotes y proceso.
  if (ruta === "#/lotes" && (hash.startsWith("#/tandas/") || hash.startsWith("#/dops/"))) return true;
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
        { class: "side-i", href: item.ruta, title: item.texto, "aria-current": activo(item.ruta, hash) ? "page" : false, onclick: cerrarMenu },
        icono(item.icono),
        h("span", { class: "side-t" }, item.texto),
      ),
    ),
  ]);

  const contraer = h(
    "button",
    {
      class: "side-i side-contraer",
      type: "button",
      "aria-pressed": String(menuContraido()),
      title: "Contraer o expandir el menú",
      onclick: (e) => {
        alternarMenu();
        e.currentTarget.setAttribute("aria-pressed", String(menuContraido()));
      },
    },
    icono("collapse"),
    h("span", { class: "side-t" }, "Contraer menú"),
  );

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
        { class: "side-user", title: `${usuario.nombres} ${usuario.apellidos}` },
        avatar(usuario.nombres, usuario.apellidos, "sm"),
        h(
          "span",
          { class: "side-user-t side-t" },
          h("b", {}, `${usuario.nombres} ${usuario.apellidos}`),
          h("span", {}, ROTULOS_ROL[usuario.rol]),
        ),
      ),
      usuario.rol !== "productor" &&
        h(
          "a",
          { class: "side-i", href: "#/mi-perfil", title: "Mi perfil", "aria-current": hash === "#/mi-perfil" ? "page" : false },
          icono("perfil"),
          h("span", { class: "side-t" }, "Mi perfil"),
        ),
      h("button", { class: "side-i", type: "button", title: "Cerrar sesión", onclick: alSalir }, icono("salir"), h("span", { class: "side-t" }, "Cerrar sesión")),
      contraer,
    ),
  );
}

function botonTema() {
  const etiqueta = () => (temaActual() === "dark" ? "Usar tema claro" : "Usar tema oscuro");
  const boton = h("button", { class: "icon-btn", type: "button", "aria-label": etiqueta(), title: etiqueta() });
  const pintar = () => {
    boton.replaceChildren(icono(temaActual() === "dark" ? "sun" : "moon"));
    boton.setAttribute("aria-label", etiqueta());
    boton.title = etiqueta();
  };
  boton.addEventListener("click", () => {
    cambiarTema();
    pintar();
  });
  pintar();
  return boton;
}

/** Ruta de navegación de la barra superior: el último tramo va en negrita. */
function ruta(migas) {
  return h(
    "nav",
    { class: "crumb", "aria-label": "Ruta de navegación" },
    migas.map(([texto, destino], i) => {
      const ultimo = i === migas.length - 1;
      return [
        i > 0 && icono("chev", "crumb-sep"),
        ultimo ? h("b", { "aria-current": "page" }, texto) : destino ? h("a", { href: destino }, texto) : h("span", {}, texto),
      ];
    }),
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

/**
 * vista: { titulo, migas: [[texto, ruta?]], antetitulo, descripcion, accion: Node,
 *          secciones: [[texto, ruta]], cabecera: Node, contenido }
 * `cabecera` reemplaza al encabezado común; las fichas (productor, parcela, cooperativa) pasan
 * null porque muestran el título dentro de su propio panel, como en el diseño.
 */
export function estructura(vista, hash, { alSalir, navegar }) {
  const barraSuperior = h(
    "header",
    { class: "nav" },
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
    ruta(vista.migas?.length ? vista.migas : [[vista.titulo]]),
    h("div", { class: "nav-r" }, botonTema()),
  );

  // Como máximo un botón principal, y nunca en modo consulta.
  const accion = rolEfectivo() === "consulta" ? null : (vista.accion ?? null);
  const encabezado =
    "cabecera" in vista
      ? vista.cabecera
      : h(
      "header",
      { class: "tab-head" },
      h(
        "div",
        { class: "tab-head-t" },
        vista.antetitulo && h("span", { class: "eyebrow" }, vista.antetitulo),
        h("h1", {}, vista.titulo),
        vista.descripcion && h("p", {}, vista.descripcion),
      ),
      accion && h("div", { class: "tab-tools" }, accion),
    );

  const secciones = vista.secciones?.length
    ? h(
        "div",
        { class: "seg-scroll" },
        h(
          "nav",
          { class: "seg", "aria-label": "Secciones" },
          vista.secciones.map(([texto, destino]) => h("a", { href: destino, "aria-current": hash === destino ? "page" : false }, texto)),
        ),
      )
    : null;

  return [
    barraLateral(hash, alSalir),
    h("button", { class: "side-scrim", type: "button", "aria-label": "Cerrar menú", onclick: cerrarMenu }),
    h(
      "main",
      { class: "principal" },
      barraSuperior,
      franjaConsulta(navegar),
      h("div", { class: "contenido" }, encabezado, secciones, vista.contenido),
    ),
  ];
}

// Plataforma · detalle de una cooperativa: datos, estado, administradores y consulta.

import { llamarApi } from "../api.js";
import { enConsulta } from "../estado.js";
import {
  abrirModal,
  avatar,
  cabeceraFicha,
  campo,
  confirmar,
  enviarCon,
  fecha,
  h,
  icono,
  mostrarClaveTemporal,
  rejilla,
  seccion,
  sinVacios,
  toast,
} from "../ui.js";
import { TIPOS_ORGANIZACION } from "../textos.js";
import { camposUbigeo, lugares } from "../ubigeo.js";
import { consultar, insigniaEstado } from "./cooperativas.js";

function abrirEdicion(c, alGuardar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-editar-coop" }, "Guardar");
  const [departamento, provincia, distrito] = camposUbigeo(c);
  const formulario = h(
    "form",
    { class: "form", id: "form-editar-coop" },
    campo({ etiqueta: "Razón social", name: "razon_social", required: true, value: c.razon_social, maxlength: 200 }),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Nombre comercial", name: "nombre_comercial", value: c.nombre_comercial ?? "", maxlength: 200 }),
      campo({ etiqueta: "RUC", name: "ruc", required: true, value: c.ruc, pattern: "[0-9]{11}", maxlength: 11, class: "input mono" }),
    ),
    h(
      "div",
      { class: "grid2" },
      departamento,
      provincia,
    ),
    distrito,
    campo({ etiqueta: "Tipo de organización", name: "tipo_organizacion", opciones: TIPOS_ORGANIZACION, value: c.tipo_organizacion }),
    // Solo las cooperativas creadas antes de la Parte 5 llegan sin código; se fija una sola vez.
    !c.codigo &&
      campo({
        etiqueta: "Código de la cooperativa",
        name: "codigo",
        pattern: "[A-Za-z]{3,6}",
        minlength: 3,
        maxlength: 6,
        title: "De 3 a 6 letras",
        class: "input mono",
        autocomplete: "off",
        ayuda: "De 3 a 6 letras. Va en el código de cada DOP y no cambia después.",
      }),
  );
  const { cerrar } = abrirModal({
    titulo: "Editar cooperativa",
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = sinVacios(datos);
    if (!datos.nombre_comercial) cuerpo.nombre_comercial = null;
    if (cuerpo.codigo) cuerpo.codigo = cuerpo.codigo.trim().toUpperCase();
    await llamarApi(`/admin/cooperativas/${c.id}`, { metodo: "PATCH", cuerpo });
    cerrar();
    toast("Cooperativa actualizada.");
    alGuardar();
  });
}

function abrirNuevoAdmin(c, alCrear) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-admin" }, "Crear administrador");
  const formulario = h(
    "form",
    { class: "form", id: "form-admin" },
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Nombres", name: "nombres", required: true, maxlength: 200 }),
      campo({ etiqueta: "Apellidos", name: "apellidos", required: true, maxlength: 200 }),
    ),
    campo({ etiqueta: "Correo", name: "correo", type: "email", required: true, autocomplete: "off" }),
  );
  const { cerrar } = abrirModal({
    titulo: "Agregar administrador",
    subtitulo: c.nombre_comercial || c.razon_social,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    const creada = await llamarApi(`/admin/cooperativas/${c.id}/administradores`, { metodo: "POST", cuerpo: datos });
    cerrar();
    const u = creada.usuario;
    mostrarClaveTemporal({ titulo: "Administrador creado", persona: `${u.nombres} ${u.apellidos}`, usuario: u.correo })(creada);
    alCrear();
  });
}

export default async function cooperativaDetalle({ parametros, navegar, recargar }) {
  const c = await llamarApi(`/admin/cooperativas/${parametros[0]}`, { sinConsulta: true });
  const nombre = c.nombre_comercial || c.razon_social;
  const soloLectura = enConsulta();

  async function cambiarEstado() {
    const suspender = c.estado === "activa";
    const seguro = await confirmar({
      titulo: suspender ? "Suspender cooperativa" : "Reactivar cooperativa",
      texto: suspender
        ? `Ningún usuario de ${nombre} podrá operar mientras esté suspendida. Sus datos se conservan.`
        : `Todos los usuarios activos de ${nombre} podrán volver a entrar.`,
      boton: suspender ? "Suspender" : "Reactivar",
      peligro: suspender,
    });
    if (!seguro) return;
    try {
      await llamarApi(`/admin/cooperativas/${c.id}`, { metodo: "PATCH", cuerpo: { estado: suspender ? "suspendida" : "activa" } });
      toast(suspender ? "Cooperativa suspendida." : "Cooperativa reactivada.");
      recargar();
    } catch (error) {
      toast(error.message, "bad");
    }
  }

  async function restablecer(admin) {
    const persona = `${admin.nombres} ${admin.apellidos}`;
    const seguro = await confirmar({
      titulo: "Restablecer contraseña",
      texto: `Se generará una nueva contraseña temporal para ${persona} y se cerrarán sus sesiones abiertas.`,
      boton: "Restablecer",
    });
    if (!seguro) return;
    try {
      const respuesta = await llamarApi(`/admin/usuarios/${admin.id}/restablecer-clave`, { metodo: "POST" });
      mostrarClaveTemporal({ titulo: "Nueva contraseña temporal", persona, usuario: admin.correo })(respuesta);
    } catch (error) {
      toast(error.message, "bad");
    }
  }

  // Los administradores se leen con el modo consulta de esa cooperativa (queda auditado).
  const administradores = h("div", { class: "tbl-box" }, h("p", { class: "panel-sub sect-espera" }, "Cargando…"));
  cargarAdministradores();

  async function cargarAdministradores() {
    try {
      const datos = await llamarApi("/usuarios", { parametros: { por_pagina: 100 }, cooperativa: c.id });
      const admins = datos.items.filter((u) => u.rol === "admin_cooperativa");
      administradores.replaceChildren(
        admins.length
          ? h(
              "table",
              { class: "tabla" },
              h("tbody", {}, admins.map((a) =>
                h(
                  "tr",
                  {},
                  h("td", {}, h("span", { class: "persona" }, avatar(a.nombres, a.apellidos, "sm"), h("span", {}, h("b", {}, `${a.nombres} ${a.apellidos}`), h("span", { class: "sec" }, a.correo)))),
                  h("td", {}, a.activo ? "Activo" : "Desactivado"),
                  h("td", { class: "acciones" }, !soloLectura && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => restablecer(a) }, "Restablecer clave")),
                ),
              )),
            )
          : h("p", { class: "panel-sub sect-espera" }, "Sin administradores."),
      );
    } catch (error) {
      administradores.replaceChildren(h("p", { class: "panel-sub" }, error.message));
    }
  }

  return {
    titulo: nombre,
    migas: [["Plataforma"], ["Cooperativas", "#/plataforma/cooperativas"], [nombre]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("cooperativa")),
        titulo: nombre,
        insignias: [insigniaEstado(c), c.es_demo && h("span", { class: "badge info" }, h("span", { class: "dot" }), "Demostración")],
        detalle: [h("span", { class: "mono" }, `RUC ${c.ruc}`), ` · ${lugares(c.distrito, c.provincia, c.departamento)}`],
        cifra: String(c.productores),
        cifraTexto: c.productores === 1 ? "productor afiliado" : "productores afiliados",
        accion: !soloLectura && h("button", { class: "btn btn-primary", type: "button", onclick: () => consultar(c, navegar) }, icono("eye"), "Consultar cooperativa"),
      }),
      seccion({
        titulo: "Datos de la cooperativa",
        sub: `Creada el ${fecha(c.creado_en)}`,
        acciones: !soloLectura && [
          h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirEdicion(c, recargar) }, icono("wrench"), "Editar datos"),
          h("button", { class: `btn btn-sm ${c.estado === "activa" ? "btn-danger" : ""}`, type: "button", onclick: cambiarEstado }, c.estado === "activa" ? "Suspender" : "Reactivar"),
        ],
        contenido: rejilla([
          { etiqueta: "Razón social", valor: c.razon_social },
          { etiqueta: "Nombre comercial", valor: c.nombre_comercial },
          { etiqueta: "RUC", valor: c.ruc, mono: true },
          {
            etiqueta: "Código de la cooperativa",
            valor: c.codigo,
            mono: true,
            extra: !c.codigo && "Falta: sin código la cooperativa no recibe tandas. Fíjalo en Editar datos.",
          },
          { etiqueta: "Tipo de organización", valor: TIPOS_ORGANIZACION.find(([v]) => v === c.tipo_organizacion)?.[1] ?? c.tipo_organizacion },
          { etiqueta: "Ubicación", valor: lugares(c.distrito, c.provincia, c.departamento) },
          { etiqueta: "Usuarios del personal", valor: String(c.usuarios), mono: true },
          { etiqueta: "Productores afiliados", valor: String(c.productores), mono: true },
        ]),
      }),
      seccion({
        titulo: "Administradores",
        acciones: !soloLectura && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirNuevoAdmin(c, cargarAdministradores) }, icono("mas"), "Agregar administrador"),
        contenido: administradores,
      }),
    ),
  };
}

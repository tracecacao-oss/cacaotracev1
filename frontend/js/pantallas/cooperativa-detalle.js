// Plataforma · detalle de una cooperativa: datos, estado, administradores y consulta.

import { llamarApi } from "../api.js";
import { enConsulta } from "../estado.js";
import { abrirModal, campo, confirmar, enviarCon, fecha, h, mostrarClaveTemporal, sinVacios, toast } from "../ui.js";
import { camposUbigeo } from "../ubigeo.js";
import { consultar, insigniaEstado } from "./cooperativas.js";

function dato(etiqueta, valor, mono = false) {
  return h("div", {}, h("dt", {}, etiqueta), h("dd", { class: mono ? "mono" : null }, valor ?? "—"));
}

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
  );
  const { cerrar } = abrirModal({
    titulo: "Editar cooperativa",
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = sinVacios(datos);
    if (!datos.nombre_comercial) cuerpo.nombre_comercial = null;
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
  const administradores = h("div", { class: "panel-b" }, "Cargando…");
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
                  h("td", {}, `${a.nombres} ${a.apellidos}`, h("span", { class: "sec" }, a.correo)),
                  h("td", {}, a.activo ? "Activo" : "Desactivado"),
                  h("td", { class: "acciones" }, !soloLectura && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => restablecer(a) }, "Restablecer clave")),
                ),
              )),
            )
          : h("p", { class: "panel-sub" }, "Sin administradores."),
      );
    } catch (error) {
      administradores.replaceChildren(h("p", { class: "panel-sub" }, error.message));
    }
  }

  return {
    titulo: nombre,
    migas: [["Plataforma"], ["Cooperativas", "#/plataforma/cooperativas"], [nombre]],
    accion: h("button", { class: "btn btn-primary", type: "button", onclick: () => consultar(c, navegar) }, "Consultar cooperativa"),
    contenido: [
      h(
        "section",
        { class: "panel" },
        h(
          "div",
          { class: "panel-h" },
          h("div", {}, h("h2", {}, "Datos de la cooperativa"), h("p", { class: "panel-sub" }, `Creada el ${fecha(c.creado_en)}${c.es_demo ? " · demostración" : ""}`)),
          insigniaEstado(c),
        ),
        h(
          "dl",
          { class: "panel-b ficha" },
          dato("Razón social", c.razon_social),
          dato("Nombre comercial", c.nombre_comercial),
          dato("RUC", c.ruc, true),
          dato("Ubicación", `${c.distrito}, ${c.provincia}, ${c.departamento}`),
          dato("Usuarios del personal", String(c.usuarios), true),
          dato("Productores afiliados", String(c.productores), true),
        ),
        !soloLectura &&
          h(
            "div",
            { class: "panel-b fila-acciones" },
            h("button", { class: "btn", type: "button", onclick: () => abrirEdicion(c, recargar) }, "Editar datos"),
            h("button", { class: `btn ${c.estado === "activa" ? "btn-danger" : ""}`, type: "button", onclick: cambiarEstado }, c.estado === "activa" ? "Suspender" : "Reactivar"),
          ),
      ),
      h(
        "section",
        { class: "panel" },
        h(
          "div",
          { class: "panel-h" },
          h("h2", {}, "Administradores"),
          !soloLectura && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirNuevoAdmin(c, cargarAdministradores) }, "Agregar administrador"),
        ),
        administradores,
      ),
    ],
  };
}

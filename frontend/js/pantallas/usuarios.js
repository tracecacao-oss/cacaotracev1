// Usuarios: lista del personal, alta, cambio de rol, desactivación y restablecimiento de contraseña.

import { llamarApi } from "../api.js";
import { estado, puede, ROTULOS_ROL } from "../estado.js";
import {
  abrirModal,
  avatar,
  buscador,
  campo,
  cargando,
  conRetraso,
  confirmar,
  enviarCon,
  errorDeCarga,
  fecha,
  h,
  icono,
  mostrarClaveTemporal,
  paginador,
  reemplazar,
  toast,
  vacio,
} from "../ui.js";

const ROLES_PERSONAL = [
  ["operador", "Operador · registra y edita datos"],
  ["lector", "Lector · solo lectura"],
  ["admin_cooperativa", "Administrador · todo, incluido el personal"],
];

function abrirAlta(alCrear) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-usuario" }, "Crear cuenta");
  const formulario = h(
    "form",
    { class: "form", id: "form-usuario" },
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Nombres", name: "nombres", required: true, maxlength: 200 }),
      campo({ etiqueta: "Apellidos", name: "apellidos", required: true, maxlength: 200 }),
    ),
    campo({ etiqueta: "Correo", name: "correo", type: "email", required: true, autocomplete: "off" }),
    campo({ etiqueta: "Rol", name: "rol", opciones: ROLES_PERSONAL, required: true }),
  );
  const { cerrar } = abrirModal({
    titulo: "Agregar usuario",
    subtitulo: "Recibirás una contraseña temporal para entregarle.",
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    const creada = await llamarApi("/usuarios", { metodo: "POST", cuerpo: datos });
    cerrar();
    alCrear(creada);
  });
}

function abrirEdicion(usuario, alGuardar) {
  const propio = usuario.id === estado.usuario.id;
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-edicion" }, "Guardar");
  const formulario = h(
    "form",
    { class: "form", id: "form-edicion" },
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Nombres", name: "nombres", required: true, value: usuario.nombres, maxlength: 200 }),
      campo({ etiqueta: "Apellidos", name: "apellidos", required: true, value: usuario.apellidos, maxlength: 200 }),
    ),
    campo({
      etiqueta: "Rol",
      name: "rol",
      opciones: ROLES_PERSONAL,
      value: usuario.rol,
      disabled: propio,
      ayuda: propio ? "No puedes cambiar tu propio rol." : null,
    }),
  );
  const { cerrar } = abrirModal({
    titulo: "Editar usuario",
    subtitulo: usuario.correo,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    await llamarApi(`/usuarios/${usuario.id}`, { metodo: "PATCH", cuerpo: datos });
    cerrar();
    alGuardar();
  });
}

export default async function usuarios({ recargar }) {
  const gestiona = puede("gestionarUsuarios");
  const lista = h("div", {}, cargando());
  let busqueda = "";
  let pagina = 1;

  async function cargar() {
    try {
      const datos = await llamarApi("/usuarios", { parametros: { q: busqueda, pagina } });
      reemplazar(lista, tabla(datos));
    } catch (error) {
      lista.replaceChildren(errorDeCarga(error));
    }
  }

  async function cambiarEstado(usuario) {
    const desactivar = usuario.activo;
    const nombre = `${usuario.nombres} ${usuario.apellidos}`;
    const seguro = await confirmar({
      titulo: desactivar ? "Desactivar cuenta" : "Reactivar cuenta",
      texto: desactivar
        ? `${nombre} ya no podrá ingresar. La cuenta no se borra y se puede reactivar.`
        : `${nombre} podrá volver a ingresar con su contraseña.`,
      boton: desactivar ? "Desactivar" : "Reactivar",
      peligro: desactivar,
    });
    if (!seguro) return;
    try {
      await llamarApi(`/usuarios/${usuario.id}`, { metodo: "PATCH", cuerpo: { activo: !desactivar } });
      toast(desactivar ? "Cuenta desactivada." : "Cuenta reactivada.");
      cargar();
    } catch (error) {
      toast(error.message, "bad");
    }
  }

  async function restablecer(usuario) {
    const nombre = `${usuario.nombres} ${usuario.apellidos}`;
    const seguro = await confirmar({
      titulo: "Restablecer contraseña",
      texto: `Se generará una nueva contraseña temporal para ${nombre} y se cerrarán sus sesiones abiertas.`,
      boton: "Restablecer",
    });
    if (!seguro) return;
    try {
      const respuesta = await llamarApi(`/usuarios/${usuario.id}/restablecer-clave`, { metodo: "POST" });
      mostrarClaveTemporal({ titulo: "Nueva contraseña temporal", persona: nombre, usuario: usuario.correo })(respuesta);
      cargar();
    } catch (error) {
      toast(error.message, "bad");
    }
  }

  function estadoDe(u) {
    if (!u.activo) return h("span", { class: "badge bad" }, h("span", { class: "dot" }), "Desactivada");
    if (u.debe_cambiar_clave) return h("span", { class: "badge warn" }, h("span", { class: "dot" }), "Clave temporal");
    return h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Activa");
  }

  function tabla(datos) {
    if (datos.total === 0) {
      return vacio({
        titulo: busqueda ? "Sin resultados" : "Aún no hay personal",
        texto: busqueda ? `Nadie coincide con “${busqueda}”.` : "Aquí aparecen las cuentas del personal de la cooperativa.",
      });
    }
    return [
      h(
        "div",
        { class: "tabla-caja" },
        h(
          "table",
          { class: "tabla" },
          h(
            "thead",
            {},
            h("tr", {}, h("th", {}, "Persona"), h("th", {}, "Rol"), h("th", {}, "Estado"), h("th", { class: "ocultar-sm" }, "Último ingreso"), gestiona && h("th", {}, h("span", { class: "sr-only" }, "Acciones"))),
          ),
          h(
            "tbody",
            {},
            datos.items.map((u) =>
              h(
                "tr",
                {},
                h(
                  "td",
                  {},
                  h("span", { class: "persona" }, avatar(u.nombres, u.apellidos, "sm"), h("span", {}, h("b", {}, `${u.nombres} ${u.apellidos}`), h("span", { class: "sec" }, u.correo))),
                ),
                h("td", {}, ROTULOS_ROL[u.rol]),
                h("td", {}, estadoDe(u)),
                h("td", { class: "ocultar-sm fecha" }, fecha(u.ultimo_acceso_en, { hora: true })),
                gestiona &&
                  h(
                    "td",
                    { class: "acciones" },
                    h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirEdicion(u, cargar) }, "Editar"),
                    h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => restablecer(u) }, "Restablecer clave"),
                    u.id !== estado.usuario.id &&
                      h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => cambiarEstado(u) }, u.activo ? "Desactivar" : "Reactivar"),
                  ),
              ),
            ),
          ),
        ),
      ),
      paginador(datos, (nueva) => {
        pagina = nueva;
        cargar();
      }),
    ];
  }

  const buscar = conRetraso((valor) => {
    busqueda = valor.trim();
    pagina = 1;
    cargar();
  });
  cargar();

  return {
    titulo: "Usuarios",
    antetitulo: "Cooperativa",
    descripcion: "Personas que trabajan en CacaoTrace por la cooperativa, con su rol y su último ingreso.",
    migas: [["Cooperativa", "#/cooperativa"], ["Usuarios"]],
    accion:
      gestiona &&
      h(
        "button",
        {
          class: "btn btn-primary",
          type: "button",
          onclick: () =>
            abrirAlta((creada) => {
              const u = creada.usuario;
              mostrarClaveTemporal({ titulo: "Cuenta creada", persona: `${u.nombres} ${u.apellidos}`, usuario: u.correo })(creada);
              recargar();
            }),
        },
        icono("mas"),
        "Agregar usuario",
      ),
    contenido: h(
      "section",
      { class: "panel" },
      h(
        "div",
        { class: "barra-lista" },
        buscador({ placeholder: "Buscar por nombre o correo", etiqueta: "Buscar usuarios", alEscribir: buscar }),
      ),
      lista,
    ),
  };
}

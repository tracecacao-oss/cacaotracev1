// Auditoría: tabla de acciones con filtros por fecha, usuario y acción.

import { llamarApi } from "../api.js";
import { ROTULOS_ROL } from "../estado.js";
import { cargando, errorDeCarga, fecha, h, paginador, reemplazar, vacio } from "../ui.js";
import { seccionesCooperativa } from "./vacia.js";

const ACCIONES = [
  ["", "Todas las acciones"],
  ["cooperativa.", "Cooperativa"],
  ["usuario.", "Usuarios"],
  ["productor.", "Productores"],
  ["parcela.", "Parcelas"],
  ["documento.", "Documentos"],
  ["superposicion.", "Superposiciones"],
  ["superadmin.", "Consultas de soporte"],
];

const TEXTO_ACCION = {
  "cooperativa.crear": "Creó la cooperativa",
  "cooperativa.editar": "Editó la cooperativa",
  "cooperativa.suspender": "Suspendió la cooperativa",
  "cooperativa.reactivar": "Reactivó la cooperativa",
  "usuario.crear": "Creó una cuenta",
  "usuario.editar": "Editó una cuenta",
  "usuario.desactivar": "Desactivó una cuenta",
  "usuario.reactivar": "Reactivó una cuenta",
  "usuario.restablecer_clave": "Restableció una contraseña",
  "usuario.cambiar_clave": "Cambió su contraseña",
  "productor.crear": "Registró un productor",
  "productor.acceso_crear": "Creó el acceso de un productor",
  "productor.acceso_desactivar": "Desactivó el acceso de un productor",
  "productor.consentimiento": "Registró el consentimiento de datos",
  "productor.editar": "Editó la ficha de un productor",
  "productor.cerrar_afiliacion": "Cerró la afiliación de un productor",
  "documento.cargar": "Cargó un documento",
  "documento.anular": "Anuló un documento",
  "parcela.crear": "Registró una parcela",
  "parcela.editar": "Editó los datos de una parcela",
  "parcela.editar_geometria": "Cambió la geometría de una parcela",
  "parcela.desactivar": "Desactivó una parcela",
  "superposicion.aceptar": "Aceptó una superposición",
  "superadmin.consultar_cooperativa": "Consultó la cooperativa (soporte)",
};

function resumen(detalle) {
  const partes = Object.entries(detalle ?? {}).map(([campo, valor]) => {
    if (valor && typeof valor === "object" && "antes" in valor) return `${campo}: ${valor.antes ?? "—"} → ${valor.despues ?? "—"}`;
    if (campo === "geometria_anterior") return "geometría anterior guardada";
    return `${campo}: ${typeof valor === "object" ? JSON.stringify(valor) : valor}`;
  });
  return partes.join(" · ");
}

export default async function auditoria() {
  const filtros = { desde: "", hasta: "", usuario_id: "", accion: "" };
  let pagina = 1;
  const lista = h("div", {}, cargando());

  // El filtro por usuario lista al personal de la cooperativa.
  const personal = await llamarApi("/usuarios", { parametros: { por_pagina: 100 } }).catch(() => ({ items: [] }));

  async function cargar() {
    try {
      const datos = await llamarApi("/auditoria", { parametros: { ...filtros, pagina, por_pagina: 50 } });
      reemplazar(lista, tabla(datos));
    } catch (error) {
      lista.replaceChildren(errorDeCarga(error));
    }
  }

  function tabla(datos) {
    if (datos.total === 0) {
      return vacio({ titulo: "Sin registros", texto: "Aquí queda cada acción que crea o cambia un dato, con su autor y la hora." });
    }
    return [
      h(
        "div",
        { class: "tabla-caja" },
        h(
          "table",
          { class: "tabla" },
          h("thead", {}, h("tr", {}, h("th", {}, "Fecha y hora"), h("th", {}, "Usuario"), h("th", {}, "Acción"), h("th", { class: "ocultar-sm" }, "Detalle"))),
          h(
            "tbody",
            {},
            datos.items.map((a) =>
              h(
                "tr",
                {},
                h("td", { class: "mono fecha" }, fecha(a.ocurrido_en, { hora: true })),
                h("td", { class: "sin-corte" }, a.usuario_nombre?.trim() || "Sistema", a.rol && h("span", { class: "sec" }, ROTULOS_ROL[a.rol] ?? a.rol)),
                h("td", { class: "sin-corte" }, TEXTO_ACCION[a.accion] ?? a.accion, h("span", { class: "sec mono" }, a.accion)),
                h("td", { class: "ocultar-sm detalle" }, h("span", { class: "sec" }, resumen(a.detalle))),
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

  function filtro(nombre, control) {
    control.addEventListener("change", () => {
      filtros[nombre] = control.value;
      pagina = 1;
      cargar();
    });
    return control;
  }

  cargar();
  return {
    titulo: "Auditoría",
    antetitulo: "Cooperativa",
    descripcion: "Cada acción que crea o cambia un dato, con su autor y la hora.",
    migas: [["Cooperativa", "#/cooperativa"], ["Auditoría"]],
    secciones: seccionesCooperativa(),
    contenido: h(
      "section",
      { class: "panel" },
      h(
        "div",
        { class: "barra-lista filtros" },
        h("label", { class: "field" }, "Desde", filtro("desde", h("input", { class: "input", type: "date" }))),
        h("label", { class: "field" }, "Hasta", filtro("hasta", h("input", { class: "input", type: "date" }))),
        h(
          "label",
          { class: "field" },
          "Usuario",
          filtro(
            "usuario_id",
            h("select", { class: "select" }, h("option", { value: "" }, "Todos"), personal.items.map((u) => h("option", { value: u.id }, `${u.nombres} ${u.apellidos}`))),
          ),
        ),
        h("label", { class: "field" }, "Acción", filtro("accion", h("select", { class: "select" }, ACCIONES.map(([v, t]) => h("option", { value: v }, t))))),
      ),
      lista,
    ),
  };
}

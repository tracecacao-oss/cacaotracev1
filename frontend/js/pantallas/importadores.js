// Importadores (tercera sección de Exportación): registros de la cooperativa, no usuarios. Nombre, dirección
// y correo son los datos del operador que el DEX entrega con los nombres de campo del Anexo II.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { abrirModal, campo, enviarCon, h, icono, seccion, toast, vacio } from "../ui.js";

/** Campos del importador; los usa también el primer paso de "Nueva orden". */
export function camposImportador(i = {}) {
  return [
    campo({ etiqueta: "Razón social", name: "razon_social", value: i.razon_social ?? "", required: true, maxlength: 200 }),
    campo({ etiqueta: "Dirección postal", name: "direccion", value: i.direccion ?? "", required: true, maxlength: 400 }),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "País", name: "pais", value: i.pais ?? "", required: true, maxlength: 200 }),
      campo({ etiqueta: "Correo de contacto", name: "correo", type: "email", value: i.correo ?? "", required: true, maxlength: 254 }),
    ),
    campo({ etiqueta: "Número EORI (opcional)", name: "eori", value: i.eori ?? "", maxlength: 17, class: "input mono", ayuda: "Dos letras del país y hasta 15 caracteres, por ejemplo DE123456789012345." }),
  ];
}

export function cuerpoImportador(datos) {
  return {
    razon_social: datos.razon_social,
    direccion: datos.direccion,
    pais: datos.pais,
    correo: datos.correo,
    eori: datos.eori?.trim() || null,
  };
}

function abrirFormulario(importador, alGuardar) {
  const nuevo = !importador;
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-importador" }, nuevo ? "Registrar importador" : "Guardar");
  const formulario = h(
    "form",
    { class: "form", id: "form-importador" },
    camposImportador(importador ?? {}),
    !nuevo && h("label", { class: "check" }, h("input", { type: "checkbox", name: "activo", value: "si", checked: importador.activo }), h("span", {}, "Activo. Un importador desactivado ya no recibe órdenes nuevas; sus órdenes se conservan.")),
  );
  const { cerrar } = abrirModal({
    titulo: nuevo ? "Nuevo importador" : "Editar importador",
    subtitulo: nuevo ? "El importador no inicia sesión: es un registro de la cooperativa." : importador.razon_social,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = cuerpoImportador(datos);
    if (nuevo) await llamarApi("/importadores", { metodo: "POST", cuerpo });
    else await llamarApi(`/importadores/${importador.id}`, { metodo: "PATCH", cuerpo: { ...cuerpo, activo: datos.activo === "si" } });
    cerrar();
    toast(nuevo ? "Importador registrado." : "Importador actualizado.");
    alGuardar();
  });
}

export default async function importadores({ recargar }) {
  const lista = await llamarApi("/importadores");
  const opera = ["admin_cooperativa", "operador"].includes(rolEfectivo());
  const tabla = lista.length
    ? h(
        "div",
        { class: "tbl-box" },
        h(
          "table",
          { class: "tabla" },
          h("thead", {}, h("tr", {}, h("th", {}, "Importador"), h("th", { class: "ocultar-sm" }, "Dirección"), h("th", {}, "Correo"), h("th", {}, "Estado"), opera && h("th", {}, h("span", { class: "sr-only" }, "Acciones")))),
          h(
            "tbody",
            {},
            lista.map((i) =>
              h(
                "tr",
                {},
                h("td", {}, h("b", {}, i.razon_social), h("span", { class: "sec" }, [i.pais, i.eori && `EORI ${i.eori}`].filter(Boolean).join(" · "))),
                h("td", { class: "ocultar-sm" }, i.direccion),
                h("td", {}, i.correo),
                h("td", {}, i.activo ? h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Activo") : h("span", { class: "badge" }, h("span", { class: "dot" }), "Inactivo")),
                opera && h("td", { class: "acciones" }, h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirFormulario(i, recargar) }, "Editar")),
              ),
            ),
          ),
        ),
      )
    : vacio({ titulo: "Sin importadores", texto: "Registra al importador que te envía órdenes de compra." });
  return {
    titulo: "Importadores",
    antetitulo: "Exportación",
    descripcion: "Quienes compran el cacao de la cooperativa. No inician sesión.",
    migas: [["Exportación", "#/exportacion"], ["Importadores"]],
    accion: opera && h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirFormulario(null, recargar) }, icono("plus"), "Nuevo importador"),
    contenido: h("section", { class: "panel inspector" }, seccion({ titulo: "Importadores", contenido: tabla })),
  };
}

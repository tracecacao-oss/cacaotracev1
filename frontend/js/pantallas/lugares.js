// Lugares de la cooperativa (Parte 5): canchas de acopio, plantas y almacenes. La tanda se recibe en
// una cancha de acopio; el proceso de la Parte 6 usa los demás. Solo el administrador los crea y edita.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { TIPOS_LUGAR } from "../textos.js";
import { abrirModal, campo, enviarCon, h, icono, seccion, toast, vacio } from "../ui.js";
import { camposUbigeo } from "../ubigeo.js";
import { seccionesCooperativa } from "./vacia.js";

const tipoTexto = (tipo) => TIPOS_LUGAR.find(([v]) => v === tipo)?.[1] ?? tipo;

function abrirFormulario(lugar, alGuardar) {
  const nuevo = !lugar;
  const l = lugar ?? { tipo: "cancha_acopio" };
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-lugar" }, nuevo ? "Crear lugar" : "Guardar");
  const [departamento, provincia, distrito] = camposUbigeo(l);
  const latitud = campo({ etiqueta: "Latitud (opcional)", name: "latitud", type: "number", step: "0.000001", min: "-90", max: "90", inputmode: "decimal", value: l.latitud ?? "", class: "input mono" });
  const longitud = campo({ etiqueta: "Longitud (opcional)", name: "longitud", type: "number", step: "0.000001", min: "-180", max: "180", inputmode: "decimal", value: l.longitud ?? "", class: "input mono" });
  const ubicarme = h(
    "button",
    {
      class: "btn btn-sm btn-ghost",
      type: "button",
      onclick: () => {
        if (!navigator.geolocation) return toast("Este navegador no da la ubicación.", "bad");
        navigator.geolocation.getCurrentPosition(
          ({ coords }) => {
            latitud.querySelector("input").value = coords.latitude.toFixed(6);
            longitud.querySelector("input").value = coords.longitude.toFixed(6);
          },
          () => toast("No se pudo obtener la ubicación.", "bad"),
          { enableHighAccuracy: true, timeout: 15000 },
        );
      },
    },
    icono("pin"),
    "Usar mi ubicación actual",
  );
  const formulario = h(
    "form",
    { class: "form", id: "form-lugar" },
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Nombre", name: "nombre", value: l.nombre ?? "", required: true, maxlength: 200 }),
      campo({ etiqueta: "Tipo", name: "tipo", opciones: TIPOS_LUGAR, value: l.tipo, required: true }),
    ),
    h("div", { class: "grid2" }, departamento, provincia),
    distrito,
    h("div", { class: "grid2" }, latitud, longitud),
    ubicarme,
    !nuevo && h("label", { class: "check" }, h("input", { type: "checkbox", name: "activo", value: "si", checked: l.activo }), h("span", {}, "Activo. Un lugar inactivo ya no recibe tandas; su historial se conserva.")),
  );
  const { cerrar } = abrirModal({
    titulo: nuevo ? "Nuevo lugar" : "Editar lugar",
    subtitulo: nuevo ? "Una cancha de acopio, una planta o un almacén de la cooperativa." : l.nombre,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = {
      nombre: datos.nombre,
      tipo: datos.tipo,
      departamento: datos.departamento,
      provincia: datos.provincia,
      distrito: datos.distrito,
      latitud: datos.latitud || null,
      longitud: datos.longitud || null,
    };
    if (nuevo) {
      await llamarApi("/lugares", { metodo: "POST", cuerpo });
    } else {
      await llamarApi(`/lugares/${l.id}`, { metodo: "PATCH", cuerpo: { ...cuerpo, activo: datos.activo === "si" } });
    }
    cerrar();
    toast(nuevo ? "Lugar creado." : "Lugar actualizado.");
    alGuardar();
  });
}

export default async function lugares({ recargar }) {
  const lista = await llamarApi("/lugares");
  const admin = rolEfectivo() === "admin_cooperativa";
  const nuevo = admin && h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirFormulario(null, recargar) }, icono("mas"), "Nuevo lugar");

  const tabla = lista.length
    ? h(
        "div",
        { class: "tbl-box" },
        h(
          "table",
          { class: "tabla" },
          h("thead", {}, h("tr", {}, h("th", {}, "Lugar"), h("th", {}, "Tipo"), h("th", { class: "ocultar-sm" }, "Ubicación"), h("th", {}, "Estado"), admin && h("th", {}, h("span", { class: "sr-only" }, "Acciones")))),
          h(
            "tbody",
            {},
            lista.map((l) =>
              h(
                "tr",
                {},
                h("td", {}, h("b", {}, l.nombre), l.latitud != null && h("span", { class: "sec mono" }, `${l.latitud}, ${l.longitud}`)),
                h("td", {}, tipoTexto(l.tipo)),
                h("td", { class: "ocultar-sm" }, `${l.distrito}, ${l.provincia}, ${l.departamento}`),
                h("td", {}, l.activo ? h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Activo") : h("span", { class: "badge" }, h("span", { class: "dot" }), "Inactivo")),
                admin && h("td", { class: "acciones" }, h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirFormulario(l, recargar) }, "Editar")),
              ),
            ),
          ),
        ),
      )
    : vacio({ titulo: "Sin lugares", texto: "Registra al menos una cancha de acopio para recibir tandas." });

  return {
    titulo: "Lugares",
    antetitulo: "Cooperativa",
    descripcion: "Los sitios físicos de la cooperativa. La tanda se pesa en una cancha de acopio.",
    migas: [["Cooperativa", "#/cooperativa"], ["Lugares"]],
    secciones: seccionesCooperativa(),
    accion: nuevo,
    contenido: h("section", { class: "panel inspector" }, seccion({ titulo: "Lugares", contenido: tabla })),
  };
}

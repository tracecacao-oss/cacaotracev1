// Padrón de productores: lista con buscador y alta mínima. La ficha está en productor.js.

import { llamarApi } from "../api.js";
import { textoConsentimiento } from "../consentimiento.js";
import { puede } from "../estado.js";
import {
  reemplazar,
  abrirModal,
  campo,
  cargando,
  conRetraso,
  enviarCon,
  errorDeCarga,
  h,
  icono,
  paginador,
  sinVacios,
  toast,
  vacio,
} from "../ui.js";

export function insigniaAcceso(acceso) {
  if (!acceso.existe) return h("span", { class: "badge" }, h("span", { class: "dot" }), "Sin acceso");
  if (!acceso.activo) return h("span", { class: "badge bad" }, h("span", { class: "dot" }), "Acceso desactivado");
  if (acceso.debe_cambiar_clave) return h("span", { class: "badge warn" }, h("span", { class: "dot" }), "Clave temporal");
  return h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Con acceso");
}

function abrirRegistro(navegar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit" }, "Registrar");
  const formulario = h(
    "form",
    { class: "form" },
    campo({
      etiqueta: "DNI",
      name: "dni",
      inputmode: "numeric",
      pattern: "[0-9]{8}",
      maxlength: 8,
      title: "8 dígitos",
      class: "input mono",
      required: true,
    }),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Nombres", name: "nombres", required: true, maxlength: 200 }),
      campo({ etiqueta: "Apellidos", name: "apellidos", required: true, maxlength: 200 }),
    ),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Teléfono (opcional)", name: "telefono", type: "tel", maxlength: 30 }),
      campo({ etiqueta: "Código de socio (opcional)", name: "codigo_socio", maxlength: 60 }),
    ),
    h(
      "label",
      { class: "check" },
      h("input", { type: "checkbox", name: "consentimiento_cooperativa", value: "si" }),
      h("span", {}, "La cooperativa cuenta con el consentimiento firmado del productor"),
    ),
  );
  const { cerrar } = abrirModal({
    titulo: "Registrar productor",
    subtitulo: "Queda afiliado a tu cooperativa desde hoy.",
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  boton.setAttribute("form", "form-productor");
  formulario.id = "form-productor";

  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = sinVacios(datos);
    if (cuerpo.consentimiento_cooperativa) {
      cuerpo.consentimiento_cooperativa = true;
      cuerpo.version_consentimiento = (await textoConsentimiento()).version;
    }
    const productor = await llamarApi("/productores", { metodo: "POST", cuerpo });
    cerrar();
    toast(`Se registró a ${productor.nombres} ${productor.apellidos}.`);
    navegar(`#/productores/${productor.id}`);
  });
}

export default async function productores({ navegar }) {
  const lista = h("div", {}, cargando());
  let busqueda = "";
  let pagina = 1;
  const puedeRegistrar = puede("registrarProductores");

  async function cargar() {
    try {
      const datos = await llamarApi("/productores", { parametros: { q: busqueda, pagina, por_pagina: 25 } });
      reemplazar(lista, tabla(datos));
    } catch (error) {
      lista.replaceChildren(errorDeCarga(error));
    }
  }

  function tabla(datos) {
    if (datos.total === 0) {
      return busqueda
        ? vacio({ titulo: "Sin resultados", texto: `Ningún productor coincide con “${busqueda}”.` })
        : vacio({
            titulo: "Aún no hay productores",
            texto: "Aquí aparece el padrón de productores afiliados a la cooperativa.",
            accion:
              puedeRegistrar &&
              h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirRegistro(navegar) }, "Registrar el primero"),
          });
    }
    return [
      h(
        "div",
        { class: "tabla-caja" },
        h(
          "table",
          { class: "tabla" },
          h("thead", {}, h("tr", {}, h("th", {}, "Productor"), h("th", {}, "DNI"), h("th", { class: "ocultar-sm" }, "Código de socio"), h("th", { class: "ocultar-sm" }, "Acceso"))),
          h(
            "tbody",
            {},
            datos.items.map((p) =>
              h(
                "tr",
                { class: "clic", onclick: () => navegar(`#/productores/${p.id}`) },
                h("td", {}, h("a", { href: `#/productores/${p.id}` }, `${p.apellidos}, ${p.nombres}`)),
                h("td", { class: "mono" }, p.dni),
                h("td", { class: "ocultar-sm" }, p.codigo_socio ?? "—"),
                h("td", { class: "ocultar-sm" }, insigniaAcceso(p.acceso)),
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
    titulo: "Productores",
    migas: [["Productores"]],
    accion:
      puedeRegistrar &&
      h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirRegistro(navegar) }, icono("mas"), "Registrar productor"),
    contenido: h(
      "section",
      { class: "panel" },
      h(
        "div",
        { class: "barra-lista" },
        h("input", {
          class: "input",
          type: "search",
          placeholder: "Buscar por DNI, nombre o código de socio",
          "aria-label": "Buscar productores",
          oninput: (e) => buscar(e.target.value),
        }),
      ),
      lista,
    ),
  };
}

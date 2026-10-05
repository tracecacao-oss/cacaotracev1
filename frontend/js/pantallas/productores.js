// Padrón de productores: lista con DNI, nombre, parcelas y pendientes; alta en dos pasos.

import { llamarApi } from "../api.js";
import { textoConsentimiento } from "../consentimiento.js";
import { puede } from "../estado.js";
import { PENDIENTES_PERSONAL } from "../textos.js";
import {
  abrirModal,
  campo,
  cargando,
  conRetraso,
  errorDeCarga,
  h,
  icono,
  paginador,
  reemplazar,
  sinVacios,
  toast,
  vacio,
} from "../ui.js";

export function seccionesProductores() {
  return [
    ["Padrón", "#/productores"],
    ["Mapa de parcelas", "#/productores/mapa"],
    ["Superposiciones", "#/productores/superposiciones"],
  ];
}

export function insigniaAcceso(acceso) {
  if (!acceso.existe) return h("span", { class: "badge" }, h("span", { class: "dot" }), "Sin acceso");
  if (!acceso.activo) return h("span", { class: "badge bad" }, h("span", { class: "dot" }), "Acceso desactivado");
  if (acceso.debe_cambiar_clave) return h("span", { class: "badge warn" }, h("span", { class: "dot" }), "Clave temporal");
  return h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Con acceso");
}

export function insigniaPendientes(pendientes) {
  if (!pendientes.length) return h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Completo");
  return h(
    "span",
    { class: "badge warn", title: pendientes.map((p) => PENDIENTES_PERSONAL[p]).join(" · ") },
    h("span", { class: "dot" }),
    pendientes.length === 1 ? "1 pendiente" : `${pendientes.length} pendientes`,
  );
}

/** Campos de la ficha, compartidos por el alta y la edición. */
export function camposFicha(p = {}) {
  const ppa = h("input", { type: "checkbox", name: "ppa_registrado", value: "si", checked: p.ppa_registrado });
  const codigoPpa = campo({ etiqueta: "Número de registro en el PPA", name: "ppa_codigo", value: p.ppa_codigo ?? "", maxlength: 60 });
  codigoPpa.hidden = !p.ppa_registrado;
  ppa.addEventListener("change", () => {
    codigoPpa.hidden = !ppa.checked;
  });
  return {
    contacto: [
      campo({ etiqueta: "Dirección postal", name: "direccion_postal", value: p.direccion_postal ?? "", required: true, maxlength: 200 }),
      h(
        "div",
        { class: "grid2" },
        campo({ etiqueta: "Teléfono (opcional)", name: "telefono", type: "tel", value: p.telefono ?? "", maxlength: 30 }),
        campo({ etiqueta: "Correo de contacto (opcional)", name: "correo_contacto", type: "email", value: p.correo_contacto ?? "" }),
      ),
      campo({ etiqueta: "RUC (opcional)", name: "ruc", value: p.ruc ?? "", inputmode: "numeric", pattern: "[0-9]{11}", maxlength: 11, title: "11 dígitos", class: "input mono" }),
    ],
    registros: [
      h("label", { class: "check" }, ppa, h("span", {}, "Está registrado en el PPA de MIDAGRI")),
      codigoPpa,
      h(
        "div",
        { class: "grid2" },
        campo({ etiqueta: "Código en Agro Digital (opcional)", name: "codigo_agrodigital", value: p.codigo_agrodigital ?? "", maxlength: 60, ayuda: "El que el productor tiene en su app Agro Digital del MIDAGRI." }),
        campo({ etiqueta: "Código de socio (opcional)", name: "codigo_socio", value: p.codigo_socio ?? "", maxlength: 60 }),
      ),
    ],
  };
}

/** Convierte el formulario de la ficha al cuerpo de la API. */
export function cuerpoFicha(datos, { vaciosComoNulos = false } = {}) {
  const cuerpo = { ...datos, ppa_registrado: datos.ppa_registrado === "si" };
  if (!cuerpo.ppa_registrado) delete cuerpo.ppa_codigo;
  for (const [clave, valor] of Object.entries(cuerpo)) {
    if (valor === "") {
      if (vaciosComoNulos) cuerpo[clave] = null;
      else delete cuerpo[clave];
    }
  }
  return cuerpo;
}

/** Formulario largo partido en pasos: 1) identidad y contacto, 2) registros y consentimiento. */
function abrirAlta(navegar) {
  const ficha = camposFicha();
  const paso1 = h(
    "div",
    { class: "form" },
    campo({ etiqueta: "DNI", name: "dni", inputmode: "numeric", pattern: "[0-9]{8}", maxlength: 8, title: "8 dígitos", class: "input mono", required: true }),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Nombres, como figuran en el DNI", name: "nombres", required: true, maxlength: 200 }),
      campo({ etiqueta: "Apellidos, como figuran en el DNI", name: "apellidos", required: true, maxlength: 200 }),
    ),
    ficha.contacto,
  );
  const paso2 = h(
    "div",
    { class: "form", hidden: true },
    ficha.registros,
    h(
      "label",
      { class: "check" },
      h("input", { type: "checkbox", name: "consentimiento_cooperativa", value: "si" }),
      h("span", {}, "La cooperativa cuenta con el consentimiento firmado del productor"),
    ),
  );
  const pasos = h("div", { class: "pasos" }, h("span", { "aria-current": "step" }, "1. Identidad y contacto"), h("span", {}, "2. Registros"));
  const mensaje = h("p", { class: "alerta bad", role: "alert", hidden: true });
  const formulario = h("form", { class: "form", id: "form-productor", novalidate: true }, pasos, paso1, paso2, mensaje);
  const atras = h("button", { class: "btn btn-ghost", type: "button", hidden: true }, "Atrás");
  const siguiente = h("button", { class: "btn btn-primary", type: "submit", form: "form-productor" }, "Siguiente");
  const { cerrar } = abrirModal({
    titulo: "Nuevo productor",
    subtitulo: "Queda afiliado a tu cooperativa desde hoy.",
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), atras, siguiente],
  });

  function irAlPaso(n) {
    paso1.hidden = n !== 1;
    paso2.hidden = n !== 2;
    atras.hidden = n !== 2;
    siguiente.textContent = n === 1 ? "Siguiente" : "Registrar productor";
    [...pasos.children].forEach((s, i) => s.setAttribute("aria-current", i + 1 === n ? "step" : "false"));
  }
  atras.addEventListener("click", () => irAlPaso(1));

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const visibles = [...(paso2.hidden ? paso1 : paso2).querySelectorAll("input")].filter((i) => !i.closest("[hidden]"));
    if (!visibles.every((i) => i.reportValidity())) return;
    if (paso2.hidden) return irAlPaso(2);

    const datos = Object.fromEntries(new FormData(formulario));
    const consentimiento = datos.consentimiento_cooperativa === "si";
    delete datos.consentimiento_cooperativa;
    const cuerpo = cuerpoFicha(datos);
    if (consentimiento) {
      cuerpo.consentimiento_cooperativa = true;
      cuerpo.version_consentimiento = (await textoConsentimiento()).version;
    }
    mensaje.hidden = true;
    siguiente.classList.add("is-loading");
    try {
      const productor = await llamarApi("/productores", { metodo: "POST", cuerpo: sinVacios(cuerpo) });
      cerrar();
      toast(`Se registró a ${productor.nombres} ${productor.apellidos}.`);
      navegar(`#/productores/${productor.id}`);
    } catch (error) {
      mensaje.textContent = error.message;
      mensaje.hidden = false;
      if (!["ppa_codigo", "codigo_agrodigital", "codigo_socio"].some((c) => error.campos?.includes(c))) irAlPaso(1);
    } finally {
      siguiente.classList.remove("is-loading");
    }
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
              h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirAlta(navegar) }, "Registrar el primero"),
          });
    }
    return [
      h(
        "div",
        { class: "tabla-caja" },
        h(
          "table",
          { class: "tabla" },
          h("thead", {}, h("tr", {}, h("th", {}, "Productor"), h("th", {}, "DNI"), h("th", { class: "ocultar-sm" }, "Parcelas"), h("th", {}, "Pendientes"))),
          h(
            "tbody",
            {},
            datos.items.map((p) =>
              h(
                "tr",
                { class: "clic", onclick: () => navegar(`#/productores/${p.id}`) },
                h("td", {}, h("a", { href: `#/productores/${p.id}` }, `${p.apellidos}, ${p.nombres}`), p.codigo_socio && h("span", { class: "sec" }, `Socio ${p.codigo_socio}`)),
                h("td", { class: "mono" }, p.dni),
                h("td", { class: "mono ocultar-sm" }, String(p.parcelas.activas)),
                h("td", {}, insigniaPendientes(p.pendientes)),
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
    secciones: seccionesProductores(),
    accion:
      puedeRegistrar &&
      h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirAlta(navegar) }, icono("mas"), "Nuevo productor"),
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

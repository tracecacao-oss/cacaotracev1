// Padrón de productores: lista con DNI, nombre, parcelas y pendientes; alta en dos pasos.

import { llamarApi } from "../api.js";
import { textoConsentimiento } from "../consentimiento.js";
import { puede } from "../estado.js";
import { PENDIENTES_PERSONAL, hectareas } from "../textos.js";
import {
  abrirModal,
  avatar,
  buscador,
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
    ["Habilitación", "#/productores/habilitacion"],
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

// ---------- Carga masiva ----------

const PLANTILLA = [
  "dni",
  "nombres",
  "apellidos",
  "direccion_postal",
  "telefono",
  "correo",
  "ruc",
  "ppa_registrado",
  "ppa_codigo",
  "codigo_agrodigital",
  "codigo_socio",
];
const ESTADOS_CARGA = {
  lista: ["ok", "Lista"],
  creada: ["ok", "Registrada"],
  error: ["bad", "Con errores"],
  repetida: ["warn", "Repetida"],
  ya_registrado: ["info", "Ya registrado"],
  otra_cooperativa: ["warn", "En otra cooperativa"],
};

/** Plantilla con solo los encabezados; el BOM hace que Excel muestre bien las tildes. */
function descargarPlantilla() {
  const enlace = h("a", {
    href: URL.createObjectURL(new Blob([`﻿${PLANTILLA.join(",")}\r\n`], { type: "text/csv" })),
    download: "plantilla-productores.csv",
  });
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
}

function tablaCarga(carga) {
  const problemas = carga.filas.filter((f) => !["lista", "creada"].includes(f.estado));
  const filas = [...problemas, ...carga.filas.filter((f) => ["lista", "creada"].includes(f.estado))];
  return h(
    "div",
    { class: "tabla-caja carga-tabla" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "Fila"), h("th", {}, "DNI"), h("th", {}, "Productor"), h("th", {}, "Estado"))),
      h(
        "tbody",
        {},
        filas.map((f) => {
          const [tono, texto] = ESTADOS_CARGA[f.estado];
          return h(
            "tr",
            {},
            h("td", { class: "mono" }, String(f.fila)),
            h("td", { class: "mono" }, f.dni ?? "—"),
            h("td", {}, [f.apellidos, f.nombres].filter(Boolean).join(", ") || "—"),
            h("td", {}, h("span", { class: `badge ${tono}` }, texto), f.mensajes.map((m) => h("span", { class: "sec" }, m))),
          );
        }),
      ),
    ),
  );
}

function abrirCargaMasiva(alTerminar) {
  const archivo = h("input", { class: "input", type: "file", id: "c-carga", accept: ".xlsx,.csv", required: true });
  const resultado = h("div", { class: "form" });
  const mensaje = h("p", { class: "alerta bad", role: "alert", hidden: true });
  const revisar = h("button", { class: "btn", type: "button" }, "Revisar archivo");
  const registrar = h("button", { class: "btn btn-primary", type: "button", hidden: true }, "Registrar");
  let revisado = null;

  const contenido = h(
    "div",
    { class: "form" },
    h(
      "p",
      { class: "panel-sub" },
      "Sube un Excel (.xlsx) o CSV con una fila por productor. Son obligatorias las columnas DNI, nombres, apellidos y dirección; las demás son opcionales. Primero se revisa cada fila y nada se guarda hasta que confirmes.",
    ),
    h("button", { class: "btn btn-sm", type: "button", onclick: descargarPlantilla }, "Descargar plantilla (CSV)"),
    h("label", { class: "field", for: "c-carga" }, "Archivo (hasta 2 MB y 1,000 productores)", archivo),
    mensaje,
    resultado,
  );
  const { cerrar } = abrirModal({
    titulo: "Carga masiva de productores",
    contenido,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cerrar"), revisar, registrar],
  });

  async function enviar(ruta, boton) {
    if (!archivo.files[0]) return archivo.reportValidity();
    const formulario = new FormData();
    formulario.append("archivo", archivo.files[0]);
    mensaje.hidden = true;
    boton.classList.add("is-loading");
    boton.disabled = true;
    try {
      return await llamarApi(ruta, { metodo: "POST", formulario });
    } catch (error) {
      mensaje.textContent = error.message;
      mensaje.hidden = false;
      return null;
    } finally {
      boton.classList.remove("is-loading");
      boton.disabled = false;
    }
  }

  archivo.addEventListener("change", () => {
    revisado = null;
    registrar.hidden = true;
    resultado.replaceChildren();
  });

  revisar.addEventListener("click", async () => {
    const carga = await enviar("/productores/carga-masiva/analizar", revisar);
    if (!carga) return;
    revisado = archivo.files[0];
    registrar.hidden = carga.listas === 0;
    registrar.textContent = `Registrar ${carga.listas} ${carga.listas === 1 ? "productor" : "productores"}`;
    reemplazar(
      resultado,
      h(
        "p",
        { class: `alerta ${carga.con_problemas ? "warn" : "info"}` },
        `${carga.total} filas: ${carga.listas} listas para registrarse` +
          (carga.con_problemas ? ` y ${carga.con_problemas} con problemas, que no se guardarán. Corrígelas en el archivo y vuelve a subirlo si quieres incluirlas.` : "."),
      ),
      carga.columnas_ignoradas.length > 0 && h("p", { class: "panel-sub" }, `Columnas que no se usan: ${carga.columnas_ignoradas.join(", ")}.`),
      tablaCarga(carga),
    );
  });

  registrar.addEventListener("click", async () => {
    if (archivo.files[0] !== revisado) return;
    const carga = await enviar("/productores/carga-masiva", registrar);
    if (!carga) return;
    registrar.hidden = true;
    revisar.hidden = true;
    archivo.disabled = true;
    reemplazar(
      resultado,
      h("p", { class: "alerta info" }, `Se registraron ${carga.creadas} ${carga.creadas === 1 ? "productor" : "productores"}.`),
      tablaCarga(carga),
    );
    toast(`Se registraron ${carga.creadas} productores.`);
    alTerminar();
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
                h(
                  "td",
                  {},
                  h(
                    "span",
                    { class: "persona" },
                    avatar(p.nombres, p.apellidos, "sm"),
                    h("span", {}, h("a", { href: `#/productores/${p.id}` }, `${p.apellidos}, ${p.nombres}`), p.codigo_socio && h("span", { class: "sec" }, `Socio ${p.codigo_socio}`)),
                  ),
                ),
                h("td", { class: "mono" }, p.dni),
                h(
                  "td",
                  { class: "mono ocultar-sm" },
                  p.parcelas.activas ? `${p.parcelas.activas} · ${hectareas(p.parcelas.area_total_ha)}` : "—",
                ),
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
    titulo: "Padrón de productores",
    antetitulo: "Productores",
    descripcion: "Productores afiliados a la cooperativa, con sus parcelas y lo que les falta para respaldar un DOP.",
    migas: [["Productores", "#/productores"], ["Padrón"]],
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
        buscador({ placeholder: "Buscar por DNI, nombre o código de socio", etiqueta: "Buscar productores", alEscribir: buscar }),
        puedeRegistrar &&
          h("div", { class: "acciones-lista" }, h("button", { class: "btn", type: "button", onclick: () => abrirCargaMasiva(cargar) }, icono("upload"), "Carga masiva")),
      ),
      lista,
    ),
  };
}

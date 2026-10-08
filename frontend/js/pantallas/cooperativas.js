// Plataforma · Cooperativas: lista, alta (en dos pasos), suspensión y selector de cooperativa a consultar.

import { llamarApi } from "../api.js";
import { fijarConsulta } from "../estado.js";
import {
  abrirModal,
  buscador,
  campo,
  cargando,
  conRetraso,
  errorDeCarga,
  h,
  icono,
  mostrarClaveTemporal,
  paginador,
  reemplazar,
  sinVacios,
  vacio,
} from "../ui.js";
import { TIPOS_ORGANIZACION } from "../textos.js";
import { camposUbigeo, lugares } from "../ubigeo.js";

export function seccionesPlataforma() {
  return [
    ["Cooperativas", "#/plataforma/cooperativas"],
    ["Superposiciones", "#/plataforma/superposiciones"],
    ["Configuración", "#/plataforma/configuracion"],
  ];
}

export function insigniaEstado(cooperativa) {
  return cooperativa.estado === "activa"
    ? h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Activa")
    : h("span", { class: "badge bad" }, h("span", { class: "dot" }), "Suspendida");
}

export function consultar(cooperativa, navegar) {
  fijarConsulta({
    id: cooperativa.id,
    nombre: cooperativa.nombre_comercial || cooperativa.razon_social,
    es_demo: cooperativa.es_demo,
  });
  navegar("#/inicio");
}

/** Formulario largo partido en pasos: 1) cooperativa, 2) su primer administrador. */
function abrirAlta(navegar) {
  const pasos = h("div", { class: "pasos" }, h("span", { "aria-current": "step" }, "1. Cooperativa"), h("span", {}, "2. Administrador"));
  const [departamento, provincia, distrito] = camposUbigeo();
  const paso1 = h(
    "div",
    { class: "form" },
    campo({ etiqueta: "Razón social", name: "razon_social", required: true, maxlength: 200 }),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Nombre comercial (opcional)", name: "nombre_comercial", maxlength: 200 }),
      campo({ etiqueta: "RUC", name: "ruc", inputmode: "numeric", pattern: "[0-9]{11}", maxlength: 11, title: "11 dígitos", class: "input mono", required: true }),
    ),
    campo({
      etiqueta: "Código de la cooperativa",
      name: "codigo",
      pattern: "[A-Za-z]{3,6}",
      minlength: 3,
      maxlength: 6,
      title: "De 3 a 6 letras",
      class: "input mono",
      autocomplete: "off",
      required: true,
      ayuda: "De 3 a 6 letras. Va en el código de cada DOP y no cambia después.",
    }),
    campo({
      etiqueta: "Tipo de organización",
      name: "tipo_organizacion",
      opciones: [["", "Elige el tipo…"], ...TIPOS_ORGANIZACION],
      required: true,
      ayuda: "Cooperativa agraria (Ley N.° 31335), asociación de productores o empresa. Se puede corregir después.",
    }),
    h(
      "div",
      { class: "grid2" },
      departamento,
      provincia,
    ),
    distrito,
    h(
      "label",
      { class: "check" },
      h("input", { type: "checkbox", name: "es_demo", value: "si" }),
      h("span", {}, "Cooperativa de demostración (datos ficticios). No se puede cambiar después."),
    ),
  );
  const paso2 = h(
    "div",
    { class: "form", hidden: true },
    h("p", { class: "panel-sub" }, "Primer administrador de la cooperativa. Recibirás su contraseña temporal."),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Nombres", name: "admin_nombres", required: true, maxlength: 200 }),
      campo({ etiqueta: "Apellidos", name: "admin_apellidos", required: true, maxlength: 200 }),
    ),
    campo({ etiqueta: "Correo", name: "admin_correo", type: "email", required: true, autocomplete: "off" }),
  );
  const mensaje = h("p", { class: "alerta bad", role: "alert", hidden: true });
  // Sin validación nativa del formulario completo: cada paso valida solo sus campos visibles.
  const formulario = h("form", { class: "form", id: "form-cooperativa", novalidate: true }, pasos, paso1, paso2, mensaje);

  const atras = h("button", { class: "btn btn-ghost", type: "button", hidden: true }, "Atrás");
  const siguiente = h("button", { class: "btn btn-primary", type: "submit", form: "form-cooperativa" }, "Siguiente");
  const { cerrar } = abrirModal({
    titulo: "Nueva cooperativa",
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), atras, siguiente],
  });

  function irAlPaso(n) {
    paso1.hidden = n !== 1;
    paso2.hidden = n !== 2;
    atras.hidden = n !== 2;
    siguiente.textContent = n === 1 ? "Siguiente" : "Crear cooperativa";
    [...pasos.children].forEach((s, i) => s.setAttribute("aria-current", i + 1 === n ? "step" : "false"));
    (n === 1 ? paso1 : paso2).querySelector("input")?.focus();
  }
  atras.addEventListener("click", () => irAlPaso(1));

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const visibles = [...(paso2.hidden ? paso1 : paso2).querySelectorAll("input,select")];
    if (!visibles.every((i) => i.reportValidity())) return;
    if (paso2.hidden) return irAlPaso(2);

    const datos = Object.fromEntries(new FormData(formulario));
    const cuerpo = sinVacios({
      razon_social: datos.razon_social,
      nombre_comercial: datos.nombre_comercial,
      ruc: datos.ruc,
      codigo: datos.codigo.trim().toUpperCase(),
      tipo_organizacion: datos.tipo_organizacion,
      departamento: datos.departamento,
      provincia: datos.provincia,
      distrito: datos.distrito,
    });
    cuerpo.es_demo = datos.es_demo === "si";
    cuerpo.administrador = { nombres: datos.admin_nombres, apellidos: datos.admin_apellidos, correo: datos.admin_correo };

    mensaje.hidden = true;
    siguiente.classList.add("is-loading");
    try {
      const creada = await llamarApi("/admin/cooperativas", { metodo: "POST", cuerpo, sinConsulta: true });
      cerrar();
      const admin = creada.administrador;
      mostrarClaveTemporal({ titulo: "Cooperativa creada", persona: `${admin.nombres} ${admin.apellidos} · administrador`, usuario: admin.correo })(creada);
      navegar(`#/plataforma/cooperativas/${creada.cooperativa.id}`);
    } catch (error) {
      mensaje.textContent = error.message;
      mensaje.hidden = false;
      // El error del RUC o de los datos de la cooperativa se corrige en el primer paso.
      const delPaso2 = error.codigo === "correo_en_uso" || (error.campos ?? []).includes("correo");
      if (!delPaso2) irAlPaso(1);
    } finally {
      siguiente.classList.remove("is-loading");
    }
  });
}

/** Adenda 2: unidades de procesamiento de Copernicus usadas en el mes; al 80 % se pausan las imágenes. */
async function tarjetaConsumo() {
  let c;
  try {
    c = await llamarApi("/admin/imagenes/consumo", { sinConsulta: true });
  } catch {
    return null;
  }
  const n = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });
  const detalle = !c.configurada
    ? "Copernicus no está configurado en el servidor: no se generan imágenes."
    : c.en_pausa
      ? `Se llegó al 80 % de la cuota: las imágenes nuevas esperan al próximo mes${c.pendientes ? ` (${c.pendientes} en espera)` : ""}.`
      : `Al llegar a ${n(c.umbral_pu)} unidades (80 %) se dejan de generar imágenes nuevas.${c.pendientes ? ` ${c.pendientes} en cola.` : ""}`;
  return h(
    "section",
    { class: "kpis", "aria-label": "Uso de imágenes satelitales" },
    h(
      "div",
      { class: `kpi ${c.en_pausa || !c.configurada ? "is-warn" : "is-info"}` },
      h("span", { class: "kpi-ic" }, icono("layers")),
      h("span", { class: "kpi-l" }, "Imágenes satelitales del mes (Copernicus)"),
      h("span", { class: "kpi-v" }, n(c.usadas_pu), h("small", {}, `de ${n(c.cuota_pu)} unidades de procesamiento`)),
      h("span", { class: "kpi-s" }, detalle),
    ),
  );
}

const MB = 1024 * 1024;
const mb = (bytes) => (bytes / MB).toLocaleString("es-PE", { maximumFractionDigits: 1 });

/** Parte 10: aviso al pasar de 70 % y de 90 % del límite del plan. */
function nivelUso(pct) {
  if (pct >= 90) return ["is-bad", "Pasó el 90 % del límite. La salida es pasar Supabase al plan de pago; lo decide el equipo."];
  if (pct >= 70) return ["is-warn", "Pasó el 70 % del límite. Conviene revisar qué cooperativa ocupa más."];
  return ["is-info", null];
}

function kpiUso(etiqueta, ic, usado, limiteMb, pct, detalle) {
  const [clase, aviso] = nivelUso(pct);
  return h(
    "div",
    { class: `kpi ${clase}` },
    h("span", { class: "kpi-ic" }, icono(ic)),
    h("span", { class: "kpi-l" }, etiqueta),
    h("span", { class: "kpi-v" }, `${mb(usado)} MB`, h("small", {}, `de ${limiteMb.toLocaleString("es-PE")} MB · ${pct.toLocaleString("es-PE")} %`)),
    h("span", { class: "kpi-s" }, aviso ?? detalle),
  );
}

/** Parte 10: espacio usado en archivos y en base de datos, y análisis en cola. */
async function panelUso() {
  let u;
  try {
    u = await llamarApi("/admin/uso", { sinConsulta: true });
  } catch {
    return null;
  }
  const cola = u.analisis_en_cola;
  return [
    h(
      "section",
      { class: "kpis", "aria-label": "Espacio usado" },
      kpiUso("Archivos (Supabase Storage)", "file", u.storage_bytes, u.limite_storage_mb, u.storage_pct, `${u.archivos.toLocaleString("es-PE")} archivos, también los anulados.`),
      kpiUso("Base de datos", "layers", u.db_bytes, u.limite_db_mb, u.db_pct, "Tamaño total de la base, con sus índices."),
      h(
        "div",
        { class: `kpi ${cola ? "is-info" : "is-ok"}` },
        h("span", { class: "kpi-ic" }, icono("clock")),
        h("span", { class: "kpi-l" }, "Análisis de cobertura en cola"),
        h("span", { class: "kpi-v" }, String(cola)),
        h("span", { class: "kpi-s" }, "La cola atiende una consulta a la vez: muchas parcelas el mismo día pueden tardar más de una hora."),
      ),
    ),
    u.por_cooperativa.length > 0 &&
      h(
        "section",
        { class: "panel" },
        h(
          "details",
          { class: "historial-analisis" },
          h("summary", {}, "Espacio por cooperativa"),
          h("p", { class: "panel-sub" }, "La base de datos por cooperativa es aproximada: suma sus filas, sin índices. Sirve para comparar, no para sumar."),
          h(
            "div",
            { class: "tabla-caja" },
            h(
              "table",
              { class: "tabla" },
              h("thead", {}, h("tr", {}, h("th", {}, "Cooperativa"), h("th", {}, "Archivos"), h("th", {}, "Espacio en archivos"), h("th", { class: "ocultar-sm" }, "Base de datos (aprox.)"))),
              h(
                "tbody",
                {},
                u.por_cooperativa.map((c) =>
                  h(
                    "tr",
                    {},
                    h("td", {}, c.cooperativa, c.es_demo && h("span", { class: "sec" }, "Demostración")),
                    h("td", { class: "mono" }, c.archivos.toLocaleString("es-PE")),
                    h("td", { class: "mono" }, `${mb(c.storage_bytes)} MB`),
                    h("td", { class: "mono ocultar-sm" }, `${mb(c.db_bytes_aprox)} MB`),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
  ];
}

export default async function cooperativas({ navegar }) {
  const lista = h("div", {}, cargando());
  let busqueda = "";
  let pagina = 1;

  async function cargar() {
    try {
      const datos = await llamarApi("/admin/cooperativas", { parametros: { q: busqueda, pagina }, sinConsulta: true });
      reemplazar(lista, tabla(datos));
    } catch (error) {
      lista.replaceChildren(errorDeCarga(error));
    }
  }

  function tabla(datos) {
    if (datos.total === 0) {
      return busqueda
        ? vacio({ titulo: "Sin resultados", texto: `Ninguna cooperativa coincide con “${busqueda}”.` })
        : vacio({
            titulo: "Aún no hay cooperativas",
            texto: "Cada cooperativa trabaja aislada de las demás, con su propio personal.",
            accion: h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirAlta(navegar) }, "Crear la primera"),
          });
    }
    return [
      h(
        "div",
        { class: "tabla-caja" },
        h(
          "table",
          { class: "tabla" },
          h("thead", {}, h("tr", {}, h("th", {}, "Cooperativa"), h("th", { class: "ocultar-sm" }, "RUC"), h("th", {}, "Estado"), h("th", { class: "ocultar-sm" }, "Usuarios"), h("th", {}, h("span", { class: "sr-only" }, "Acciones")))),
          h(
            "tbody",
            {},
            datos.items.map((c) =>
              h(
                "tr",
                {},
                h(
                  "td",
                  {},
                  h("a", { href: `#/plataforma/cooperativas/${c.id}` }, c.nombre_comercial || c.razon_social),
                  h("span", { class: "sec" }, `${lugares(c.distrito, c.provincia)}${c.es_demo ? " · demostración" : ""}`),
                ),
                h("td", { class: "mono ocultar-sm" }, c.ruc),
                h("td", {}, insigniaEstado(c)),
                h("td", { class: "mono ocultar-sm" }, String(c.usuarios)),
                h("td", { class: "acciones" }, h("button", { class: "btn btn-sm", type: "button", onclick: () => consultar(c, navegar) }, icono("ojo"), "Consultar")),
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
  const [consumo, uso] = await Promise.all([tarjetaConsumo(), panelUso()]);

  return {
    titulo: "Cooperativas",
    antetitulo: "Plataforma",
    descripcion: "Cooperativas que usan CacaoTrace, con su estado y sus usuarios.",
    migas: [["Plataforma"], ["Cooperativas"]],
    secciones: seccionesPlataforma(),
    accion: h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirAlta(navegar) }, icono("mas"), "Nueva cooperativa"),
    contenido: [
      uso,
      consumo,
      h(
        "section",
        { class: "panel" },
        h(
          "div",
          { class: "barra-lista" },
          buscador({ placeholder: "Buscar por nombre o RUC", etiqueta: "Buscar cooperativas", alEscribir: buscar }),
        ),
        lista,
      ),
    ],
  };
}

// Datos y expediente legal de la organización (Parte 8; adenda 6, secciones 4, 5 y 10): los datos que el DEX
// necesita para identificar al exportador y el expediente en tres bloques. Identidad (ficha RUC, partida y
// poderes) es lo único que frena un lote; Tributos y registro, y la Política con sus cinco temas, se muestran
// y llegan al informe de hallazgos. Solo aparecen los documentos que aplican al tipo de organización; los que
// ya no se cargan van al final, plegados. Solo el administrador edita los datos, carga o anula documentos y
// políticas; el operador y el lector los ven.

import { descargarArchivo, llamarApi } from "../api.js";
import { abrirCotejo, anularDocumento, verDocumento } from "../documentos.js";
import { rolEfectivo } from "../estado.js";
import { hoyLima as hoy } from "../fechas.js";
import { ESTADOS_CASILLA, ESTADOS_REQUISITO, TIPOS_ORGANIZACION, insigniaNivel } from "../textos.js";
import { lugares } from "../ubigeo.js";
import { abrirModal, cabeceraFicha, campo, claseTono, enviarCon, fecha, h, icono, leyendaTonos, ordenarPorTono, rejilla, seccion, toast, vacio } from "../ui.js";

const TEMAS_POLITICA = [
  ["integridad", "Integridad"],
  ["no_fraude", "No fraude"],
  ["canal_denuncias", "Canal de quejas y denuncias"],
  ["trabajo_digno", "Trabajo digno"],
  ["revision_de_documentos", "Revisión de documentos"],
];
const NOMBRE_TEMA = Object.fromEntries(TEMAS_POLITICA);

function insignia(clase, texto) {
  return h("span", { class: `badge ${clase}`.trim() }, h("span", { class: "dot" }), texto);
}

function nombreTipo(codigo) {
  return TIPOS_ORGANIZACION.find(([c]) => c === codigo)?.[1] ?? codigo;
}

function abrirDatos(c, alGuardar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-datos-coop" }, "Guardar");
  const formulario = h(
    "form",
    { class: "form", id: "form-datos-coop" },
    campo({ etiqueta: "Dirección postal", name: "direccion_postal", value: c.direccion_postal ?? "", required: true, maxlength: 400 }),
    campo({ etiqueta: "Correo de contacto", name: "correo", type: "email", value: c.correo ?? "", required: true, maxlength: 254 }),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Representante legal", name: "representante_nombre", value: c.representante_nombre ?? "", required: true, maxlength: 200 }),
      campo({ etiqueta: "DNI del representante", name: "representante_dni", value: c.representante_dni ?? "", required: true, pattern: "[0-9]{8}", inputmode: "numeric", maxlength: 8, class: "input mono" }),
    ),
  );
  const { cerrar } = abrirModal({ titulo: "Datos de la organización", subtitulo: "Los usa el DEX para identificar al exportador.", contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    await llamarApi("/cooperativa", { metodo: "PATCH", cuerpo: datos });
    cerrar();
    toast("Datos guardados.");
    alGuardar();
  });
}

/** Sección 5, regla 2: el contacto del canal (un teléfono, un correo o dónde está el buzón). */
function abrirContacto(c, alGuardar, { luego } = {}) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-canal" }, luego ? "Guardar y descargar" : "Guardar");
  const formulario = h(
    "form",
    { class: "form", id: "form-canal" },
    h("p", {}, "A dónde lleva una persona su queja o su denuncia. El sistema no recibe denuncias: solo muestra este contacto a los productores y lo escribe en la política y en la hoja de su declaración anual."),
    campo({ etiqueta: "Contacto del canal de quejas y denuncias", name: "canal_denuncias_contacto", value: c.canal_denuncias_contacto ?? "", required: true, minlength: 3, maxlength: 200, ayuda: "Un teléfono, un correo o la ubicación de un buzón. Antes de publicarlo, la organización define quién lo atiende." }),
  );
  const { cerrar } = abrirModal({ titulo: "Canal de quejas y denuncias", contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    await llamarApi("/cooperativa", { metodo: "PATCH", cuerpo: datos });
    cerrar();
    toast("Contacto guardado.");
    if (luego) await luego();
    alGuardar();
  });
}

function abrirCarga(casilla, alCargar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-legal-coop" }, "Cargar documento");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true });
  // La declaración de renta lleva la fecha de presentación y vence sola (sección 4, regla 2).
  const fechas = casilla.vence_solo
    ? campo({ etiqueta: "Fecha de presentación", name: "fecha_emision", type: "date", max: hoy(), required: true, ayuda: "Vence sola a los 18 meses de esta fecha." })
    : h("div", { class: "grid2" }, campo({ etiqueta: "Fecha de emisión", name: "fecha_emision", type: "date", max: hoy(), required: true }), campo({ etiqueta: "Fecha de vencimiento (si tiene)", name: "fecha_vencimiento", type: "date" }));
  const formulario = h(
    "form",
    { class: "form", id: "form-legal-coop" },
    h("div", { class: "grid2" }, campo({ etiqueta: casilla.vence_solo ? "Número de orden" : "Número (partida, registro o constancia)", name: "numero", required: true, maxlength: 200 }), campo({ etiqueta: "Entidad emisora", name: "entidad_emisora", required: true, maxlength: 200 })),
    fechas,
    h("label", { class: "field" }, "Archivo (foto o PDF, hasta 10 MB)", archivo),
  );
  const { cerrar } = abrirModal({ titulo: `Cargar: ${casilla.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = new FormData();
    cuerpo.append("tipo", casilla.codigo);
    for (const clave of ["numero", "entidad_emisora", "fecha_emision", "fecha_vencimiento"]) if (datos[clave]) cuerpo.append(clave, datos[clave]);
    cuerpo.append("archivo", archivo.files[0]);
    await llamarApi("/cooperativa/documentos", { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast("Documento cargado.");
    alCargar();
  });
}

/** Identidad: rojo si falta o venció (frena un lote). Lo demás no frena: amarillo si falta, verde si está. */
function tonoCasilla(c) {
  if (c.estado === "vigente") return "listo";
  if (c.estado === "por_vencer") return "falta";
  return c.frena_lote ? "bloquea" : "falta";
}

function filaCasilla(c, puedo, recargar, consultaRuc) {
  const [clase, texto] = ESTADOS_CASILLA[c.estado] ?? ["", c.estado];
  const vigentes = c.documentos.filter((d) => d.vigente);
  const consultas = c.codigo === "ficha_ruc" && consultaRuc ? [[consultaRuc, "Consulta RUC de SUNAT"]] : [];
  const ayuda = c.codigo === "ficha_ruc" ? "Anota el estado y la condición del contribuyente que muestra SUNAT." : undefined;
  return h(
    "li",
    { class: c.anterior ? "casilla" : claseTono(tonoCasilla(c)) },
    h(
      "div",
      { class: "casilla-h" },
      h(
        "div",
        {},
        h("b", {}, c.nombre),
        h("span", { class: "sec" }, c.anterior ? "Ya no se carga: no cuenta para nada." : `${c.frena_lote ? "Frena un lote si falta" : "No frena un lote"}${c.registro_consultable ? " · con registro público" : " · sin registro público consultable"}`),
      ),
      !c.anterior && h("span", { class: "fila-acciones" }, insignia(clase, texto), c.nivel && insigniaNivel(c.nivel), c.vence_en && h("span", { class: "badge" }, `vence ${fecha(c.vence_en)}`)),
    ),
    vigentes.map((d) =>
      h(
        "div",
        { class: "casilla-doc" },
        h("span", {}, `N.º ${d.numero ?? "—"} · ${d.entidad_emisora ?? "—"} · ${c.vence_solo ? "presentada" : "emitido"} ${fecha(d.fecha_emision)}${d.fecha_vencimiento ? ` · vence ${fecha(d.fecha_vencimiento)}` : ""}`),
        d.cotejado_en && h("span", { class: "sec" }, `Cotejado el ${fecha(d.cotejado_en)}: ${d.cotejo_nota}`),
        h(
          "span",
          { class: "fila-acciones" },
          h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(d) }, icono("eye"), "Ver"),
          !c.anterior && puedo.cotejar && c.registro_consultable && !d.cotejado_en && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirCotejo(d, { titulo: c.nombre, consultas, ayuda }, recargar) }, "Cotejar en fuente"),
          puedo.admin && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => anularDocumento(d, recargar) }, "Anular"),
        ),
      ),
    ),
    !c.anterior && puedo.admin && h("div", { class: "fila-acciones" }, h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirCarga(c, recargar) }, icono("upload"), vigentes.length ? "Cargar otro" : "Cargar documento")),
  );
}

function listaCasillas(casillas, puedo, recargar, consultaRuc) {
  return h("ul", { class: "casillas" }, ordenarPorTono(casillas, tonoCasilla).map((x) => filaCasilla(x, puedo, recargar, consultaRuc)));
}

function requisito(r) {
  const [clase, texto] = ESTADOS_REQUISITO[r.estado] ?? ["", r.estado];
  return h("p", { class: "requisito-org" }, h("b", {}, r.nombre), r.referencias.length > 0 && h("span", { class: "sec" }, ` · orientador, ${r.referencias.join(", ")}`), " ", insignia(clase, texto), r.falta.length > 0 && h("span", { class: "sec" }, ` Falta: ${r.falta.join(", ")}.`));
}

// ---------- Política (sección 5) ----------

function abrirCargaPolitica(p, alCargar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-politica" }, "Cargar política");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true });
  const temas = TEMAS_POLITICA.map(([codigo, nombre]) => h("label", { class: "check" }, h("input", { type: "checkbox", name: "temas", value: codigo }), nombre));
  const plantilla = h("input", { type: "checkbox", name: "plantilla" });
  const formulario = h(
    "form",
    { class: "form", id: "form-politica" },
    h("fieldset", { class: "field" }, h("legend", {}, "Temas que cubre"), h("div", { class: "checks" }, temas), h("small", {}, "Los marcas tú: el sistema no lee el archivo. La plantilla del sistema cubre los cinco.")),
    h("div", { class: "grid2" }, campo({ etiqueta: "Fecha de adopción", name: "adoptada_en", type: "date", max: hoy(), required: true }), campo({ etiqueta: "Órgano que la adoptó", name: "organo", required: true, minlength: 2, maxlength: 200, value: p.organo_sugerido.replace(/^el /, "") })),
    h("label", { class: "check" }, plantilla, `Es la plantilla del sistema, versión ${p.version_plantilla}, firmada`),
    h("label", { class: "field" }, "Política firmada (foto o PDF, hasta 10 MB)", archivo),
  );
  const { cerrar } = abrirModal({ titulo: "Cargar política", subtitulo: "Una o varias: cada tema cuenta si alguna política vigente lo cubre.", contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const marcados = temas.map((t) => t.querySelector("input")).filter((x) => x.checked).map((x) => x.value);
    if (!marcados.length) throw new Error("Marca al menos un tema.");
    const cuerpo = new FormData();
    for (const tema of marcados) cuerpo.append("temas", tema);
    cuerpo.append("adoptada_en", datos.adoptada_en);
    cuerpo.append("organo", datos.organo);
    if (plantilla.checked) cuerpo.append("version_plantilla", String(p.version_plantilla));
    cuerpo.append("archivo", archivo.files[0]);
    await llamarApi("/cooperativa/politicas", { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast("Política cargada.");
    alCargar();
  });
}

function abrirAnulacionPolitica(politica, alAnular) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-politica" }, "Anular política");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-politica" },
    h("p", {}, "La política no se borra: queda anulada con su motivo y sus temas dejan de contar."),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, minlength: 10, maxlength: 4000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular política", subtitulo: `Adoptada el ${fecha(politica.adoptada_en)}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/cooperativa/politicas/${politica.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("Política anulada.", "warn");
    alAnular();
  });
}

function bloquePolitica(c, p, puedo, recargar) {
  const descargar = () => descargarArchivo("/cooperativa/politica/hoja", `politica-para-firmar-${c.ruc}.pdf`).catch((error) => toast(error.message, "bad"));
  // Sección 5, plantilla, regla 5: sin el contacto del canal, la pantalla lo pide antes de descargar.
  const alDescargar = () => (c.canal_denuncias_contacto ? descargar() : abrirContacto(c, recargar, { luego: descargar }));
  const temas = ordenarPorTono(p.temas, (t) => (t.estado === "sustentado" ? "listo" : "falta"));
  const politicas = p.politicas;
  return seccion({
    titulo: "Política",
    sub: "Cinco temas: integridad, no fraude, canal de quejas y denuncias, trabajo digno y revisión de documentos. No frena un lote: lo que falte llega al informe de hallazgos. Las políticas no vencen.",
    acciones: puedo.admin && [
      h("button", { class: "btn btn-sm", type: "button", onclick: alDescargar }, icono("download"), "Descargar política para firmar"),
      h("button", { class: "btn btn-sm btn-primary", type: "button", onclick: () => abrirCargaPolitica(p, recargar) }, icono("upload"), "Cargar política"),
    ],
    contenido: [
      requisito(p.requisito),
      h(
        "ul",
        { class: "casillas" },
        temas.map((t) =>
          h(
            "li",
            { class: claseTono(t.estado === "sustentado" ? "listo" : "falta") },
            h(
              "div",
              { class: "casilla-h" },
              h("div", {}, h("b", {}, t.nombre), h("span", { class: "sec" }, t.que_dice)),
              h("span", { class: "fila-acciones" }, insignia(...(ESTADOS_REQUISITO[t.estado] ?? ["", t.estado])), t.adoptada_en && h("span", { class: "badge" }, `adoptada ${fecha(t.adoptada_en)}`)),
            ),
            t.falta && h("p", { class: "sec" }, `Falta: ${t.falta}`),
          ),
        ),
      ),
      rejilla([
        {
          etiqueta: "Contacto del canal de quejas y denuncias",
          valor: c.canal_denuncias_contacto,
          extra: puedo.admin ? h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirContacto(c, recargar) }, c.canal_denuncias_contacto ? "Cambiar" : "Escribir el contacto") : "Lo escribe el administrador.",
        },
      ]),
      h("h4", { class: "dex-sub" }, "Políticas cargadas"),
      politicas.length === 0
        ? vacio({ titulo: "Sin políticas", texto: puedo.admin ? "Descarga la plantilla, fírmala con el órgano de dirección y cárgala marcando sus temas." : "El administrador las carga." })
        : h(
            "div",
            { class: "tbl-box" },
            h(
              "table",
              { class: "tabla" },
              h("thead", {}, h("tr", {}, h("th", {}, "Temas"), h("th", {}, "Adoptada"), h("th", { class: "ocultar-sm" }, "Órgano"), h("th", {}, "Estado"), h("th", {}, h("span", { class: "sr-only" }, "Acciones")))),
              h(
                "tbody",
                {},
                politicas.map((x) =>
                  h(
                    "tr",
                    {},
                    h("td", {}, x.temas.map((t) => NOMBRE_TEMA[t] ?? t).join(", "), x.version_plantilla && h("span", { class: "sec" }, `Plantilla del sistema, versión ${x.version_plantilla}`)),
                    h("td", {}, fecha(x.adoptada_en)),
                    h("td", { class: "ocultar-sm" }, x.organo),
                    h("td", {}, x.vigente ? insignia("ok", "Vigente") : insignia("", "Anulada"), x.motivo_anulacion && h("span", { class: "sec" }, `Motivo: ${x.motivo_anulacion}`)),
                    h(
                      "td",
                      {},
                      h(
                        "span",
                        { class: "fila-acciones" },
                        x.documento && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(x.documento) }, icono("eye"), "Ver"),
                        puedo.admin && x.vigente && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirAnulacionPolitica(x, recargar) }, "Anular"),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
    ],
  });
}

export default async function cooperativaLegal({ recargar }) {
  const [c, exp, p] = await Promise.all([llamarApi("/cooperativa"), llamarApi("/cooperativa/expediente"), llamarApi("/cooperativa/politicas")]);
  const rol = rolEfectivo();
  const puedo = { admin: rol === "admin_cooperativa", cotejar: ["admin_cooperativa", "operador"].includes(rol) };
  const nombres = Object.fromEntries(exp.casillas.map((x) => [x.codigo, x.nombre]));
  const requisitos = Object.fromEntries(exp.requisitos.map((r) => [r.codigo, r]));
  const identidad = exp.casillas.filter((x) => x.identidad);
  const tributos = exp.casillas.filter((x) => !x.identidad);
  return {
    titulo: "Datos y expediente legal",
    migas: [["Cooperativa", "#/cooperativa"], ["Datos y expediente legal"]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("cooperativa")),
        titulo: c.razon_social,
        insignias: [insignia(exp.estado === "completo" ? "ok" : "bad", exp.estado === "completo" ? "Identidad completa" : "Falta la identidad")],
        detalle: [h("span", { class: "mono" }, `RUC ${c.ruc}`), ` · ${nombreTipo(c.tipo_organizacion)}`, c.codigo ? ` · código ${c.codigo}` : "", ` · ${lugares(c.distrito, c.provincia, c.departamento)}`],
      }),
      seccion({
        titulo: "Datos de la organización",
        sub: "Los usa el DEX para identificar al exportador. Los cuatro son necesarios para que un lote quede listo.",
        acciones: puedo.admin && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirDatos(c, recargar) }, "Editar"),
        contenido: [
          c.faltan_datos.length > 0 && h("p", { class: "alerta bad" }, `Falta: ${c.faltan_datos.join(", ")}. Sin estos datos, ningún lote queda listo.`),
          rejilla([
            { grupo: "Organización" },
            { etiqueta: "Razón social", valor: c.razon_social },
            { etiqueta: "RUC", valor: c.ruc, mono: true },
            { etiqueta: "Tipo", valor: nombreTipo(c.tipo_organizacion) },
            { etiqueta: "Dirección postal", valor: c.direccion_postal },
            { etiqueta: "Correo de contacto", valor: c.correo },
            { grupo: "Representante legal" },
            { etiqueta: "Nombre", valor: c.representante_nombre },
            { etiqueta: "DNI", valor: c.representante_dni, mono: true },
          ]),
        ],
      }),
      seccion({
        titulo: "Identidad",
        sub: "Ficha RUC, partida registral y vigencia de poderes: el DEX nombra al exportador y a su representante. Si alguno falta o venció, ningún lote queda listo.",
        contenido: [
          requisito(requisitos.identidad),
          exp.faltan.length > 0 && h("p", { class: "alerta bad" }, `Falta o está vencido: ${exp.faltan.map((x) => nombres[x]).join(", ")}.`),
          leyendaTonos({ bloquea: "falta o venció: ningún lote queda listo", falta: "vence pronto", listo: "vigente" }),
          exp.consulta_ruc && h("p", { class: "panel-sub" }, "Para cotejar la ficha RUC: ", h("a", { href: exp.consulta_ruc, target: "_blank", rel: "noopener" }, "Consulta RUC de SUNAT"), ". El sistema no consulta esa página: la comparación la hace una persona."),
          listaCasillas(identidad, puedo, recargar, exp.consulta_ruc),
        ],
      }),
      seccion({
        titulo: "Tributos y registro",
        sub: "No frenan un lote: lo que falte se muestra y llega al informe de hallazgos. La declaración de renta vence sola a los 18 meses de su presentación.",
        contenido: [
          requisito(requisitos.tributos),
          requisitos.registro_cooperativas?.estado !== "no_aplica" && requisito(requisitos.registro_cooperativas),
          leyendaTonos({ bloquea: null, falta: "falta, vencido o por vencer: no frena", listo: "vigente" }),
          listaCasillas(tributos, puedo, recargar, exp.consulta_ruc),
        ],
      }),
      bloquePolitica(c, p, puedo, recargar),
      exp.anteriores.length > 0 &&
        h(
          "section",
          { class: "sect" },
          h(
            "details",
            { class: "no-aplican" },
            h("summary", {}, `Documentos anteriores (${exp.anteriores.length})`),
            h("p", { class: "panel-sub" }, "Ya no se cargan o no aplican a este tipo de organización. Se conservan y no cuentan para nada."),
            h("ul", { class: "casillas" }, exp.anteriores.map((x) => filaCasilla(x, puedo, recargar, null))),
          ),
        ),
    ),
  };
}

// Documentos de sustento: lista con ver y anular, y carga con foto o PDF.
// En el celular, el selector de archivos ofrece tomar la foto con la cámara.

import { llamarApi } from "./api.js";
import { TIPOS_DOCUMENTO } from "./textos.js";
import { abrirModal, campo, enviarCon, fecha, h, toast, vacio } from "./ui.js";

export async function verDocumento(documento) {
  // La ventana se abre en el mismo clic para que el navegador no la bloquee.
  const ventana = window.open("about:blank", "_blank");
  try {
    const { url } = await llamarApi(`/documentos/${documento.id}/url`);
    if (ventana) {
      ventana.opener = null;
      ventana.location.href = url;
    } else {
      window.location.assign(url);
    }
  } catch (error) {
    ventana?.close();
    toast(error.message, "bad");
  }
}

/** Anula un documento con motivo; no se borra. */
export function anularDocumento(documento, alCambiar) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular" }, "Anular documento");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular" },
    h("p", {}, "El documento no se borra: queda anulado y deja de respaldar el dato."),
    campo({ etiqueta: "Motivo", name: "motivo", required: true, maxlength: 200 }),
  );
  const { cerrar } = abrirModal({
    titulo: `Anular ${(TIPOS_DOCUMENTO[documento.tipo] ?? "documento").toLowerCase()}`,
    subtitulo: documento.nombre_original,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/documentos/${documento.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("Documento anulado.");
    alCambiar();
  });
}

/**
 * Registra el cotejo en fuente de un documento: qué se consultó y qué se encontró (Parte 4). Desde la adenda 6
 * lo usan el expediente de la organización y la declaración aduanera del lote. `consultas`: [[url, nombre]] de
 * los registros públicos donde se coteja; `ayuda`: lo que conviene anotar.
 */
export function abrirCotejo(documento, { titulo, consultas = [], ayuda }, alCotejar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-cotejo" }, "Registrar cotejo");
  const formulario = h(
    "form",
    { class: "form", id: "form-cotejo" },
    h("p", {}, "Cotejar es comprobar el documento en el registro público de quien lo emitió. El sistema no consulta ese registro: lo hace una persona, y queda constancia de quién y cuándo."),
    consultas.length > 0 && h("p", { class: "fila-acciones" }, consultas.map(([url, nombre]) => h("a", { href: url, target: "_blank", rel: "noopener" }, nombre))),
    h("label", { class: "field" }, "Qué consultaste y qué encontraste", h("textarea", { class: "input texto-libre", name: "nota", required: true, minlength: 10, maxlength: 4000, rows: 3 }), ayuda && h("small", {}, ayuda)),
  );
  const { cerrar } = abrirModal({ titulo: `Cotejar: ${titulo}`, subtitulo: `N.º ${documento.numero ?? "—"} · ${documento.entidad_emisora ?? ""}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(`/documentos/${documento.id}/cotejo`, { metodo: "POST", cuerpo: { nota } });
    cerrar();
    toast("Cotejo registrado.");
    alCotejar();
  });
}

// La hoja firmada hizo vigente su declaración (adenda 5): no se anula a mano.
const NO_ANULABLES = new Set(["hoja_declaracion_productor"]);

export function listaDocumentos(documentos, { puedeAnular = false, alCambiar }) {
  if (!documentos.length) return vacio({ titulo: "Sin documentos", texto: "Aquí aparecen los documentos que respaldan los datos." });
  return h(
    "div",
    { class: "tabla-caja" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "Documento"), h("th", { class: "ocultar-sm" }, "Cargado"), h("th", {}, "Estado"), h("th", {}, h("span", { class: "sr-only" }, "Acciones")))),
      h(
        "tbody",
        {},
        documentos.map((d) =>
          h(
            "tr",
            {},
            h("td", {}, TIPOS_DOCUMENTO[d.tipo] ?? d.tipo, h("span", { class: "sec" }, d.nombre_original)),
            h("td", { class: "ocultar-sm fecha" }, fecha(d.creado_en, { hora: true }), d.subido_por_nombre && h("span", { class: "sec" }, d.subido_por_nombre)),
            h(
              "td",
              {},
              d.vigente
                ? h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Vigente")
                : h("span", { class: "badge", title: d.motivo_anulacion }, h("span", { class: "dot" }), "Anulado"),
            ),
            h(
              "td",
              { class: "acciones" },
              h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(d) }, "Ver"),
              puedeAnular && d.vigente && !NO_ANULABLES.has(d.tipo) && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => anularDocumento(d, alCambiar) }, "Anular"),
            ),
          ),
        ),
      ),
    ),
  );
}

/** Formulario de carga. tipos: [[valor, texto]]; ruta: endpoint que recibe tipo + archivo. */
export function formularioCarga({ tipos, ruta, alCargar, textoBoton = "Cargar documento" }) {
  const boton = h("button", { class: "btn btn-primary", type: "submit" }, textoBoton);
  const formulario = h(
    "form",
    { class: "form carga" },
    tipos.length > 1
      ? campo({ etiqueta: "Tipo de documento", name: "tipo", opciones: tipos, required: true })
      : h("input", { type: "hidden", name: "tipo", value: tipos[0][0] }),
    h(
      "label",
      { class: "field" },
      "Archivo (foto o PDF, hasta 10 MB)",
      h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true }),
    ),
    boton,
  );
  enviarCon(formulario, boton, async () => {
    const datos = new FormData(formulario);
    await llamarApi(ruta, { metodo: "POST", formulario: datos });
    formulario.reset();
    toast("Documento cargado.");
    await alCargar();
  });
  return formulario;
}

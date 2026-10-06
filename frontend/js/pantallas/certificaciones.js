// Certificaciones de la cooperativa (Parte 9): las que estén vigentes aparecen en el contexto del informe de
// hallazgos (criterio 7). Cada una se registra con su documento. Solo el administrador registra, edita o
// anula; el resto del personal las ve. Una certificación no se borra: se anula con motivo.

import { llamarApi } from "../api.js";
import { verDocumento } from "../documentos.js";
import { rolEfectivo } from "../estado.js";
import { abrirModal, cabeceraFicha, campo, enviarCon, fecha, h, icono, seccion, toast, vacio } from "../ui.js";
import { seccionesCooperativa } from "./vacia.js";

const ESTADOS = {
  vigente: ["ok", "Vigente"],
  por_iniciar: ["info", "Por iniciar"],
  vencida: ["warn", "Vencida"],
  anulada: ["bad", "Anulada"],
};

function insignia([clase, texto]) {
  return h("span", { class: `badge ${clase}`.trim() }, h("span", { class: "dot" }), texto);
}

function campos(c = {}) {
  return [
    campo({ etiqueta: "Nombre de la certificación", name: "nombre", value: c.nombre ?? "", required: true, minlength: 2, maxlength: 200, ayuda: "Tal como figura en el documento, por ejemplo el sello o el programa." }),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Entidad certificadora", name: "entidad_certificadora", value: c.entidad_certificadora ?? "", required: true, minlength: 2, maxlength: 200 }),
      campo({ etiqueta: "Número", name: "numero", value: c.numero ?? "", required: true, maxlength: 100, class: "input mono" }),
    ),
    h("div", { class: "grid2" }, campo({ etiqueta: "Vigente desde", name: "vigente_desde", type: "date", value: c.vigente_desde ?? "", required: true }), campo({ etiqueta: "Vigente hasta", name: "vigente_hasta", type: "date", value: c.vigente_hasta ?? "", required: true })),
  ];
}

function abrirRegistro(alGuardar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-certificacion" }, "Registrar");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true });
  const formulario = h("form", { class: "form", id: "form-certificacion" }, campos(), h("label", { class: "field" }, "Documento de la certificación (foto o PDF, hasta 10 MB)", archivo));
  const { cerrar } = abrirModal({ titulo: "Registrar certificación", subtitulo: "Aparece en el contexto del informe de hallazgos mientras esté vigente.", contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = new FormData();
    for (const clave of ["nombre", "entidad_certificadora", "numero", "vigente_desde", "vigente_hasta"]) cuerpo.append(clave, datos[clave]);
    cuerpo.append("archivo", archivo.files[0]);
    await llamarApi("/certificaciones", { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast("Certificación registrada.");
    alGuardar();
  });
}

function abrirEdicion(c, alGuardar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-editar-cert" }, "Guardar");
  const formulario = h("form", { class: "form", id: "form-editar-cert" }, campos(c));
  const { cerrar } = abrirModal({ titulo: "Editar certificación", subtitulo: c.nombre, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    await llamarApi(`/certificaciones/${c.id}`, { metodo: "PATCH", cuerpo: datos });
    cerrar();
    toast("Certificación actualizada.");
    alGuardar();
  });
}

function abrirAnulacion(c, alAnular) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-cert" }, "Anular");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-cert" },
    h("p", {}, "La certificación no se borra: queda anulada con su motivo y deja de aparecer en el informe."),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, minlength: 10, maxlength: 1000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular certificación", subtitulo: c.nombre, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/certificaciones/${c.id}`, { metodo: "PATCH", cuerpo: { anular: true, motivo } });
    cerrar();
    toast("Certificación anulada.", "warn");
    alAnular();
  });
}

function tabla(lista, admin, recargar) {
  if (!lista.length) return vacio({ titulo: "Sin certificaciones", texto: "El informe dirá que la cooperativa no registra certificaciones vigentes." });
  return h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "Certificación"), h("th", {}, "Número"), h("th", {}, "Vigencia"), h("th", {}, "Estado"), h("th", {}, h("span", { class: "sr-only" }, "Acciones")))),
      h(
        "tbody",
        {},
        lista.map((c) =>
          h(
            "tr",
            {},
            h("td", {}, h("b", {}, c.nombre), h("span", { class: "sec" }, c.entidad_certificadora)),
            h("td", { class: "mono" }, c.numero),
            h("td", {}, `${fecha(c.vigente_desde)} a ${fecha(c.vigente_hasta)}`),
            h("td", {}, insignia(ESTADOS[c.estado] ?? ["", c.estado]), c.motivo_anulacion && h("span", { class: "sec" }, `Motivo: ${c.motivo_anulacion}`)),
            h(
              "td",
              {},
              h(
                "span",
                { class: "fila-acciones" },
                c.documento_id && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento({ id: c.documento_id }) }, icono("eye"), "Ver"),
              admin && c.estado !== "anulada" && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirEdicion(c, recargar) }, "Editar"),
                admin && c.estado !== "anulada" && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirAnulacion(c, recargar) }, "Anular"),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

export default async function certificaciones({ recargar }) {
  const lista = await llamarApi("/certificaciones");
  const admin = rolEfectivo() === "admin_cooperativa";
  const vigentes = lista.filter((c) => c.estado === "vigente").length;
  return {
    titulo: "Certificaciones",
    migas: [["Cooperativa", "#/cooperativa"], ["Certificaciones"]],
    secciones: seccionesCooperativa(),
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("shield")),
        titulo: "Certificaciones de la cooperativa",
        detalle: "Las vigentes aparecen en el contexto del informe de hallazgos, tal como se registraron. El sistema no las coteja con la entidad certificadora.",
        cifra: String(vigentes),
        cifraTexto: vigentes === 1 ? "vigente" : "vigentes",
        accion: admin && h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirRegistro(recargar) }, icono("mas"), "Registrar certificación"),
      }),
      seccion({ titulo: "Registradas", contenido: tabla(lista, admin, recargar) }),
    ),
  };
}

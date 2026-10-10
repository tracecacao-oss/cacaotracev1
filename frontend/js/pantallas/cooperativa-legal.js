// Datos y expediente legal de la cooperativa (Parte 8): los datos que el DEX necesita para identificar al
// exportador y las seis casillas del expediente, con su estado, su nivel de verificación y sus acciones. No
// hay exenciones: las seis deben estar vigentes. Solo el administrador edita los datos y carga o anula
// documentos; el operador y el lector los ven.

import { llamarApi } from "../api.js";
import { anularDocumento, verDocumento } from "../documentos.js";
import { rolEfectivo } from "../estado.js";
import { hoyLima as hoy } from "../fechas.js";
import { ESTADOS_CASILLA, insigniaNivel } from "../textos.js";
import { lugares } from "../ubigeo.js";
import { abrirModal, cabeceraFicha, campo, claseTono, enviarCon, fecha, h, icono, leyendaTonos, ordenarPorTono, rejilla, seccion, toast } from "../ui.js";

function insignia(clase, texto) {
  return h("span", { class: `badge ${clase}`.trim() }, h("span", { class: "dot" }), texto);
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
  const { cerrar } = abrirModal({ titulo: "Datos de la cooperativa", subtitulo: "Los usa el DEX para identificar al exportador.", contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    await llamarApi("/cooperativa", { metodo: "PATCH", cuerpo: datos });
    cerrar();
    toast("Datos guardados.");
    alGuardar();
  });
}

function abrirCarga(casilla, alCargar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-legal-coop" }, "Cargar documento");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true });
  const formulario = h(
    "form",
    { class: "form", id: "form-legal-coop" },
    h("div", { class: "grid2" }, campo({ etiqueta: "Número (partida, registro o constancia)", name: "numero", required: true, maxlength: 200 }), campo({ etiqueta: "Entidad emisora", name: "entidad_emisora", required: true, maxlength: 200 })),
    h("div", { class: "grid2" }, campo({ etiqueta: "Fecha de emisión", name: "fecha_emision", type: "date", max: hoy(), required: true }), campo({ etiqueta: "Fecha de vencimiento (si tiene)", name: "fecha_vencimiento", type: "date" })),
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

function abrirCotejo(documento, casilla, alCotejar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-cotejo-coop" }, "Registrar cotejo");
  const formulario = h(
    "form",
    { class: "form", id: "form-cotejo-coop" },
    h("p", {}, "Cotejar es comprobar el documento en el registro público de quien lo emitió. Queda constancia de quién lo hizo y cuándo."),
    h("label", { class: "field" }, "Qué consultaste y qué encontraste", h("textarea", { class: "input texto-libre", name: "nota", required: true, minlength: 10, maxlength: 4000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: `Cotejar: ${casilla.nombre}`, subtitulo: `N.º ${documento.numero ?? "—"} · ${documento.entidad_emisora ?? ""}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(`/documentos/${documento.id}/cotejo`, { metodo: "POST", cuerpo: { nota } });
    cerrar();
    toast("Cotejo registrado.");
    alCotejar();
  });
}

/** Los seis impiden que un lote quede listo: rojo si falta o venció, amarillo si vence pronto, verde vigente. */
function tonoCasilla(c) {
  return c.estado === "vigente" ? "listo" : c.estado === "por_vencer" ? "falta" : "bloquea";
}

function filaCasilla(c, puedo, recargar) {
  const [clase, texto] = ESTADOS_CASILLA[c.estado] ?? ["", c.estado];
  const vigentes = c.documentos.filter((d) => d.vigente);
  return h(
    "li",
    { class: claseTono(tonoCasilla(c)) },
    h(
      "div",
      { class: "casilla-h" },
      h("div", {}, h("b", {}, c.nombre), h("span", { class: "sec" }, `${c.grupo}${c.registro_consultable ? " · con registro público" : " · sin registro público consultable"}`)),
      h("span", { class: "fila-acciones" }, insignia(clase, texto), c.nivel && insigniaNivel(c.nivel), c.vence_en && h("span", { class: "badge" }, `vence ${fecha(c.vence_en)}`)),
    ),
    vigentes.map((d) =>
      h(
        "div",
        { class: "casilla-doc" },
        h("span", {}, `N.º ${d.numero ?? "—"} · ${d.entidad_emisora ?? "—"} · emitido ${fecha(d.fecha_emision)}${d.fecha_vencimiento ? ` · vence ${fecha(d.fecha_vencimiento)}` : ""}`),
        d.cotejado_en && h("span", { class: "sec" }, `Cotejado el ${fecha(d.cotejado_en)}: ${d.cotejo_nota}`),
        h(
          "span",
          { class: "fila-acciones" },
          h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(d) }, icono("eye"), "Ver"),
          puedo.cotejar && c.registro_consultable && !d.cotejado_en && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirCotejo(d, c, recargar) }, "Cotejar en fuente"),
          puedo.admin && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => anularDocumento(d, recargar) }, "Anular"),
        ),
      ),
    ),
    puedo.admin && h("div", { class: "fila-acciones" }, h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirCarga(c, recargar) }, icono("upload"), vigentes.length ? "Cargar otro" : "Cargar documento")),
  );
}

export default async function cooperativaLegal({ recargar }) {
  const [c, exp] = await Promise.all([llamarApi("/cooperativa"), llamarApi("/cooperativa/expediente")]);
  const rol = rolEfectivo();
  const puedo = { admin: rol === "admin_cooperativa", cotejar: ["admin_cooperativa", "operador"].includes(rol) };
  const nombres = Object.fromEntries(exp.casillas.map((x) => [x.codigo, x.nombre]));
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
        insignias: [insignia(exp.estado === "completo" ? "ok" : "bad", exp.estado === "completo" ? "Expediente completo" : "Expediente incompleto")],
        detalle: [h("span", { class: "mono" }, `RUC ${c.ruc}`), c.codigo ? ` · código ${c.codigo}` : "", ` · ${lugares(c.distrito, c.provincia, c.departamento)}`],
      }),
      seccion({
        titulo: "Datos de la cooperativa",
        sub: "Los usa el DEX para identificar al exportador. Los cuatro son necesarios para que un lote quede listo.",
        acciones: puedo.admin && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirDatos(c, recargar) }, "Editar"),
        contenido: [
          c.faltan_datos.length > 0 && h("p", { class: "alerta bad" }, `Falta: ${c.faltan_datos.join(", ")}. Sin estos datos, ningún lote queda listo.`),
          rejilla([
            { grupo: "Cooperativa" },
            { etiqueta: "Razón social", valor: c.razon_social },
            { etiqueta: "RUC", valor: c.ruc, mono: true },
            { etiqueta: "Dirección postal", valor: c.direccion_postal },
            { etiqueta: "Correo de contacto", valor: c.correo },
            { grupo: "Representante legal" },
            { etiqueta: "Nombre", valor: c.representante_nombre },
            { etiqueta: "DNI", valor: c.representante_dni, mono: true },
          ]),
        ],
      }),
      seccion({
        titulo: "Expediente legal",
        sub: "Seis documentos sin exenciones: los seis deben estar vigentes o por vencer para que un lote quede listo.",
        contenido: [
          exp.faltan.length > 0 && h("p", { class: "alerta bad" }, `Falta o está vencido: ${exp.faltan.map((x) => nombres[x]).join(", ")}.`),
          leyendaTonos({ bloquea: "falta o venció: ningún lote queda listo", falta: "vence pronto", listo: "vigente" }),
          h("ul", { class: "casillas" }, ordenarPorTono(exp.casillas, tonoCasilla).map((x) => filaCasilla(x, puedo, recargar))),
        ],
      }),
    ),
  };
}

// Detalle de tanda, con el inspector del diseño: datos, documento de entrega, requisitos, alertas, historial de
// decisiones y enlace a su DOP. Mientras está registrada u observada se edita y se decide; una vez
// validada o anulada ya no tiene ningún botón de edición.

import { llamarApi } from "../api.js";
import { formularioCarga, listaDocumentos } from "../documentos.js";
import { rolEfectivo } from "../estado.js";
import { PRODUCTO, REQUISITOS_TANDA, insigniaDop, insigniaNivel, insigniaTanda, kilos } from "../textos.js";
import { camposTanda, cuerpoTanda, descargarPdf, listaAlertas, listaRequisitos } from "../tandas.js";
import { abrirModal, cabeceraFicha, enviarCon, fecha, h, icono, rejilla, seccion, toast } from "../ui.js";

const DECISION = { validar: "Validó la tanda y emitió su DOP", observar: "Observó la tanda", anular: "Anuló la tanda" };

function abrirEdicion(t, lugares, configuracion, alGuardar) {
  const campos = camposTanda(t, { lugares, configuracion });
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-tanda" }, "Guardar cambios");
  const formulario = h("form", { class: "form", id: "form-tanda" }, h("b", {}, "Pesaje y cosecha"), campos.pesaje, h("b", {}, "Documento de entrega"), campos.documento);
  const { cerrar } = abrirModal({
    titulo: "Corregir la tanda",
    subtitulo: `${t.codigo} · cada cambio queda en la auditoría con su valor anterior`,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    if (datos.cosecha_desde > datos.cosecha_hasta) throw new Error("La cosecha empieza después de terminar: revisa las fechas.");
    await llamarApi(`/tandas/${t.id}`, { metodo: "PATCH", cuerpo: cuerpoTanda(datos, t) });
    cerrar();
    toast("Tanda corregida.");
    alGuardar();
  });
}

function abrirValidacion(t, configuracion, alValidar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-validar" }, icono("check"), "Validar y emitir DOP");
  const formulario = h(
    "form",
    { class: "form", id: "form-validar" },
    h("p", {}, "Validar emite el DOP: una copia sellada del productor, la parcela y la tanda que ya no cambia."),
    t.alertas.length > 0 && listaAlertas(t.alertas, t.alertas_detalle, configuracion),
    h(
      "label",
      { class: "field" },
      t.nota_obligatoria ? "Nota de validación (obligatoria con alertas, mínimo 50 caracteres)" : "Nota de validación (opcional)",
      h("textarea", { class: "input texto-libre", name: "nota", required: t.nota_obligatoria, minlength: t.nota_obligatoria ? 50 : 0, maxlength: 4000, rows: 4 }),
    ),
  );
  const { cerrar } = abrirModal({ titulo: "Validar tanda", subtitulo: t.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    const validada = await llamarApi(`/tandas/${t.id}/validar`, { metodo: "POST", cuerpo: { nota: nota.trim() || null } });
    cerrar();
    toast(`DOP emitido: ${validada.dop.codigo}`);
    alValidar();
  });
}

function abrirMotivo(t, accion, alGuardar) {
  const anular = accion === "anular";
  const boton = h("button", { class: `btn ${anular ? "btn-danger" : "btn-primary"}`, type: "submit", form: "form-motivo" }, anular ? "Anular tanda" : "Observar tanda");
  const formulario = h(
    "form",
    { class: "form", id: "form-motivo" },
    h(
      "p",
      {},
      anular
        ? "Anular es para una tanda registrada por error: no genera DOP ni cuenta en ningún cálculo. No se puede deshacer."
        : "La tanda queda observada con tu motivo. Se corrige y se valida después.",
    ),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, maxlength: 200, rows: 3 })),
  );
  const { cerrar } = abrirModal({
    titulo: anular ? "Anular tanda" : "Observar tanda",
    subtitulo: t.codigo,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/tandas/${t.id}/${accion}`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast(anular ? "Tanda anulada." : "Tanda observada.", "warn");
    alGuardar();
  });
}

export default async function tanda({ parametros: [id], recargar }) {
  const [t, configuracion, lugares] = await Promise.all([llamarApi(`/tandas/${id}`), llamarApi("/configuracion"), llamarApi("/lugares")]);
  const registro = ["admin_cooperativa", "operador"].includes(rolEfectivo());
  const abierta = ["registrada", "observada"].includes(t.estado);
  const editable = registro && abierta;
  const archivosDoc = t.documentos.filter((d) => d.tipo === "documento_entrega");
  const nombreDoc = t.doc_entrega_tipo_nombre ?? "Documento de entrega";
  const faltan = t.requisitos.filter((r) => !r.cumple).map((r) => REQUISITOS_TANDA[r.codigo] ?? r.codigo);

  const accion = t.dop
    ? h("a", { class: "btn btn-primary", href: `#/dops/${t.dop.id}` }, icono("file"), "Ver DOP")
    : editable &&
      h(
        "button",
        {
          class: "btn btn-primary",
          type: "button",
          disabled: !t.puede_validar,
          title: t.puede_validar ? "Valida la tanda y emite su DOP" : `Falta: ${faltan.join(", ")}`,
          onclick: () => abrirValidacion(t, configuracion, recargar),
        },
        icono("check"),
        "Validar y emitir DOP",
      );

  const evaluacion = seccion({
    titulo: abierta ? "Requisitos y alertas" : "Requisitos y alertas al decidir",
    sub: abierta
      ? "Todos los requisitos deben cumplirse. Las alertas no impiden validar: obligan a dejar una nota."
      : "Tal como estaban cuando se tomó la última decisión.",
    contenido: [listaRequisitos(t.requisitos), h("div", { class: "subtitulo-seccion" }, "Alertas"), listaAlertas(t.alertas, t.alertas_detalle, configuracion)],
  });

  const datos = seccion({
    titulo: "Pesaje y cosecha",
    sub: `Registrada por ${t.registrada_por_nombre ?? "—"} el ${fecha(t.creado_en, { hora: true })}`,
    acciones: editable && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirEdicion(t, lugares, configuracion, recargar) }, icono("wrench"), "Corregir"),
    contenido: rejilla([
      { etiqueta: "Cancha de acopio", valor: t.lugar_nombre },
      { etiqueta: "Fecha y hora del pesaje", valor: fecha(t.recibida_en, { hora: true }) },
      { etiqueta: "Producto", valor: PRODUCTO[t.estado_producto] },
      { etiqueta: "Peso neto en balanza", valor: kilos(t.peso_kg), mono: true },
      { etiqueta: "Peso seco equivalente", valor: kilos(t.peso_seco_equivalente_kg), mono: true, extra: t.estado_producto === "baba" ? "Estimación para comparar contra el tope; el peso seco real se mide en el proceso." : null },
      { etiqueta: "Sacos", valor: t.numero_sacos == null ? null : String(t.numero_sacos), mono: true },
      t.estado_producto === "seco" && { etiqueta: "Humedad", valor: t.humedad_pct == null ? null : `${t.humedad_pct} %`, mono: true },
      { etiqueta: "Variedad", valor: t.variedad_nombre },
      { etiqueta: "Tipo de semilla", valor: t.tipo_semilla },
      { etiqueta: "Cosecha", valor: `Del ${fecha(t.cosecha_desde)} al ${fecha(t.cosecha_hasta)}` },
    ]),
  });

  const documento = seccion({
    titulo: nombreDoc,
    sub: t.doc_entrega_tipo ? "Documento de entrega de la tanda. Sin cotejo en su fuente: queda como documentado." : "Sin documento de entrega la tanda se guarda, pero no se valida.",
    acciones: t.doc_entrega_numero && insigniaNivel("documentado"),
    contenido: [
      rejilla([
        { etiqueta: "Tipo", valor: t.doc_entrega_tipo_nombre },
        { etiqueta: "Serie y número", valor: t.doc_entrega_numero, mono: true },
        { etiqueta: "Fecha de emisión", valor: t.doc_entrega_fecha_emision ? fecha(t.doc_entrega_fecha_emision) : null },
        { etiqueta: "RUC del emisor", valor: t.doc_entrega_ruc_emisor, mono: true },
        { etiqueta: "Peso declarado", valor: t.doc_entrega_peso_kg == null ? null : kilos(t.doc_entrega_peso_kg), mono: true },
      ]),
      listaDocumentos(archivosDoc, { puedeAnular: editable, alCambiar: recargar }),
      editable &&
        !archivosDoc.some((d) => d.vigente) &&
        formularioCarga({ tipos: [["documento_entrega", nombreDoc]], ruta: `/tandas/${t.id}/documentos`, alCargar: recargar, textoBoton: "Cargar el documento" }),
    ],
  });

  const decisiones = seccion({
    titulo: "Historial de decisiones",
    sub: "Cada decisión queda registrada y no se edita.",
    acciones: editable && [
      t.estado === "registrada" && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirMotivo(t, "observar", recargar) }, "Observar"),
      h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirMotivo(t, "anular", recargar) }, "Anular"),
    ],
    contenido: t.decisiones.length
      ? h(
          "ol",
          { class: "linea-tiempo" },
          t.decisiones.map((d) =>
            h(
              "li",
              {},
              h("b", {}, DECISION[d.decision] ?? d.decision),
              h("span", { class: "sec" }, [fecha(d.decidida_en, { hora: true }), d.decidida_por_nombre].filter(Boolean).join(" · ")),
              d.nota && h("span", { class: "sec" }, d.decision === "validar" ? `Nota: ${d.nota}` : `Motivo: ${d.nota}`),
            ),
          ),
        )
      : h("p", { class: "panel-sub" }, "Todavía sin decisiones: la tanda está registrada."),
  });

  const dop =
    t.dop &&
    seccion({
      titulo: "DOP",
      acciones: insigniaDop(t.dop.estado),
      contenido: h(
        "div",
        { class: "fila-acciones" },
        h("a", { class: "btn btn-sm mono", href: `#/dops/${t.dop.id}` }, t.dop.codigo),
        h("button", { class: "btn btn-sm", type: "button", onclick: () => descargarPdf(`/dops/${t.dop.id}/pdf`) }, icono("download"), "Descargar PDF"),
      ),
    });

  return {
    titulo: t.codigo,
    migas: [["Lotes y proceso", "#/lotes"], ["Recepción", "#/lotes/recepcion"], [t.codigo]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("sack")),
        titulo: t.codigo,
        codigo: true,
        insignias: [insigniaTanda(t.estado), t.dop && insigniaDop(t.dop.estado)],
        detalle: [
          h("a", { href: `#/productores/${t.productor.id}` }, `${t.productor.nombres} ${t.productor.apellidos}`),
          " · ",
          h("a", { href: `#/parcelas/${t.parcela.id}`, class: "mono" }, t.parcela.codigo),
          ` ${t.parcela.nombre} · ${fecha(t.recibida_en, { hora: true })}`,
        ],
        cifra: kilos(t.peso_kg),
        cifraTexto: PRODUCTO[t.estado_producto].toLowerCase(),
        accion: rolEfectivo() === "consulta" ? null : accion,
      }),
      dop,
      evaluacion,
      datos,
      documento,
      decisiones,
    ),
  };
}

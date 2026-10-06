// Detalle de un lote de exportación con pestañas Selección, Genealogía, Indicadores y, desde la Parte 8,
// Embarque y Recomprobación. Un lote con desviación FIFO muestra su etiqueta y su motivo; uno bloqueado, una
// franja fija con las comprobaciones que fallan. Los resultados se nombran "sin observaciones" y "con
// observaciones". Un lote armado se anula con motivo; uno bloqueado o listo, solo un administrador.

import { llamarApi } from "../api.js";
import { anularDocumento, verDocumento } from "../documentos.js";
import { rolEfectivo } from "../estado.js";
import { estadoLote, insignia, insigniaFifo, seccionesExportacion, tarjetasIndicadores, vistaGenealogia } from "../exportacion.js";
import { kilos } from "../textos.js";
import { abrirModal, cabeceraFicha, campo, cargando, enviarCon, errorDeCarga, fecha, h, icono, reemplazar, seccion, toast } from "../ui.js";

const PESTANAS = [
  ["seleccion", "Selección"],
  ["genealogia", "Genealogía"],
  ["indicadores", "Indicadores"],
  ["embarque", "Embarque"],
  ["recomprobacion", "Recomprobación"],
];
const RESULTADO = {
  sin_observaciones: ["ok", "Sin observaciones"],
  con_observaciones: ["warn", "Con observaciones"],
};
const hoy = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Lima" }).format(new Date());
let recordada = { id: null, clave: "seleccion" };

function abrirAnulacion(l, alAnular) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-lote" }, "Anular lote");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-lote" },
    h(
      "p",
      { class: "alerta warn" },
      l.estado === "en_armado"
        ? "La selección se descarta y la orden queda abierta para otro lote."
        : "Los kilos vuelven al saldo de cada tanda final, las agotadas vuelven al stock y la orden queda abierta para otro lote. La genealogía se conserva como historial.",
    ),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, maxlength: 200, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular lote", subtitulo: l.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/lotes/${l.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("Lote anulado.", "warn");
    alAnular();
  });
}

function puedeAnular(l) {
  const rol = rolEfectivo();
  if (["en_armado", "armado"].includes(l.estado)) return ["admin_cooperativa", "operador"].includes(rol);
  return ["bloqueado", "listo"].includes(l.estado) && rol === "admin_cooperativa";
}

function pestanaSeleccion(l, opera, recargar) {
  const total = l.asignaciones.reduce((s, a) => s + Number(a.kg_asignados), 0);
  return seccion({
    titulo: "Selección",
    sub: l.estado === "en_armado" ? "La selección todavía puede cambiar. Los saldos se descuentan al confirmar." : "Los kilos que el lote tomó de cada tanda final. Un lote confirmado ya no cambia su stock.",
    acciones: [
      opera && l.estado === "en_armado" && h("a", { class: "btn btn-sm", href: `#/lotes-exportacion/${l.id}/armar` }, icono("layers"), "Cambiar la selección"),
      puedeAnular(l) && h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirAnulacion(l, recargar) }, "Anular lote"),
    ].filter(Boolean),
    contenido: l.asignaciones.length
      ? h(
          "div",
          { class: "tbl-box" },
          h(
            "table",
            { class: "tabla" },
            h("thead", {}, h("tr", {}, h("th", {}, "Tanda final"), h("th", { class: "ocultar-sm" }, "Ingreso al stock"), h("th", { class: "num" }, "Saldo actual"), h("th", { class: "num" }, "Kilos del lote"))),
            h(
              "tbody",
              {},
              l.asignaciones.map((a) =>
                h(
                  "tr",
                  {},
                  h("td", {}, h("a", { href: `#/tandas-finales/${a.tanda_final_id}`, class: "mono" }, a.codigo), h("span", { class: "sec" }, [a.corrida_codigo, a.dpp?.codigo].filter(Boolean).join(" · "))),
                  h("td", { class: "ocultar-sm" }, fecha(a.ingreso_stock_en, { hora: true })),
                  h("td", { class: "num mono" }, kilos(a.saldo_kg)),
                  h("td", { class: "num mono" }, kilos(a.kg_asignados)),
                ),
              ),
            ),
            h("tfoot", {}, h("tr", {}, h("th", { colspan: 3 }, "Total"), h("th", { class: "num mono" }, kilos(total)))),
          ),
        )
      : h("p", { class: "panel-sub" }, "Sin tandas finales seleccionadas."),
  });
}

function pestanaGenealogia(l) {
  if (l.estado === "en_armado") return seccion({ titulo: "Genealogía", contenido: h("p", { class: "panel-sub" }, "La genealogía se calcula al confirmar el lote.") });
  const caja = h("div", {}, cargando());
  llamarApi(`/lotes/${l.id}/genealogia`)
    .then((g) => reemplazar(caja, vistaGenealogia(g, { lote: l, incrustada: true })))
    .catch((error) => reemplazar(caja, errorDeCarga(error)));
  return [seccion({ titulo: "Genealogía", sub: "De los kilos del lote, cuántos vienen de cada parcela, con las proporciones que fijó cada corrida." }), caja];
}

function pestanaIndicadores(l) {
  if (!l.indicadores) return seccion({ titulo: "Indicadores", contenido: h("p", { class: "panel-sub" }, "Los indicadores se calculan al confirmar el lote.") });
  return seccion({
    titulo: "Indicadores",
    sub: "Se calculan y se muestran tal cual. Ninguno califica el lote: todos pasan al informe de hallazgos.",
    contenido: tarjetasIndicadores(l.indicadores),
  });
}

// ---------- Embarque ----------

function abrirCargaEmbarque(l, tipo, alCargar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-embarque" }, "Cargar documento");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true });
  const formulario = h(
    "form",
    { class: "form", id: "form-embarque" },
    h("div", { class: "grid2" }, campo({ etiqueta: "Número", name: "numero", required: true, maxlength: 200 }), campo({ etiqueta: "Entidad emisora", name: "entidad_emisora", required: true, maxlength: 200, ayuda: `Habitualmente: ${tipo.emisor_habitual}.` })),
    campo({ etiqueta: "Fecha de emisión", name: "fecha_emision", type: "date", max: hoy(), required: true }),
    h("label", { class: "field" }, "Archivo (foto o PDF, hasta 10 MB)", archivo),
    h("p", { class: "panel-sub" }, "El sistema no lee el documento ni compara sus cifras con las del lote: eso lo revisa una persona."),
  );
  const { cerrar } = abrirModal({ titulo: `Cargar: ${tipo.nombre}`, subtitulo: l.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = new FormData();
    cuerpo.append("tipo", tipo.codigo);
    for (const clave of ["numero", "entidad_emisora", "fecha_emision"]) cuerpo.append(clave, datos[clave]);
    cuerpo.append("archivo", archivo.files[0]);
    await llamarApi(`/lotes/${l.id}/documentos`, { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast("Documento cargado. Recomprueba el lote para que lo tome en cuenta.");
    alCargar();
  });
}

function pestanaEmbarque(l, opera, recargar) {
  const caja = h("div", {}, cargando());
  llamarApi(`/lotes/${l.id}/documentos`)
    .then((e) =>
      reemplazar(
        caja,
        e.faltan.length > 0 && h("p", { class: "alerta warn" }, `Falta: ${e.faltan.join(", ")}.`),
        h(
          "ul",
          { class: "casillas" },
          e.tipos.map((t) => {
            const vigentes = t.documentos.filter((d) => d.vigente);
            return h(
              "li",
              { class: "casilla" },
              h(
                "div",
                { class: "casilla-h" },
                h("div", {}, h("b", {}, t.nombre), h("span", { class: "sec" }, `Emisor habitual: ${t.emisor_habitual}`)),
                insignia(t.cargado ? ["ok", "Cargado"] : ["warn", "Falta"]),
              ),
              vigentes.map((d) =>
                h(
                  "div",
                  { class: "casilla-doc" },
                  h("span", {}, `N.º ${d.numero ?? "—"} · ${d.entidad_emisora ?? "—"} · emitido ${fecha(d.fecha_emision)}`),
                  h(
                    "span",
                    { class: "fila-acciones" },
                    h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(d) }, icono("eye"), "Ver"),
                    opera && e.editable && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => anularDocumento(d, recargar) }, "Anular"),
                  ),
                ),
              ),
              opera && e.editable && h("div", { class: "fila-acciones" }, h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirCargaEmbarque(l, t, recargar) }, icono("upload"), vigentes.length ? "Cargar otro" : "Cargar documento")),
            );
          }),
        ),
      ),
    )
    .catch((error) => reemplazar(caja, errorDeCarga(error)));
  return seccion({
    titulo: "Documentos de embarque",
    sub: l.estado === "cerrado" ? "El lote tiene DEX: sus documentos de embarque ya no cambian." : "Los cuatro deben estar cargados antes de emitir el DEX. Si falta uno, el lote deja de estar listo.",
    contenido: caja,
  });
}

// ---------- Recomprobación ----------

function enlaceCaso(c, irAPestana) {
  switch (c.tipo) {
    case "parcela":
      return h("a", { href: `#/parcelas/${c.id}` }, "Ir a la parcela");
    case "dop":
      return h("a", { href: `#/dops/${c.id}` }, "Ir al DOP");
    case "dpp":
      return h("a", { href: `#/dpps/${c.id}` }, "Ir al DPP");
    case "cooperativa":
    case "expediente_cooperativa":
      return h("a", { href: "#/cooperativa/legal" }, "Ir al expediente de la cooperativa");
    case "importador":
      return h("a", { href: "#/exportacion/importadores" }, "Ir al importador");
    case "embarque":
      return h("button", { class: "btn-link", type: "button", onclick: () => irAPestana("embarque") }, "Cargar el documento");
    default:
      return null;
  }
}

function comprobaciones(r, irAPestana) {
  return h(
    "ul",
    { class: "comprobaciones" },
    r.comprobaciones.map((c) =>
      h(
        "li",
        { class: `comprobacion ${c.resultado}` },
        h("span", { class: "comprobacion-marca", "aria-hidden": "true" }, icono(c.resultado === "sin_observaciones" ? "check" : "alert")),
        h(
          "div",
          {},
          h("div", { class: "comprobacion-h" }, h("b", {}, c.nombre), insignia(RESULTADO[c.resultado]), h("span", { class: "sec" }, c.sobre)),
          c.casos.length > 0 &&
            h(
              "ul",
              { class: "casos" },
              c.casos.map((caso) => h("li", {}, h("span", {}, caso.texto), caso.detalle && h("span", { class: "sec" }, caso.detalle), enlaceCaso(caso, irAPestana))),
            ),
        ),
      ),
    ),
  );
}

function pestanaRecomprobacion(l, opera, recargar, irAPestana) {
  const r = l.recomprobacion;
  const historial = h("div", {});
  const recomprobable = ["armado", "bloqueado", "listo"].includes(l.estado);
  async function recomprobar(e) {
    const boton = e.currentTarget;
    boton.classList.add("is-loading");
    try {
      const res = await llamarApi(`/lotes/${l.id}/recomprobar`, { metodo: "POST" });
      toast(res.resultado === "sin_observaciones" ? "Recomprobación sin observaciones: el lote está listo." : "Recomprobación con observaciones: el lote quedó bloqueado.", res.resultado === "sin_observaciones" ? "ok" : "warn");
      recargar();
    } catch (error) {
      toast(error.message, "bad");
      boton.classList.remove("is-loading");
    }
  }
  llamarApi(`/lotes/${l.id}/recomprobaciones`)
    .then((lista) =>
      reemplazar(
        historial,
        lista.length > 1 &&
          h(
            "details",
            { class: "historial" },
            h("summary", {}, `Historial (${lista.length} recomprobaciones)`),
            h(
              "ul",
              { class: "lista-simple" },
              lista.map((x) => h("li", {}, `${fecha(x.ejecutada_en, { hora: true })} · `, insignia(RESULTADO[x.resultado]), ` · ${x.ejecutada_por_nombre ?? "Sistema (tarea diaria)"}`)),
            ),
          ),
      ),
    )
    .catch(() => null);
  return seccion({
    titulo: "Recomprobación",
    sub: "Las nueve comprobaciones con la fecha del día: confirma que cada requisito que ya se cumplió sigue en pie. No es una evaluación de riesgo. El lote queda listo solo si todas salen sin observaciones.",
    acciones: opera && recomprobable && h("button", { class: "btn btn-primary btn-sm", type: "button", onclick: recomprobar }, icono("rotate"), "Recomprobar"),
    contenido: r
      ? [
          h("p", { class: "panel-sub" }, `Última: ${fecha(r.ejecutada_en, { hora: true })} · ${r.ejecutada_por_nombre ?? "Sistema (tarea diaria)"} · `, insignia(RESULTADO[r.resultado])),
          comprobaciones(r, irAPestana),
          historial,
        ]
      : h("p", { class: "panel-sub" }, recomprobable ? "Todavía no se recomprobó este lote." : "Se recomprueba un lote armado, bloqueado o listo."),
  });
}

export default async function loteExportacion({ parametros: [id], recargar }) {
  const l = await llamarApi(`/lotes/${id}`);
  const opera = ["admin_cooperativa", "operador"].includes(rolEfectivo());
  if (recordada.id !== id) recordada = { id, clave: l.estado === "bloqueado" ? "recomprobacion" : "seleccion" };
  const cuerpo = h("div", { class: "contenido-pestana" });
  const barra = h("div", { class: "seg", role: "tablist", "aria-label": "Secciones del lote" });
  const generadores = {
    seleccion: () => pestanaSeleccion(l, opera, recargar),
    genealogia: () => pestanaGenealogia(l),
    indicadores: () => pestanaIndicadores(l),
    embarque: () => pestanaEmbarque(l, opera, recargar),
    recomprobacion: () => pestanaRecomprobacion(l, opera, recargar, mostrar),
  };
  function mostrar(clave) {
    recordada = { id, clave };
    for (const b of barra.children) b.setAttribute("aria-selected", String(b.dataset.clave === clave));
    reemplazar(cuerpo, generadores[clave]());
  }
  for (const [clave, texto] of PESTANAS) barra.append(h("button", { type: "button", role: "tab", "data-clave": clave, onclick: () => mostrar(clave) }, texto));
  mostrar(recordada.clave);

  const fallan = l.recomprobacion ? l.recomprobacion.comprobaciones.filter((c) => c.resultado === "con_observaciones").length : 0;
  const franja =
    l.estado === "bloqueado" &&
    h(
      "div",
      { class: "verif bad franja-fija", role: "status" },
      icono("alert"),
      h("div", {}, h("b", {}, `Lote bloqueado: ${fallan} ${fallan === 1 ? "comprobación" : "comprobaciones"} con observaciones`), h("span", {}, "No puede recibir DEX hasta que se corrija lo que falla y se recompruebe.")),
      h("button", { class: "btn btn-sm", type: "button", onclick: () => mostrar("recomprobacion") }, "Ver la recomprobación"),
    );

  return {
    titulo: l.codigo,
    migas: [["Exportación", "#/exportacion"], ["Lotes", "#/exportacion/lotes"], [l.codigo]],
    secciones: seccionesExportacion(),
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      franja,
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("container")),
        titulo: l.codigo,
        codigo: true,
        insignias: [estadoLote(l.estado), l.desviacion_fifo && insigniaFifo()],
        detalle: ["Orden ", h("a", { href: `#/ordenes/${l.orden.id}`, class: "mono" }, l.orden.codigo), ` · ${l.importador} · ${l.calidad}`, l.armado_en ? ` · armado el ${fecha(l.armado_en, { hora: true })} por ${l.armado_por_nombre ?? "—"}` : ""],
        cifra: kilos(l.masa_neta_kg ?? l.seleccionado_kg),
        cifraTexto: l.masa_neta_kg ? `masa neta · ${l.numero_parcelas} ${l.numero_parcelas === 1 ? "parcela" : "parcelas"}` : `seleccionado de ${kilos(l.cantidad_kg)}`,
        accion: opera && l.estado === "en_armado" && h("a", { class: "btn btn-primary", href: `#/lotes-exportacion/${l.id}/armar` }, icono("layers"), "Armar lote"),
      }),
      l.alertas
        .filter((a) => a.codigo === "exclusion_posterior_al_cierre")
        .map((a) => h("div", { class: "verif warn" }, icono("alert"), h("div", {}, h("b", {}, `La parcela ${a.parcela_codigo} se excluyó después de cerrar el lote`), h("span", {}, "El DEX no cambia porque está sellado. Informar al importador corresponde a la cooperativa.")))),
      l.desviacion_fifo && h("div", { class: "verif warn" }, icono("alert"), h("div", {}, h("b", {}, "La selección se apartó del orden FIFO"), h("span", {}, `Motivo: ${l.motivo_desviacion}`))),
      l.estado === "anulado" && h("div", { class: "verif bad" }, icono("alert"), h("div", {}, h("b", {}, `Lote anulado el ${fecha(l.anulado_en, { hora: true })}${l.anulado_por_nombre ? ` por ${l.anulado_por_nombre}` : ""}`), h("span", {}, `Motivo: ${l.motivo_anulacion}`))),
      h("div", { class: "ins-tabs seg-scroll" }, barra),
      cuerpo,
    ),
  };
}
